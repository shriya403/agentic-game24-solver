"""Structured, proof-checked solved examples for final-jury Chroma retrieval."""
from __future__ import annotations

import hashlib
import json
import math

from core.proof import audit
from ta2.rag import ChromaRAG
from ta2.tools import ToolFailure

# Independent teaching examples, outside the original five benchmark inputs.
SEEDS = [
    ([2, 2, 2, 3], "2*2*2*3"),
    ([1, 2, 4, 8], "(8+4)*2*1"),
    ([1, 2, 5, 7], "(7+5)*2*1"),
]


def evidence_record(text: str, distance: float) -> dict | None:
    """Project untrusted stored content onto two checked math fields only."""
    if not isinstance(text, str) or len(text) > 1000 or not math.isfinite(distance):
        return None
    try:
        item = json.loads(text)
        if not isinstance(item, dict) or set(item) != {"cards", "expression"} or not isinstance(item["cards"], list):
            return None
        cert = audit(item["expression"], item["cards"])
        if cert["valid"]:
            return dict(source="Verified example", puzzle=item["cards"], expression=item["expression"],
                        text=f"{item['cards']} → {item['expression']} = 24", distance=distance)
    except (ValueError, TypeError):
        pass
    return None


class ExampleIndex:
    def __init__(self, path, client, k):
        if type(k) is not int or k not in (1, 3):
            raise ValueError("Choose k=1 or k=3.")
        self.backend = ChromaRAG(path, client, collection="jury_solved_v1")
        self.k = k

    def close(self):
        self.backend.close()

    def remember(self, cards, expression):
        if not audit(expression, cards)["valid"]:
            raise ValueError("Only certified expressions may enter the solved-example index.")
        document = json.dumps({"cards": sorted(cards), "expression": expression})
        key = hashlib.sha256(document.encode()).hexdigest()
        try:
            if not self.backend.collection.get(ids=[key])["ids"]:
                vectors = self.backend.client.embed([document])
                self.backend.collection.upsert(ids=[key], documents=[document], embeddings=vectors,
                                              metadatas=[{"source": "Verified example"}])
        except ToolFailure:
            raise
        except Exception as exc:
            raise ToolFailure("index_write", str(exc)) from exc

    def seed(self):
        for cards, expression in SEEDS:
            self.remember(cards, expression)

    def retrieve(self, query):
        matches = self.backend.retrieve(query, self.k)
        evidence = []
        for match in matches:
            row = evidence_record(match["text"], match["distance"])
            # Source names, IDs and other metadata also come from the index.
            # Only a content hash may cross the retrieval-to-prompt boundary.
            digest = hashlib.sha256(match["text"].encode()).hexdigest()
            if row and match["id"] == digest:
                row["id"] = digest
                evidence.append(row)
        return evidence
