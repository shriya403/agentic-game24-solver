# Five minutes at the jury desk

**Presenter** Shriya Jitendra Shinde, MIT ADT University, Pune. Extract the submission and run `run_final.bat` from the project root. Allow time for first-time dependency installation before the examination. Present the dashboard at 100% browser zoom. The names below refer to sections of the final dashboard.

| Time | Action | What the examiner can check |
|---|---|---|
| 0:00–0:35 | Open **Mission Control**. Introduce four cards, four legal operators, and the requirement to use each card exactly once. Point to the model service status. | Distinguish the available execution modes. The archived Windows results and the current session have different provenance. |
| 0:35–1:25 | Open **Jury Mode** and click **Run fractional demonstration** on **3, 3, 8, 8**. Say aloud that this is a live, explicitly selected deterministic run. | Read the certificate aloud. For `8 / (3 - 8 / 3)`, the denominator is exactly one third. The four leaves match the four cards. |
| 1:25–2:15 | Open **Reasoning Tree**. Select an intermediate operation, identify the resulting values, then inspect a rejected alternative. Open **Agent Operations** to follow the corresponding execution events. | Point to an actual event and state who produced it. Report a model call only if the run records one. |
| 2:15–3:00 | Open **Memory + RAG**, then **Last run**. Expand **Checkpointed conversation** and compare the previous-expression answer with history enabled and disabled. | Show that the checkpoint remembers the expression. The demonstration ran with retrieval off. The saved real-model trace below includes retrieved passages. |
| 3:00–3:55 | Open **Safety Center**, then **Fault demonstrations** and **Run all checks**. Expand **Correct value, incorrect cards**. Compare it with **Exhaustive unsolvability check**. | A wrong expression fails for a concrete reason. Exhausting all legal states can establish impossibility. Hitting a hop limit leaves the puzzle unresolved. |
| 3:55–5:00 | Open **Evaluation Lab** and select the archived Qwen study. Read the four solvable-case counts. Return to the solver or Jury Mode and export the current evidence. | TA1 linear 0/4, TA1 ToT 2/4, TA2 model 1/4, TA2 hybrid 4/4. Explain the exact-search assistance and one-seed limitation. The export belongs to this session's run. |

## A real model trace for discussion

In the archived `results/ta2-acceptance-ad0424cd/memory-and-rag.json`, inspect `first.events`. For the hard case, the proposer emitted `((3 + 3/8) * 8)`. The verifier found 27. Hybrid search then visited 345 states and returned `8 / (3 - 8 / 3)`. The second verification passed at hop 7. This sequence includes both model-generated proposals and a tool-generated answer. The archive is a recorded Windows run. [Trace](../results/ta2-acceptance-ad0424cd/memory-and-rag.json)

## Optional live Qwen segment

When the local Ollama service has both models and the Chroma corpus is ready, use **Live Solver** with **Local Qwen**. Use a fresh thread when changing execution mode. Show the reported outcome even when the model proposes an invalid expression. For a retrieval experiment, run the same puzzle under the same model settings with retrieval disabled, k=1 and k=3, using fresh threads and isolated memory. Compare sources, candidate origin and verified result. A single pair of runs supports a case observation.

For a saved, service-independent replay, choose **Jury Mode** and **Load saved replay**. Read the provenance shown beside the result. If a model or database is unavailable, show the actual error, use the archived model evidence for the model segment, and return to the live deterministic demonstration for the arithmetic. [Saved study](../results/ta2-acceptance-ad0424cd/evaluation.summary.md)
