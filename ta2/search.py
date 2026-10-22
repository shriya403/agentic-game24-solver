"""Bounded exact arithmetic search tool, never labelled as model reasoning."""
from dataclasses import dataclass

from game24.engine import initial_terms, legal_moves
from .tools import check_puzzle


@dataclass
class SearchResult:
    expression: str | None
    nodes: int
    complete: bool


def exact_search(numbers, max_nodes=10000):
    """Find a legal expression or prove exhaustion; budget exhaustion is inconclusive."""
    check_puzzle(numbers)
    if type(max_nodes) is not int or not 1 <= max_nodes <= 100000:
        raise ValueError("Search node budget must be in 1..100000")
    visited = set()
    nodes = 0
    exhausted = False

    def visit(terms):
        nonlocal nodes, exhausted
        key = tuple(sorted(t.value for t in terms))
        if key in visited:
            return None
        if nodes >= max_nodes:
            exhausted = True
            return None
        nodes += 1
        visited.add(key)
        if len(terms) == 1:
            return terms[0].expression if terms[0].value == 24 else None
        for _, following in legal_moves(terms):
            result = visit(following)
            if result:
                return result
            if exhausted:
                break
        return None

    expression = visit(initial_terms(numbers))
    return SearchResult(expression, nodes, not exhausted)
