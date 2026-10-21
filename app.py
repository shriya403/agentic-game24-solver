from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from game24.engine import exhaustive_solve
from game24.experiment import PUZZLES, run_benchmark
from game24.ollama_client import OllamaClient
from game24.workflow import Game24Workflow

st.set_page_config(page_title="Agentic Game of 24", page_icon="🧠", layout="wide")

st.title("Agentic Game of 24 Solver")
st.caption("A controlled comparison of one-path reasoning and Tree-of-Thought search")

with st.sidebar:
    st.header("Experiment controls")
    mode = st.radio("Execution mode", ["Ollama — Qwen2.5:3b", "Deterministic fallback"])
    model = st.text_input("Ollama model", "qwen2.5:3b")
    seed = st.number_input("Seed", 0, 99999, 42)
    st.info("Fallback mode is a working algorithmic demo. It is never labelled as a Qwen measurement.")

client = OllamaClient(model=model) if mode.startswith("Ollama") else None
ollama_ready = bool(client and client.available())
if mode.startswith("Ollama") and not ollama_ready:
    st.warning("Ollama is not reachable. Start `ollama serve` and pull `qwen2.5:3b`, or choose deterministic fallback.")

tab_solve, tab_benchmark, tab_about = st.tabs(["Live solver", "Benchmark", "Methodology"])

with tab_solve:
    presets = {"Easy — 4,7,8,8": (4, 7, 8, 8), "Medium — 1,5,5,5": (1, 5, 5, 5), "Hard — 3,3,8,8": (3, 3, 8, 8)}
    preset = st.selectbox("Puzzle", list(presets))
    cols = st.columns(4)
    values = tuple(int(cols[i].number_input(f"Number {i+1}", value=presets[preset][i], step=1)) for i in range(4))
    method = st.radio("Reasoning strategy", ["Linear", "ToT"], horizontal=True)
    if st.button("Solve and verify", type="primary", use_container_width=True):
        workflow = Game24Workflow(client if ollama_ready else None)
        result = workflow.run(values, method, int(seed))
        st.session_state["last_result"] = result
    result = st.session_state.get("last_result")
    if result:
        a, b, c, d = st.columns(4)
        a.metric("Verified", "YES" if result.valid else "NO")
        b.metric("Steps", result.steps)
        c.metric("Nodes explored", result.nodes_explored)
        d.metric("Latency", f"{result.wall_time_sec:.3f}s")
        st.subheader("Final expression")
        st.code(result.expression or "No valid expression", language="text")
        st.caption(f"Mode: {result.mode} · Model: {result.model} · Validator: {result.validator_message}")
        if result.trace:
            st.subheader("Concise arithmetic trace")
            for index, step in enumerate(result.trace, 1):
                st.write(f"{index}. {step}")
        if result.branches:
            st.subheader("Branch evaluation and pruning")
            branch_df = pd.DataFrame([{
                "Depth": x.depth, "Move": x.move, "State": ", ".join(x.state),
                "Evaluation": x.evaluation, "Score": x.score, "Reason": x.reason,
            } for x in result.branches])
            st.dataframe(branch_df, use_container_width=True, hide_index=True)
        if result.raw_response:
            with st.expander("Raw Qwen response"):
                st.text(result.raw_response)

with tab_benchmark:
    st.write("Runs the three fixed puzzles with both methods under identical settings.")
    runs = st.slider("Seeds per condition", 1, 5, 1)
    if st.button("Run six-condition benchmark", use_container_width=True):
        rows = run_benchmark(range(42, 42 + runs), use_ollama=ollama_ready, model=model)
        st.session_state["benchmark"] = pd.DataFrame(rows)
    df = st.session_state.get("benchmark")
    if df is not None:
        st.dataframe(df[["puzzle", "method", "success", "valid", "steps", "nodes_explored", "wall_time_sec", "output_tokens", "mode", "expression"]], use_container_width=True, hide_index=True)
        summary = df.groupby("method", as_index=False).agg(
            success_rate=("success", "mean"), average_steps=("steps", "mean"),
            average_latency=("wall_time_sec", "mean"), average_output_tokens=("output_tokens", "mean"),
            average_nodes=("nodes_explored", "mean"),
        )
        summary["success_rate"] *= 100
        st.subheader("Summary")
        st.dataframe(summary, use_container_width=True, hide_index=True)
        st.bar_chart(summary.set_index("method")[["success_rate"]])
        st.bar_chart(summary.set_index("method")[["average_latency", "average_output_tokens"]])
        data = df.to_csv(index=False).encode()
        st.download_button("Download results.csv", data, "results.csv", "text/csv", use_container_width=True)

with tab_about:
    st.subheader("Why this is agentic")
    st.write("The system follows a goal-directed loop: create candidate actions, execute exact arithmetic, evaluate states, prune weak branches, adapt the next action, and independently verify the outcome.")
    st.subheader("Independent ground truth")
    for puzzle in PUZZLES:
        expression, trace, nodes = exhaustive_solve(puzzle)
        st.code(f"{list(puzzle)} → {expression} = 24  (ground-truth nodes: {nodes})", language="text")
    st.subheader("Scientific boundary")
    st.write("Visible arithmetic traces are recorded; the project does not claim access to a model's private hidden chain-of-thought. Deterministic fallback results and Ollama results are kept separate.")

