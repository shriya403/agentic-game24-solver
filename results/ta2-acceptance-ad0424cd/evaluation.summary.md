# Five-case TA1 versus TA2 evaluation

Local model execution; exact-tool assistance is disclosed per row.

| System | Verified solvable | Proven unsolvable | Mean solvable time | Tool failures | Assisted rows |
|---|---:|---:|---:|---:|---:|
| TA1_Linear | 0/4 | 0 | 0.807s | 0 | 0 |
| TA1_ToT | 2/4 | 0 | 7.544s | 0 | 5 |
| TA2_Hybrid | 4/4 | 1 | 2.852s | 0 | 5 |
| TA2_Model | 1/4 | 0 | 4.675s | 0 | 0 |

Budget exhaustion and failure to find a solution are not unsolvability proofs.
TA1 ToT has exact look-ahead assistance. TA2 hybrid uses explicit bounded exact search after model rejection.
Tool-assisted success is system capability, not proof of improved Qwen reasoning.
The shipped retrieval corpus contains no worked evaluation answers. Each case uses fresh execution/Store memory.
Search budgets differ. One seed is descriptive evidence, not a statistically reliable superiority claim.
