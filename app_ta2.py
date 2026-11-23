"""Separate TA2 UI; the frozen app.py remains untouched."""
import os
from pathlib import Path
import uuid
import sqlite3
import streamlit as st
from ta2.tools import LocalOllama, ToolFailure
from ta2.rag import ChromaRAG
from ta2.workflow import TA2Workflow

st.set_page_config(page_title="Game of 24 — TA2", layout="wide")
st.title("Game of 24 — TA2")
mode = st.sidebar.radio("Execution mode", ["Local Qwen + RAG", "Deterministic oracle demo"])
data_dir = st.sidebar.text_input("Persistent data directory", os.environ.get("TA2_DATA_DIR", str(Path.home() / ".game24-ta2")))
if "ta2_thread" not in st.session_state:
    st.session_state.ta2_thread = uuid.uuid4().hex
thread = st.sidebar.text_input("Thread ID", key="ta2_thread")
namespace = st.sidebar.text_input("Memory namespace", "default")
st.sidebar.caption("Thread and memory identifiers organize data; they are not authentication. Use locally with trusted users.")
cards = [int(c.number_input(f"Card {i+1}", min_value=1, max_value=13, value=v))
         for i, (c,v) in enumerate(zip(st.columns(4), (3,3,8,8)))]
max_hops = st.slider("Maximum role/tool hops", 1, 30, 12)
search_policy = st.sidebar.selectbox("Solving policy", ["model", "hybrid"])
st.sidebar.caption("Hybrid explicitly invokes exact search after an invalid model attempt. Its answers are tool-assisted.")
action = st.radio("Action", ["Solve", "Resume interrupted thread", "Show saved history"])
st.caption("The oracle demo uses exhaustive search, without model calls or semantic retrieval. It is not Qwen evidence.")
if st.button("Solve with TA2", type="primary"):
    workflow = None
    rag = None
    try:
        offline = mode == "Deterministic oracle demo"
        client = None if offline else LocalOllama()
        if client and action != "Show saved history":
            client.ready()
        rag = None if offline or action == "Show saved history" else ChromaRAG(Path(data_dir) / "chroma", client)
        workflow = TA2Workflow(data_dir, client, rag, max_hops=max_hops, offline=offline, search_policy=search_policy)
        if action == "Show saved history":
            st.session_state.ta2_result = workflow.snapshot(thread).values or None
            if not st.session_state.ta2_result:
                st.info("No saved state for this thread.")
        elif action == "Resume interrupted thread":
            st.session_state.ta2_result = workflow.resume(thread)
        else:
            st.session_state.ta2_result = workflow.run(cards, thread, namespace=namespace)
    except (ToolFailure, ValueError, OSError, sqlite3.Error) as exc:
        st.error(str(exc))
    finally:
        if workflow:
            workflow.close()
        if rag:
            rag.close()
result = st.session_state.get("ta2_result")
if result:
    st.write("Status:", result["status"])
    st.write("Execution mode:", result["mode"])
    st.write("Candidate source:", result.get("candidate_origin", "legacy"))
    st.code(result["expression"] or "No verified expression")
    st.write("Verifier:", result["feedback"])
    st.metric("Hops", result["hops"])
    st.subheader("Agent and tool events")
    st.json(result["events"])
    st.subheader("Retrieved evidence")
    st.json(result["evidence"])
    st.subheader("Thread history and memory")
    st.json({"history": result["history"], "memory": result["memory"]})
    if result["errors"]:
        st.error("A tool failed; inspect details below.")
        st.json(result["errors"])


st.divider()
st.subheader("Faculty TA2 evidence demonstrations")
with st.expander("U3 — Grounded RAG: k=1 vs k=3 and unsupported questions"):
    from ta2.qa import compare_k
    rag_question = st.text_input(
        "Ask the reference corpus",
        "Why are fractional intermediate values allowed in Game of 24?",
        key="jury_rag_question",
    )
    if st.button("Compare retrieval k=1 and k=3", key="jury_rag_button"):
        try:
            qa_client = LocalOllama()
            qa_client.ready()
            with ChromaRAG(Path(data_dir) / "chroma", qa_client) as qa_rag:
                st.session_state["jury_rag_result"] = compare_k(rag_question, qa_rag, qa_client)
        except (ToolFailure, ValueError, OSError) as exc:
            st.error(f"RAG audit could not finish: {exc}")
    if "jury_rag_result" in st.session_state:
        report = st.session_state["jury_rag_result"]
        for key in ("k1", "k3"):
            row = report[key]
            st.write(f"{key}: {row['answer']}")
            st.caption(f"Grounded: {row['grounded']} · Citation IDs: {row['citations']}")
            st.json(row["sources"])
    st.caption("Try 'Who founded Neptune Motors?' to demonstrate the 'I don't know' refusal.")

with st.expander("U3 — Checkpointed follow-up versus memory disabled"):
    from ta2.followup import contextual_followup
    memory_question = st.text_input(
        "Follow-up dependent on the selected saved thread",
        "What was my previous expression?",
        key="jury_memory_question",
    )
    if st.button("Compare with / without memory", key="jury_memory_button"):
        memory_workflow = None
        try:
            # Snapshot reads do not require an LLM. Use the same persisted thread ID.
            memory_workflow = TA2Workflow(data_dir, offline=True)
            saved_state = memory_workflow.snapshot(thread).values
            st.session_state["jury_memory_result"] = {
                "thread": thread,
                "with_memory": contextual_followup(saved_state, memory_question),
                "without_memory": contextual_followup(saved_state, memory_question, True),
            }
        except (ValueError, OSError, sqlite3.Error) as exc:
            st.error(f"Memory comparison could not finish: {exc}")
        finally:
            if memory_workflow:
                memory_workflow.close()
    if "jury_memory_result" in st.session_state:
        st.json(st.session_state["jury_memory_result"])

with st.expander("U4 — Mathematical guardrail: approved and rejected paths"):
    from ta2.tools import verify
    demonstration_cards = [2, 2, 6, 6]
    safe = verify("2*6+2*6", demonstration_cards)
    unsafe = verify("2+2+6+6", demonstration_cards)
    st.json({
        "cards": demonstration_cards,
        "approved": {"expression": "2*6+2*6", "verified": safe.valid, "feedback": safe.message},
        "rejected": {"expression": "2+2+6+6", "verified": unsafe.valid, "feedback": unsafe.message},
    })
    st.caption("Verifier approval is mathematical, not an unverified evaluator confidence score.")
