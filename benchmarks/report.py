"""Summarize and independently validate a saved benchmark directory."""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

from core.proof import audit


def summarize(directory: Path) -> str:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    with (directory / "metrics.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    traces = json.loads((directory / "traces.json").read_text(encoding="utf-8"))
    if not manifest.get("completed") or len(rows) != manifest["rows"] or len(rows) != len(traces):
        raise ValueError("A complete manifest, CSV and matching trace count are required.")
    groups = defaultdict(list)
    for i, (row, trace) in enumerate(zip(rows, traces, strict=True)):
        if (trace["row"], trace["case"], trace["system"], trace["seed"], trace["rag_k"]) != (
            i, row["case"], row["system"], int(row["seed"]), int(row["rag_k"])
        ):
            raise ValueError(f"Identity mismatch in trace {i}")
        proof = audit(row["expression"], manifest["cases"][row["case"]])
        if proof["valid"] != (row["verified"] == "True"):
            raise ValueError(f"Independent auditor disagrees with row {i}")
        groups[row["system"], int(row["rag_k"])].append(row)
    lines = [
        f"# {manifest['mode'].capitalize()} evaluation",
        "",
        f"Rechecked {len(rows)} rows with the independent proof auditor. "
        f"Seeds {', '.join(map(str, manifest['seeds']))}. Python {manifest['python']}.",
        "",
        "| System | Retrieval k | Solvable proofs | Unsolvability proofs | Tool failures | Mean seconds on solvable trials | Generation calls (all cases) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for (system, k), group in groups.items():
        solvable = [row for row in group if row["expected_solvable"] == "True"]
        verified = sum(row["verified"] == "True" for row in solvable)
        impossible = sum(row["proven_unsolvable"] == "True" for row in group)
        failures = sum(row["status"] == "tool_failure" for row in group)
        measurements = [float(row["wall_time_sec"]) for row in solvable if row["wall_time_sec"]]
        duration = f"{mean(measurements):.3f}" if len(measurements) == len(solvable) else "incomplete"
        calls = sum(int(row["model_calls"] or 0) for row in group)
        lines.append(f"| {system} | {k} | {verified}/{len(solvable)} | {impossible}/{len(group)-len(solvable)} | "
                     f"{failures} | {duration} | {calls} |")
    model_rows = [row for row in rows if row["system"] == "TA2_Model"]
    k_values = sorted({int(row["rag_k"]) for row in model_rows})
    if len(k_values) > 1:
        lines.extend(["", "## Matched retrieval trials", "",
                      "| Case | Seed | " + " | ".join(f"k={k}" for k in k_values) + " |",
                      "|---|---:|" + "---|" * len(k_values)])
        outcomes = {(r["case"], int(r["seed"]), int(r["rag_k"])): r["status"] for r in model_rows}
        for case in manifest["cases"]:
            for seed in manifest["seeds"]:
                cells = [outcomes[case, seed, k] for k in k_values]
                lines.append(f"| {case} | {seed} | " + " | ".join(cells) + " |")
        lines.extend(["", "Each arm uses the same cards, seed, model and maximum hop count. "
                      "Retrieved snippets and evaluator actions are available in traces.json. "
                      "Changes across arms describe individual runs. They do not establish a general benefit."])
    lines.extend(["", "TA1 ToT uses exact look-ahead during candidate selection and scoring. "
                  "TA2_Exact uses an exhaustive arithmetic oracle. TA2_Model supplies exact validation "
                  "feedback to its evaluator. TA2_Hybrid can invoke a bounded exact search tool. "
                  "Per-row assistance and failure details appear in metrics.csv.",
                  "", "See docs/EVALUATION.md for the corpus, timing window and comparison limits."])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(summarize(args.directory), end="")
