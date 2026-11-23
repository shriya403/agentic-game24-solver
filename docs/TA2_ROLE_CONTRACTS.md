# TA2 role contracts and boundary review (jury evidence, not the student report)

The five fields below match the faculty's Unit 4 role-design requirement. The names correspond to observable nodes or tools in `ta2/workflow.py`.

| Agent or role | Goal | Tools | Inputs → outputs | Limits and trust boundary |
|---|---|---|---|---|
| Supervisor | Dispatch a complete, bounded verification cycle | LangGraph state, conditional routing, persisted checkpoint | Current state, phase, hop budget → next node or termination status | `MAX_HOPS=12` default; preserves budget after restart; cannot mark a solution verified without the verifier |
| Retriever / memory reader | Supply relevant rules and previously verified results | LangChain-Chroma vector store, local nomic embeddings, SQLite Store | Current puzzle, namespace → cited evidence and exact prior verified memory | Must use local documents; empty/missing index fails explicitly; namespaces are not authentication |
| Proposer | Generate up to three complete expression candidates | Qwen2.5:3b locally via Ollama | Cards, evidence, feedback, state → 1–3 bounded candidate expressions | Cannot self-certify; no code execution; invalid generated structure causes a tool failure |
| Evaluator | Rank only candidates already proposed and assess validity feedback | Qwen2.5:3b, exact `verify()` tool | Candidate list and exact assessments → selected candidate, evaluation event | Can be overruled when it misranks a mathematically valid candidate; cannot invent new candidates |
| Mathematical Verifier | Decide whether the submitted answer is correct | Safe AST validator and exact `Fraction` arithmetic | Selected expression and four original cards → verified/invalid with reason | Rejects extra/repeated cards, unsupported syntax, division by zero and wrong value |
| Exact search specialist | Provide a bounded deterministic repair after model rejection | Exhaustive legal-move search | Cards and persisted search budget → verified candidate or inconclusive/proven no-solution result | Used only under hybrid policy; tool-generated answers are attributed; search-budget exhaustion is not impossibility proof |
| Safety and failure gate (cross-cutting) | Stop unsafe outputs or broken tool calls | Input checks, expression guardrail, `ToolFailure`, retries and supervisor | Untrusted text/tool errors → rejection, retry or explicit terminal error | Retrieved content never overrides instructions; transport failures never masquerade as model success |

## Coordinator path

Normal: `retrieve → proposer → evaluator → verifier → finish`.

Hybrid repair after invalid candidate: `retrieve → proposer → evaluator → verifier → exact search → evaluator → verifier → finish`.

The model's evaluation score is not proof. Only exact verification grants `verified`; exhausted budgets and complete no-solution proofs are distinct statuses.

## Two oversight paths to demonstrate

Run `python -m ta2.cli guard-audit`. On cards `[2,2,6,6]`, the independent verifier approves `2*6+2*6` and rejects `2+2+6+6`. This is a verifier guardrail demo; it is not a human sign-off.

For failure routing, inspect the existing tests `test_hybrid_never_hides_generation_failure`, `test_transient_retry` and `test_store_read_failure_is_explicit`. Their fixtures are deliberately injected failures and must not be described as observed production incidents.

## Academic integrity and credits

These are engineering documentation notes, not the four-page submitted report. The group must write its own report, contribution table and oral explanation, cite its own run evidence, and disclose the use of AI-assisted debugging or scaffolding as required by the faculty.
