# Individual viva guide

**Shriya Jitendra Shinde · Agentic AI · MIT ADT University, Pune**

Practice each answer in your own words. Keep a verified expression, a rejected expression, and a timed-out or budget-limited run available as three distinct examples.

### Why use the Game of 24?

An expression can sound plausible and still fail. Four cards give us an exact, independently checkable outcome and a small enough search space to study branching. That makes this puzzle a controlled setting for comparing ways to generate candidates.

### What do CoT and ToT mean in this project?

The TA1 linear model produces a single answer attempt. TA1 ToT explores legal arithmetic states with a bounded beam. It scores alternatives, keeps a subset, and logs decisions. The examiner can inspect generated operations and verifier outputs. Internal model thought is outside the evidence. [TA1 agents](../game24/agents.py)

### Which decisions actually involve AI?

In TA2 model mode, separate proposer and evaluator calls use the same local Qwen model with different role instructions. The proposer emits up to three expressions. The evaluator ranks them alongside exact tool assessments. LangGraph routes work, the verifier checks arithmetic, and hybrid search can repair a failed round. These latter components are deterministic. [Role contracts](TA2_ROLE_CONTRACTS.md)

### Why can a mathematically exact system benefit from an LLM?

Exact search already solves the four-card domain. The model makes it possible to study candidate generation and ranking with imperfect proposals. Comparing a model-generated expression to a tool-generated repair shows where each contributes.

### Why represent intermediate values as fractions?

For 3, 3, 8, 8, take `8 / 3`, then `3 - 8/3 = 1/3`, then `8 / (1/3) = 24`. Recording exact numerators and denominators lets each equality be checked directly. An integer-only policy would discard the first move.

### What earns a solution a certificate?

The checker parses a restricted arithmetic expression, checks operators, evaluates each operation exactly, and compares the multiset of integer leaves against the four input cards. The expression must equal 24. For example, with 1, 2, 3, 4, the expression `24` hits the target value and fails card usage. [TA1 checker](../game24/validator.py)

### Can the supervisor overrule the model?

In the historical TA2 evaluator node, exact checks identify verified candidates among the proposed options. If Qwen selects an invalid one while a valid one exists, the node substitutes the valid index and records the override. The verifier still runs. The supervisor routes the next step and counts dispatches. [TA2 workflow](../ta2/workflow.py)

### What do MAX_HOPS and the search budget each limit?

The TA2 supervisor bounds workflow dispatches and reserves enough hops to verify a new candidate. The exact search separately bounds distinct value states explored. A complete exhaustive failure proves no solution under these rules. Reaching either budget before completion gives an inconclusive result. [Search](../ta2/search.py)

### When is it safe to merge two arithmetic branches?

For the goal of reaching 24, branches with the same multiset of remaining exact values have the same possible arithmetic continuations. Keep an expression witness with each term so that card usage remains auditable. This preserves reachability but can discard distinct proofs. It would be unsuitable if the goal were to enumerate every expression.

### How are thread memory and long-term memory different?

A LangGraph checkpoint restores execution state for one thread, including the remaining budget and recent history. SQLite Store keeps reusable records such as verified puzzle results under a namespace. A fresh thread can demonstrate persistence independently of a browser refresh. A namespace is an organizational key. [Historical persistence evidence](../results/ta2-acceptance-ad0424cd/restart.log)

### Why compare retrieval at k=1 and k=3?

One passage gives the model less context to process. Three may supply a missing rule or add distracting material. Compare actual passages, distances, citations, token counts and the verified outcome under matched settings. Semantic proximity alone gives no causal evidence that a passage helped. [Chroma retriever](../ta2/rag.py)

### How do you handle an instruction inside a retrieved passage?

Treat the passage as untrusted reference data. Verification remains independent of retrieved text. A controlled test can show that a particular invalid candidate is rejected. That demonstration covers the tested behavior and does not establish robustness to every possible prompt injection.

### What do the measured results establish?

The archived single-seed Windows study tested five identical puzzles including one unsolvable case. Across the four solvable puzzles, TA1 linear verified 0, TA1 ToT verified 2, TA2 model verified 1, and TA2 hybrid verified 4. TA1 ToT used look-ahead, and the hybrid mode used exact-search assistance. These figures describe system outcomes under the recorded settings. [Per-case data](../results/ta2-acceptance-ad0424cd/evaluation.csv)

### How do you avoid overstating efficiency?

Quote elapsed seconds, tokens, calls, states and branches with their units. These measure different types of work. A workflow hop is a routed step and may contain several tool calls. A zero model-token count on a deterministic run says nothing about Qwen's token efficiency. The archived latency excludes setup. [Study manifest](../results/ta2-acceptance-ad0424cd/evaluation.manifest.json)

### What would make the next experiment stronger?

Pre-register a larger held-out puzzle set and a difficulty criterion. Repeat multiple seeds, randomize run order, define comparable budgets and log model digests and hardware. Use isolated memory/index directories. Cross RAG depth with search policy, analyze solved and unsolvable cases separately, and quantify uncertainty.

### Where could this design transfer?

A spreadsheet assistant could suggest a formula while a separate checker tests allowed references and recomputes outputs. The pattern requires a domain-specific checker and a definition of success. Accuracy measurements on Game24 cannot predict spreadsheet accuracy.

### How should I describe individual contributions?

Identify the part you can explain and demonstrate personally. Bring a source diff, a failing example, and the corresponding test. Distinguish your work, collaborator contributions and AI-assisted scaffolding in line with your course requirements. The repository alone does not establish authorship of individual features.
