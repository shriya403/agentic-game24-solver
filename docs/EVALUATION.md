# Five-puzzle evaluation

Four card sets have solutions. The fifth, 1 · 1 · 1 · 1, is an unsolvable control. Count verified solutions among the four solvable cases. Count a proof of impossibility separately. Record a timeout, budget stop, malformed model output or rejected guess as its own outcome.

## Recovered Qwen study

The original Windows run used Qwen2.5:3b at temperature 0, seed 42, Python 3.12.10, LangGraph 1.2.16, Chroma 1.5.9 and nomic-embed-text. Each TA2 case had a fresh thread and Store. The rules-only retrieval corpus contained no worked benchmark answers. In November 2026 we re-audited the expression and card multiset in each of the 20 recovered CSV rows with the final-jury proof auditor. All 20 recorded validity flags agreed.

| Original Windows configuration | Verified solvable | Solved cases | Impossibility proofs | Mean wall seconds on the four solvables |
|---|---:|---|---:|---:|
| TA1 linear model | 0/4 | None | 0/1 | 0.807 |
| TA1 ToT model with exact look-ahead | 2/4 | Easy, control | 0/1 | 7.544 |
| TA2 model with mathematical checks | 1/4 | Fractional | 0/1 | 4.675 |
| TA2 hybrid with bounded exact search | 4/4 | All four | 1/1 | 2.852 |

The original CSV, summary, complete trace and manifest are in [the recovered acceptance directory](../results/ta2-acceptance-ad0424cd/). TA1 ToT preselects three first moves using exact feasibility, applies deterministic scores when model scores are absent, and retains two branches. TA2 model generates up to three whole expressions per proposal. A separate deterministic check can override an evaluator ranking. Hybrid can route to a bounded exact search after a rejection. These differences affect both computation and success rates.

## Local reference execution

The new Linux reference run uses seed 42 and no model or retrieval calls. All 15 rows ran to completion. The linear greedy path solved the control puzzle alone (1/4). TA1's deterministically scored tree solved all four solvable cases (4/4). TA2's explicit exhaustive oracle solved all four (4/4) and established impossibility for four ones. TA2's reference graph uses SQLite and LangGraph, so its recorded process time and persisted database size include that work. This run measures arithmetic and routing behavior. See the [measured rows](../benchmarks/evidence/reference/metrics.csv) and [branch and verifier traces](../benchmarks/evidence/reference/traces.json).

## Current model comparison and retrieval ablation

Run the following from the project root after installing its Python dependencies. Supply a fresh output directory for each experiment. The runner preserves existing artifacts and records each completed trial.

```powershell
python -m benchmarks.run --mode reference --output data/experiments/reference-01
python -m benchmarks.run --mode ollama --rag-k 0 1 3 --output data/experiments/qwen-01
```

The second command evaluates 25 trials. For each of the five card sets it executes linear Qwen generation, Qwen-ranked TA1 ToT, and three TA2 runs with identical seeds and budgets. The three arms supply zero documents, one nearest chunk or three nearest chunks. For an additional hybrid arm use `--policies model hybrid`. For repeated trials use `--seeds 42 43 44`. The current ablation ingests both general-purpose Markdown documents in `ta2/corpus/` so k=3 can return three distinct chunks. Unlike the final dashboard's worked-example memory demo, the evaluation corpus contains no worked benchmark answer and the Store is fresh for every case/arm. Model tags are qwen2.5:3b and nomic-embed-text. Corpus and runner hashes are in the manifest.

Each arm runs once per seed in fixed order, sharing a model server. Machine load, caching, run order, concurrent smoke tests and model warm-up can affect timing. One seed on five fixed puzzles supports a case comparison. It cannot establish a general speedup, model improvement, or causal retrieval advantage. Read each recorded retrieval as evidence provided to the proposer. Claims that a chunk caused a choice require stronger evidence.

## Reading the measurements

- **Correctness** comes from the independent restricted-AST auditor using exact fractions. `verified` describes the expression. `status` describes the workflow. The archived and fresh audits are asserted by the evidence tests. Missing answers receive no validity credit.
- **Cost** includes wall seconds and Python process CPU seconds for workflow execution; model inference runs in a different process. Graph construction, corpus ingestion, the ground-truth calculation, CSV writes and independent post-run audits are outside the timing window. Elapsed times can include service and queue delays. The original Windows script wraps TA2 graph initialization and cleanup in its timer, despite its manifest's broader setup-exclusion note. Wall times across these experiments use different instrumentation.
- **TA1** reports its native step count, expanded candidates, and beam-pruning count. These exclude hidden recursive exact-look-ahead work; the pruning counter also excludes candidates discarded before first-stage scoring. Frozen TA1 reports a depth count on unsuccessful tree runs.
- **TA2** exposes supervisor hops and the number of visited exact-search nodes when its hybrid tool ran. Native TA2 discards the offline oracle's internal node count. Blank step, node and pruning entries indicate missing or inapplicable counters. The final-jury replay exposes additional tree instrumentation for its own deterministic implementation.
- **Requests** count logical generation and embedding operations during the trial. Retry attempts, readiness checks, and corpus initialization have separate meanings. Ollama response counters supply prompt/output tokens. A blank field indicates unavailable data. Positive-k runs record retrieved chunk IDs, source, text and distance.
- **Storage** measures final file bytes in the individual closed TA2 working directory, excluding the shared index and model files. It is not a peak-memory metric. Historical CSVs retain their original fields.
- **Trace** row numbers are zero-based data-row indexes in the corresponding CSV. The new traces expose arithmetic candidates, scores, sources, verification and routing. The runner flushes each CSV row and atomically replaces its trace document; only a completed manifest denotes a completed comparison.

To reproduce the saved exact trace for 3 · 3 · 8 · 8 with a verified three-operation explanation, use a new filename.

```powershell
python -m benchmarks.trace --output data/experiments/fractional-trace-01.json
```

To recheck every row and print its summary after completion, run `python -m benchmarks.report data/experiments/qwen-01`. It checks the mapping from trace to measurement and recalculates each expression with the independent proof auditor. The reference run's [generated summary](../benchmarks/evidence/reference/summary.md) accompanies its raw observations.
