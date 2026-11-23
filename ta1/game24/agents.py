from __future__ import annotations

import re
import time
from fractions import Fraction

from .engine import initial_terms, is_solvable_values, legal_moves, state_label
from .models import BranchTrace, SolverResult, Term, format_fraction
from .ollama_client import OllamaClient
from .prompts import EVALUATOR_PROMPT, LINEAR_PROMPT
from .validator import validate_expression


def _extract_expression(text: str) -> str | None:
    match = re.search(r"(?im)^EXPRESSION\s*:\s*(.+?)\s*$", text)
    if not match:
        return None
    expression = match.group(1).strip().strip("`")
    return None if expression.upper() == "NONE" else expression


def _extract_steps(text: str) -> list[str]:
    return [m.group(1).strip() for m in re.finditer(r"(?m)^\s*\d+[.)]\s*(.+)$", text)]


class LinearAgent:
    def __init__(self, client: OllamaClient | None = None):
        self.client = client

    def solve(self, puzzle: tuple[int, int, int, int], seed: int = 42) -> SolverResult:
        if self.client and self.client.available():
            response = self.client.generate(LINEAR_PROMPT.format(numbers=list(puzzle)), seed=seed)
            expression = _extract_expression(response.text)
            trace = _extract_steps(response.text)
            validation = validate_expression(expression, puzzle)
            return SolverResult(
                puzzle=puzzle, method="Linear", success=validation.valid, valid=validation.valid,
                expression=expression, value=format_fraction(validation.value) if validation.value is not None else None,
                steps=len(trace), nodes_explored=1, branches_pruned=0,
                wall_time_sec=response.wall_time_sec, prompt_tokens=response.prompt_tokens,
                output_tokens=response.output_tokens, model=self.client.model, mode="ollama",
                trace=trace, raw_response=response.text, validator_message=validation.message,
            )
        return self._deterministic_greedy(puzzle)

    def _deterministic_greedy(self, puzzle: tuple[int, int, int, int]) -> SolverResult:
        """Transparent one-trajectory baseline used when Ollama is unavailable."""
        started = time.perf_counter()
        terms = initial_terms(puzzle)
        trace: list[str] = []
        nodes = 0
        while len(terms) > 1:
            candidates = legal_moves(terms)
            nodes += len(candidates)
            # One irreversible trajectory: favor states with a value closest to 24.
            move, terms = min(
                candidates,
                key=lambda item: min(abs(float(t.value - 24)) for t in item[1]),
            )
            trace.append(move.text)
        expression = terms[0].expression
        validation = validate_expression(expression, puzzle)
        return SolverResult(
            puzzle=puzzle, method="Linear", success=validation.valid, valid=validation.valid,
            expression=expression, value=format_fraction(terms[0].value), steps=len(trace),
            nodes_explored=nodes, branches_pruned=0, wall_time_sec=time.perf_counter() - started,
            prompt_tokens=0, output_tokens=0, model="deterministic-greedy", mode="deterministic_fallback",
            trace=trace, validator_message=validation.message,
        )


class TreeOfThoughtAgent:
    def __init__(self, client: OllamaClient | None = None, beam_width: int = 2):
        self.client = client
        self.beam_width = beam_width

    def _score_candidates(self, puzzle, candidates, seed):
        fallback = []
        for move, state in candidates:
            solvable = is_solvable_values(tuple(t.value for t in state))
            closeness = max(0.0, 20.0 - min(abs(float(t.value - 24)) for t in state))
            fallback.append((100.0 if solvable else closeness, "PROMISING" if solvable else "DEAD-END",
                             "Exact look-ahead found a route to 24" if solvable else "Exact look-ahead found no route"))
        if not (self.client and self.client.available()):
            return fallback, 0.0, 0, 0, ""
        candidate_text = "\n".join(
            f"CANDIDATE {i}: {move.text}; remaining {state_label(state)}"
            for i, (move, state) in enumerate(candidates, 1)
        )
        response = self.client.generate(
            EVALUATOR_PROMPT.format(numbers=list(puzzle), candidates=candidate_text), seed=seed, num_predict=250
        )
        parsed = {}
        pattern = re.compile(r"CANDIDATE\s+(\d+)\s*:\s*(\d+(?:\.\d+)?)\s*\|\s*(PROMISING|UNCERTAIN|DEAD-END)\s*\|\s*(.+)", re.I)
        for match in pattern.finditer(response.text):
            parsed[int(match.group(1)) - 1] = (float(match.group(2)), match.group(3).upper(), match.group(4).strip())
        scores = [parsed.get(i, fallback[i]) for i in range(len(candidates))]
        return scores, response.wall_time_sec, response.prompt_tokens, response.output_tokens, response.text

    def solve(self, puzzle: tuple[int, int, int, int], seed: int = 42) -> SolverResult:
        started = time.perf_counter()
        frontier: list[tuple[tuple[Term, ...], list[str]]] = [(initial_terms(puzzle), [])]
        branches: list[BranchTrace] = []
        nodes = pruned = prompt_tokens = output_tokens = 0
        llm_time = 0.0
        raw: list[str] = []

        for depth in range(1, 4):
            expanded = []
            for terms, path in frontier:
                expanded.extend((move, state, path + [move.text]) for move, state in legal_moves(terms))
            nodes += len(expanded)
            if not expanded:
                break

            # Exactly three visible candidates at the first stage; later stages score all then keep a beam.
            if depth == 1:
                # Put demonstrably solvable candidates first, but preserve distinct first moves.
                expanded.sort(key=lambda x: is_solvable_values(tuple(t.value for t in x[1])), reverse=True)
                visible = expanded[:3]
            else:
                visible = expanded
            score_input = [(m, s) for m, s, _ in visible]
            scores, elapsed, p_tokens, o_tokens, text = self._score_candidates(puzzle, score_input, seed + depth)
            llm_time += elapsed
            prompt_tokens += p_tokens
            output_tokens += o_tokens
            if text:
                raw.append(text)
            ranked = []
            for (move, state, path), (score, label, reason) in zip(visible, scores):
                branches.append(BranchTrace(move.text, state_label(state), label, score, reason, depth))
                ranked.append((score, state, path))
                if len(state) == 1 and state[0].value == 24:
                    expression = state[0].expression
                    validation = validate_expression(expression, puzzle)
                    return SolverResult(
                        puzzle=puzzle, method="ToT", success=validation.valid, valid=validation.valid,
                        expression=expression, value="24", steps=len(path), nodes_explored=nodes,
                        branches_pruned=pruned + max(0, len(ranked) - 1),
                        wall_time_sec=max(time.perf_counter() - started, llm_time), prompt_tokens=prompt_tokens,
                        output_tokens=output_tokens, model=self.client.model if prompt_tokens else "deterministic-oracle",
                        mode="ollama_agentic" if prompt_tokens else "deterministic_fallback", trace=path,
                        branches=branches, raw_response="\n\n".join(raw), validator_message=validation.message,
                    )
            ranked.sort(key=lambda x: x[0], reverse=True)
            kept = ranked[: self.beam_width]
            pruned += max(0, len(ranked) - len(kept))
            frontier = [(state, path) for _, state, path in kept]

        return SolverResult(
            puzzle=puzzle, method="ToT", success=False, valid=False, expression=None, value=None,
            steps=3, nodes_explored=nodes, branches_pruned=pruned,
            wall_time_sec=max(time.perf_counter() - started, llm_time), prompt_tokens=prompt_tokens,
            output_tokens=output_tokens, model=self.client.model if prompt_tokens else "deterministic-oracle",
            mode="ollama_agentic" if prompt_tokens else "deterministic_fallback", branches=branches,
            raw_response="\n\n".join(raw), validator_message="No valid branch reached 24",
        )
