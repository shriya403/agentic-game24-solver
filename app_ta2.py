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
st.caption("The oracle demo uses exhaustive search, without model calls or semantic retrieval. It is not Qwen evidence.")
if st.button("Solve with TA2", type="primary"):
    workflow = None
    try:
        offline = mode == "Deterministic oracle demo"
        client = None if offline else LocalOllama()
        if client:
            client.ready()
        rag = None if offline else ChromaRAG(Path(data_dir) / "chroma", client)
        workflow = TA2Workflow(data_dir, client, rag, max_hops=max_hops, offline=offline)
        st.session_state.ta2_result = workflow.run(cards, thread, namespace=namespace)
    except (ToolFailure, ValueError, OSError, sqlite3.Error) as exc:
        st.error(str(exc))
    finally:
        if workflow:
            workflow.close()
result = st.session_state.get("ta2_result")
if result:
    st.write("Status:", result["status"])
    st.code(result["expression"] or "No verified expression")
    st.write("Verifier:", result["feedback"])
    st.metric("Hops", result["hops"])
    st.subheader("Agent and tool events")
    st.json(result["events"])
    st.subheader("Retrieved evidence")
    st.json(result["evidence"])
    if result["errors"]:
        st.error("A tool failed; inspect details below.")
        st.json(result["errors"])
