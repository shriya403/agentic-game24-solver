"""Check the benchmark's scientific controls and independently re-audit saved evidence."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from benchmarks.run import CASES, ROOT, RetrievalArm, benchmark
from core.proof import audit


class BenchmarkEvidenceTests(unittest.TestCase):
    def test_reference_and_archive_verify_every_row(self):
        runs = [(ROOT/"benchmarks/evidence/reference/metrics.csv", 3),
                (ROOT/"results/ta2-acceptance-ad0424cd/evaluation.csv", 4)]
        for path, count in runs:
            with self.subTest(path=path), path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
                self.assertEqual(len(rows), len(CASES) * count)
                for row in rows:
                    puzzle = dict(CASES)[row["case"]]
                    recorded = row["puzzle"].strip("[]").split(",")
                    self.assertEqual(tuple(map(int, recorded)), puzzle)
                    self.assertEqual(audit(row["expression"], puzzle)["valid"], row["verified"] == "True")
                for case, _ in CASES:
                    self.assertEqual(len({r["system"] for r in rows if r["case"] == case}), count)

    def test_duplicate_output_is_rejected_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            marker = target/"manifest.json"
            marker.write_text("original", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                benchmark(target, "reference")
            self.assertEqual(marker.read_text(encoding="utf-8"), "original")

    def test_k_zero_bypasses_and_positive_k_reaches_retriever(self):
        retriever = Mock()
        self.assertEqual(RetrievalArm(retriever, 0).retrieve("query"), [])
        retriever.retrieve.assert_not_called()
        for k in (1, 3):
            RetrievalArm(retriever, k).retrieve("query")
            retriever.retrieve.assert_called_with("query", k=k)

    def test_fractional_replay_certificate_and_selected_path(self):
        replay = json.loads((ROOT/"traces/fractional-exact.json").read_text(encoding="utf-8"))
        cert = audit(replay["expression"], replay["puzzle"])
        self.assertEqual(cert, replay["certificate"])
        self.assertEqual(replay["explanation"], cert["steps"])
        self.assertEqual(sum(node["decision"] == "selected" for node in replay["branches"]), 3)
        self.assertEqual(replay["metrics"]["model_calls"], 0)
