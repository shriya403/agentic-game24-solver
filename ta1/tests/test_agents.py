import unittest

from game24.agents import LinearAgent, TreeOfThoughtAgent


class AgentTests(unittest.TestCase):
    def test_tot_fallback_solves_selected_puzzles(self):
        agent = TreeOfThoughtAgent()
        for puzzle in [(4, 7, 8, 8), (1, 5, 5, 5), (3, 3, 8, 8)]:
            result = agent.solve(puzzle)
            self.assertTrue(result.valid, result.validator_message)
            self.assertEqual(result.mode, "deterministic_fallback")
            self.assertEqual(result.steps, 3)

    def test_linear_is_one_trajectory(self):
        result = LinearAgent().solve((4, 7, 8, 8))
        self.assertEqual(result.method, "Linear")
        self.assertEqual(len(result.trace), 3)


if __name__ == "__main__":
    unittest.main()

