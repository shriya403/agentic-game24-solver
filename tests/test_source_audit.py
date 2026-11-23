import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.audit_ta1 import ROOT, compare


class AuditTests(unittest.TestCase):
    def test_exact_snapshot(self):
        report = compare(ROOT / "ta1")
        self.assertEqual(report["summary"]["exact"], len(report["files"]))

    def test_crlf_differences_and_real_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for name in ("app.py", "README.md", "Agentic_Game24_Jury_Deck.pptx"):
                shutil.copy2(ROOT / "ta1" / name, folder / name)
            text = folder / "app.py"
            text.write_bytes(text.read_bytes().replace(b"\n", b"\r\n"))
            for name in ("README.md", "Agentic_Game24_Jury_Deck.pptx"):
                with (folder / name).open("ab") as stream:
                    stream.write(b"\nchange\r\n")
            report = compare(folder)
            statuses = {item["path"]: item["status"] for item in report["files"]}
            self.assertEqual(statuses["app.py"], "line_endings_only")
            self.assertEqual(statuses["README.md"], "content_changed")
            self.assertEqual(statuses["Agentic_Game24_Jury_Deck.pptx"], "content_changed")
            self.assertEqual(statuses["run_experiment.py"], "missing")
