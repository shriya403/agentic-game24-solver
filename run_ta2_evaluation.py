"""Five fixed puzzles, frozen TA1 strategies versus the separate TA2 graph."""
from __future__ import annotations

import argparse
import csv
import json
import tempfile
import time
import uuid
import platform
from importlib.metadata import version
from contextlib import ExitStack
from pathlib import Path

from game24.engine import exhaustive_solve
from game24.workflow import Game24Workflow
from game24.ollama_client import OllamaClient
from game24.validator import validate_expression
from ta2.tools import LocalOllama, ToolFailure
from ta2.rag import ChromaRAG
from ta2.workflow import TA2Workflow
from ta2.reporting import write_summary

CASES = [("easy", (4, 7, 8, 8)), ("fractional", (1, 5, 5, 5)),
         ("deceptive", (3, 3, 8, 8)), ("control", (1, 2, 3, 4)),
         ("unsolvable", (1, 1, 1, 1))]


def evaluate(output, offline=False, runs=1, model="qwen2.5:3b", corpus=None,
             base_url="http://localhost:11434", search_policy="model", progress=None):
    if not 1 <= runs <= 5 or search_policy not in ("model", "hybrid", "both"):
        raise ValueError("Use runs 1..5 and search policy model, hybrid, or both")
    rows, traces = [], []
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    artifacts = {"csv": output, "traces": output.with_suffix(".traces.json"),
                 "summary": output.with_suffix(".summary.md"), "manifest": output.with_suffix(".manifest.json")}
    if any(p.exists() for p in artifacts.values()):
        raise ValueError("Output exists; choose a new evaluation filename")
    policies = ["model", "hybrid"] if search_policy == "both" else [search_policy]
    manifest = {"completed": False, "offline": offline, "model": model,
                "embedding_model": "none" if offline else "nomic-embed-text", "temperature": 0,
                "seeds": list(range(42, 42+runs)), "search_policies": policies,
                "max_hops": 12, "search_budget": 10000,
                "memory_policy": "fresh thread and Store per case/seed/policy; rules-only RAG",
                "python": platform.python_version(), "platform": platform.platform(),
                "versions": {p: version(p) for p in ["langgraph", "langgraph-checkpoint-sqlite", "chromadb"]},
                "limitations": "TA1 ToT is oracle-assisted. Tool budgets differ. Setup excluded from latency."}

    def save():
        if rows:
            with output.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
        artifacts["traces"].write_text(json.dumps(traces, indent=2), encoding="utf-8")
        artifacts["manifest"].write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def record(row, trace):
        rows.append(row)
        traces.append(trace)
        save()  # preserve completed work even if a later model/tool fails
        if progress:
            progress(f"[{len(rows)}/{len(CASES)*runs*(2+len(policies))}] {row['case']} {row['system']} seed={row['seed']}: {row['status']}")

    with tempfile.TemporaryDirectory(prefix="game24-ta2-eval-") as root, ExitStack() as resources:
        rag = None
        if not offline:
            setup_client = LocalOllama(base_url=base_url, model=model)
            setup_client.ready()
            rag = resources.enter_context(ChromaRAG(Path(root) / "chroma", setup_client))
            rag.ingest([corpus or Path(__file__).parent / "ta2/corpus/rules.md"])
        for case, puzzle in CASES:
            expected = exhaustive_solve(puzzle)[0] is not None
            for seed in range(42, 42 + runs):
                baseline = Game24Workflow(None if offline else OllamaClient(model=model, base_url=base_url))
                for method in ("Linear", "ToT"):
                    started = time.perf_counter()
                    row = dict(case=case, puzzle=list(puzzle), system="TA1_"+method, seed=seed,
                               mode="deterministic_fallback" if offline else "ollama", status="tool_failure",
                               expected_solvable=expected, verified=False, wall_time_sec=0., prompt_tokens=0,
                               output_tokens=0, hops="", tool_calls="", expression="",
                               oracle_assisted=(method=="ToT" or offline), search_nodes=0, error="")
                    trace = {"case": case, "seed": seed, "system": row["system"]}
                    try:
                        result = baseline.run(puzzle, method, seed)
                        valid = validate_expression(result.expression, puzzle).valid
                        row.update(mode=result.mode, status="fallback" if result.mode=="deterministic_fallback" and not offline
                                   else "verified" if valid else "no_valid_answer", verified=valid,
                                   prompt_tokens=result.prompt_tokens, output_tokens=result.output_tokens,
                                   expression=result.expression)
                        trace["result"] = result.to_dict()
                    except Exception as exc:
                        row["error"] = str(exc)
                        trace["error"] = str(exc)
                    row["wall_time_sec"] = time.perf_counter()-started
                    record(row, trace)
                for policy in policies:
                    client = None if offline else LocalOllama(base_url=base_url, model=model)
                    if rag:
                        rag.client = client
                    system = "TA2" if len(policies)==1 else "TA2_"+policy.capitalize()
                    started = time.perf_counter()
                    row = dict(case=case, puzzle=list(puzzle), system=system, seed=seed,
                               mode="deterministic_ta2" if offline else "ollama_ta2_hybrid" if policy=="hybrid" else "ollama_ta2",
                               status="tool_failure", expected_solvable=expected, verified=False,
                               wall_time_sec=0., prompt_tokens=0, output_tokens=0, hops="", tool_calls="",
                               expression="", oracle_assisted=offline, search_nodes=0, error="")
                    trace = {"case": case, "seed": seed, "system": system}
                    workflow = None
                    try:
                        workflow = TA2Workflow(Path(root)/f"{case}-{seed}-{policy}", client=client, rag=rag,
                                               offline=offline, search_policy=policy)
                        state = workflow.run(puzzle, uuid.uuid4().hex, seed, namespace=f"{case}-{seed}-{policy}")
                        row.update(status=state["status"], verified=validate_expression(state["expression"],puzzle).valid,
                                   prompt_tokens=state["prompt_tokens"], output_tokens=state["output_tokens"],
                                   hops=state["hops"], tool_calls=state["tool_calls"], expression=state["expression"],
                                   oracle_assisted=(offline or state["search_used"] or state["memory_assisted"]), search_nodes=state["search_nodes"],
                                   error=json.dumps(state["errors"]))
                        trace["state"] = state
                    except Exception as exc:
                        row["error"] = str(exc)
                        trace["error"] = str(exc)
                    finally:
                        if workflow:
                            workflow.close()
                    row["wall_time_sec"] = time.perf_counter()-started
                    record(row, trace)
        manifest["completed"] = True
        save()
        write_summary(rows, artifacts["summary"], offline=offline)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--model", default="qwen2.5:3b")
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument("--search-policy", choices=["model", "hybrid", "both"], default="both")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        rows = evaluate(args.output, args.offline, args.runs, args.model, base_url=args.base_url,
                        search_policy=args.search_policy, progress=lambda s: print(s, flush=True))
    except (ValueError, ToolFailure) as exc:
        parser.exit(2, f"Evaluation: {exc}\n")
    print(f"Saved {len(rows)} rows, raw traces, manifest and summary.")
    print("OFFLINE: oracle demo; no Qwen measurements." if args.offline else
          "LOCAL MODEL RUN: model-only and exact-tool-assisted rows are identified separately.")
    if any(r["status"] in ("fallback", "tool_failure") for r in rows):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
