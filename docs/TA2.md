# TA2: complete group workflow and evidence guide

The extension implements the eight requirements requested in this chat. The exact
instructor SOP was not supplied, so formal SOP-specific compliance remains subject
to that document. Frozen TA1 files, tests, dependency declarations and previously
recorded results are unchanged. TA2 lives in `ta2/`, `tests_ta2/`, and separate
entry points.

## Windows: run everything in one command

Use **Command Prompt**, not the Ollama `>>>` chat. Keep your existing Ollama
application running. Both `qwen2.5:3b` and `nomic-embed-text` were already downloaded
successfully on your Windows computer; no repeated model download is needed.

From your existing project folder with `.venv-ta2` activated:

```bat
git pull --ff-only origin codex/ta2-extension
python -m pip install -r requirements-ta2.txt
python run_ta2_acceptance.py --output-dir results/ta2-final
```

Choose a new output directory if that directory already exists. The script refuses
to mix runs or overwrite previous evidence. Without `--output-dir`, it chooses a
unique directory automatically.

The acceptance command:

1. Runs the unchanged TA1 suite and the TA2 suite, retaining full logs.
2. Checks real generation, real nomic embeddings, persistent Chroma retrieval,
   thread continuity, SQLite Store isolation and checkpoint resume in a new process.
3. Runs all five puzzles against TA1 Linear, TA1 ToT, TA2 model-only, and TA2 hybrid.
4. Saves an acceptance report, settings manifest, progress, CSV, traces and summary.

The real run produces **20 rows per seed** (five puzzles × four systems).
`--runs 5` produces 100 rows. During evaluation it prints progress after each
completed solver. Individual local calls may still take time, depending on hardware.

Artifacts in the output directory:

| Artifact | Evidence |
|---|---|
| `ACCEPTANCE.md`, `acceptance.json` | Capability checks, completion status, unresolved blockers |
| `tests.log`, `tests_ta2.log` | Actual tests executed, counts and outcomes |
| `memory-and-rag.json`, `restart.log` | Source-bearing retrieval, two turns, isolated namespaces and new-process resume |
| `memory-demo/` | Inspectable SQLite checkpoints, SQLite Store and persistent Chroma index |
| `evaluation.csv` | Case-level correctness, timings, tokens, hops, tool calls and assistance |
| `evaluation.traces.json` | Raw model/agent results and mathematical verification |
| `evaluation.manifest.json` | Models, settings, versions, platform, budgets, seeds and completion |
| `evaluation.summary.md` | Mechanical TA1-versus-TA2 outcome table |

`complete: true` requires all real capability checks, no evaluation tool failures,
and hybrid verification of all four solvable puzzles plus a complete-search proof
for the unsolvable puzzle. Model-only failures remain in the report. Passing the
acceptance checks does not mean Qwen reasoning improved or that it solved every
puzzle independently.

For an offline development check:

```bat
python run_ta2_acceptance.py --offline
```

Offline validation intentionally reports real model/RAG validation as unrun. It
uses explicit deterministic oracle demonstrations, never fabricated Qwen results.

## Requirement coverage

| Requirement | Implementation | Acceptance evidence |
|---|---|---|
| 1. LangGraph thread memory/checkpointer | `ta2/workflow.py`: `SqliteSaver`, explicit thread IDs, bounded history, typed durable state, restart | Repeated turns, thread/namespace isolation, interrupted graph resumed in another Python process |
| 2. Persistent SQLite Store | `ta2/storage.py`: LangGraph `BaseStore`, independent durable SQLite records, namespace separation | CRUD/reopen tests, verified memory retrieved after restart, isolation across groups and modes |
| 3. Chroma RAG + nomic | `ta2/rag.py`, `ta2/corpus/rules.md`: persistent vectors, stable chunk IDs, explicit `/api/embed`, sources and distances | Actual local nomic call, rules ingestion/retrieval; re-ingestion and cleanup regressions |
| 4. Proposer/Evaluator/Verifier | `ta2/prompts.py`, `ta2/workflow.py`: distinct nodes and explicit candidate contracts | Trace includes proposals, model scores, exact candidate assessments and final independent verification |
| 5. Supervisor + MAX_HOPS | `ta2/workflow.py`: dispatch decisions, persisted budget, complete-cycle reservation, bounded search | Budgets 1–14 tested; original hop/search budgets survive resume |
| 6. Mathematical guardrails | `ta2/tools.py`: exact frozen validator reuse, card/domain/syntax/size bounds; `ta2/search.py` | Fractional solutions pass; injection, extra constants, repeats, invalid operators and zero division are rejected |
| 7. Tool failures | `ta2/tools.py`, workflow error routes and resource lifecycles | Injected timeout/HTTP/schema/embedding/Store failures; bounded retry and explicit terminal outcomes |
| 8. Five-case TA1 vs TA2 evaluation | `run_ta2_evaluation.py`, `ta2/reporting.py` | Matched puzzles/seeds, independent validation, fresh memory, explicit assistance, retained CSV/traces/summary |

## Model-only versus hybrid: honest attribution

The first local model-only run solved no puzzles. Those measurements are retained;
this extension does not relabel or overwrite them.

- **Model policy** asks Qwen for expressions, evaluates all candidates using exact
  mathematical checks, obtains Qwen's ranking, and independently verifies the
  selected expression. If a correct candidate exists but Qwen ranks an incorrect
  one first, a documented guardrail selects the correct candidate. It does not
  synthesize an answer using exhaustive search.
- **Hybrid policy** performs that same model attempt. After a rejected expression,
  the supervisor explicitly calls a bounded exact arithmetic search tool. Its
  candidate still goes through the Evaluator and Verifier. The trace records the
  search node count, source and whether enumeration completed. No answers are
  hardcoded and no worked benchmark answers are put in the retrieval corpus.
- **Offline mode** is an explicit deterministic oracle demo without Qwen or nomic.

CSV `mode`, `oracle_assisted`, `search_nodes` and trace `candidate_origin` disclose
assistance. TA1 ToT already uses exact look-ahead, including in its Qwen mode;
that frozen behavior is also labelled. Hybrid success is an engineering result
for a model-plus-tools system, not proof of Qwen-only mathematical ability.

## Coordination and mathematical truth

The default budget is `MAX_HOPS=12`. One hop means a supervisor dispatch to a tool
or role; supervisor and finish nodes themselves do not count. Before proposal or
search, the supervisor reserves enough remaining hops for the complete
proposal/evaluation/verification cycle. It stops before beginning a cycle that
cannot finish. This fixes the previous unmatched-expression/stale-feedback issue.

Standard successful model path:

```text
retrieve → Proposer → Evaluator → Verifier → finish
```

Hybrid repair path after rejection:

```text
retrieve → Proposer → Evaluator → Verifier → exact-search tool → Evaluator → Verifier
```

Only the final mathematical Verifier grants `verified`. Confidence scores cannot
override exact arithmetic. State records the exact expression covered by each
verification, exact value, card usage and rejection reason. Four integer cards in
1..13 are supported; negative/fractional intermediate values are legal. Expressions
are limited to 256 characters, three-digit numeric literals and 32 AST nodes.
Arbitrary code, attribute access, extra constants, exponentiation and division by
zero are rejected. Retrieved text is untrusted reference data, not instructions
or executable commands.

Search has a separate persisted node budget (default 10000). `no_solution` is used
only after complete enumeration. `search_budget_exceeded` is inconclusive, as is
`max_hops_exceeded`. A model failing to find a valid expression is not a proof of
unsolvability. Model/schema/transport failures remain `tool_failure`; hybrid does
not secretly replace a broken model call with offline output.

## UI and individual commands

Launch the separate UI:

```bat
python -m streamlit run app_ta2.py
```

Choose the model or hybrid policy explicitly. UI actions include solving, resuming
an interrupted thread, and reading saved history. It displays execution mode,
candidate source, verifier feedback, hops, evidence, history, memory and errors.
The frozen `app.py` remains TA1.

Individual CLI commands (global options precede the command):

```bat
python -m ta2.cli check
python -m ta2.cli ingest ta2/corpus/rules.md
python -m ta2.cli solve 3 3 8 8 --thread group-v2 --namespace group --search-policy hybrid
python -m ta2.cli history --thread group-v2
python -m ta2.cli resume --thread interrupted-v2 --search-policy hybrid
python run_ta2_evaluation.py --search-policy both --output results/ta2-v2.csv
```

Use a new thread when switching execution policies. Completed legacy threads keep
their readable history; old interrupted v1 threads require a new thread because the
workflow topology changed. The resume command requires the original models/policy;
it uses persisted budgets even if a new process requests a larger budget.

Default interactive data is `~/.game24-ta2/`; change it using `TA2_DATA_DIR` or
`--data-dir`. `checkpoints.sqlite` holds graph state; `store.sqlite` independently
holds verified solutions; `chroma/` holds semantic evidence. The shipped rules
corpus has no worked evaluation answers. Evaluations use fresh threads and Store
namespaces for every case, seed and policy to prevent answer leakage.

## Failure handling, lifecycle and platform limits

Transport errors, HTTP 429 and HTTP 5xx retry at most twice by default with bounded
backoff. Permanent HTTP errors and malformed output fail explicitly. Missing models,
empty indexes, embedding failures and Store errors are distinguishable. Generated
output and embedding vectors are validated before use. Only local Ollama HTTP
endpoints are accepted; no API key is required.

Every Chroma client is explicitly closed, including shared/reopened clients and
exception paths, before temporary index deletion. Cleanup failures are not hidden.
The public lifecycle API requires Chroma >=1.5.9. SQLite initialization/checkpointer
failures are infrastructure blockers and cannot be turned into application success.

This is a trusted local classroom application: group namespaces organize state but
are not authentication against someone with filesystem access. The SQLite Store
supports equality filters and namespaces, not TTL or semantic search. Chroma handles
semantic search. Ingestion upserts before deleting stale chunks, but Chroma does not
provide a multi-operation transaction. Changing embedding models requires a new index.

The five provisional puzzle cases are `[4,7,8,8]`, `[1,5,5,5]`, `[3,3,8,8]`,
`[1,2,3,4]`, and unsolvable `[1,1,1,1]`. Restart, memory and injected-failure
scenarios are additional tests. If the instructor prescribes different five cases,
those exact definitions must be supplied before claiming formal SOP compliance.
One seed is descriptive evidence; tool budgets differ. Report measured outcomes
and costs rather than claiming universal improvement.
