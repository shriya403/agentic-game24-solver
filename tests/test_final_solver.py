"""Jury evidence contract, checked through the same API as the application."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from core.proof import audit
from final_jury.examples import SEEDS
from final_jury.solver import MeasuredOllama, solve
from final_jury.workflow import JuryWorkflow
from ta2.tools import ToolFailure


class ScriptedRanking:
    """Scripted Ollama contract fixture for repeat suppression, independent of model quality."""
    model = embedding_model = "fixture"
    prompt_tokens = output_tokens = calls = 0

    def generate(self, prompt, seed):
        self.calls += 1
        if "Role: Evaluator" in prompt:
            return dict(index=0, score=99, reason="Fixture response.")
        return dict(candidates=["3+3+8+8"])


class JuryTests(unittest.TestCase):
    def test_exact_tree_replay_and_rejection_memory_after_reopen(self):
        with TemporaryDirectory() as directory:
            stages = []
            r = solve([3,3,8,8], data_dir=directory, thread_id="demo", on_event=stages.append)
            self.assertEqual(r["status"], "verified")
            self.assertTrue(any(e["role"] == "proposer" and e["stage"] == "started" for e in stages))
            self.assertTrue(r["oracle_assisted"])
            self.assertEqual(r["metrics"]["hops"], 4)
            self.assertEqual(r["metrics"]["model_calls"], 0)
            self.assertIsNone(r["metrics"]["output_tokens"])
            selected = [row for row in r["branches"] if row["decision"] == "selected"]
            self.assertEqual([row["depth"] for row in selected], [1,2,3])
            self.assertEqual(selected[-1]["state"], ["24"])
            self.assertEqual(r["explanation"], ["8 / 3 = 8/3", "3 - 8/3 = 1/3", "8 / (1/3) = 24"])
            reopened = solve([3,3,8,8], data_dir=directory, thread_id="demo")
            self.assertTrue(reopened["memory"])
            self.assertEqual(reopened["status"], "verified")
            self.assertLess(reopened["metrics"]["nodes_explored"], r["metrics"]["nodes_explored"])

    def test_budget_and_unsolvable_are_distinct(self):
        with TemporaryDirectory() as directory:
            for hops, expected in ((1,"max_hops_exceeded"), (12,"no_solution")):
                r = solve([1,1,1,1], data_dir=directory, max_hops=hops)
                self.assertEqual(r["status"], expected)
                self.assertFalse(r["certificate"]["valid"])

    def test_exact_reference_methods(self):
        r = solve([3,3,8,8], "tree")
        self.assertEqual(r["status"], "verified")
        self.assertTrue(all(b["evaluator"] == "exact look-ahead" for b in r["branches"]))
        row = solve([3,3,8,8], "linear")
        self.assertEqual(row["status"], "no_valid_answer")
        self.assertEqual(len(row["branches"]), 3)
        self.assertFalse(row["oracle_assisted"])

    def test_live_reference_uses_model_indices_even_if_response_contains_blank_lines(self):
        response = "CANDIDATE 1: 90 | PROMISING | A fixture ranking.\n\nNo more scores"
        def request(client, path, payload=None):
            client.requests_by_path[path] += 1
            if path == "/api/tags":
                return {"models": [{"name": "qwen2.5:3b"}]}
            return {"response": response, "prompt_eval_count":10, "eval_count":7}
        with patch.object(MeasuredOllama, "_request", request):
            trial = solve([3,3,8,8], "tree", mode="model")
        first = [row for row in trial["branches"] if row["depth"] == 1]
        self.assertEqual([r["evaluator"] for r in first], ["ollama","exact look-ahead","exact look-ahead"])
        self.assertEqual(trial["metrics"]["model_calls"], 3)
        self.assertEqual(trial["metrics"]["output_tokens"], 21)

    def test_no_model_fallback_on_unavailable_service(self):
        with patch.object(MeasuredOllama, "ready", side_effect=ToolFailure("readiness", "fixture outage")):
            for approach in ("multi","tree","linear"):
                r = solve([3,3,8,8], approach, mode="model")
                self.assertEqual(r["status"], "tool_failure")
                self.assertFalse(r["certificate"]["valid"])
                self.assertEqual(r["branches"], [])

    def test_repeated_model_proposals_are_skipped(self):
        with TemporaryDirectory() as directory:
            flow = JuryWorkflow(directory, client=ScriptedRanking(), max_hops=7)
            try:
                r = flow.run([3,3,8,8], "test")
                self.assertEqual(r["status"], "max_hops_exceeded")
                evaluations = [e for e in r["events"] if e["role"] == "evaluator"]
                self.assertEqual(len(evaluations), 1)
                proposer = [e for e in r["events"] if e["role"] == "proposer"]
                self.assertEqual(proposer[-1]["accepted_for_evaluation"], [])
            finally:
                flow.close()

    def test_database_path_error(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "regular_file"
            path.write_text("keep")
            trial = solve([2,2,2,3], data_dir=path)
            self.assertEqual(trial["status"], "tool_failure")
            self.assertEqual(path.read_text(), "keep")

    def test_seed_examples_verified_and_outside_benchmark(self):
        from run_ta2_evaluation import CASES
        controls = {tuple(sorted(p)) for _,p in CASES}
        for cards, example in SEEDS:
            self.assertTrue(audit(example, cards)["valid"])
            self.assertNotIn(tuple(sorted(cards)), controls)
