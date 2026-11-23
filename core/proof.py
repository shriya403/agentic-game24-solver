"""Independent, resource-bounded arithmetic certificate. No model or search imports."""
from __future__ import annotations

import ast
from collections import Counter
from fractions import Fraction
import operator
import re
from typing import Sequence

OPERATIONS = {
    ast.Add: ("+", operator.add), ast.Sub: ("-", operator.sub),
    ast.Mult: ("*", operator.mul), ast.Div: ("/", operator.truediv),
}


def audit(expression: str | None, numbers: Sequence[int]) -> dict:
    """Evaluate a four-card expression and replay its exact arithmetic in postorder."""
    cards = list(numbers)
    used: list[int] = []
    steps: list[str] = []
    cert = dict(puzzle=cards, expression=expression, value=None, used_numbers=used,
                usage_ok=False, valid=False, message="", steps=steps)
    if len(cards) != 4 or any(type(n) is not int or not 1 <= n <= 13 for n in cards):
        cert["message"] = "Expected four integer cards from 1 to 13."
        return cert

    def visit(node: ast.AST) -> Fraction:
        if isinstance(node, ast.Constant) and type(node.value) is int:
            return Fraction(node.value)
        if not isinstance(node, ast.BinOp) or type(node.op) not in OPERATIONS:
            raise ValueError("Use only integer cards, parentheses and + − × ÷.")
        left, right = visit(node.left), visit(node.right)
        symbol, operation = OPERATIONS[type(node.op)]
        if symbol == "/" and right == 0:
            raise ValueError("Division by zero.")
        value = operation(left, right)
        # Group fractional divisors to avoid reading 8 / (1/3) as (8/1)/3.
        right_text = f"({right})" if right < 0 or (symbol == "/" and right.denominator != 1) else str(right)
        steps.append(f"{left} {symbol} {right_text} = {value}")
        return value

    try:
        if not isinstance(expression, str) or not 1 <= len(expression) <= 256:
            raise ValueError("Supply an expression of 1–256 characters.")
        text = expression.strip().translate(str.maketrans("−×÷", "-*/"))
        if not re.fullmatch(r"[0-9+*/()\s-]+", text) or re.search(r"\d{4}", text):
            raise ValueError("Unsupported character or oversized integer literal.")
        tree = ast.parse(text, mode="eval")
        nodes = list(ast.walk(tree))
        if len(nodes) > 32:
            raise ValueError("Expression exceeds the 32-node AST budget.")
        constants = sorted((n for n in nodes if isinstance(n, ast.Constant)),
                           key=lambda n: (n.lineno, n.col_offset))
        used.extend(n.value for n in constants if type(n.value) is int)
        cert["usage_ok"] = Counter(used) == Counter(cards)
        value = visit(tree.body)
        cert["value"] = str(value)
        if not cert["usage_ok"]:
            raise ValueError(f"Card usage mismatch. Expected {sorted(cards)}, used {sorted(used)}.")
        if value != 24:
            raise ValueError(f"Expression evaluates to {value}. The target is 24.")
        cert.update(valid=True, message="Every card appears once and the exact value is 24.")
    except (ValueError, SyntaxError, RecursionError) as exc:
        cert["message"] = str(exc)
    return cert
