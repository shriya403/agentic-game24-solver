"""Exact branch trace, using the frozen arithmetic engine's legal moves."""
from __future__ import annotations

from game24.engine import initial_terms, legal_moves, state_label


def exact_tree(numbers: list[int], rejected_roots: set[tuple[str, ...]] | None = None) -> tuple[str | None, list[dict]]:
    """Depth-first search. Memoize only value multisets proven to be dead ends."""
    failed = set()
    branches: list[dict] = []

    def visit(terms, parent, depth):
        key = tuple(sorted(term.value for term in terms))
        if len(terms) == 1:
            return terms[0].expression if terms[0].value == 24 else None
        for move, state in legal_moves(terms):
            state_key = tuple(sorted(t.value for t in state))
            row = dict(id=f"b{len(branches)+1}", parent=parent, move=move.text,
                       state=state_label(state), depth=depth, decision="pruned", reason="")
            branches.append(row)
            if depth == 1 and rejected_roots and tuple(sorted(row["state"])) in rejected_roots:
                row["reason"] = "SQLite records complete exhaustion of this first-move state."
                continue
            if state_key in failed:
                row["reason"] = "An equivalent multiset already exhausted its legal continuations."
                continue
            found = visit(state, row["id"], depth + 1)
            if found:
                row.update(decision="selected", reason="Leads to a terminal exact value of 24.")
                return found
            failed.add(state_key)
            row["reason"] = ("Terminal value differs from 24." if len(state) == 1
                             else "All legal continuations exhausted.")
        failed.add(key)
        return None

    expression = visit(initial_terms(numbers), "root", 1)
    return expression, branches
