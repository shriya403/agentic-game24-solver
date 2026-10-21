# TA2 extension: group setup and acceptance guide

TA2 is additive. `game24/`, `tests/`, `app.py`, `run_experiment.py`, the TA1
dependency manifests, and the recorded TA1 baseline remain unchanged. The exact
TA2 SOP was not supplied; this implements the eight requested capabilities and
uses a documented provisional five-puzzle evaluation. Match the final submission
against your instructor's precise SOP before claiming formal compliance.

## Windows quick start

Use your existing local Ollama installation and downloaded Qwen model. Codex
Cloud HTTP 403 responses do not diagnose your Windows installation.

From the repository root in PowerShell:

```powershell
python -m venv .venv-ta2
.\.venv-ta2\Scripts\python -m pip install -r requirements-ta2.txt
ollama pull nomic-embed-text
# If Ollama is not already running, run `ollama serve` in another terminal.
.\.venv-ta2\Scripts\python -m ta2.cli check
.\.venv-ta2\Scripts\python -m ta2.cli ingest ta2/corpus/rules.md
.\.venv-ta2\Scripts\python -m ta2.cli solve 3 3 8 8 --thread group-demo --namespace group
.\.venv-ta2\Scripts\python -m streamlit run app_ta2.py
```

The `check` command verifies both installed model names, an actual embedding,
and an actual JSON generation. No API key is required. Defaults are Qwen2.5:3b,
nomic-embed-text, and localhost:11434. `--model`, `--embedding-model`, and
`--base-url` are global CLI options placed before the subcommand. Only local
HTTP endpoints are accepted. `ollama pull` is not run automatically.

On Linux, use `python -m venv .venv-ta2`, install with
`.venv-ta2/bin/python -m pip install -r requirements-ta2.txt`, and substitute
`.venv-ta2/bin/python` in the commands above. The original TA1 environment can
remain separate. Direct TA2 dependencies were tested with
langgraph-checkpoint-sqlite 3.1.2, Chroma 1.5.9, and LangGraph 1.2.16.

## Components and execution contract

| Component | Files | Behavior |
|---|---|---|
| Thread memory | `ta2/workflow.py` | SQLite checkpointer, explicit thread IDs, bounded history, restart/resume |
| Durable Store | `ta2/storage.py` | LangGraph BaseStore backed by a separate SQLite database; CRUD, namespace listing, equality-filter search |
| Semantic retrieval | `ta2/rag.py`, `ta2/corpus/rules.md` | Persistent Chroma, explicit nomic embeddings, overlapping chunks, stable IDs, source citations |
| Agent roles | `ta2/prompts.py`, `ta2/workflow.py` | Proposer candidates, Evaluator ranking, deterministic Verifier, feedback loop |
| Coordination | `ta2/workflow.py` | Supervisor dispatches retrieve → proposer → evaluator → verifier, then repairs or terminates |
| Tool boundaries | `ta2/tools.py` | Timeouts, bounded transient retries, JSON contracts, bounded expressions, exact TA1 validator reuse |
| Evaluation | `run_ta2_evaluation.py` | Five cases, both frozen TA1 strategies plus TA2, CSV and raw traces |
| UI | `app_ta2.py` | Separate persistent TA2 UI, agent events, retrieval evidence and explicit failure states |

`MAX_HOPS=12` counts each supervisor dispatch to retrieval or an agent. Supervisor
and finish nodes are not counted. The counter and original budget are saved in
checkpoints; resume cannot increase the budget. Graph recursion limits provide
a second bound. A normal successful attempt uses four dispatches. Invalid
expressions return verifier feedback to the Proposer until the budget expires.

Only the independent exact verifier grants `verified`. The Evaluator cannot
approve mathematical truth. Inputs are four integer cards in 1..13; intermediate
fractions and negative results are allowed. Expressions are limited to 256
characters, three-digit literals, and 32 AST nodes. Calls, attributes, powers,
extra constants, missing/reused cards, division by zero and wrong targets are
rejected. Retrieved context is bounded reference data, not executable commands.

## Persistence and isolation

Default data lives outside the checkout in `~/.game24-ta2/`. Override using
`TA2_DATA_DIR` or the CLI's global `--data-dir`. Files include:

- `checkpoints.sqlite`: execution state, history, role outputs, routing and hop budget;
- `store.sqlite`: independently queryable verified solutions;
- `chroma/`: retrieved rule documents and their vectors.

Repeat a completed thread to retain its last 20 turns. Each new puzzle resets
run-local candidates, errors and hops. An interrupted thread must be resumed:

```powershell
.\.venv-ta2\Scripts\python -m ta2.cli resume --thread group-demo
```

Programmatic interruption is available through
`workflow.run(cards, thread_id, interrupt_after=["evaluator"])`. Close the
workflow, recreate it with the same data directory/models/mode, and call
`workflow.resume(thread_id)`. Resume uses the persisted budget. Namespaces are
checked on thread reuse; use distinct thread IDs for different groups. Verified
Store memory is further separated by execution mode, so offline oracle records
do not become model-run evidence. A thread cannot change modes.

This is a trusted local classroom application. Namespace identifiers are not
authentication or a security boundary against someone who controls the data
directory. SQLite Store supports equality filters, not TTL or semantic queries;
use Chroma for semantic retrieval. Ingestion upserts before deleting stale
chunks; Chroma ingestion is not a multi-operation transaction. Do not change
the embedding model in an existing collection; use a new data directory/index.

## Failure behavior

Transient transport errors, HTTP 429 and HTTP 5xx responses retry twice by
default with bounded backoff. Permanent HTTP failures and malformed output fail
explicitly. Model mode requires both models and an ingested RAG index. It does
not silently switch to a deterministic solver. Retrieval, generation and Store
failures produce structured tool errors; exhausted hop budgets have their own
termination status. Checkpoint/database initialization failures are infrastructure
errors and must be resolved before execution can continue.

Normal terminal statuses are `verified`, `max_hops_exceeded`, `tool_failure`,
and offline-only `no_solution` (proved by exhaustive search). Failure to find a
model-generated answer does not prove mathematical unsolvability. CLI solve
returns exit code 2 for tool failures and hop exhaustion.

## Tests and offline demo

```powershell
.\.venv-ta2\Scripts\python -m unittest discover -s tests -v
.\.venv-ta2\Scripts\python -m unittest discover -s tests_ta2 -v
.\.venv-ta2\Scripts\python -m ta2.cli --offline solve 3 3 8 8 --thread offline-demo
.\.venv-ta2\Scripts\python run_ta2_evaluation.py --offline --output results/ta2-offline.csv
```

Offline TA2 uses an explicitly labelled exhaustive oracle. It exercises the
graph, SQLite memory, verifier and output pipeline, but performs no semantic
retrieval or real model calls. Tests exercise real persistent Chroma with
fixture embeddings, plus mocked Ollama response/retry contracts. Those tests
are not evidence of nomic or Qwen quality. The test suite also exercises
cross-process checkpoint restoration, namespace isolation, input attacks,
MAX_HOPS, embedding failures, invalid model output and five-case evaluation.

## Five-case comparison and reporting

```powershell
.\.venv-ta2\Scripts\python run_ta2_evaluation.py --runs 1 --output results/ta2-qwen.csv
```

The fixed provisional cases are `[4,7,8,8]`, `[1,5,5,5]`, `[3,3,8,8]`,
`[1,2,3,4]`, and unsolvable `[1,1,1,1]`. Each seed runs frozen TA1 Linear,
frozen TA1 ToT, and TA2: 15 rows per seed, 75 for five seeds. The harness
independently verifies final expressions and writes a sibling `.traces.json`.
Existing outputs are refused rather than overwritten. Restart/continuity and
injected-failure scenarios are tested separately from these puzzle cases.

Model evaluation checks both local models, creates a fresh rules-only Chroma
index, and isolates checkpoints/Store for each case and seed. The reference
corpus has no worked benchmark answers. Offline results are labelled oracle
demos. Frozen TA1 ToT remains oracle-assisted even when Qwen is available;
the CSV records that asymmetry. Its arithmetic beam search and TA2's multi-agent
loop also have different budgets; report tokens, latency and hops rather than
claiming matched compute. TA1 unexpected fallback/tool failures cause a nonzero
evaluation exit and remain visible in the CSV. Do not equate failure to find a
solution with a correct unsolvability proof. Model/index setup time is excluded
from per-solver latency, while TA2 retrieval calls are included.

Group acceptance checklist:

- [ ] Run both unchanged TA1 tests and new TA2 tests.
- [ ] Run `check` on Windows to verify Qwen and nomic actual calls.
- [ ] Ingest the rules and inspect source-bearing retrieval evidence.
- [ ] Demonstrate a second turn, fresh-thread isolation, and process restart.
- [ ] Demonstrate an invalid candidate being rejected and bounded repair.
- [ ] Demonstrate an unavailable model/retrieval failure without fake success.
- [ ] Run real five-case evaluation; retain CSV, traces and settings.
- [ ] Check exact cases and API requirements against the instructor's TA2 SOP.

Cloud validation can establish implementation correctness without establishing
that your separate Windows model server was tested. Local Qwen and nomic
performance must be measured on your Windows machine.
