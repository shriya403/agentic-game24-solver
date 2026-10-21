from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from itertools import combinations

from .models import Move, Term, format_fraction


def initial_terms(numbers: tuple[int, ...] | list[int]) -> tuple[Term, ...]:
    return tuple(Term(Fraction(n), str(n)) for n in numbers)


def legal_moves(terms: tuple[Term, ...]) -> list[tuple[Move, tuple[Term, ...]]]:
    """Enumerate unique legal next states using exact Fraction arithmetic."""
    generated: list[tuple[Move, tuple[Term, ...]]] = []
    seen: set[tuple[Fraction, ...]] = set()
    for i, j in combinations(range(len(terms)), 2):
        a, b = terms[i], terms[j]
        rest = [terms[k] for k in range(len(terms)) if k not in (i, j)]
        options = [
            (a, "+", b, a.value + b.value),
            (a, "*", b, a.value * b.value),
            (a, "-", b, a.value - b.value),
            (b, "-", a, b.value - a.value),
        ]
        if b.value != 0:
            options.append((a, "/", b, a.value / b.value))
        if a.value != 0:
            options.append((b, "/", a, b.value / a.value))
        for left, op, right, value in options:
            expr = f"({left.expression} {op} {right.expression})"
            result = Term(value, expr)
            new_terms = tuple(rest + [result])
            key = tuple(sorted((t.value for t in new_terms)))
            if key in seen:
                continue
            seen.add(key)
            generated.append((Move(left, op, right, result), new_terms))
    return generated


@lru_cache(maxsize=8192)
def is_solvable_values(values: tuple[Fraction, ...], target: Fraction = Fraction(24)) -> bool:
    values = tuple(sorted(values))
    if len(values) == 1:
        return values[0] == target
    terms = tuple(Term(v, format_fraction(v)) for v in values)
    return any(is_solvable_values(tuple(t.value for t in state), target) for _, state in legal_moves(terms))


def exhaustive_solve(numbers: tuple[int, ...] | list[int], target: int = 24) -> tuple[str | None, list[str], int]:
    """Return one ground-truth solution, its arithmetic trace, and explored node count."""
    nodes = 0

    def search(terms: tuple[Term, ...], path: list[str]) -> tuple[str | None, list[str]]:
        nonlocal nodes
        nodes += 1
        if len(terms) == 1:
            return (terms[0].expression, path) if terms[0].value == target else (None, [])
        for move, state in legal_moves(terms):
            expression, solved_path = search(state, path + [move.text])
            if expression:
                return expression, solved_path
        return None, []

    expression, trace = search(initial_terms(numbers), [])
    return expression, trace, nodes


def state_label(terms: tuple[Term, ...]) -> list[str]:
    return [format_fraction(t.value) for t in terms]

