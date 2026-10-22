# TA2 Windows acceptance results

The group ran `python run_ta2_acceptance.py` on Windows with local Ollama,
Qwen2.5:3b and nomic-embed-text. The terminal output supplied in the project
conversation confirms completion of all eight listed capability checks.

## Test results

- Frozen TA1: 8 tests passed.
- TA2 extension: 36 tests passed.
- Persistence, Store, new-process resume and RAG demonstration completed.
- Five-case evaluation: 20 solver executions completed.

## Observed evaluation

One seed (42), four solvable puzzles and one unsolvable puzzle:

| System | Verified solvable puzzles | Unsolvable case outcome |
|---|---:|---|
| TA1 Linear | 0/4 | No valid answer; no proof |
| TA1 ToT | 2/4 | No valid answer; no proof |
| TA2 Model | 1/4 | Hop budget exhausted; no proof |
| TA2 Hybrid | 4/4 | Complete exact search proved no solution |

TA1 ToT solved the easy and control cases. TA2 Model solved the fractional case.
TA2 Hybrid solved all four solvable cases. The model-only unsuccessful cases
terminated at the hop budget without accepting invalid answers. No tool failures
were reported in these 20 progress entries.

TA2 Hybrid is explicitly model-plus-tools: exact search can supply an expression
after a rejected model proposal. TA1 ToT also uses exact look-ahead. These results
therefore do not establish improved Qwen-only reasoning or matched compute.
One seed is descriptive evidence, not statistical proof of superiority.

## Evidence location and scope

The runner reported this directory on the group's Windows machine:

```text
results/ta2-acceptance-ad0424cd/
```

It contains the acceptance report, evaluation CSV, raw traces, settings manifest,
test logs and memory/RAG demonstration artifacts. This summary is based on the
supplied terminal output; the original Windows artifacts were not available to
the cloud checkout when this summary was written and are not included by this
commit. Keep original measurements unchanged when uploading them separately.

The eight requirements are mapped in [TA2.md](TA2.md). The instructor's exact SOP
was not supplied, so additional SOP-specific requirements remain outside this
validation claim. Frozen TA1 source, tests and recorded baseline are unchanged.
