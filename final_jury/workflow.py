"""Jury extensions to the original checkpointed supervisor graph."""
from __future__ import annotations

import hashlib
import json
import sqlite3

from core.proof import audit
from core.tree import exact_tree
from ta2.tools import ToolFailure
from ta2.workflow import TA2Workflow


class JuryWorkflow(TA2Workflow):
    branches: list[dict]
    on_event = None

    def _node(self, name):
        original = super()._node(name)

        def observe(state):
            if self.on_event:
                self.on_event(dict(role=name, hop=state["hops"], stage="started"))
            result = original(state)
            if self.on_event:
                self.on_event(dict(role=name, hop=result.get("hops", state["hops"]), stage="completed"))
            return result

        return observe

    def _rejected_namespace(self, state):
        puzzle = ",".join(map(str, sorted(state["puzzle"])))
        return ("rejected", state["namespace"], puzzle)

    @staticmethod
    def _key(expression, cards):
        cert = audit(expression, cards)
        # Terminal states with the same consumed multiset and rational value are equivalent.
        if cert["value"] is not None:
            content = json.dumps([sorted(cert["used_numbers"]), cert["value"]])
        else:
            content = expression.strip()
        return hashlib.sha256(content.encode()).hexdigest()

    def _retrieve(self, s):
        try:
            key = ",".join(map(str, sorted(s["puzzle"])))
            item = self.store.get(("verified", s["namespace"], s["mode"]), key)
            memory = [item.value] if item else []
            evidence = self.rag.retrieve(f"cards {sorted(s['puzzle'])} arithmetic solution") if self.rag else []
            event = self._event(s, "retrieve", sources=[e["source"] for e in evidence],
                                k=getattr(self.rag, "k", 0), memory_hits=len(memory),
                                retrieval="enabled" if self.rag else "disabled")
            return dict(memory=memory, evidence=evidence, events=event, phase="proposer",
                        memory_assisted=bool(memory))
        except (ToolFailure, sqlite3.Error) as exc:
            return self._failure(s, "retrieve", exc)

    def _proposer(self, s):
        if self.offline:
            try:
                previous = self.store.get(self._rejected_namespace(s), "exact_first_moves")
                known = {tuple(row) for row in previous.value["states"]} if previous else set()
                answer, self.branches = exact_tree(s["puzzle"], known)
                newly_failed = {tuple(sorted(b["state"])) for b in self.branches
                                if b["depth"] == 1 and b["decision"] == "pruned"}
                if newly_failed - known:
                    self.store.put(self._rejected_namespace(s), "exact_first_moves",
                                   dict(states=sorted(known | newly_failed), run_id=s["run_id"],
                                        reason="Exact search exhausted each remaining-value multiset."))
            except sqlite3.Error as exc:
                return self._failure(s, "failed_branch_memory", exc)
            event = self._event(s, "proposer", candidates=[answer] if answer else [],
                                oracle=True, nodes=1+len(self.branches),
                                source="depth-first exact arithmetic", cached_dead_states=len(known), evidence_used=False)
            if answer is None:
                return dict(status="no_solution", events=event, search_nodes=1+len(self.branches),
                            search_used=True)
            return dict(candidates=[answer], phase="evaluator", rounds=s["rounds"]+1,
                        search_used=True, search_nodes=1+len(self.branches),
                        candidate_origin="offline_oracle", events=event)
        result = super()._proposer(s)
        if "candidates" not in result:
            return result
        try:
            fresh = []
            seen = set()
            for candidate in result["candidates"]:
                key = self._key(candidate, s["puzzle"])
                if key not in seen and self.store.get(self._rejected_namespace(s), key) is None:
                    fresh.append(candidate)
                seen.add(key)
            result["events"][-1].update(accepted_for_evaluation=fresh,
                                        context_example_count=len(s["evidence"]))
            result["candidates"] = fresh
            if not fresh:
                result.update(phase="proposer", feedback="All proposals repeat rejected equivalent terminal states. Try different operations.")
            return result
        except sqlite3.Error as exc:
            return self._failure(s, "failed_branch_lookup", exc)

    def _evaluator(self, s):
        result = super()._evaluator(s)
        if "events" not in result:
            return result
        event = result["events"][-1]
        event["ranking_source"] = "deterministic" if self.offline else "ollama"
        event["assessment_source"] = "restricted AST guard"
        if self.offline:
            event.update(reason="Single candidate from complete arithmetic search.", model_index=None)
        try:
            for assessment in event["assessments"]:
                if not assessment["valid"]:
                    candidate = s["candidates"][assessment["index"]]
                    self.store.put(self._rejected_namespace(s), self._key(candidate, s["puzzle"]),
                                   dict(expression=candidate, reason=assessment["reason"], run_id=s["run_id"]))
            return result
        except sqlite3.Error as exc:
            return self._failure(s, "failed_branch_write", exc)

    def _verifier(self, s):
        result = super()._verifier(s)
        cert = audit(s["expression"], s["puzzle"])
        if result["valid"] != cert["valid"]:
            return dict(status="verification_disagreement", valid=False, feedback=cert["message"],
                        events=self._event(s, "verifier", certificate=cert, disagreement=True))
        return result

    def _finish(self, s):
        result = super()._finish(s)
        if s["status"] == "no_solution" and self.offline:
            try:
                self.store.put(self._rejected_namespace(s), "complete_search",
                               dict(run_id=s["run_id"], puzzle=s["puzzle"], nodes=s["search_nodes"],
                                    reason="All reachable value states exhausted."))
            except sqlite3.Error as exc:
                result.update(self._failure(s, "failed_branch_write", exc))
        return result
