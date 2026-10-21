"""Persistent Chroma retrieval with explicit Ollama embeddings; no auto-downloads."""
from __future__ import annotations

import hashlib
from pathlib import Path
from .tools import ToolFailure


class ChromaRAG:
    def __init__(self, path, client, collection="ta2_rules"):
        import chromadb
        self.client = client
        try:
            self.db = chromadb.PersistentClient(path=str(path), settings=chromadb.Settings(anonymized_telemetry=False))
            self.collection = self.db.get_or_create_collection(collection, embedding_function=None,
                              metadata={"embedding_model": client.embedding_model})
        except Exception as exc:
            raise ToolFailure("retrieval_init", type(exc).__name__) from exc
        if self.collection.metadata.get("embedding_model") != client.embedding_model:
            raise ToolFailure("retrieval", "Collection embedding model differs from configured model")

    def ingest(self, paths):
        try:
            return self._ingest(paths)
        except ToolFailure:
            raise
        except Exception as exc:
            raise ToolFailure("ingest", type(exc).__name__) from exc

    def _ingest(self, paths):
        total = 0
        for path in paths:
            path = Path(path)
            if path.stat().st_size > 1_000_000:
                raise ToolFailure("ingest", "Document exceeds 1 MB")
            text = path.read_text(encoding="utf-8")
            chunks = [text[i:i+1000] for i in range(0, len(text), 800) if text[i:i+1000].strip()]
            source = str(path.resolve())
            vectors = self.client.embed(chunks) if chunks else []
            ids = [hashlib.sha256(f"{source}:{i}".encode()).hexdigest() for i in range(len(chunks))]
            # Upsert before deleting stale chunks, so failed embeddings/upserts do
            # not erase the previous source. Chroma does not offer a multi-call transaction.
            previous_ids = self.collection.get(where={"source": source})["ids"]
            if chunks:
                self.collection.upsert(ids=ids, documents=chunks, embeddings=vectors,
                    metadatas=[{"source": source, "chunk": i} for i in range(len(chunks))])
            stale = sorted(set(previous_ids) - set(ids))
            if stale:
                self.collection.delete(ids=stale)
            total += len(chunks)
        return total

    def retrieve(self, query, k=3):
        try:
            count = self.collection.count()
            if not count:
                raise ToolFailure("retrieval", "Chroma collection is empty; ingest the rules first")
            result = self.collection.query(query_embeddings=self.client.embed([query]), n_results=min(k, count))
            return [{"id": key, "text": text[:1000], "source": meta["source"], "distance": distance}
                    for key, text, meta, distance in zip(result["ids"][0], result["documents"][0],
                                                       result["metadatas"][0], result["distances"][0])]
        except ToolFailure:
            raise
        except Exception as exc:
            raise ToolFailure("retrieval", type(exc).__name__) from exc
