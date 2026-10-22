"""Acceptance regressions for the completed TA2 workflow, preserving TA1 tests."""
import tempfile
import unittest
from pathlib import Path

from ta2.search import exact_search
from ta2.tools import verify, ToolFailure
from ta2.workflow import TA2Workflow
from ta2.reporting import summarize
from run_ta2_evaluation import evaluate, CASES


class Model:
    model = "fixture"
    embedding_model = "fixture-embedding"
    prompt_tokens = output_tokens = calls = 0

    def __init__(self, candidates=None, evaluator_index=0):
        self.candidates = candidates or ["3+3+8+8"]
        self.evaluator_index = evaluator_index
        self.prompts = []

    def generate(self, prompt, seed=42):
        self.calls += 1
        self.prompts.append(prompt)
        if "Role: Evaluator" in prompt:
            return {"index": self.evaluator_index, "score": 100, "reason": "Fixture confidence is not proof"}
        return {"candidates": self.candidates}


class RAG:
    def retrieve(self, query):
        return [{"id": "rules", "source": "fixture-rules", "text": "Use all cards exactly once", "distance": 0.}]


class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def workflow(self, **kwargs):
        w = TA2Workflow(self.directory.name, client=kwargs.pop("client", Model()), rag=kwargs.pop("rag", RAG()), **kwargs)
        self.addCleanup(w.close)
        return w

    def test_all_budgets_reserve_complete_verification_cycles(self):
        for budget in range(1, 15):
            with self.subTest(budget=budget):
                w = self.workflow(max_hops=budget)
                result = w.run([3,3,8,8], f"budget-{budget}")
                self.assertLessEqual(result["hops"], budget)
                self.assertFalse(result["valid"])
                if result["expression"]:
                    self.assertEqual(result["expression"], result["verification"]["expression"])
                    self.assertEqual(result["feedback"], result["verification"]["message"])

    def test_evaluator_guardrail_prefers_valid_candidate(self):
        w = self.workflow(client=Model(["3+3+8+8", "8/(3-8/3)"]))
        result = w.run([3,3,8,8], "misrank")
        self.assertTrue(result["valid"])
        event = next(e for e in result["events"] if e["role"] == "evaluator")
        self.assertTrue(event["guardrail_override"])
        self.assertEqual(event["model_index"], 0)
        self.assertEqual(event["index"], 1)
        self.assertEqual(result["candidate_origin"], "model")
        self.assertFalse(result["search_used"])

    def test_hybrid_repairs_invalid_proposal_and_discloses_tool(self):
        w = self.workflow(search_policy="hybrid")
        result = w.run([3,3,8,8], "hybrid")
        self.assertEqual(result["status"], "verified")
        self.assertTrue(verify(result["expression"], result["puzzle"]).valid)
        self.assertEqual(result["mode"], "ollama_ta2_hybrid")
        self.assertEqual(result["candidate_origin"], "exact_search_tool")
        self.assertTrue(result["search_used"])
        self.assertGreater(result["search_nodes"], 0)
        self.assertEqual(result["hops"], 7)

    def test_hybrid_does_not_call_search_for_valid_model_answer(self):
        w = self.workflow(search_policy="hybrid", client=Model(["8/(3-8/3)"]))
        result = w.run([3,3,8,8], "model-success")
        self.assertEqual(result["status"], "verified")
        self.assertFalse(result["search_used"])

    def test_exact_search_proof_and_budget_are_distinct(self):
        result = exact_search([1,1,1,1])
        self.assertIsNone(result.expression)
        self.assertTrue(result.complete)
        result = exact_search([3,3,8,8], max_nodes=1)
        self.assertIsNone(result.expression)
        self.assertFalse(result.complete)

    def test_search_solves_four_cases_without_reference_answers(self):
        for case, puzzle in CASES:
            with self.subTest(case=case):
                result = exact_search(puzzle)
                self.assertTrue(result.complete)
                if case != "unsolvable":
                    self.assertTrue(verify(result.expression, puzzle).valid)
                else:
                    self.assertIsNone(result.expression)

    def test_unsolvability_proof_and_search_failure_reported(self):
        w = self.workflow(search_policy="hybrid")
        result = w.run([1,1,1,1], "unsolvable")
        self.assertEqual(result["status"], "no_solution")
        self.assertTrue(result["search_used"])
        self.assertFalse(result["valid"])
        w = self.workflow(search_policy="hybrid", search_budget=1)
        result = w.run([3,3,8,8], "bounded")
        self.assertEqual(result["status"], "search_budget_exceeded")
        self.assertNotEqual(result["status"], "no_solution")

    def test_hybrid_never_hides_generation_failure(self):
        model = Model()
        def fail(*args):
            raise ToolFailure("generate", "injected")
        model.generate = fail
        w = self.workflow(client=model, search_policy="hybrid")
        result = w.run([3,3,8,8], "failure")
        self.assertEqual(result["status"], "tool_failure")
        self.assertFalse(result["search_used"])

    def test_hybrid_cannot_increase_saved_search_budget_on_resume(self):
        w = TA2Workflow(self.directory.name, client=Model(), rag=RAG(), search_policy="hybrid", search_budget=1)
        w.run([3,3,8,8], "resume", interrupt_after=["verifier"])
        w.close()
        w = self.workflow(search_policy="hybrid", search_budget=10000)
        result = w.resume("resume")
        self.assertEqual(result["status"], "search_budget_exceeded")
        self.assertEqual(result["search_budget"], 1)

    def test_evaluation_both_policies_and_summary_artifacts(self):
        target = Path(self.directory.name) / "comparison.csv"
        rows = evaluate(target, offline=True, search_policy="both")
        self.assertEqual(len(rows), 20)
        self.assertEqual({r["system"] for r in rows}, {"TA1_Linear", "TA1_ToT", "TA2_Model", "TA2_Hybrid"})
        self.assertTrue(target.with_suffix(".manifest.json").exists())
        self.assertTrue(target.with_suffix(".summary.md").exists())
        result = next(r for r in summarize(rows) if r["system"] == "TA2_Hybrid")
        self.assertEqual(result["verified_solvable"], 4)
        self.assertEqual(result["solvable_cases"], 4)
        self.assertEqual(result["proved_unsolvable"], 1)
        self.assertEqual(result["false_accepts"], 0)


if __name__ == "__main__":
    unittest.main()
