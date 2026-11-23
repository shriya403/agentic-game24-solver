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
    ingest.add_argument("paths", nargs="*", type=Path,
                        help="Markdown documents or directories; default: all ta2/corpus/*.md")
    audit = sub.add_parser("rag-audit", help="Compare grounded answers at k=1 and k=3")
    audit.add_argument("question")
    followup = sub.add_parser("followup", help="Answer a contextual question from saved thread history")
    followup.add_argument("--thread", required=True)
    followup.add_argument("--question", required=True)
    followup.add_argument("--without-memory", action="store_true")
    solve = sub.add_parser("solve")
    solve.add_argument("cards", nargs=4, type=int)
    solve.add_argument("--thread", required=True)
    solve.add_argument("--namespace", default="default")
    solve.add_argument("--seed", type=int, default=42)
    solve.add_argument("--max-hops", type=int, default=12)
    solve.add_argument("--search-policy", choices=["model", "hybrid"], default="model")
    solve.add_argument("--search-budget", type=int, default=10000)
    resume = sub.add_parser("resume")
    resume.add_argument("--thread", required=True)
    resume.add_argument("--search-policy", choices=["model", "hybrid"], default="model")
    inspect = sub.add_parser("history", help="Read checkpointed state without model calls")
    inspect.add_argument("--thread", required=True)
    args = parser.parse_args()
    client = None if args.offline else LocalOllama(args.base_url, args.model, args.embedding_model)
    try:
        with ExitStack() as resources:
            if args.command in ("check", "ingest", "rag-audit") and args.offline:
                parser.error("check, ingest and rag-audit require Ollama; offline mode supplies no embeddings")
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
            if client and args.command not in ("history", "followup"):
                client.ready()
            rag = (resources.enter_context(ChromaRAG(data / "chroma", client))
                   if client and args.command not in ("history", "followup") else None)
            if args.command == "ingest":
                requested = args.paths or [Path("ta2/corpus")]
                paths = [file for item in requested
                         for file in (sorted(item.glob("*.md")) if item.is_dir() else [item])]
                if not paths:
                    raise ToolFailure("ingest", "No Markdown documents found")
                print(json.dumps({"chunks_upserted": rag.ingest(paths),
                                  "sources": [str(p) for p in paths],
                                  "collection_chunks": rag.collection.count()}))
                return
            if args.command == "rag-audit":
                from .qa import compare_k
                print(json.dumps(compare_k(args.question, rag, client), indent=2))
                return
            workflow = TA2Workflow(data, client=client, rag=rag, offline=args.offline,
                                   max_hops=getattr(args, "max_hops", 12),
                                   search_policy=getattr(args, "search_policy", "model"),
                                   search_budget=getattr(args, "search_budget", 10000))
            try:
                if args.command == "history":
                    print(json.dumps(workflow.snapshot(args.thread).values, indent=2))
                    return
                if args.command == "followup":
                    from .followup import contextual_followup
                    result = contextual_followup(workflow.snapshot(args.thread).values,
                                                 args.question, args.without_memory)
                    print(json.dumps(result, indent=2))
                    return
                state = (workflow.resume(args.thread) if args.command == "resume" else
                         workflow.run(args.cards, args.thread, args.seed, args.namespace))
                print(json.dumps(state, indent=2))
                if state["status"] in ("tool_failure", "max_hops_exceeded", "search_budget_exceeded"):
                    raise SystemExit(2)
            finally:
                workflow.close()
    except (ToolFailure, ValueError, OSError, sqlite3.Error) as exc:
        parser.exit(2, f"TA2: {exc}\n")


if __name__ == "__main__":
    main()
