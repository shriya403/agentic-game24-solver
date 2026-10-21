from __future__ import annotations

import ast
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    value: Fraction | None
    message: str
    used_numbers: tuple[int, ...] = ()


class ExpressionError(ValueError):
    pass


def _evaluate(node: ast.AST, leaves: list[int]) -> Fraction:
    if isinstance(node, ast.Expression):
        return _evaluate(node.body, leaves)
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        if node.value < 0:
            raise ExpressionError("Negative literals are not allowed")
        leaves.append(node.value)
        return Fraction(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in (ast.Add, ast.Sub, ast.Mult, ast.Div):
        left = _evaluate(node.left, leaves)
        right = _evaluate(node.right, leaves)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if right == 0:
            raise ExpressionError("Division by zero")
        return left / right
    raise ExpressionError("Only integer literals, parentheses, +, -, *, and / are allowed")


def validate_expression(expression: str | None, numbers: tuple[int, ...] | list[int], target: int = 24) -> ValidationResult:
    if not expression:
        return ValidationResult(False, None, "No expression was supplied")
    try:
        tree = ast.parse(expression.strip().replace("×", "*").replace("÷", "/"), mode="eval")
        leaves: list[int] = []
        value = _evaluate(tree, leaves)
    except (SyntaxError, ExpressionError, ZeroDivisionError) as exc:
        return ValidationResult(False, None, str(exc))
    if Counter(leaves) != Counter(numbers):
        return ValidationResult(
            False,
            value,
            f"Number usage mismatch: expected {list(numbers)}, used {leaves}",
            tuple(leaves),
        )
    if value != target:
        return ValidationResult(False, value, f"Expression equals {value}, not {target}", tuple(leaves))
    return ValidationResult(True, value, "Valid: every input used once and the exact value is 24", tuple(leaves))

