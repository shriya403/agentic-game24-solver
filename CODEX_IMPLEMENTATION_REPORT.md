# Final engineering report · GAME24 AI

**Game of 24 Solver: Chain-of-Thought vs Tree-of-Thought**
Shriya Jitendra Shinde · Agentic AI · MIT ADT University, Pune · November 2026

## Result

The repository now has a single Streamlit entry point for the jury and keeps the original TA1, early TA2, and expanded TA2 applications accessible. A new evaluator view identifies how each TA1 tree ranking was obtained. The final workflow records rejected proposals, separates an explicit deterministic run from model generation, and produces an independent proof certificate. A five-minute deterministic demonstration, saved Windows model study, fresh live-model traces, and failure demonstrations support presentation under different service conditions.

## Implementation checklist

| Work | Delivered evidence |
|---|---|
| Recover and back up | Complete original Git bundle verified before edits. All 23 TA1 blobs match the pinned commit. Short 68-line client recovered from the earlier TA2 branch. Full provenance in [source recovery](docs/SOURCE_RECOVERY.md). |
| Unify the entry points | Windows batch launcher, Python 3.12 bootstrap, version-pinned stack, eight-section Streamlit application and four accessible historical entry points. |
| Stabilize reasoning | Reused legal arithmetic moves and the TA2 supervisor graph. Added equivalent-state pruning, persisted rejections, separate deterministic and model score provenance, independent guard and trace-derived explanations. |
| Restore memory and RAG | Initialized both SQLite databases and two Chroma collections. Rebuilt 14 course chunks and three proof-checked examples. Repeated initialization preserved counts. Cross-process thread resume, Store isolation and k=1/3 retrieval passed. [Schema and integration receipts](docs/INTEGRATION.md) |
| Verify UI | Chromium inspected a live fractional solve, downloadable JSON with a valid certificate, reasoning tree, operations, and evaluation views. At 1280×720 and 390×844 the live proof was readable without horizontal overflow. The phone sidebar opened the branch inspector. |
| Measure | Re-audited every expression in the 20-row historical Qwen study and the current 15-row reference comparison. Additional measured model runs retain their own provenance, assistance flags, and queue-dependent times. [Evaluation report](docs/EVALUATION.md) |
| Test faults | Ten controlled scenarios. Includes rejected wrong arithmetic, wrong cards, division by zero, unsupported syntax, untrusted retrieved text, missing evidence, bounded routing, unsolvable input, disconnected SQLite and unavailable model service. [Safety evidence](docs/SAFETY.md) |
| Package | Editable 13-slide PowerPoint rendered in LibreOffice, walkthrough, architecture diagram, viva guide, release source branch and downloadable repository ZIP. |

## What changed in a live solve

With 3, 3, 8, 8 the final live Qwen-ranked TA1 tree returned `8 / (3 - 8 / 3)`. It recorded three generation calls, 1,696 prompt tokens and 578 generated tokens. The branch trace labels the exact look-ahead and applicable deterministic scores. The independent auditor replayed 8/3, then 3 − 8/3 = 1/3, then 8 ÷ (1/3) = 24. The input leaves were 8, 3, 8, 3. Shared-CPU elapsed time included queueing and an additional HTTP attempt. [Recorded run](traces/qwen-tree-337a40475e454a50a99df16d930c5de4.json)

A separate final multi-agent run used real Qwen and k=1 solved-example retrieval with 1, 2, 3, 4. The model selected an expression worth 22. The guard rejected it at four dispatches. Both the generated candidate and the mathematical reason survive in the trace. This failure is relevant on stage because the same solver can show a fluent proposal and a correct rejection. [Recorded run](traces/live-integration/final-solver.json)

## Scientific findings

| Method | Historical Windows Qwen study, verified out of four solvable | Current explicit deterministic comparison |
|---|---:|---:|
| TA1 linear | 0/4 | 1/4 greedy |
| TA1 ToT | 2/4 with exact look-ahead | 4/4 with exact look-ahead |
| TA2 | 1/4 with model proposals and tool checks | 4/4 with exhaustive oracle |
| TA2 hybrid | 4/4 with exact search available | Separate historical arm |

The unsolvable fifth input was assessed separately. Historical hybrid and the current exhaustive TA2 reference established impossibility. A model-only hop stop leaves the answer unresolved. Four solvable cases, a single seed, different computational budgets, and assistance from exact search limit the inference. Across-machine timings include different model-service and hardware costs. The additional fresh model study completed 11 of 25 planned trials before the delivery cut-off. Its individual results, time costs, retrieval counts and errors are included. It supports no aggregate claim about RAG improving accuracy.

## Verification

The pristine TA1 suite had eight passing tests. The recovered TA2 suite had 40 passing tests before the follow-up fix. The Linux release ran 71 tests with 239 successful subtests, including agreement with an independent subset-DP solver, handling of duplicate-card orderings, restart, final solver integration, observable branch provenance, fault handling, and all eight dashboard sections. The separate real integration check passed five of five checks, including genuine model output and actual embeddings. See [structured verification results](traces/tests/verification.json) and [JUnit XML](traces/tests/jury-junit.xml).

On native Windows the CI job installed the project with Python 3.12, launched the actual batch file, observed Streamlit's health endpoint and ran both test suites. On Linux we additionally exercised the Python bootstrap against a clean source archive and started each historical app with Streamlit AppTest. The final code run passed 31 jury tests and 40 TA2 tests on native Windows. The [public CI run](https://github.com/shriya403/agentic-game24-solver/actions/runs/45139273783) and [extracted Windows receipt](traces/tests/windows-ci.log) record the outcome.

During testing, a mixed-wording memory question returned the previous cards when it asked for the previous puzzle expression. The follow-up router now prioritizes the requested field and the cross-process test checks the corrected behavior.

## Scope and future work

The repository was selected as the source after the Windows Desktop path was supplied without an attached ZIP. Existing private SQLite history, rejected branches, local dashboard changes and user-indexed documents outside Git could not be compared or recovered. Rebuilt stores begin with zero personal records. The archive's original results remain available under `results/`.

For a larger experiment, counterbalance trial order, isolate the model server from other jobs, and repeat across seeds and unseen puzzles. Compare identical search budgets and retain the proportion of model-generated rankings per puzzle. For an assessment requiring the student's own contribution statement, supply the actual roles and disclose AI assistance in this integration, documentation and test preparation.
