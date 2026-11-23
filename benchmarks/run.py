"""Re-run the five historical cases. Each output directory belongs to one experiment."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import tempfile
import time
from contextlib import ExitStack, closing
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from core.proof import audit
from game24.engine import exhaustive_solve, is_solvable_values
from game24.ollama_client import OllamaClient
from game24.workflow import Game24Workflow
from run_ta2_evaluation import CASES
from ta2.rag import ChromaRAG
from ta2.tools import LocalOllama, ToolFailure
from ta2.workflow import TA2Workflow

ROOT = Path(__file__).resolve().parents[1]
MODEL = "qwen2.5:3b"
FIELDS = """case puzzle system seed mode policy rag_k expected_solvable status verified
proven_unsolvable expression assistance steps nodes_explored branches_pruned hops
wall_time_sec model_calls embedding_calls prompt_tokens output_tokens retrieved_chunks
cpu_time_sec data_bytes error""".split()


class MeasuredTA1(OllamaClient):
    """Preserve frozen prompts and scoring, but make loss of the model explicit."""
    calls = 0

    def available(self):
        if not super().available():
            raise ToolFailure("readiness", "Ollama went offline during TA1 measurement")
        return True

    def generate(self, *args, **kwargs):
        self.calls += 1
        return super().generate(*args, **kwargs)


class MeasuredTA2(LocalOllama):
    generations = 0
    embeddings = 0
    missing_prompt_count = False
    missing_output_count = False

    def _request(self, path, payload=None):
        if path == "/api/generate":
            self.generations += 1
        if path == "/api/embed":
            self.embeddings += 1
        try:
            data = super()._request(path, payload)
        except ToolFailure:
            if path == "/api/generate":
                self.missing_prompt_count = self.missing_output_count = True
            raise
        if path == "/api/generate":
            self.missing_prompt_count |= "prompt_eval_count" not in data
            self.missing_output_count |= "eval_count" not in data
        return data


class RetrievalArm:
    def __init__(self, index, k):
        self.index = index
        self.k = k

    def retrieve(self, query):
        return self.index.retrieve(query, k=self.k) if self.k else []


def write_json(path, data):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def run_ta1(row, cards, live, base_url):
    client = MeasuredTA1(model=MODEL, base_url=base_url) if live else None
    workflow = Game24Workflow(client)
    method = row["system"].split("_")[1]
    is_solvable_values.cache_clear()
    row["assistance"] = ("exact look-ahead" if method == "ToT" else
                         "model generation" if live else "deterministic greedy")
    started, cpu = time.perf_counter(), time.process_time()
    try:
        result = workflow.run(cards, method, row["seed"])
    finally:
        row.update(wall_time_sec=time.perf_counter()-started, cpu_time_sec=time.process_time()-cpu,
                   model_calls=client.calls if client else 0)
    proof = audit(result.expression, cards)
    row.update(status="verified" if proof["valid"] else "no_valid_answer",
               verified=proof["valid"], expression=result.expression, steps=result.steps,
               nodes_explored=result.nodes_explored, branches_pruned=result.branches_pruned,
               prompt_tokens=(result.prompt_tokens or None) if live else 0,
               output_tokens=(result.output_tokens or None) if live else 0)
    # Save legal operations and emitted scores. Full model completions are unnecessary.
    return {"branches": [dict(move=b.move, state=b.state, score=b.score, evaluation=b.evaluation,
                              depth=b.depth) for b in result.branches],
            "validation": proof,
            "steps": result.trace if not live or method == "ToT" else []}


def run_ta2(row, cards, state_dir, live, client, index):
    k = row["rag_k"]
    initial = (client.generations, client.embeddings, client.prompt_tokens, client.output_tokens)
    client.missing_prompt_count = client.missing_output_count = False
    rag = RetrievalArm(index, k) if live else None
    workflow = TA2Workflow(state_dir, client=client if live else None, rag=rag,
                           offline=not live, max_hops=12, search_policy=row["policy"] if live else "model")
    with closing(workflow):
        started, cpu = time.perf_counter(), time.process_time()
        try:
            state = workflow.run(cards, "measurement", seed=row["seed"], namespace="measurement")
        finally:
            row.update(wall_time_sec=time.perf_counter()-started, cpu_time_sec=time.process_time()-cpu,
                       model_calls=client.generations-initial[0], embedding_calls=client.embeddings-initial[1],
                       prompt_tokens=None if client.missing_prompt_count else client.prompt_tokens-initial[2],
                       output_tokens=None if client.missing_output_count else client.output_tokens-initial[3])
    proof = audit(state["expression"], cards)
    status = state["status"]
    if status == "verified" and not proof["valid"]:
        status = "verification_disagreement"
    row.update(status=status, verified=proof["valid"], expression=state["expression"],
               proven_unsolvable=state["status"] == "no_solution",
               assistance="offline exhaustive oracle" if not live else
                          "bounded exact search" if state["search_used"] else "model + exact verifier",
               hops=state["hops"], retrieved_chunks=len(state["evidence"]),
               nodes_explored=state["search_nodes"] if state["search_used"] else None,
               error=" | ".join(e["message"] for e in state["errors"]),
               data_bytes=sum(p.stat().st_size for p in state_dir.rglob("*") if p.is_file()))
    events = [{k: v for k,v in e.items() if k != "reason"} for e in state["events"]]
    return {"events": events, "evidence": state["evidence"], "verification": state["verification"],
            "origin": state["candidate_origin"], "independent_audit": proof, "errors": state["errors"]}


def benchmark(out, mode, seeds=(42,), rag_ks=(0, 1, 3), policies=("model",), base_url="http://localhost:11434"):
    live = mode == "ollama"
    if any(type(seed) is not int or seed < 0 for seed in seeds):
        raise ValueError("Seeds must be nonnegative integers")
    if mode not in ("ollama", "reference") or not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("Specify ollama or reference and one or more distinct seeds")
    if not rag_ks or not set(rag_ks) <= {0, 1, 3} or not policies or not set(policies) <= {"model", "hybrid"}:
        raise ValueError("Use k=0,1,3 and policy model/hybrid")
    if len(set(rag_ks)) != len(rag_ks) or len(set(policies)) != len(policies):
        raise ValueError("Duplicate conditions would reuse a checkpoint")
    client = MeasuredTA2(base_url=base_url)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    corpora = sorted((ROOT/"ta2/corpus").glob("*.md"))
    manifest = dict(schema_version=1, completed=False, mode=mode, seeds=list(seeds),
                    rag_ks=list(rag_ks) if live else [0], policies=list(policies) if live else ["offline"],
                    generation_model=MODEL if live else None, embedding_model="nomic-embed-text" if live and any(rag_ks) else None,
                    temperature=0 if live else None, started_utc=datetime.now(timezone.utc).isoformat(),
                    python=platform.python_version(), platform=platform.platform(), max_hops=12, search_budget=10000,
                    versions={p: version(p) for p in ("langgraph","chromadb","langgraph-checkpoint-sqlite")},
                    corpus_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in corpora} if live and any(rag_ks) else {},
                    cases=dict(CASES), benchmark_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    write_json(out/"manifest.json", manifest)
    traces, rows = [], []
    conditions = [("TA1_Linear", "single", 0), ("TA1_ToT", "beam", 0)]
    conditions += ([("TA2_"+p.capitalize(), p, k) for k in rag_ks for p in policies] if live
                   else [("TA2_Exact", "exhaustive", 0)])
    with tempfile.TemporaryDirectory(prefix="game24-benchmark-") as temp, ExitStack() as stack:
        workdir = Path(temp)
        index = None
        rag_error = ""
        if live:
            try:
                client.ready(require_embeddings=False)
            except ToolFailure as exc:
                manifest["blocker"] = str(exc)
                write_json(out/"manifest.json", manifest)
                raise
            if any(rag_ks):
                try:
                    client.ready(require_embeddings=True)
                    index = stack.enter_context(ChromaRAG(workdir/"index", client))
                    index.ingest(corpora)
                except ToolFailure as exc:
                    rag_error = str(exc)
        with (out/"metrics.csv").open("x", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            for case, cards in CASES:
                solvable = exhaustive_solve(cards)[0] is not None
                for seed in seeds:
                    for system, policy, k in conditions:
                        row = dict.fromkeys(FIELDS)
                        row.update(case=case, puzzle=",".join(map(str,cards)), system=system,
                                   seed=seed, mode=mode, policy=policy, rag_k=k, expected_solvable=solvable,
                                   status="tool_failure", verified=False, proven_unsolvable=False,
                                   model_calls=0, embedding_calls=0, retrieved_chunks=0, error="")
                        try:
                            if k and rag_error:
                                raise ToolFailure("rag_setup", rag_error)
                            if system.startswith("TA1"):
                                detail = run_ta1(row, cards, live, base_url)
                            else:
                                detail = run_ta2(row, cards, workdir/f"case-{len(rows)}", live, client, index)
                        except Exception as exc:
                            row["error"] = f"{type(exc).__name__}: {exc}"
                            detail = {"error":row["error"]}
                        writer.writerow(row)
                        stream.flush()
                        traces.append({"row":len(rows), "case":case, "system":system, "seed":seed, "rag_k":k, **detail})
                        write_json(out/"traces.json", traces)
                        rows.append(row)
                        print(f"{case} {system} k={k} {row['status']}", flush=True)
    manifest.update(completed=True, rows=len(rows), failures=sum(
        r["status"] in {"tool_failure", "verification_disagreement"} for r in rows))
    write_json(out/"manifest.json", manifest)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("reference","ollama"), required=True)
    parser.add_argument("--output", type=Path, required=True, help="New directory, must not already exist")
    parser.add_argument("--seeds", nargs="+", type=int, default=[42])
    parser.add_argument("--rag-k", nargs="+", choices=(0,1,3), type=int, default=[0,1,3])
    parser.add_argument("--policies", nargs="+", choices=("model","hybrid"), default=["model"])
    parser.add_argument("--base-url", default="http://localhost:11434")
    args = parser.parse_args()
    try:
        rows = benchmark(args.output, args.mode, args.seeds, args.rag_k, args.policies, args.base_url)
    except (FileExistsError, ValueError, ToolFailure) as exc:
        parser.exit(2, f"{exc}\n")
    if any(row["status"] in {"tool_failure", "verification_disagreement"} for row in rows):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
