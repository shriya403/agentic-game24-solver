from __future__ import annotations

import argparse
import json
import os
import sqlite3
from contextlib import ExitStack
from pathlib import Path

from .tools import LocalOllama, ToolFailure
from .rag import ChromaRAG
from .workflow import TA2Workflow


def main():
    parser = argparse.ArgumentParser(description="TA2 Game of 24 extension (TA1 remains unchanged)")
    parser.add_argument("--data-dir", default=os.environ.get("TA2_DATA_DIR", str(Path.home() / ".game24-ta2")))
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument("--model", default="qwen2.5:3b")
    parser.add_argument("--embedding-model", default="nomic-embed-text")
    parser.add_argument("--offline", action="store_true", help="Explicit deterministic oracle demo, not model evidence")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="Check local model tags and actual embeddings/generation")
    ingest = sub.add_parser("ingest")
    ingest.add_argument("paths", nargs="+", type=Path)
    solve = sub.add_parser("solve")
    solve.add_argument("cards", nargs=4, type=int)
    solve.add_argument("--thread", required=True)
    solve.add_argument("--namespace", default="default")
    solve.add_argument("--seed", type=int, default=42)
    solve.add_argument("--max-hops", type=int, default=12)
    resume = sub.add_parser("resume")
    resume.add_argument("--thread", required=True)
    args = parser.parse_args()
    client = None if args.offline else LocalOllama(args.base_url, args.model, args.embedding_model)
    try:
        with ExitStack() as resources:
            if args.command in ("check", "ingest") and args.offline:
                parser.error("check and ingest require Ollama; offline mode supplies no embeddings")
            if args.command == "check":
                client.ready()
                vectors = client.embed(["Use every Game of 24 card exactly once."])
                result = client.generate('Return JSON: {"ready": true}')
                if result.get("ready") is not True:
                    raise ToolFailure("check", "Model did not return the expected readiness response")
                print(json.dumps({"generation": "ok", "embedding_dimensions": len(vectors[0])}))
                return
            data = Path(args.data_dir)
            data.mkdir(parents=True, exist_ok=True)
            if client:
                client.ready()
            rag = resources.enter_context(ChromaRAG(data / "chroma", client)) if client else None
            if args.command == "ingest":
                print(json.dumps({"chunks_upserted": rag.ingest(args.paths)}))
                return
            workflow = TA2Workflow(data, client=client, rag=rag, offline=args.offline,
                                   max_hops=getattr(args, "max_hops", 12))
            try:
                state = (workflow.resume(args.thread) if args.command == "resume" else
                         workflow.run(args.cards, args.thread, args.seed, args.namespace))
                print(json.dumps(state, indent=2))
                if state["status"] in ("tool_failure", "max_hops_exceeded"):
                    raise SystemExit(2)
            finally:
                workflow.close()
    except (ToolFailure, ValueError, OSError, sqlite3.Error) as exc:
        parser.exit(2, f"TA2: {exc}\n")


if __name__ == "__main__":
    main()
