from __future__ import annotations

import argparse
from datetime import datetime, timezone

from game24.experiment import run_benchmark, save_csv


def main():
    parser = argparse.ArgumentParser(description="Run the CoT-style vs ToT Game-of-24 benchmark")
    parser.add_argument("--runs", type=int, default=1, help="Number of fixed seeds (42, 43, ...)")
    parser.add_argument("--model", default="qwen2.5:3b")
    parser.add_argument("--no-ollama", action="store_true", help="Use transparent deterministic fallback")
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    rows = run_benchmark(range(42, 42 + args.runs), not args.no_ollama, args.model)
    suffix = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output = args.output or f"results/benchmark-{suffix}.csv"
    path = save_csv(rows, output)
    print(f"Saved {len(rows)} rows to {path}")
    modes = sorted({row['mode'] for row in rows})
    print(f"Execution mode(s): {', '.join(modes)}")
    if "deterministic_fallback" in modes:
        print("Note: these are fallback measurements, not Qwen/Ollama results.")


if __name__ == "__main__":
    main()

