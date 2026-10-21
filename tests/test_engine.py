import unittest

from game24.engine import exhaustive_solve
from game24.validator import validate_expression


class EngineTests(unittest.TestCase):
    def test_all_selected_puzzles_are_solvable(self):
        for puzzle in [(4, 7, 8, 8), (1, 5, 5, 5), (3, 3, 8, 8)]:
            expression, trace, nodes = exhaustive_solve(puzzle)
            self.assertIsNotNone(expression)
            self.assertEqual(len(trace), 3)
            self.assertGreater(nodes, 0)
            self.assertTrue(validate_expression(expression, puzzle).valid)

    def test_known_hard_solution(self):
        result = validate_expression("8/(3-8/3)", (3, 3, 8, 8))
        self.assertTrue(result.valid)


if __name__ == "__main__":
    unittest.main()

