"""End-to-end dashboard interactions using Streamlit's native testing surface."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "final_jury/app.py"


class JuryDashboardTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        env = patch.dict(os.environ, {"GAME24_DATA_DIR": self.directory.name})
        env.start()
        self.addCleanup(env.stop)
        self.app = AppTest.from_file(str(APP), default_timeout=30).run()

    def page(self, name):
        self.app.radio(key="workspace").set_value(name).run()
        self.assertFalse(self.app.exception)

    def click(self, label):
        next(b for b in self.app.button if b.label == label).click().run()
        self.assertFalse(self.app.exception)

    def test_fractional_demo_and_evidence_inspection(self):
        self.click("Enter Jury Mode")
        self.click("Run fractional demonstration")
        run = self.app.session_state["last_run"]
        self.assertTrue(run["certificate"]["valid"])
        self.assertEqual(run["metrics"]["model_calls"], 0)
        self.assertEqual(self.app.session_state["run_origin"], "Live execution")
        self.page("Reasoning Tree")
        self.assertTrue(self.app.get("graphviz_chart"))
        self.app.selectbox[0].set_value("pruned").run()
        self.assertFalse(self.app.exception)
        for name in ["Agent Operations", "Memory + RAG", "Evaluation Lab", "Live Solver"]:
            self.page(name)
        self.page("Jury Mode")
        self.click("Load saved replay")
        self.assertIn("Saved replay", self.app.session_state["run_origin"])

    def test_invalid_certificate_and_controlled_faults(self):
        self.page("Safety Center")
        self.app.text_input[0].set_value("8+8+8")
        self.click("Check expression")
        self.assertFalse(self.app.session_state["last_audit"]["valid"])
        self.click("Run all checks")
        self.assertEqual(len(self.app.session_state["safety_rows"]), 10)
        self.assertTrue(all(r["passed"] for r in self.app.session_state["safety_rows"]))
