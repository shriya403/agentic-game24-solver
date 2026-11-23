"""One entry point for the three historical approaches and final evidence."""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from contextlib import ExitStack
import re
from pathlib import Path
import sqlite3
from time import perf_counter
from typing import Sequence
from uuid import uuid4

from core.proof import audit
from game24.agents import LinearAgent, TreeOfThoughtAgent
from game24.engine import initial_terms, is_solvable_values, legal_moves, state_label
from game24.ollama_client import LLMResponse
from ta2.tools import LocalOllama, ToolFailure, check_puzzle


class MeasuredOllama(LocalOllama):
    """Count request kinds separately, retaining null for missing generation telemetry."""
    def __post_init__(self):
        super().__post_init__()
        self.requests_by_path = Counter()
        self.generation_tokens_available = True

    def _request(self, path, payload=None):
        self.requests_by_path[path] += 1
        response = super()._request(path, payload)
        if path == "/api/generate":
            self.generation_tokens_available &= all(
                type(response.get(key)) is int for key in ("prompt_eval_count", "eval_count"))
        return response


class _OriginalModelAdapter:
    """Use the original prompts with a strict model path after a readiness check."""
    def __init__(self, client):
        self.responses = []
        self.client = client
        self.model = client.model

    def available(self):
        return True  # solve() verified the specific model. Generation failures propagate.

    def generate(self, prompt, seed=42, num_predict=700):
        t = perf_counter()
        data = self.client._request("/api/generate", dict(
            prompt=prompt, model=self.model, stream=False,
            options=dict(temperature=0, seed=seed, num_predict=num_predict)))
        if not isinstance(data.get("response"), str):
            raise ToolFailure("generate", "Missing text response")
        self.responses.append(data["response"])
        p, o = data.get("prompt_eval_count") or 0, data.get("eval_count") or 0
        self.client.prompt_tokens += p
        self.client.output_tokens += o
        return LLMResponse(data["response"], perf_counter()-t, p, o, (data.get("total_duration") or 0)/1e9)


def _baseline_tree(result, responses):
    """Recover parent links by replaying the original deterministic beam ordering."""
    frontier = [("root", initial_terms(result.puzzle), [])]
    rows = []
    beam_width = 2
    for depth in range(1, 4):
        response = responses[depth-1] if depth <= len(responses) else ""
        # Match the frozen parser so mixed model and exact fallback scores remain distinguishable.
        model_indices = {int(m.group(1)) for m in re.finditer(
            r"CANDIDATE\s+(\d+)\s*:\s*(\d+(?:\.\d+)?)\s*\|\s*(PROMISING|UNCERTAIN|DEAD-END)\s*\|\s*(.+)",
            response, re.I)}
        recorded = [b for b in result.branches if b.depth == depth]
        expanded = [(parent, m, state, path + [m.text]) for parent, terms, path in frontier
                    for m, state in legal_moves(terms)]
        if depth == 1:
            expanded.sort(key=lambda x: is_solvable_values(tuple(t.value for t in x[2])), reverse=True)
            expanded = expanded[:3]
        ranked = []
        for index, ((parent, move, state, path), observation) in enumerate(zip(expanded, recorded), 1):
            if move.text != observation.move:
                raise RuntimeError("Branch replay differs from the recorded TA1 trace")
            row = dict(id=f"b{len(rows)+1}", parent=parent, depth=depth, move=move.text,
                       state=observation.state, decision="evaluated", reason=observation.reason,
                       score=observation.score, evaluator="ollama" if index in model_indices else "exact look-ahead")
            rows.append(row)
            ranked.append((observation.score, row, state, path))
        ranked.sort(key=lambda x: x[0], reverse=True)
        frontier = []
        for index, (_, row, state, path) in enumerate(ranked):
            if result.valid and result.trace[:depth] == path:
                row["decision"] = "selected"
            elif index >= beam_width and (depth != 3 or not result.valid):
                row["decision"] = "pruned"
            elif depth < 3:
                row["decision"] = "retained"
            if index < beam_width:
                frontier.append((row["id"], state, path))
    return rows


def _baseline(out, numbers, method, mode, client, seed):
    adapter = _OriginalModelAdapter(client) if mode == "model" else None
    agent = LinearAgent(adapter) if method == "linear" else TreeOfThoughtAgent(adapter)
    r = agent.solve(tuple(numbers), seed)
    out.update(expression=r.expression, status="verified" if r.valid else "no_valid_answer",
               oracle_assisted=method == "tree", branches=_baseline_tree(r, adapter.responses if adapter else []) if method == "tree" else [])
    if method == "linear" and mode == "exact":
        terms = initial_terms(numbers)
        parent = "root"
        for depth, choice in enumerate(r.trace, 1):
            move, terms = next((m, state) for m, state in legal_moves(terms) if m.text == choice)
            node = f"b{depth}"
            out["branches"].append(dict(id=node, parent=parent, depth=depth, move=move.text,
                                        state=state_label(terms), decision="selected",
                                        reason="Greedy move with a remaining value closest to 24."))
            parent = node
    out["events"].append(dict(role="linear" if method == "linear" else "tree", hop=0,
                              source=mode, backend=r.model, message=r.validator_message))
    out["metrics"].update(steps=r.steps, nodes_explored=r.nodes_explored, branches_pruned=r.branches_pruned)


def _multi(out, numbers, mode, client, rag, k, data_dir, max_hops, thread_id, seed, on_event):
    from final_jury.examples import ExampleIndex
    from final_jury.workflow import JuryWorkflow

    with ExitStack() as stack:
        index = None
        if rag:
            index = ExampleIndex(data_dir / "chroma", client, k)
            stack.callback(index.close)
            index.seed()
        workflow = JuryWorkflow(data_dir, client=client, offline=mode == "exact", rag=index, max_hops=max_hops)
        stack.callback(workflow.close)
        workflow.on_event = on_event
        workflow.branches = []
        s = workflow.run(numbers, thread_id, seed, namespace="jury")
        out.update(run_id=s["run_id"], expression=s["expression"] or None, status=s["status"],
                   oracle_assisted=mode == "exact" and s["search_used"], events=s["events"],
                   memory=s["memory"], evidence=s["evidence"], branches=workflow.branches,
                   errors=[f"{e['tool']}: {e['message']}" for e in s["errors"]])
        out["events"].append(dict(role="supervisor", hop=s["hops"], dispatch="finish", status=s["status"]))
        for item in out["evidence"]:
            common = sum((Counter(item["puzzle"]) & Counter(numbers)).values())
            item["shared_cards"] = common
            item["relevance"] = ("Same card multiset." if common == 4 else
                                 f"Shares {common} of four cards. A different puzzle requires a fresh proof.")
            overlap = bool(item.get("expression") and any(
                item["expression"] in event.get("candidates", []) for event in s["events"]))
            if mode == "exact":
                item["influence"] = "Displayed for inspection. Exact search does not consult retrieved examples."
            elif s["rounds"] == 0:
                item["influence"] = "Retrieved. No completed proposal recorded."
            elif overlap:
                item["influence"] = "Example expression also appeared in a proposal. Causality is unmeasured."
            else:
                item["influence"] = "Supplied as context. Direct influence on the proposal is unmeasured."
        if not workflow.branches:
            round_no = 0
            for event in s["events"]:
                if event["role"] == "proposer":
                    round_no += 1
                    accepted = event.get("accepted_for_evaluation", event.get("candidates", []))
                    for i, candidate in enumerate(event.get("candidates", [])):
                        cert = audit(candidate, numbers)
                        out["branches"].append(dict(id=f"r{round_no}c{i}", parent="root",
                            move=candidate, depth=1, state=[cert["value"]] if cert["value"] else [],
                            decision=("selected" if s["valid"] and candidate == s["expression"] else
                                      "pruned" if candidate not in accepted or not cert["valid"] else "evaluated"),
                            reason=cert["message"]))
        out["metrics"].update(hops=s["hops"], steps=s["rounds"],
            nodes_explored=s["search_nodes"] if s["search_used"] else len(out["branches"]),
            branches_pruned=sum(b["decision"] == "pruned" for b in out["branches"]))
        if index is not None and s["status"] == "verified" and audit(s["expression"], numbers)["valid"]:
            index.remember(numbers, s["expression"])


def solve(numbers: Sequence[int], method: str = "multi", *, mode: str = "exact",
          data_dir: str | Path = "data/runtime", rag: bool = False, k: int = 3,
          max_hops: int = 12, thread_id: str | None = None, seed: int = 42,
          on_event: Callable[[dict], None] | None = None) -> dict:
    """Run a new solve. Exact mode must be chosen explicitly in the user interface."""
    started = perf_counter()
    cards = list(check_puzzle(numbers))
    if method not in ("multi", "linear", "tree") or mode not in ("model", "exact"):
        raise ValueError("Choose a supported method and mode.")
    if k not in (1, 3) or (rag and method != "multi"):
        raise ValueError("RAG supports multi-agent trials with k=1 or 3.")
    thread_id = uuid4().hex if thread_id is None else thread_id
    client = MeasuredOllama(timeout=120, retries=1)
    out = dict(schema_version=1, run_id=uuid4().hex, thread_id=thread_id, puzzle=cards, method=method,
               mode=mode, seed=seed, rag=rag, k=k if rag else 0, max_hops=max_hops, status="started",
               model=client.model if mode == "model" else None,
               embedding_model=client.embedding_model if rag else None,
               expression=None, oracle_assisted=False, events=[], evidence=[], memory=[], branches=[],
               errors=[], metrics=dict(steps=0, nodes_explored=0, branches_pruned=0, hops=0))
    try:
        if on_event:
            on_event(dict(role="readiness", hop=0, stage="started"))
        if mode == "model":
            client.ready(require_embeddings=rag)
        if method == "multi":
            _multi(out, cards, mode, client, rag, k, Path(data_dir), max_hops, thread_id, seed, on_event)
        else:
            if on_event:
                on_event(dict(role=method, hop=0, stage="started"))
            _baseline(out, cards, method, mode, client, seed)
    except (ToolFailure, OSError, sqlite3.Error, ImportError) as exc:
        out["status"] = "tool_failure"
        out["errors"].append(f"{getattr(exc, 'tool', type(exc).__name__)}: {exc}")
    if on_event:
        on_event(dict(role="proof_auditor", hop=out["metrics"]["hops"], stage="started"))
    cert = audit(out["expression"], cards)
    out["certificate"] = cert
    if out["status"] == "verified" and not cert["valid"]:
        out["status"] = "verification_disagreement"
    out["explanation"] = cert["steps"] if cert["valid"] else []
    out["events"].append(dict(role="proof_auditor", hop=out["metrics"]["hops"], valid=cert["valid"],
                              reason=cert["message"]))
    if out["explanation"]:
        out["events"].append(dict(role="explanation", hop=out["metrics"]["hops"],
                                  source="verified AST postorder replay", steps=out["explanation"]))
    generations = client.requests_by_path["/api/generate"]
    for field in ("prompt_tokens", "output_tokens"):
        out["metrics"][field] = (getattr(client, field) if generations and client.generation_tokens_available
                                 and out["status"] != "tool_failure" else None)
    out["metrics"].update(model_calls=generations, tool_calls=client.calls, http_attempts=client.attempts,
                          embedding_calls=client.requests_by_path["/api/embed"],
                          latency_s=perf_counter()-started)
    return out
