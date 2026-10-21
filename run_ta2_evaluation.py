"""Five fixed puzzles, frozen TA1 strategies versus the separate TA2 graph."""
from __future__ import annotations

import argparse
import csv
import json
import tempfile
import time
import uuid
from pathlib import Path

from game24.engine import exhaustive_solve
from game24.workflow import Game24Workflow
from game24.ollama_client import OllamaClient
from game24.validator import validate_expression
from ta2.tools import LocalOllama, ToolFailure
from ta2.rag import ChromaRAG
from ta2.workflow import TA2Workflow

CASES = [("easy", (4, 7, 8, 8)), ("fractional", (1, 5, 5, 5)),
         ("deceptive", (3, 3, 8, 8)), ("control", (1, 2, 3, 4)),
         ("unsolvable", (1, 1, 1, 1))]


def evaluate(output, offline=False, runs=1, model="qwen2.5:3b", corpus=None, base_url="http://localhost:11434"):
    if not 1 <= runs <= 5:
        raise ValueError("runs must be in 1..5")
    rows = []
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    trace_path = output.with_suffix(".traces.json")
    if output.exists() or trace_path.exists():
        raise ValueError("Output exists; choose a new evaluation filename")
    # Fresh persistence and retrieval per evaluation prevent previous answer leakage.
    with tempfile.TemporaryDirectory(prefix="game24-ta2-eval-") as root:
        rag = None
        if not offline:
            setup_client = LocalOllama(base_url=base_url, model=model)
            setup_client.ready()
            rag = ChromaRAG(Path(root) / "chroma", setup_client)
            rag.ingest([corpus or Path(__file__).parent / "ta2/corpus/rules.md"])
        traces = []
        for case, puzzle in CASES:
            expected = exhaustive_solve(puzzle)[0] is not None
            for seed in range(42, 42 + runs):
                baseline = Game24Workflow(None if offline else OllamaClient(model=model, base_url=base_url))
                for method in ("Linear", "ToT"):
                    started = time.perf_counter()
                    try:
                        result = baseline.run(puzzle, method, seed)
                        valid = validate_expression(result.expression, puzzle).valid
                        fallback = result.mode == "deterministic_fallback"
                        status = "fallback" if fallback and not offline else ("verified" if valid else "no_valid_answer")
                        rows.append(dict(case=case, puzzle=list(puzzle), system="TA1_" + method, seed=seed,
                            mode=result.mode, status=status, expected_solvable=expected, verified=valid,
                            wall_time_sec=time.perf_counter()-started, prompt_tokens=result.prompt_tokens,
                            output_tokens=result.output_tokens, hops="", tool_calls="", expression=result.expression,
                            oracle_assisted=(method == "ToT"), error=""))
                        traces.append({"case": case, "seed": seed, "system": "TA1_" + method, "result": result.to_dict()})
                    except Exception as exc:
                        rows.append(dict(case=case, puzzle=list(puzzle), system="TA1_" + method, seed=seed,
                            mode="deterministic_fallback" if offline else "ollama", status="tool_failure",
                            expected_solvable=expected, verified=False, wall_time_sec=time.perf_counter()-started,
                            prompt_tokens=0, output_tokens=0, hops="", tool_calls="", expression="",
                            oracle_assisted=(method == "ToT"), error=str(exc)))
                client = None if offline else LocalOllama(base_url=base_url, model=model)
                if rag:
                    rag.client = client
                # Isolate Store/checkpoints across cases and seeds as well as thread IDs.
                workflow = TA2Workflow(Path(root) / f"{case}-{seed}", client=client, rag=rag, offline=offline)
                started = time.perf_counter()
                try:
                    state = workflow.run(puzzle, uuid.uuid4().hex, seed, namespace=f"{case}-{seed}")
                    valid = validate_expression(state["expression"], puzzle).valid
                    rows.append(dict(case=case, puzzle=list(puzzle), system="TA2", seed=seed, mode=state["mode"],
                        status=state["status"], expected_solvable=expected, verified=valid,
                        wall_time_sec=time.perf_counter()-started, prompt_tokens=state["prompt_tokens"],
                        output_tokens=state["output_tokens"], hops=state["hops"], tool_calls=state["tool_calls"],
                        expression=state["expression"], oracle_assisted=offline, error=json.dumps(state["errors"])))
                    traces.append({"case": case, "seed": seed, "system": "TA2", "state": state})
                finally:
                    workflow.close()
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    trace_path.write_text(json.dumps(traces, indent=2), encoding="utf-8")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--model", default="qwen2.5:3b")
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        rows = evaluate(args.output, args.offline, args.runs, args.model, base_url=args.base_url)
    except (ValueError, ToolFailure) as exc:
        parser.exit(2, f"Evaluation: {exc}\n")
    print(f"Saved {len(rows)} rows and raw traces. Offline results are oracle demos, not Qwen evidence.")
    if any(r["status"] in ("fallback", "tool_failure") for r in rows):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
