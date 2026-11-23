"""Targeted SOP-gap tests. These are fixtures, not live Qwen measurements."""
import tempfile
import unittest
from pathlib import Path

from ta2.followup import UNKNOWN, contextual_followup
from ta2.qa import answer_grounded, compare_k
from ta2.rag import ChromaRAG


ROOT = Path(__file__).resolve().parents[1]


class EmbeddingFixture:
    embedding_model = "fixture-embedding"

    def embed(self, texts):
        return [[float(len(text) % 11 + 1), 1.0, 0.5] for text in texts]


class RetrieverFixture:
    def retrieve(self, question, k=3):
        return [
            {"id": f"id-{i}", "source": f"reference-{i}.md", "distance": float(i) / 10,
             "text": "Division can produce fractional intermediate values. Fractions are allowed."}
            for i in range(k)
        ]


class QAFixture:
    def generate(self, prompt):
        return {"answer": "Division can produce fractional intermediate values.",
                "citations": ["S1"]}


class JuryReadinessTests(unittest.TestCase):
    def test_full_corpus_has_eight_or_more_chunks(self):
        with tempfile.TemporaryDirectory() as tmp:
            documents = sorted((ROOT / "ta2" / "corpus").glob("*.md"))
            with ChromaRAG(Path(tmp) / "chroma", EmbeddingFixture()) as rag:
                written = rag.ingest(documents)
                self.assertGreaterEqual(written, 8)
                self.assertEqual(rag.collection.count(), written)
                self.assertEqual(len(rag.retrieve("fraction intermediate arithmetic", k=1)), 1)
                self.assertEqual(len(rag.retrieve("fraction intermediate arithmetic", k=3)), 3)

    def test_source_grounding_k_comparison_and_out_of_domain_refusal(self):
        rag = RetrieverFixture()
        model = QAFixture()
        question = "Can division produce fractional intermediate values?"
        results = compare_k(question, rag, model)
        self.assertTrue(results["k1"]["grounded"])
        self.assertEqual(results["k3"]["citations"], ["S1"])
        self.assertEqual(len(results["k1"]["sources"]), 1)
        self.assertEqual(len(results["k3"]["sources"]), 3)
        unrelated = answer_grounded("Who founded Neptune Motors?", rag, model, k=3)
        self.assertFalse(unrelated["grounded"])
        self.assertEqual(unrelated["citations"], [])
        self.assertIn("I don't know", unrelated["answer"])

    def test_conversation_followup_requires_prior_thread(self):
        state = {"history": [
            {"puzzle": [1, 2, 3, 4], "expression": "(1*2)*(3*4)", "status": "verified"},
            {"puzzle": [3, 3, 8, 8], "expression": "8/(3-8/3)", "status": "verified"},
        ]}
        question = "What was my last expression?"
        yes = contextual_followup(state, question)
        no = contextual_followup(state, question, without_memory=True)
        self.assertTrue(yes["memory_used"])
        self.assertIn("8/(3-8/3)", yes["answer"])
        self.assertFalse(no["memory_used"])
        self.assertEqual(no["answer"], UNKNOWN)

    def test_unknown_question_is_not_invented_from_history(self):
        state = {"history": [{"puzzle": [3, 3, 8, 8],
                             "expression": "8/(3-8/3)", "status": "verified"}]}
        reply = contextual_followup(state, "Which city did I visit?")
        self.assertFalse(reply["memory_used"])
        self.assertIn("I don't know", reply["answer"])


if __name__ == "__main__":
    unittest.main()
