"""Persistent Chroma retrieval with explicit Ollama embeddings; no auto-downloads."""
from __future__ import annotations

import hashlib
from pathlib import Path
from .tools import ToolFailure
from langchain_core.embeddings import Embeddings
from langchain_chroma import Chroma


class LocalNomicEmbeddings(Embeddings):
    """LangChain embedding adapter backed by local Ollama."""
    def __init__(self, client):
        self.client = client

    def embed_documents(self, texts):
        return self.client.embed(list(texts))

    def embed_query(self, text):
        return self.client.embed([text])[0]


class ChromaRAG:
    def __init__(self, path, client, collection="ta2_rules"):
        import chromadb
        self.client = client
        try:
            self.db = chromadb.PersistentClient(path=str(path), settings=chromadb.Settings(anonymized_telemetry=False))
            self.collection = self.db.get_or_create_collection(collection, embedding_function=None,
                              metadata={"embedding_model": client.embedding_model})
        except Exception as exc:
            if hasattr(self, "db"):
                self.db.close()
            raise ToolFailure("retrieval_init", type(exc).__name__) from exc
        if self.collection.metadata.get("embedding_model") != client.embedding_model:
            self.db.close()
            raise ToolFailure("retrieval", "Collection embedding model differs from configured model")
        try:
            self.vectorstore = Chroma(
                client=self.db, collection_name=collection,
                embedding_function=LocalNomicEmbeddings(client),
            )
        except Exception as exc:
            self.db.close()
            raise ToolFailure("retrieval_init", type(exc).__name__) from exc

    def close(self):
        """Release this client's references, including Windows SQLite/index handles."""
        self.vectorstore = None
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()

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
            # LangChain-Chroma runs similarity retrieval through the same persistent
            # Chroma client. IDs, distances and sources remain visible for audit.
            results = self.vectorstore.similarity_search_with_score(query, k=min(k, count))
            return [{"id": doc.id, "text": doc.page_content[:1000],
                     "source": doc.metadata["source"], "distance": float(distance)}
                    for doc, distance in results]
        except ToolFailure:
            raise
        except Exception as exc:
            raise ToolFailure("retrieval", type(exc).__name__) from exc
