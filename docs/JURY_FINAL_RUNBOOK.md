# Final jury runbook — Game of 24 TA2

This is an operator checklist and evidence map, **not** the student-authored 4-page report. Read the faculty SOP and use your own group/division details.

## 1. Get the reviewed changes on Windows

From the local project directory, stop any existing Streamlit process with Ctrl+C, then run:

```bat
git status --short
git fetch origin jury-final-2026-11-23
git switch -c jury-final-2026-11-23 FETCH_HEAD
python -m pip install -r requirements-ta2.txt
```

If `git status --short` lists local edits, preserve or commit them before switching branches. Do not discard work to force a checkout.

## 2. Required smoke checks

```bat
python -m unittest discover -s tests -v
python -m unittest discover -s tests_ta2 -v
python -m ta2.cli check
python -m ta2.cli ingest
python -m ta2.cli rag-audit "Can division produce fractional intermediate values?"
python -m ta2.cli rag-audit "Who founded Neptune Motors?"
python -m ta2.cli guard-audit
python -m streamlit run app_ta2.py
```

The ingestion command now discovers all Markdown documents under `ta2/corpus/`. Check that `collection_chunks` is at least 8. The `rag-audit` output contains separate `k1` and `k3` retrieval evidence; the unknown-question example must say `I don't know` with no citations.

The previously accepted Windows test log had 8 TA1 and 36 TA2 tests. New tests were added to this jury branch; do not claim they passed until you rerun them. The new code is not a saved Qwen evaluation.

## 3. UI demonstration order

1. Open the Streamlit local URL and set `Local Qwen + RAG`, `hybrid`, `MAX_HOPS=12`, thread `jury-example-01`.
2. Enter cards 3, 3, 8, 8 and click `Solve with TA2`. Record `status`, `candidate_origin`, `verification`, `hops` and agent events. A mathematically equivalent expression is acceptable.
3. Expand `U3 — Grounded RAG`. Ask the fractional-intermediate question at k=1 and k=3. Inspect source paths, distances and citations. Then ask `Who founded Neptune Motors?` and show abstention.
4. Expand `U3 — Checkpointed follow-up versus memory disabled`. Ask `What was my previous expression?` against the same thread. Show an answer with memory and `I don't know` without it.
5. Expand `U4 — Mathematical guardrail`. Show one approved and one rejected expression for the same card set.
6. For edge cases, switch to a fresh thread and enter 1, 1, 1, 1. Under hybrid policy, complete exact search may establish `no_solution`. A hop limit or search budget exhaustion is *not* proof.
7. Contrast with `app.py`, the frozen TA1 Streamlit app, using separate browser sessions only if faculty asks.

## 4. Repeatable five-case evidence

```bat
python run_ta2_acceptance.py --output-dir results/ta2-jury-final-20261123
```

Choose a new directory name for every run: the runner deliberately refuses to overwrite evidence. It runs both test suites, cross-process resume, SQLite memory isolation, genuine nomic embeddings, source-bearing retrieval, k1/k3 QA, and 20 local-model comparisons over the same five inputs. Inspect `acceptance.json` and `evaluation.summary.md`; check *actual* `complete`, test counts and statuses rather than assuming success.

The stored **older branch** acceptance evidence (seed 42) recorded: TA1 Linear 0/4, TA1 ToT 2/4, TA2 model-only 1/4 and TA2 hybrid 4/4 solvable cases. Hybrid also proved the unsolvable input. This is prior evidence, not a new run. The hybrid solver receives exact search assistance, which is disclosed in the CSV. One seed is not statistically conclusive.

The five benchmark inputs are 4,7,8,8; 1,5,5,5; 3,3,8,8; 1,2,3,4; and 1,1,1,1. No worked answers to these benchmark cases appear in the retrieval corpus.

## 5. Evidence map for the eight faculty components

| SOP item | Implementation | Demonstration / evidence |
|---|---|---|
| U3-1 Short-term memory | `ta2/workflow.py` SQLite checkpointer, `ta2/followup.py` | Same thread contextual question vs memory-disabled answer, process-restart trace |
| U3-2 Long-term memory | `ta2/storage.py` | SQLite Store and isolated namespace after restart |
| U3-3 RAG | `ta2/rag.py`, `ta2/qa.py`, `ta2/corpus/*.md` | At least 8 chunks, real nomic embed, k=1/k=3 with sources, refusal |
| U3-4 Tools and failures | `ta2/tools.py`, tests | Injected timeout/schema/Store failure tests and bounded retries |
| U4-1 Distinct roles | `ta2/workflow.py` and `docs/TA2_ROLE_CONTRACTS.md` | Five-field role table and recorded role trace |
| U4-2 Bounded coordination | `ta2/workflow.py` supervisor | Hop counts, interruptions, preserved resume budget |
| U4-3 Oversight / guardrail | `ta2/tools.py` + CLI/UI guard audit | Mathematically approved and rejected paths |
| U4-4 / EV Evaluation | `run_ta2_evaluation.py`, `run_ta2_acceptance.py` | Same five cases, metrics, TA1 vs TA2 table and explicit oracle flags |

## 6. Assemble submission after writing your own report

```bat
python package_ta2_submission.py --name GroupNN_Division_Game24_TA2
```

Replace `GroupNN` and `Division` with the exact official roster values before running. The script makes `submissions/<name>/ta1`, `ta2`, `traces`, and a ZIP archive, preserving recorded evidence. It copies an existing root-level `report.pdf` if present; otherwise it writes `REPORT_REQUIRED.txt` and explicitly marks the package incomplete.

Faculty requires your own report.pdf of at most four pages with architecture, five-field role table, SOP component evidence, the five-case TA1-vs-TA2 comparison, measured limitations, and the *actual* team contribution table. Do not fabricate measurements or contributions. Disclose any AI-assisted debugging or scaffolding as the academic-integrity section requires.
