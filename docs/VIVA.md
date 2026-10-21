# Jury Viva — High-Scoring Answers

## Is this really Agentic AI, or only prompting?

The LLM is one component. The system maintains state, generates candidate actions, invokes deterministic arithmetic, evaluates intermediate states, prunes alternatives, adapts the next action, and validates the goal. That creates a perception–reasoning–action–feedback loop rather than one prompt and one response.

## What makes the agent autonomous?

**Plan, act, evaluate, adapt.** It receives a goal, chooses candidate arithmetic actions, observes tool results, discards weak states, and selects subsequent actions from the updated state.

## Agent versus workflow?

The graph provides predictable control and safety. The agent supplies dynamic decisions inside that graph, such as which branch is promising. A workflow has predefined transitions; agentic behavior chooses actions from the current state.

## Why Tree-of-Thought rather than linear reasoning?

Linear reasoning commits to one route. If an early choice is wrong, later steps inherit that error. ToT preserves alternatives, evaluates them, and can prune or backtrack, treating reasoning as search.

## Why does ToT not always win?

It spends more inference on branch generation and evaluation. Easy tasks may gain no accuracy but still incur more latency and tokens.

## What is the practical cost of ToT?

Extra candidate generation, evaluator calls, retained state, nodes, output tokens, and latency. The benchmark measures each cost rather than discussing it only theoretically.

## Which puzzle should show the clearest difference?

`[3,3,8,8]`, because `8/(3-8/3)=24` requires a non-obvious fractional intermediate. State the observed result from the actual CSV; do not claim a CoT failure if it did not occur.

## What happens if Qwen hallucinates a solution?

The LLM is never the judge. The AST validator permits only integers and the four arithmetic operators, checks the exact multiset of inputs, evaluates with rational arithmetic, and accepts only exact value 24.

## Why exact Fraction arithmetic?

Floating-point values can produce rounding ambiguity. Fractions preserve values such as `1/3` exactly, which is essential for the hard puzzle.

## Why Qwen2.5:3b?

It is compact enough for local inference through Ollama and adequate for a classroom arithmetic-search experiment. Local execution avoids cloud credentials and supports repeatable fixed-seed runs.

## Why LangGraph?

ToT contains a natural loop: generate, evaluate, prune, expand, and stop. LangGraph makes this state and conditional control visible, testable, and bounded.

## Why no vector database?

There is no document retrieval or long-term semantic memory. Adding a vector database would not solve a requirement and would introduce unnecessary complexity.

## CoT safety/accuracy terminology

The project records a concise visible arithmetic trace. It does not claim to access or expose a model's private hidden chain-of-thought.

## Main limitation

The experiment has only three puzzle families. Its result demonstrates the mechanism and cost tradeoff, not universal superiority of ToT.

## Best future improvement

Use adaptive routing: try the cheaper linear strategy, validate it, and invoke ToT only when it fails or a difficulty estimator predicts deceptive search.

