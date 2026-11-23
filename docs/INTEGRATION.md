# Memory and local-model integration

The Linux integration run used Python 3.12.14 and Ollama 0.40.17 on CPU. The official model registry manifests identified Qwen2.5:3b and nomic-embed-text:latest. Downloaded layers were checked against the manifest SHA-256 digests. Generation and embedding requests ran on loopback. Library versions, result statuses, retrieved text, source IDs and distances are in [the integration receipt](../traces/live-integration/integration.json).

| Check | Observed result |
|---|---|
| Model readiness | Qwen returned the requested JSON boolean. Ollama reported 44 prompt tokens and 6 generated tokens. |
| Embeddings | nomic-embed-text returned 768 finite coordinates for the test sentence. |
| Course-reference retrieval | Chroma indexed 14 chunks from two packaged documents. After closing and reopening the client, the same question retrieved one and three source-bearing chunks. |
| Solved-example retrieval | Three proof-checked teaching examples persisted in a separate collection. After reopening, queries returned one and three verified expressions. Their similarity distances do not establish a benefit to a subsequent solution. |
| Interrupted workflow | A separate Python process resumed an interrupted LangGraph thread and produced a valid certificate for 3, 3, 8, 8. The test selected deterministic arithmetic search to isolate checkpoint behavior. |
| Conversation and durable memory | A second turn saw two turns of history and recalled the expression. Disabling history produced an explicit unknown answer. The separate namespace had no verified-memory hit. |

On the first execution of the inherited restart demo, asking for the “previous puzzle expression” returned the cards. The follow-up router now prioritizes the requested expression or status over the generic word “puzzle”. The repaired router passed the multi-process acceptance check and a mixed-wording regression in the original TA2 test suite.

## Rebuild from packaged sources

The following commands start from the unified project root with its virtual environment active and a local Ollama server running.

```console
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
python -m final_jury.prepare_data --data-dir data/runtime --receipt data/rebuild-receipt.json
python -m final_jury.check_integrations --output data/integration-check-01
```

The rebuild creates the databases in the chosen directory, initializes the checkpoint schema, embeds the packaged Markdown corpus into the `ta2_rules` collection, and adds the three teaching examples to `jury_solved_v1`. Identical documents at the same path have stable chunk IDs. When rerunning the command, supply a new receipt filename. The integration check uses a temporary directory to test restart, isolation and index reopen. It exits with a nonzero status if a dependency fails.

| Database | Tables and keys |
|---|---|
| `checkpoints.sqlite` | LangGraph creates `checkpoints`, keyed by thread ID, checkpoint namespace and checkpoint ID, and `writes`, keyed by the same three fields plus task ID and write index. These tables retain graph state and pending writes. |
| `store.sqlite` | `ta2_items` has a composite primary key of namespace and key. Each row has a JSON value and creation and update timestamps. The workflows use namespaces for verified solutions and rejected branches. |
| `chroma/` | The embedding-model name is stored with each collection. The course corpus and verified examples have separate collection names. Chroma manages the physical index and SQLite metadata. |

The packaged receipts describe newly initialized data. Personal Windows checkpoint history, previously learned solutions, failed branches, and user-indexed documents require the original runtime files to be restored. Packaged seed data can reconstruct the teaching examples and course corpus.

## Evidence interpretation

A verified expression proves correctness for one input multiset. A k comparison measures what the retriever returned for its query. The generation smoke check measures one small schema-following response. Benchmark accuracy, latency and token use must be read from the per-case experiment records with the associated assistance and execution labels.

On the clean rebuild run the checkpoint, pending-write and store tables each contained zero rows. After indexing, the two collections contained 14 and 3 records respectively. Repeating the command in the same directory produced an identical receipt, including the reopened counts and retrieved IDs. [Initial schema and index receipt](../traces/live-integration/rebuild.json) · [Repeated run](../traces/live-integration/rebuild-repeated.json)

## Live final-jury solve

A fresh `solve([1, 2, 3, 4], "multi", mode="model", rag=True, k=1, max_hops=4)` run retrieved one verified teaching example. Across two Qwen generation calls, the proposer offered three candidates and the evaluator selected the first. Its exact value was 22. The verifier rejected it and the supervisor ended the run after four dispatches. The counter recorded 906 input and 81 generated tokens over responses with telemetry. The shared CPU run took 238.41 seconds, including queue time and one extra HTTP attempt. This case demonstrates the end-to-end failure path on a solvable puzzle. [Live trace and proof auditor verdict](../traces/live-integration/final-solver.json)
