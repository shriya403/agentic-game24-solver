"""Initialize the jury runtime databases and rebuild bundled retrieval examples."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from final_jury.examples import ExampleIndex, SEEDS
from ta2.rag import ChromaRAG
from ta2.tools import LocalOllama
from ta2.workflow import TA2Workflow


def prepare(data: Path) -> dict:
    data.mkdir(parents=True, exist_ok=True)
    tables = {}
    with closing(TA2Workflow(data, offline=True)) as workflow:
        workflow.saver.setup()
    for filename, names in [("checkpoints.sqlite", ["checkpoints", "writes"]),
                            ("store.sqlite", ["ta2_items"])]:
        with closing(sqlite3.connect(data / filename)) as db:
            tables[filename] = {}
            for name in names:
                ddl = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                                 (name,)).fetchone()[0]
                count = db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                tables[filename][name] = {"ddl": ddl, "rows": count}
    client = LocalOllama(timeout=90, retries=1)
    paths = sorted((Path(__file__).resolve().parents[1] / "ta2" / "corpus").glob("*.md"))
    chroma = data / "chroma"
    with ChromaRAG(chroma, client) as rules:
        written = rules.ingest(paths)
    with closing(ExampleIndex(chroma, client, 3)) as solved:
        solved.seed()
    with ChromaRAG(chroma, client) as rules:
        rule_count = rules.collection.count()
        rule_ids = [row["id"] for row in rules.retrieve("Fractional intermediate values", 3)]
    with closing(ExampleIndex(chroma, client, 3)) as solved:
        example_count = solved.backend.collection.count()
        example_ids = [row["id"] for row in solved.retrieve("Arithmetic solution for [1, 2, 3, 4]")]
    return {"sqlite_tables": tables, "embedding_model": client.embedding_model,
            "corpus_files": [p.name for p in paths], "chunks_upserted": written,
            "ta2_rules": {"count_after_reopen": rule_count, "retrieved_ids": rule_ids},
            "jury_solved_v1": {"seed_examples": len(SEEDS), "count_after_reopen": example_count,
                               "verified_retrieved_ids": example_ids}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path,
                        default=Path(os.environ.get("GAME24_DATA_DIR", "data/runtime")))
    parser.add_argument("--receipt", type=Path, help="Save the receipt to a new JSON file.")
    args = parser.parse_args()
    if args.receipt and args.receipt.exists():
        parser.error("Choose a new receipt filename.")
    receipt = json.dumps(prepare(args.data_dir), indent=2) + "\n"
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        with args.receipt.open("x", encoding="utf-8") as handle:
            handle.write(receipt)
    print(receipt)


if __name__ == "__main__":
    main()
