"""Mechanical summaries that distinguish solving, proof, and budget exhaustion."""
from pathlib import Path


def summarize(rows):
    result = []
    for system in sorted({r["system"] for r in rows}):
        group = [r for r in rows if r["system"] == system]
        solvable = [r for r in group if r["expected_solvable"]]
        result.append({"system": system, "solvable_cases": len(solvable),
                       "verified_solvable": sum(r["verified"] for r in solvable),
                       "proved_unsolvable": sum(not r["expected_solvable"] and r["status"] == "no_solution" for r in group),
                       "false_accepts": sum(not r["expected_solvable"] and r["verified"] for r in group),
                       "mean_solvable_seconds": sum(r["wall_time_sec"] for r in solvable)/len(solvable) if solvable else 0,
                       "prompt_tokens": sum(r["prompt_tokens"] for r in group),
                       "output_tokens": sum(r["output_tokens"] for r in group),
                       "tool_failures": sum(r["status"] in ("tool_failure", "fallback") for r in group),
                       "assisted_rows": sum(r["oracle_assisted"] for r in group)})
    return result


def write_summary(rows, path, offline=False):
    lines = ["# Five-case TA1 versus TA2 evaluation", "",
             "OFFLINE oracle demonstration; no Qwen performance evidence." if offline else
             "Local model execution; exact-tool assistance is disclosed per row.", "",
             "| System | Verified solvable | Proven unsolvable | Mean solvable time | Tool failures | Assisted rows |",
             "|---|---:|---:|---:|---:|---:|"]
    for r in summarize(rows):
        lines.append(f"| {r['system']} | {r['verified_solvable']}/{r['solvable_cases']} | {r['proved_unsolvable']} | {r['mean_solvable_seconds']:.3f}s | {r['tool_failures']} | {r['assisted_rows']} |")
    lines += ["", "Budget exhaustion and failure to find a solution are not unsolvability proofs.",
              "TA1 ToT has exact look-ahead assistance. TA2 hybrid uses explicit bounded exact search after model rejection.",
              "Tool-assisted success is system capability, not proof of improved Qwen reasoning.",
              "The shipped retrieval corpus contains no worked evaluation answers. Each case uses fresh execution/Store memory.",
              "Search budgets differ. One seed is descriptive evidence, not a statistically reliable superiority claim."]
    Path(path).write_text("\n".join(lines)+"\n", encoding="utf-8")
