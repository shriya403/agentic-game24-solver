"""Capture a new, independently audited fractional demonstration."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from final_jury.solver import solve


def capture(path: Path):
    with TemporaryDirectory(prefix="game24-trace-") as data_dir:
        result = solve([3, 3, 8, 8], method="multi", mode="exact", data_dir=data_dir)
    if result["status"] != "verified" or not result["certificate"]["valid"]:
        raise RuntimeError(f"Fractional demonstration failed: {result['status']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    capture(parser.parse_args().output)
