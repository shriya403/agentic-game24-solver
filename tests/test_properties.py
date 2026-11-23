"""Compare the checked-in engines with an independent exact subset-DP enumerator."""
from fractions import Fraction
from itertools import combinations, combinations_with_replacement, permutations
import unittest

from core.proof import audit
from ta1.game24.engine import exhaustive_solve, initial_terms, legal_moves
from ta2.search import exact_search


def subset_values(cards):
    """All results per subset of physical card indices, including duplicate values."""
    subsets = {}
    for width in range(1, len(cards) + 1):
        for indices in combinations(range(len(cards)), width):
            subset = frozenset(indices)
            if width == 1:
                subsets[subset] = {Fraction(cards[indices[0]])}
                continue
            possible = set()
            for left_width in range(1, width):
                for left_indices in combinations(indices, left_width):
                    left = frozenset(left_indices)
                    right = subset - left
                    for a in subsets[left]:
                        for b in subsets[right]:
                            possible.update((a + b, a - b, a * b))
                            if b:
                                possible.add(a / b)
            subsets[subset] = possible
    return subsets


class ArithmeticProperties(unittest.TestCase):
    def test_bounded_exhaustive_range(self):
        ordered_count = 0
        multiset_count = 0
        for cards in combinations_with_replacement(range(1, 6), 4):
            with self.subTest(cards=cards):
                values = subset_values(cards)
                expected = 24 in values[frozenset(range(4))]
                expression, steps, nodes = exhaustive_solve(cards)
                self.assertEqual(expression is not None, expected)
                self.assertGreater(nodes, 0)
                self.assertEqual(len(steps), 3 if expected else 0)
                if expression:
                    proof = audit(expression, cards)
                    self.assertTrue(proof["valid"], proof["message"])
                multiset_count += 1

                # The TA1 move generator must cover every pair reduction exactly
                # once per value multiset, even when the cards repeat.
                expected_states = set()
                for pair in combinations(range(4), 2):
                    untouched = [Fraction(n) for i, n in enumerate(cards) if i not in pair]
                    for result in values[frozenset(pair)]:
                        expected_states.add(tuple(sorted([*untouched, result])))
                states = [tuple(sorted(term.value for term in state))
                          for _, state in legal_moves(initial_terms(cards))]
                self.assertEqual(set(states), expected_states)
                self.assertEqual(len(states), len(set(states)))

                for order in sorted(set(permutations(cards))):
                    result = exact_search(order)
                    self.assertTrue(result.complete, order)
                    self.assertEqual(result.expression is not None, expected, order)
                    if result.expression:
                        proof = audit(result.expression, order)
                        self.assertTrue(proof["valid"], (order, proof))
                    ordered_count += 1
        self.assertEqual(multiset_count, 70)
        self.assertEqual(ordered_count, 625)


if __name__ == "__main__":
    unittest.main()
