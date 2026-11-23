from __future__ import annotations

import csv
from pathlib import Path

from .ollama_client import OllamaClient
from .workflow import Game24Workflow

PUZZLES = [(4, 7, 8, 8), (1, 5, 5, 5), (3, 3, 8, 8)]


def run_benchmark(
    seeds: list[int] | tuple[int, ...] = (42,),
    use_ollama: bool = True,
    model: str = "qwen2.5:3b",
):
    client = OllamaClient(model=model) if use_ollama else None
    workflow = Game24Workflow(client)
    results = []
    for puzzle in PUZZLES:
        for method in ("Linear", "ToT"):
            for seed in seeds:
                result = workflow.run(puzzle, method, seed)
                row = result.to_dict()
                row["seed"] = seed
                results.append(row)
    return results


def save_csv(rows: list[dict], path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("No result rows to save")
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return destination

