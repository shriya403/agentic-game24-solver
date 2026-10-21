# Experimental Report — Agentic Game of 24 Solver

## 1. Problem statement

The Game of 24 supplies four integers. Each must be used exactly once with `+`, `-`, `×`, `÷`, and parentheses to produce exactly 24. Small language models can make an attractive early arithmetic choice that prevents a valid solution later.

**Research question:** Does explicit Tree-of-Thought search improve solution reliability on non-obvious puzzles compared with a single sequential reasoning attempt, and what extra computational cost does it impose?

## 2. Hypothesis

Tree-of-Thought should help most when the successful route depends on a non-obvious fractional intermediate. It should provide little accuracy benefit on easy cases while still increasing nodes, tokens, and latency.

## 3. Inputs

| Difficulty | Numbers | Verified ground truth |
|---|---|---|
| Easy | 4, 7, 8, 8 | `(7 - 8/8) × 4 = 24` |
| Medium | 1, 5, 5, 5 | `(5 - 1/5) × 5 = 24` |
| Hard | 3, 3, 8, 8 | `8 ÷ (3 - 8/3) = 24` |

## 4. Agentic AI methodology

The orchestrator validates the input and routes it to one of two strategies. The linear agent requests one concise arithmetic trajectory. The ToT agent generates candidate moves, stores the resulting states, invokes an evaluator, prunes weak candidates, expands the best states, and repeats until a terminal state. A deterministic tool validates the proposed expression independently.

The system is agentic because it performs **plan → act → evaluate → adapt** with persistent state and tool feedback. LangGraph supplies the controlled workflow; Qwen supplies dynamic scoring when available; Python supplies safe arithmetic execution and validation.

## 5. Tools and technologies

| Tool | Role |
|---|---|
| Python | Core state, search, metrics, and tests |
| Qwen2.5:3b | Linear generation and branch evaluation |
| Ollama | Local model serving |
| LangGraph | Stateful conditional orchestration |
| Streamlit | Interactive prototype |
| Pandas / Matplotlib | Result summaries and charts |
| Exact AST validator | Rejects hallucinated or invalid expressions |

A vector database is not used because the task has no retrieval or semantic-memory requirement.

## 6. Controlled protocol

- identical model and machine for both methods;
- temperature 0;
- fixed seeds beginning at 42;
- fresh request context;
- the same three puzzles and arithmetic rules;
- independent validation;
- success, validity, steps, nodes, latency, prompt tokens, and output tokens recorded.

Run `python run_experiment.py --runs 5` to create 30 measurements. Paste or export the resulting summary table below before submission.

## 7. Result table

| Puzzle | Method | Success | Valid | Steps | Nodes | Time (s) | Output tokens | Expression |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 4,7,8,8 | Linear | Run locally | — | — | — | — | — | — |
| 4,7,8,8 | ToT | Run locally | — | — | — | — | — | — |
| 1,5,5,5 | Linear | Run locally | — | — | — | — | — | — |
| 1,5,5,5 | ToT | Run locally | — | — | — | — | — | — |
| 3,3,8,8 | Linear | Run locally | — | — | — | — | — | — |
| 3,3,8,8 | ToT | Run locally | — | — | — | — | — | — |

## 8. Interpretation template

If linear reasoning fails on `[3,3,8,8]` while ToT succeeds, explain that the successful path preserves `8/3`, then creates `1/3`, then divides 8 by that fraction. ToT helped by retaining and evaluating alternatives—not by knowing different arithmetic.

If both methods succeed, report that no accuracy advantage was demonstrated in this sample. The evidence still shows that ToT makes branch search explicit and auditable, at the measured token and latency cost.

## 9. Limitations

- Three puzzles are a teaching experiment, not a general reasoning benchmark.
- Five seeds improve reliability but remain a small sample.
- The evaluator can mis-rank a valid branch.
- The deterministic oracle fallback is useful for demonstration but is not an LLM result.
- Visible arithmetic traces are not the model's private hidden chain-of-thought.

## 10. Conclusion

Tree-of-Thought trades computation for search coverage. It is justified when early choices are deceptive or failure is costly; it is inefficient for trivial cases. The appropriate deployment pattern is therefore adaptive: begin with a low-cost linear attempt, verify it, and invoke ToT only if validation fails or estimated difficulty is high.

