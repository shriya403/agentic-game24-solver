"""Run live, fixture-free integration checks and save source-bearing JSON evidence."""
from __future__ import annotations

import argparse
import json
import platform
import sys
from contextlib import closing
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory

from final_jury.examples import ExampleIndex
from run_ta2_acceptance import memory_demo
from ta2.rag import ChromaRAG
from ta2.tools import LocalOllama


def check(output: Path) -> dict:
    # Exclusive creation prevents mixing this evidence with any prior run.
    output.mkdir(parents=True, exist_ok=False)
    report = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0],
        "platform": platform.system(),
        "packages": {name: version(name) for name in
                     ["chromadb", "langgraph", "langgraph-checkpoint-sqlite", "langchain-chroma"]},
        "checks": {},
    }
    records = report["checks"]

    def record(name, operation):
        try:
            result = operation()
            records[name] = {"status": "passed", "evidence": result}
        except Exception as exc:
            records[name] = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
        (output / "integration.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    client = LocalOllama(base_url="http://127.0.0.1:11434", timeout=90, retries=0)

    def generation():
        client.ready()
        result = client.generate('Output exactly this JSON object with a boolean value: {"ready":true}')
        if result.get("ready") is not True:
            raise ValueError(f"Unexpected readiness response: {result}")
        return {"model": client.model, "response": result, "input_tokens": client.prompt_tokens,
                "output_tokens": client.output_tokens}

    def embeddings():
        vector = client.embed(["Exact arithmetic permits fractional intermediate results."])[0]
        return {"model": client.embedding_model, "dimensions": len(vector), "finite": True}

    def retrieval(path):
        paths = sorted((Path(__file__).resolve().parents[1] / "ta2/corpus").glob("*.md"))
        with ChromaRAG(path, client) as index:
            count = index.ingest(paths)
        with ChromaRAG(path, client) as reopened:
            query = "Why does the solver keep fractional intermediate values?"
            rows = {str(k): reopened.retrieve(query, k) for k in [1, 3]}
        for k, matches in rows.items():
            if len(matches) != int(k) or any(not row["id"] for row in matches):
                raise ValueError("Retrieval returned incomplete evidence")
            for row in matches:
                row["source"] = Path(row["source"]).name
        return {"query": query, "written_chunks": count, "reopened_and_retrieved": rows}

    def examples(path):
        with closing(ExampleIndex(path, client, 1)) as index:
            index.seed()
        query = "Game of 24 cards [3,3,8,8], verified arithmetic example"
        rows = {}
        for k in (1, 3):
            with closing(ExampleIndex(path, client, k)) as reopened:
                matches = reopened.retrieve(query)
                if len(matches) != k or any(not row["expression"] for row in matches):
                    raise ValueError("Verified solved examples missing after reopen")
                rows[str(k)] = matches
        return {"query": query, "verified_examples": rows}

    with TemporaryDirectory(prefix="game24-integrations-") as location:
        tmp = Path(location)
        def memory():
            # The persisted graph and SQLite store are real. The search policy is exact.
            result = memory_demo(tmp, True, client.base_url, client.model)
            evidence = json.loads((tmp / "memory-and-rag.json").read_text(encoding="utf-8"))
            return {"execution": "deterministic TA2 search", "checkpoints_and_store": result,
                    "resumed_state": {k: evidence["resumed_in_new_process"][k] for k in
                                      ("puzzle", "expression", "status", "valid", "hops", "mode")},
                    "followup_with_memory": evidence["followup_with_memory"],
                    "followup_without_memory": evidence["followup_without_memory"]}
        record("sqlite_langgraph_cross_process", memory)
        record("ollama_generation", generation)
        record("ollama_embeddings", embeddings)
        record("chroma_corpus_reopen", lambda: retrieval(tmp / "corpus-index"))
        record("chroma_solved_examples_reopen", lambda: examples(tmp / "examples-index"))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="A new evidence directory")
    report = check(parser.parse_args().output)
    print(json.dumps({k: row["status"] for k, row in report["checks"].items()}, indent=2))
    raise SystemExit(int(any(row["status"] != "passed" for row in report["checks"].values())))
