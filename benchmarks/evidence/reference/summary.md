# Reference evaluation

Rechecked 15 rows with the independent proof auditor. Seeds 42. Python 3.12.14.

| System | Retrieval k | Solvable proofs | Unsolvability proofs | Tool failures | Mean seconds on solvable trials | Generation calls (all cases) |
|---|---:|---:|---:|---:|---:|---:|
| TA1_Linear | 0 | 1/4 | 0/1 | 0 | 0.002 | 0 |
| TA1_ToT | 0 | 4/4 | 0/1 | 0 | 0.007 | 0 |
| TA2_Exact | 0 | 4/4 | 1/1 | 0 | 0.029 | 0 |

TA1 ToT uses exact look-ahead during candidate selection and scoring. TA2_Exact uses an exhaustive arithmetic oracle. TA2_Model supplies exact validation feedback to its evaluator. TA2_Hybrid can invoke a bounded exact search tool. Per-row assistance and failure details appear in metrics.csv.

See docs/EVALUATION.md for the corpus, timing window and comparison limits.
