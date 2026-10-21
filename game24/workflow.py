from __future__ import annotations

from typing import Any, TypedDict

from .agents import LinearAgent, TreeOfThoughtAgent
from .ollama_client import OllamaClient


class WorkflowState(TypedDict, total=False):
    puzzle: tuple[int, int, int, int]
    method: str
    seed: int
    result: Any


class Game24Workflow:
    """LangGraph orchestration with a dependency-free fallback for easy demos/tests."""
    def __init__(self, client: OllamaClient | None = None):
        self.linear = LinearAgent(client)
        self.tot = TreeOfThoughtAgent(client)
        self.graph = self._build_graph()

    def _build_graph(self):
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError:
            return None

        graph = StateGraph(WorkflowState)
        graph.add_node("validate_input", self._validate_input)
        graph.add_node("linear_agent", self._linear_node)
        graph.add_node("tot_agent", self._tot_node)
        graph.add_edge(START, "validate_input")
        graph.add_conditional_edges(
            "validate_input", lambda state: state["method"],
            {"Linear": "linear_agent", "ToT": "tot_agent"},
        )
        graph.add_edge("linear_agent", END)
        graph.add_edge("tot_agent", END)
        return graph.compile()

    @staticmethod
    def _validate_input(state: WorkflowState) -> WorkflowState:
        puzzle = tuple(state["puzzle"])
        if len(puzzle) != 4 or any(not isinstance(n, int) or isinstance(n, bool) for n in puzzle):
            raise ValueError("Puzzle must contain exactly four integers")
        return state

    def _linear_node(self, state: WorkflowState) -> WorkflowState:
        return {**state, "result": self.linear.solve(state["puzzle"], state.get("seed", 42))}

    def _tot_node(self, state: WorkflowState) -> WorkflowState:
        return {**state, "result": self.tot.solve(state["puzzle"], state.get("seed", 42))}

    def run(self, puzzle: tuple[int, int, int, int], method: str, seed: int = 42):
        state: WorkflowState = {"puzzle": puzzle, "method": method, "seed": seed}
        if method not in ("Linear", "ToT"):
            raise ValueError("method must be Linear or ToT")
        if self.graph:
            return self.graph.invoke(state)["result"]
        self._validate_input(state)
        return self.linear.solve(puzzle, seed) if method == "Linear" else self.tot.solve(puzzle, seed)

