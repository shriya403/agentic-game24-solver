"""Checkpointed supervisor / proposer / evaluator / verifier graph."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph, START, END

from .storage import SQLiteStore
from .tools import ToolFailure, check_puzzle, verify
from .prompts import PROPOSER, EVALUATOR
from .search import exact_search

MAX_HOPS = 12


class State(TypedDict, total=False):
    puzzle: list[int]
    seed: int
    run_id: str
    namespace: str
    mode: str
    history: list[dict]
    events: list[dict]
    evidence: list[dict]
    memory: list[dict]
    candidates: list[str]
    expression: str
    feedback: str
    valid: bool
    hops: int
    next: str
    phase: str
    status: str
    errors: list[dict]
    started: float
    prompt_tokens: int
    output_tokens: int
    tool_calls: int
    max_hops: int
    metric_base: list[int]
    model: str
    embedding_model: str
    search_policy: str
    search_nodes: int
    search_used: bool
    candidate_origin: str
    verification: dict
    rounds: int
    schema_version: int
    search_budget: int
    memory_assisted: bool


class TA2Workflow:
    def __init__(self, data_dir, client=None, rag=None, max_hops=MAX_HOPS, offline=False,
                 search_policy="model", search_budget=10000):
        if type(max_hops) is not int or not 1 <= max_hops <= 100:
            raise ValueError("max_hops must be in 1..100")
        if not offline and client is None:
            raise ValueError("Model mode requires an Ollama client")
        if search_policy not in ("model", "hybrid"):
            raise ValueError("search_policy must be model or hybrid")
        if type(search_budget) is not int or not 1 <= search_budget <= 100000:
            raise ValueError("search_budget must be in 1..100000")
        self.client, self.rag, self.max_hops, self.offline = client, rag, max_hops, offline
        self.search_policy, self.search_budget = search_policy, search_budget
        path = Path(data_dir)
        path.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path / "checkpoints.sqlite", check_same_thread=False)
        self.saver = SqliteSaver(self.connection)
        self.store = SQLiteStore(path / "store.sqlite")
        graph = StateGraph(State)
        for name in ("supervisor", "retrieve", "proposer", "evaluator", "verifier", "search", "finish"):
            graph.add_node(name, self._node(name))
        graph.add_edge(START, "supervisor")
        graph.add_conditional_edges("supervisor", lambda s: s["next"],
                                    {n: n for n in ("retrieve", "proposer", "evaluator", "verifier", "search", "finish")})
        for name in ("retrieve", "proposer", "evaluator", "verifier", "search"):
            graph.add_edge(name, "supervisor")
        graph.add_edge("finish", END)
        self.graph = graph.compile(checkpointer=self.saver, store=self.store)

    def close(self):
        self.store.close()
        self.connection.close()

    def _mode(self):
        return ("deterministic_ta2" if self.offline else
                "ollama_ta2_hybrid" if self.search_policy == "hybrid" else "ollama_ta2")

    def _node(self, name):
        def execute(state):
            result = getattr(self, "_" + name)(state)
            result.update(dict(zip(("prompt_tokens", "output_tokens", "tool_calls"),
                                   [a-b for a,b in zip(self._metrics(), state["metric_base"])])))
            return result
        return execute

    @staticmethod
    def config(thread_id):
        if not isinstance(thread_id, str) or not thread_id.strip() or len(thread_id) > 128:
            raise ValueError("Provide a nonempty thread_id of at most 128 characters")
        return {"configurable": {"thread_id": thread_id}, "recursion_limit": 210}

    def snapshot(self, thread_id):
        return self.graph.get_state(self.config(thread_id))

    def run(self, puzzle, thread_id, seed=42, namespace="default", interrupt_after=None):
        cards = check_puzzle(puzzle)
        if not isinstance(namespace, str) or not namespace or len(namespace) > 128:
            raise ValueError("Invalid memory namespace")
        config = self.config(thread_id)
        previous = self.graph.get_state(config)
        if previous.next:
            raise ValueError("Thread has an unfinished run; resume it or use a new thread")
        if previous.values and previous.values.get("namespace") != namespace:
            raise ValueError("Thread belongs to another namespace")
        mode = self._mode()
        if previous.values and previous.values.get("mode") != mode:
            raise ValueError("Use a new thread when changing execution mode")
        history = previous.values.get("history", [])[-20:] if previous.values else []
        state = State(puzzle=list(cards), seed=seed, run_id=uuid.uuid4().hex, namespace=namespace,
                      mode=mode, history=history,
                      events=[], evidence=[], memory=[], candidates=[], expression="", feedback="",
                      valid=False, hops=0, phase="retrieve", status="running", errors=[],
                      started=time.time(), prompt_tokens=0, output_tokens=0, tool_calls=0,
                      max_hops=self.max_hops, metric_base=self._metrics(),
                      model="deterministic-oracle" if self.offline else getattr(self.client, "model", "fixture"),
                      embedding_model="none" if self.offline else getattr(self.client, "embedding_model", "unknown"),
                      search_policy=self.search_policy, search_nodes=0, search_used=False,
                      candidate_origin="none", verification={}, rounds=0, schema_version=2,
                      search_budget=self.search_budget, memory_assisted=False)
        return self.graph.invoke(state, config, interrupt_after=interrupt_after)

    def resume(self, thread_id):
        snapshot = self.snapshot(thread_id)
        if not snapshot.next:
            raise ValueError("Thread has no interrupted execution to resume")
        if snapshot.values.get("schema_version") != 2:
            raise ValueError("This interrupted thread uses an older workflow; start a new thread")
        expected = self._mode()
        if snapshot.values["mode"] != expected:
            raise ValueError("Resume requires the original execution mode")
        if not self.offline and (snapshot.values["model"] != getattr(self.client, "model", "fixture")
                or snapshot.values["embedding_model"] != self.client.embedding_model):
            raise ValueError("Resume requires the original generation and embedding models")
        # A new process has new counters; retain counters committed by earlier nodes.
        self.graph.update_state(self.config(thread_id), {"metric_base": [
            current - saved for current, saved in zip(self._metrics(), [snapshot.values.get(k, 0)
                for k in ("prompt_tokens", "output_tokens", "tool_calls")])]})
        return self.graph.invoke(None, self.config(thread_id))

    def _metrics(self):
        return [getattr(self.client, k, 0) for k in ("prompt_tokens", "output_tokens", "calls")]

    def _supervisor(self, s):
        metrics = dict(zip(("prompt_tokens", "output_tokens", "tool_calls"),
                           [a-b for a,b in zip(self._metrics(), s["metric_base"])]))
        if s["status"] != "running":
            return {**metrics, "next": "finish"}
        if s["valid"]:
            return {**metrics, "status": "verified", "next": "finish"}
        # Reserve enough dispatches to finish a proposal/evaluation/verification
        # cycle. A new candidate never escapes without its own verifier result.
        required = {"retrieve": 1, "proposer": 3, "evaluator": 2, "verifier": 1, "search": 3}[s["phase"]]
        if s["hops"] + required > s["max_hops"]:
            return {**metrics, "status": "max_hops_exceeded", "next": "finish",
                    "events": self._event(s, "supervisor", termination="insufficient_budget_for_complete_cycle")}
        return {**metrics, "next": s["phase"], "hops": s["hops"] + 1,
                "events": self._event(s, "supervisor", dispatch=s["phase"], hop=s["hops"] + 1)}

    def _failure(self, s, tool, exc):
        # Network retries happen within the tool. Exhausted failures terminate explicitly.
        return {"status": "tool_failure", "errors": s["errors"] + [
            {"tool": tool, "message": str(exc), "attempts": getattr(exc, "attempts", 1)}]}

    def _event(self, s, role, **fields):
        return s["events"] + [{"role": role, "hop": s["hops"], **fields}]

    def _retrieve(self, s):
        try:
            # Store memory is scoped by caller-provided namespace and exact puzzle.
            key = ",".join(map(str, sorted(s["puzzle"])))
            item = self.store.get(("verified", s["namespace"], s["mode"]), key)
            memory = [item.value] if item else []
            evidence = self.rag.retrieve(f"Game of 24 cards {s['puzzle']}: exact use-once rules and fractional intermediate strategy") if self.rag else []
            if not self.offline and not self.rag:
                raise ToolFailure("retrieval", "Model mode requires an ingested Chroma RAG index")
            return {"memory": memory, "evidence": evidence, "phase": "proposer",
                    "memory_assisted": bool(memory),
                    "events": self._event(s, "retrieve", sources=[e["source"] for e in evidence], memory_hits=len(memory))}
        except (ToolFailure, sqlite3.Error) as exc:
            return self._failure(s, "retrieve", exc)

    def _context(self, s):
        return json.dumps({"cards": s["puzzle"], "reference_data": s["evidence"],
                           "verified_memory": s["memory"], "recent_turns": s["history"][-5:],
                           "feedback": s["feedback"], "verification": s["verification"],
                           "previous_candidates": s["candidates"]})

    def _proposer(self, s):
        try:
            if self.offline:
                from game24.engine import exhaustive_solve
                expression, _, _ = exhaustive_solve(s["puzzle"])
                if expression is None:
                    return {"status": "no_solution", "events": self._event(s, "proposer", oracle=True)}
                candidates = [expression]
            else:
                data = self.client.generate(PROPOSER + self._context(s), s["seed"] + s["hops"])
                candidates = data.get("candidates")
                if (not isinstance(candidates, list) or not 1 <= len(candidates) <= 3
                        or any(not isinstance(c, str) or not 1 <= len(c) <= 256 for c in candidates)):
                    raise ToolFailure("proposer", "Expected 1..3 bounded candidate expressions")
            return {"candidates": list(dict.fromkeys(candidates)), "phase": "evaluator",
                    "rounds": s["rounds"] + 1,
                    "candidate_origin": "offline_oracle" if self.offline else "model",
                    "events": self._event(s, "proposer", candidates=candidates, oracle=self.offline)}
        except ToolFailure as exc:
            return self._failure(s, "proposer", exc)

    def _evaluator(self, s):
        try:
            checks = [verify(c, s["puzzle"]) for c in s["candidates"]]
            assessments = [{"index": i, "valid": r.valid, "reason": r.message,
                            "exact_value": str(r.value) if r.value is not None else None}
                           for i, r in enumerate(checks)]
            data = {"index": 0, "score": 100, "reason": "Offline oracle fixture"} if self.offline else self.client.generate(
                EVALUATOR + self._context(s) + "\nCandidates: " + json.dumps(s["candidates"])
                + "\nDeterministic tool assessments: " + json.dumps(assessments), s["seed"])
            index, score, reason = data.get("index"), data.get("score"), data.get("reason")
            if (type(index) is not int or not 0 <= index < len(s["candidates"])
                    or type(score) is not int or not 0 <= score <= 100
                    or not isinstance(reason, str) or len(reason) > 1000):
                raise ToolFailure("evaluator", "Invalid candidate ranking schema")
            original = index
            legal = [i for i, check in enumerate(checks) if check.valid]
            if legal and index not in legal:
                index = legal[0]
            return {"expression": s["candidates"][index], "phase": "verifier", "valid": False,
                    "feedback": "Awaiting verification of selected candidate", "verification": {},
                    "events": self._event(s, "evaluator", index=index, model_index=original,
                                          score=score, reason=reason, assessments=assessments,
                                          guardrail_override=(original != index))}
        except ToolFailure as exc:
            return self._failure(s, "evaluator", exc)

    def _verifier(self, s):
        result = verify(s["expression"], s["puzzle"])
        verification = {"expression": s["expression"], "valid": result.valid, "message": result.message,
                        "value": str(result.value) if result.value is not None else None,
                        "used_numbers": list(result.used_numbers)}
        phase = "search" if s["search_policy"] == "hybrid" and not s["search_used"] else "proposer"
        return {"valid": result.valid, "feedback": result.message, "phase": phase,
                "verification": verification,
                "events": self._event(s, "verifier", **verification)}

    def _search(self, s):
        result = exact_search(s["puzzle"], s["search_budget"])
        update = {"search_used": True, "search_nodes": result.nodes,
                  "events": self._event(s, "search", nodes=result.nodes, complete=result.complete,
                                        source="exact_arithmetic_tool", expression=result.expression)}
        if result.expression:
            update.update(candidates=[result.expression], phase="evaluator", candidate_origin="exact_search_tool")
        else:
            update.update(status="no_solution" if result.complete else "search_budget_exceeded",
                          expression="", valid=False, verification={},
                          feedback="Exact search exhausted all legal states" if result.complete else "Search node budget exhausted; result inconclusive")
        return update

    def _finish(self, s):
        history = (s["history"] + [{"puzzle": s["puzzle"], "expression": s["expression"],
                                   "status": s["status"], "feedback": s["feedback"]}])[-20:]
        result = {"history": history}
        if s["valid"]:
            try:
                self.store.put(("verified", s["namespace"], s["mode"]), ",".join(map(str, sorted(s["puzzle"]))),
                               {"expression": s["expression"], "puzzle": s["puzzle"], "run_id": s["run_id"], "mode": s["mode"],
                                "candidate_origin": s["candidate_origin"], "search_used": s["search_used"]})
            except sqlite3.Error as exc:
                result.update(self._failure(s, "store_write", exc))
        return result
