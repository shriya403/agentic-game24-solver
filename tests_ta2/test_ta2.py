from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import sqlite3
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from ta2.tools import LocalOllama, ToolFailure, check_puzzle, verify
from ta2.storage import SQLiteStore
from ta2.workflow import TA2Workflow
from ta2.rag import ChromaRAG
from run_ta2_evaluation import evaluate


class FakeModel:
    """Controlled contract fixture: never presented as a real model measurement."""
    embedding_model = "test-fixture-only"
    prompt_tokens = output_tokens = calls = 0

    def __init__(self, candidates=None, fail=False):
        self.candidates = candidates or ["8/(3-8/3)"]
        self.fail = fail

    def generate(self, prompt, seed=42):
        self.calls += 1
        self.prompt_tokens += 10
        self.output_tokens += 5
        if self.fail:
            raise ToolFailure("generation", "Injected failure", 3)
        if "Role: Evaluator" in prompt:
            return {"index": 0, "score": 90, "reason": "Test fixture ranking"}
        return {"candidates": self.candidates}

    def embed(self, texts):
        return [[float("fraction" in t.lower()), float("card" in t.lower()), 1.] for t in texts]


class FakeRAG:
    def retrieve(self, query):
        return [{"id": "fixture", "source": "fixture", "text": "Use all cards", "distance": 0.}]


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def workflow(self, **kwargs):
        w = TA2Workflow(self.tmp.name, **kwargs)
        self.addCleanup(w.close)
        return w

    def test_offline_verification_and_store(self):
        w = self.workflow(offline=True)
        r = w.run([3,3,8,8], "one")
        self.assertEqual(r["status"], "verified")
        self.assertEqual(r["mode"], "deterministic_ta2")
        self.assertEqual([e["role"] for e in r["events"] if e["role"] != "supervisor"],
                         ["retrieve", "proposer", "evaluator", "verifier"])
        self.assertEqual([e["dispatch"] for e in r["events"] if e["role"] == "supervisor"],
                         ["retrieve", "proposer", "evaluator", "verifier"])
        self.assertTrue(w.store.get(("verified", "default", "deterministic_ta2"), "3,3,8,8"))

    def test_thread_history_and_namespace_isolation(self):
        w = self.workflow(offline=True)
        w.run([3,3,8,8], "one", namespace="a")
        second = w.run([3,3,8,8], "one", namespace="a")
        other = w.run([3,3,8,8], "two", namespace="b")
        self.assertEqual(len(second["history"]), 2)
        self.assertEqual(len(second["memory"]), 1)
        self.assertEqual(len(other["history"]), 1)
        self.assertEqual(other["memory"], [])
        with self.assertRaises(ValueError):
            w.run([3,3,8,8], "one", namespace="b")

    def test_process_restart_and_resume(self):
        w = TA2Workflow(self.tmp.name, offline=True)
        r = w.run([3,3,8,8], "resume", interrupt_after=["evaluator"])
        self.assertEqual(r["hops"], 3)
        self.assertTrue(w.snapshot("resume").next)
        with self.assertRaises(ValueError):
            w.run([3,3,8,8], "resume")
        w.close()
        code = """
import sys
from ta2.workflow import TA2Workflow
w=TA2Workflow(sys.argv[1], offline=True)
r=w.resume('resume')
assert r['status']=='verified'
assert r['hops']==4
assert w.store.get(('verified','default','deterministic_ta2'),'3,3,8,8')
w.close()
print('restart verified')
"""
        p = subprocess.run([sys.executable, "-c", code, self.tmp.name], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("restart verified", p.stdout)

    def test_max_hops_and_resume_budget(self):
        w = TA2Workflow(self.tmp.name, offline=True, max_hops=2)
        w.run([3,3,8,8], "budget", interrupt_after=["proposer"])
        w.close()
        w = self.workflow(offline=True, max_hops=99)
        result = w.resume("budget")
        self.assertEqual(result["status"], "max_hops_exceeded")
        self.assertEqual(result["hops"], 2)
        self.assertFalse(result["valid"])

    def test_evaluator_cannot_certify_invalid_expression(self):
        w = self.workflow(client=FakeModel(["3+3+8+8"]), rag=FakeRAG(), max_hops=7)
        r = w.run([3,3,8,8], "invalid")
        self.assertFalse(r["valid"])
        self.assertEqual(r["status"], "max_hops_exceeded")
        self.assertIn("not 24", r["feedback"])
        self.assertFalse(w.store.search(("verified",)))

    def test_tool_failure_has_no_fallback_success(self):
        w = self.workflow(client=FakeModel(fail=True), rag=FakeRAG())
        r = w.run([3,3,8,8], "failure")
        self.assertEqual(r["status"], "tool_failure")
        self.assertEqual(r["errors"][0]["attempts"], 3)
        self.assertFalse(r["valid"])

    def test_missing_rag_fails_explicitly(self):
        w = self.workflow(client=FakeModel())
        r = w.run([3,3,8,8], "no-rag")
        self.assertEqual(r["status"], "tool_failure")
        self.assertEqual(r["errors"][0]["tool"], "retrieve")

    def test_schema_failure(self):
        model = FakeModel()
        model.generate = lambda *a: {"candidates": "not a list"}
        w = self.workflow(client=model, rag=FakeRAG())
        r = w.run([3,3,8,8], "schema")
        self.assertEqual(r["status"], "tool_failure")

    def test_metrics_are_per_run(self):
        w = self.workflow(client=FakeModel(), rag=FakeRAG())
        first = w.run([3,3,8,8], "metrics")
        second = w.run([3,3,8,8], "metrics")
        self.assertEqual(first["prompt_tokens"], 20)
        self.assertEqual(second["prompt_tokens"], 20)
        self.assertEqual(second["tool_calls"], 2)

    def test_no_solution_offline_is_proven(self):
        w = self.workflow(offline=True)
        r = w.run([1,1,1,1], "unsolvable")
        self.assertEqual(r["status"], "no_solution")
        self.assertFalse(r["valid"])

    def test_store_read_failure_is_explicit(self):
        w = self.workflow(offline=True)
        with patch.object(w.store, "get", side_effect=sqlite3.OperationalError("database is locked")):
            r = w.run([3,3,8,8], "db-failure")
        self.assertEqual(r["status"], "tool_failure")
        self.assertEqual(r["errors"][0]["tool"], "retrieve")

    def test_resume_preserves_model_metrics(self):
        w = TA2Workflow(self.tmp.name, client=FakeModel(), rag=FakeRAG())
        first = w.run([3,3,8,8], "metrics-resume", interrupt_after=["evaluator"])
        self.assertEqual(first["tool_calls"], 2)
        w.close()
        reopened = self.workflow(client=FakeModel(), rag=FakeRAG())
        result = reopened.resume("metrics-resume")
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["tool_calls"], 2)
        self.assertEqual(result["prompt_tokens"], 20)


class GuardrailTests(unittest.TestCase):
    def test_valid_fraction(self):
        self.assertTrue(verify("8/(3-8/3)", [3,3,8,8]).valid)

    def test_rejects_unsafe_and_invalid(self):
        for expr in ["__import__('os')", "8**3", "8/(3-3)+8", "8*3", "3+3+8+8", "("*300, "999999+3+8+8"]:
            with self.subTest(expr=expr):
                self.assertFalse(verify(expr, [3,3,8,8]).valid)

    def test_input_domain(self):
        for puzzle in [[True,3,8,8], [0,3,8,8], [14,3,8,8], [3,8,8], [3.,3,8,8]]:
            with self.assertRaises(ValueError):
                check_puzzle(puzzle)


class StoreRAGTests(unittest.TestCase):
    def test_chroma_context_closes_after_exception(self):
        with tempfile.TemporaryDirectory() as d:
            rag = ChromaRAG(d, FakeModel())
            with patch.object(rag.db, "close", wraps=rag.db.close) as close:
                with self.assertRaisesRegex(RuntimeError, "injected"):
                    with rag:
                        raise RuntimeError("injected")
                close.assert_called_once()
            # No cleanup suppression: Windows must be able to delete the directory.

    def test_sqlite_store_reopen_crud(self):
        with tempfile.TemporaryDirectory() as d, ExitStack() as resources:
            path = Path(d)/"store.sqlite"
            s = SQLiteStore(path)
            s.put(("user", "a"), "key", {"value": 1})
            s.close()
            s = SQLiteStore(path)
            self.assertEqual(s.get(("user", "a"), "key").value, {"value": 1})
            self.assertEqual(len(s.search(("user",), filter={"value": 1})), 1)
            self.assertEqual(s.search(("other",)), [])
            self.assertEqual(s.list_namespaces(prefix=("user",)), [("user", "a")])
            s.put(("user", "a"), "key", {"value": 2})
            s.delete(("user", "a"), "key")
            self.assertIsNone(s.get(("user", "a"), "key"))
            s.close()

    def test_real_chroma_persistence_and_idempotent_ingest(self):
        with tempfile.TemporaryDirectory() as d, ExitStack() as resources:
            source = Path(d)/"rules.md"
            source.write_text("Use every card once. Fraction intermediates are legal.")
            rag = resources.enter_context(ChromaRAG(Path(d)/"chroma", FakeModel()))
            self.assertEqual(rag.ingest([source]), 1)
            rag.ingest([source])
            self.assertEqual(rag.collection.count(), 1)
            reopened = resources.enter_context(ChromaRAG(Path(d)/"chroma", FakeModel()))
            result = reopened.retrieve("fraction card")
            self.assertEqual(result[0]["source"], str(source.resolve()))
            self.assertIn("Fraction", result[0]["text"])
            source.write_text("New card rule")
            reopened.ingest([source])
            self.assertEqual(reopened.collection.count(), 1)
            self.assertEqual(reopened.retrieve("card")[0]["text"], "New card rule")

    def test_empty_index_is_failure(self):
        with tempfile.TemporaryDirectory() as d, ExitStack() as resources:
            rag = resources.enter_context(ChromaRAG(d, FakeModel()))
            with self.assertRaises(ToolFailure):
                rag.retrieve("card")

    def test_embedding_failure_preserves_existing_index(self):
        with tempfile.TemporaryDirectory() as d, ExitStack() as resources:
            p = Path(d)/"rules.md"
            p.write_text("Card rule")
            model = FakeModel()
            rag = resources.enter_context(ChromaRAG(Path(d)/"chroma", model))
            rag.ingest([p])
            def fail(texts):
                raise ToolFailure("embed", "Injected embedding failure")
            model.embed = fail
            with self.assertRaises(ToolFailure):
                rag.ingest([p])
            self.assertEqual(rag.collection.count(), 1)


class ModelToolTests(unittest.TestCase):
    def test_http_model_rag_graph_integration(self):
        # Real HTTP client, real Chroma and graph; fixture responses, not Ollama quality evidence.
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, value):
                body = json.dumps(value).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                self.reply({"models": [{"name": "qwen2.5:3b"}, {"name": "nomic-embed-text:latest"}]})

            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if self.path == "/api/embed":
                    self.reply({"embeddings": [[1.,2.,3.] for _ in data['input']]})
                else:
                    result = ({"index": 0, "score": 95, "reason": "fixture"} if "Role: Evaluator" in data['prompt']
                              else {"candidates": ["8/(3-8/3)"]})
                    self.reply({"response": json.dumps(result), "prompt_eval_count": 7, "eval_count": 4})
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = LocalOllama(base_url=f"http://127.0.0.1:{server.server_port}")
            client.ready()
            with tempfile.TemporaryDirectory() as d, ExitStack() as resources:
                source = Path(d)/"rules.md"
                source.write_text("Use every card once; fractional intermediates are legal.")
                rag = resources.enter_context(ChromaRAG(Path(d)/"chroma", client))
                rag.ingest([source])
                w = TA2Workflow(Path(d)/"state", client=client, rag=rag)
                try:
                    result = w.run([3,3,8,8], "http-fixture")
                    self.assertTrue(result["valid"])
                    self.assertEqual(result["prompt_tokens"], 14)
                    self.assertEqual(result["tool_calls"], 3)  # embedding query + two agents
                    self.assertEqual(len(result["evidence"]), 1)
                finally:
                    w.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_transient_retry(self):
        client = LocalOllama(retries=1)
        response = io.BytesIO(json.dumps({"embeddings": [[1.,2.]]}).encode())
        with patch("urllib.request.urlopen", side_effect=[urllib.error.URLError("test"), response]), patch("time.sleep"):
            self.assertEqual(client.embed(["card"]), [[1.,2.]])
        self.assertEqual(client.attempts, 2)

    def test_no_retry_permanent_http_error(self):
        client = LocalOllama()
        error = urllib.error.HTTPError("local", 404, "missing model", {}, None)
        with patch("urllib.request.urlopen", side_effect=error) as request:
            with self.assertRaises(ToolFailure):
                client.generate("test")
            self.assertEqual(request.call_count, 1)

    def test_readiness_checks_requested_models(self):
        client = LocalOllama()
        with patch.object(client, "_request", return_value={"models": [{"name": "qwen2.5:3b"}]}):
            with self.assertRaises(ToolFailure):
                client.ready()

    def test_invalid_embedding_schema(self):
        client = LocalOllama()
        with patch.object(client, "_request", return_value={"embeddings": [[float("nan")]]}):
            with self.assertRaises(ToolFailure):
                client.embed(["card"])


class EvaluationTests(unittest.TestCase):
    def test_five_cases_three_systems_and_preserved_outputs(self):
        with tempfile.TemporaryDirectory() as d, ExitStack() as resources:
            path = Path(d)/"eval.csv"
            rows = evaluate(path, offline=True)
            self.assertEqual(len(rows), 15)
            self.assertEqual(len({r["case"] for r in rows}), 5)
            self.assertTrue(path.with_suffix(".traces.json").exists())
            self.assertTrue(all(r["mode"] != "ollama_ta2" for r in rows))
            unsolvable = next(r for r in rows if r["system"] == "TA2" and r["case"] == "unsolvable")
            self.assertFalse(unsolvable["expected_solvable"])
            self.assertEqual(unsolvable["status"], "no_solution")
            with self.assertRaises(ValueError):
                evaluate(path, offline=True)


if __name__ == "__main__":
    unittest.main()
