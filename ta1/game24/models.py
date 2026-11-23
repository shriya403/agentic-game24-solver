from __future__ import annotations

from dataclasses import asdict, dataclass, field
from fractions import Fraction
from typing import Any, Literal


@dataclass(frozen=True)
class Term:
    value: Fraction
    expression: str


@dataclass(frozen=True)
class Move:
    left: Term
    operator: str
    right: Term
    result: Term

    @property
    def text(self) -> str:
        return f"{self.left.expression} {self.operator} {self.right.expression} = {format_fraction(self.result.value)}"


@dataclass
class BranchTrace:
    move: str
    state: list[str]
    evaluation: str
    score: float
    reason: str
    depth: int = 1


@dataclass
class SolverResult:
    puzzle: tuple[int, int, int, int]
    method: Literal["Linear", "ToT"]
    success: bool
    valid: bool
    expression: str | None
    value: str | None
    steps: int
    nodes_explored: int
    branches_pruned: int
    wall_time_sec: float
    prompt_tokens: int
    output_tokens: int
    model: str
    mode: str
    trace: list[str] = field(default_factory=list)
    branches: list[BranchTrace] = field(default_factory=list)
    raw_response: str = ""
    validator_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["puzzle"] = ",".join(map(str, self.puzzle))
        data["trace"] = " | ".join(self.trace)
        data["branches"] = " | ".join(
            f"{b.move} -> [{', '.join(b.state)}] ({b.evaluation})" for b in self.branches
        )
        return data


def format_fraction(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"

