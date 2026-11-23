"""Regression tests for the ten examiner-facing demonstrations."""
import json
import unittest

from final_jury.safety import CASES, run_case, run_suite


class SafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = {row["case"]: row for row in run_suite()}

    def test_all_checks_run_and_pass(self):
        self.assertEqual(set(self.records), set(CASES))
        self.assertEqual(len(CASES), 10)
        for slug, row in self.records.items():
            with self.subTest(case=slug):
                self.assertTrue(row["passed"], row["observed"])
                self.assertIsInstance(json.dumps(row), str)

    def test_retrieved_text_reaches_model_but_guard_rejects(self):
        evidence = self.records["retrieval_instruction"]["evidence"]
        self.assertTrue(evidence["scripted_model_received_instruction"])
        self.assertIsNone(evidence["final_index_projection"])
        self.assertEqual(evidence["scripted_model_calls"], 2)
        self.assertEqual(evidence["verification"]["value"], "22")
        self.assertFalse(evidence["verification"]["valid"])

    def test_faults_are_terminal_and_observable(self):
        for case, tool in [("database_unavailable", "retrieve"), ("model_unavailable", "proposer")]:
            with self.subTest(case=case):
                state = self.records[case]["evidence"]
                self.assertEqual(state["status"], "tool_failure")
                self.assertFalse(state["valid"])
                self.assertEqual(state["errors"][0]["tool"], tool)

    def test_no_unrelated_answer_when_sources_missing(self):
        result = self.records["missing_evidence"]["evidence"]
        self.assertFalse(result["grounded"])
        self.assertEqual(result["generation_calls"], 0)
        self.assertEqual(result["sources"], [])

    def test_unknown_case_fails_explicitly(self):
        with self.assertRaises(ValueError):
            run_case("unknown")


if __name__ == "__main__":
    unittest.main()
