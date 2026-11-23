"""Local Streamlit entry point. Launch from the project root with streamlit run final_jury/app.py."""
from __future__ import annotations

import json
import os
import platform
import sqlite3
import sys
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from queue import Empty, Queue

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from final_jury.display import CSS, certificate, export, hero, tile, trace_tree

PAGES = ["Mission Control", "Live Solver", "Reasoning Tree", "Agent Operations",
         "Memory + RAG", "Evaluation Lab", "Safety Center", "Jury Mode"]
PRESETS = {"Easy": (4, 7, 8, 8), "Fractional": (1, 5, 5, 5),
           "Challenging": (3, 3, 8, 8), "Unsolvable": (1, 1, 1, 1)}
METHODS = {"Linear reasoning": "linear", "Single-agent ToT": "tree", "Multi-agent ToT": "multi"}
HISTORICAL = ROOT / "results" / "ta2-acceptance-ad0424cd"
DATA = Path(os.environ.get("GAME24_DATA_DIR", ROOT / "data" / "runtime")).resolve()


def navigate(page: str) -> None:
    st.session_state["workspace"] = page


def navigation_button(label: str, page: str, **kwargs) -> None:
    st.button(label, on_click=navigate, args=(page,), **kwargs)


def run_solver(cards: list | tuple, method: str, mode: str, **options) -> dict:
    from final_jury.solver import solve

    events = Queue()
    with st.status("Starting workflow…", expanded=False) as indicator:
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(solve, list(cards), method, mode=mode, on_event=events.put, **options)
            while not result.done() or not events.empty():
                try:
                    event = events.get(timeout=.1)
                except Empty:
                    continue
                role = str(event["role"]).replace("_", " ").title()
                indicator.update(label=f"{role} · {event['stage']} · hop {event['hop']}")
            run = result.result()
        indicator.update(label="Workflow finished · " + run["status"].replace("_", " "),
                         state="error" if run["status"] == "tool_failure" else "complete")
        return run


def live_run(cards: list | tuple, method: str, mode: str, **options) -> None:
    st.session_state.pop("last_run", None)
    st.session_state.run_origin = "Live execution"
    try:
        st.session_state.last_run = run_solver(cards, method, mode, data_dir=DATA, **options)
    except (ValueError, OSError, sqlite3.Error, RuntimeError) as exc:
        st.error(f"Run stopped · {exc}")


def show_run(run: dict) -> None:
    st.subheader("Run result")
    st.caption(f"{st.session_state.run_origin} · {run['method']} / {run['mode']} · cards {run['puzzle']} · {run['run_id']}")
    m = run["metrics"]
    a, b, c = st.columns(3)
    a.metric("Workflow status", run["status"].replace("_", " ").title())
    b.metric("Elapsed", f"{m['latency_s']:.3f} s")
    c.metric("Generation calls", m.get("model_calls") if m.get("model_calls") is not None else "—")
    for err in run.get("errors", []):
        st.error(str(err))
    if run.get("expression") or run.get("certificate", {}).get("valid"):
        certificate(run["certificate"])
        for step in run.get("explanation", []):
            st.write(step)
    else:
        st.info("This run ended without a verified expression.")
    export(run)


def active_run() -> dict | None:
    run = st.session_state.get("last_run")
    if not run:
        st.info("Run a puzzle to inspect its recorded workflow.")
        navigation_button("Open Live Solver", "Live Solver")
    return run


def mission() -> None:
    st.title("Mission Control")
    hero("Game of 24 Solver", "Make exactly 24.",
         "Compare linear reasoning and tree search as they combine four cards to reach exactly 24.",
         PRESETS["Challenging"])
    a, b, _ = st.columns([1, 1, 2])
    with a:
        navigation_button("Open Live Solver", "Live Solver", type="primary", width="stretch")
    with b:
        navigation_button("Enter Jury Mode", "Jury Mode", width="stretch")
    st.subheader("Project evolution")
    for col, args in zip(st.columns(3), [
        ("TA1", "Search strategies", "Compare a linear attempt with a tree of candidate operations."),
        ("TA2", "Memory & supervision", "Inspect thread checkpoints, retrieval and bounded role dispatch."),
        ("Final jury", "Independent proof", "Audit each expression and inspect the evidence behind a result."),
    ]):
        with col:
            tile(*args)
    st.subheader("System health")
    from ta2.tools import LocalOllama, ToolFailure

    a, b, c = st.columns(3)
    a.metric("Python runtime", platform.python_version())
    try:
        b.metric("LangGraph installed", version("langgraph"))
    except PackageNotFoundError:
        b.metric("LangGraph installed", "Missing")
    c.metric("Local store", "Present" if (DATA / "store.sqlite").is_file() else "Awaiting run")
    st.caption("The exact-search demonstration runs locally. Model generation and semantic retrieval use Ollama.")
    if st.button("Check local models"):
        try:
            LocalOllama(timeout=3, retries=0).ready()
            st.success("Ollama lists qwen2.5:3b and nomic-embed-text.")
        except (ToolFailure, OSError, ValueError) as exc:
            st.warning(str(exc))


def live() -> None:
    st.title("Live Solver")
    st.caption("Choose four cards, a search method and an execution engine.")
    preset = st.selectbox("Puzzle preset", [*PRESETS, "Custom"], index=1)
    if preset == "Custom":
        cards = tuple(c.number_input(f"Card {i}", min_value=1, max_value=13, value=n)
                      for i, (c, n) in enumerate(zip(st.columns(4), PRESETS["Fractional"]), 1))
    else:
        cards = PRESETS[preset]
    hero("Current puzzle", "Reach exactly 24.", "Use each card once with +, −, × or ÷.", cards)
    method_col, mode_col = st.columns(2)
    method_name = method_col.selectbox("Reasoning approach", list(METHODS), index=2)
    mode_name = mode_col.radio("Execution engine", ["Deterministic", "Local Qwen"], horizontal=True)
    method, mode = METHODS[method_name], ("exact" if mode_name == "Deterministic" else "model")
    if mode == "exact":
        strategy = {"multi": "Exact depth-first search with duplicate-state pruning",
                    "tree": "Beam search with exact feasibility checks",
                    "linear": "Greedy linear baseline"}[method]
        st.caption(f"{strategy} · model generation disabled.")
    elif method == "tree":
        st.caption("TA1 ToT uses model reasoning with deterministic feasibility assistance.")
    if method == "multi":
        with st.expander("Workflow controls"):
            hops = st.slider("Maximum hops", 1, 30, 12)
            rag = st.checkbox("Retrieve solved examples")
            k = st.radio("Retrieved examples", [1, 3], index=1, horizontal=True, disabled=not rag)
            default_thread = st.session_state.setdefault("base_thread", uuid.uuid4().hex[:12])
            thread = st.text_input("Thread ID", value=f"jury-{default_thread}-{mode}", key=f"thread_{mode}")
    else:
        hops, rag, k, thread = 12, False, 3, None
    if st.button("Run solver", type="primary"):
        live_run(cards, method, mode, rag=rag, max_hops=hops, k=k, thread_id=thread)
    if run := st.session_state.get("last_run"):
        show_run(run)


def tree() -> None:
    st.title("Reasoning Tree")
    run = active_run()
    if not run:
        return
    st.caption(f"{st.session_state.run_origin} · {run['puzzle']} · {run['method']} / {run['mode']}")
    rows = run.get("branches", [])
    if not rows:
        st.info("This method recorded no branch-level observations.")
    else:
        decisions = list(dict.fromkeys(str(r.get("decision", "")) for r in rows))
        filter_value = st.selectbox("Filter decisions", ["All decisions", *decisions])
        visible = [r for r in rows if filter_value == "All decisions" or r["decision"] == filter_value]
        index = next((i for i, row in reversed(list(enumerate(visible)))
                      if row.get("decision") in ("selected", "verified")), 0)
        row = st.selectbox("Inspect a branch", visible, index=index,
                           format_func=lambda r: f"{r['id']} · {r.get('move','')} · {r['decision']}")
        st.graphviz_chart(trace_tree(rows, run["puzzle"], row), width="stretch")
        st.caption(f"Focused path and nearby alternatives · {len(rows)} recorded branches available in the selector.")
        with st.container(border=True):
            st.write("**Operation**", row.get("move", "Initial state"))
            st.write("**Remaining state**", row["state"] if isinstance(row.get("state"), str) else " · ".join(map(str, row.get("state", []))))
            st.write("**Evaluation**", row.get("reason", "No evaluation recorded"))
            if row.get("evaluator"):
                st.write("**Scoring source**", row["evaluator"])
            if row.get("score") is not None:
                st.write("**Recorded score**", row["score"])
    if run.get("certificate", {}).get("valid"):
        certificate(run["certificate"])


def operations() -> None:
    st.title("Agent Operations")
    run = active_run()
    if not run:
        return
    st.caption(f"{st.session_state.run_origin} · {run['method']} / {run['mode']} · {run['run_id']}")
    metrics = run["metrics"]
    for col, label, field in zip(st.columns(4), ["Hops", "Generation calls", "Input tokens", "Output tokens"],
                                 ["hops", "model_calls", "prompt_tokens", "output_tokens"]):
        col.metric(label, metrics.get(field) if metrics.get(field) is not None else "—")
    st.caption("A dash indicates the measurement is unavailable.")
    st.write("**Final stage**", run["status"])
    events = run.get("events", [])
    if events:
        rows = [{"Event": i, "Hop": e.get("hop"), "Role": e.get("role"),
                 "Action": e.get("action") or e.get("dispatch") or e.get("decision") or e.get("message") or "View recorded fields"}
                for i, e in enumerate(events, 1)]
        st.dataframe(rows, hide_index=True, width="stretch")
        i = st.slider("Inspect event", 1, len(events), len(events)) if len(events) > 1 else 1
        st.json(events[i-1])
    else:
        st.info("This execution ended before a workflow event was recorded.")
    with st.expander("All recorded metrics"):
        st.json(metrics)
    export(run)


def memory() -> None:
    st.title("Memory + RAG")
    st.caption("Inspect persistent records and the retrieval context used for a puzzle.")
    tab1, tab2, tab3 = st.tabs(["Last run", "Persistent store", "Compare retrieval"])
    with tab1:
        run = st.session_state.get("last_run")
        if run:
            st.write("**Run**", run["run_id"])
            if run["method"] == "multi":
                st.write("**Thread**", run["thread_id"])
                with st.expander("Checkpointed conversation"):
                    if st.session_state.run_origin == "Live execution" and (DATA / "checkpoints.sqlite").is_file():
                        from ta2.workflow import TA2Workflow
                        from ta2.followup import contextual_followup
                        try:
                            with closing(TA2Workflow(DATA, offline=True)) as flow:
                                snapshot = flow.snapshot(run["thread_id"]).values
                            question = "What was my previous expression?"
                            st.write(question)
                            st.write("**With saved history**", contextual_followup(snapshot, question)["answer"])
                            st.write("**With history disabled**", contextual_followup(snapshot, question, True)["answer"])
                            st.json(snapshot.get("history", []) if snapshot else [])
                        except (ValueError, OSError, sqlite3.Error) as exc:
                            st.warning(f"Checkpoint unavailable · {exc}")
                    else:
                        st.info("No local checkpoint for this run.")
            st.write("**Retrieved examples**")
            evidence = run.get("evidence") or []
            if evidence:
                for i, item in enumerate(evidence, 1):
                    with st.expander(f"Result {i} · {item.get('source',item.get('id','example'))}"):
                        st.json(item)
                retrieval_note = ("The exact proposer ignores retrieved examples." if run["mode"] == "exact"
                                      else "Inspect the proposer event for its context-example count. Retrieval alone cannot establish an improvement.")
                st.caption(retrieval_note)
            else:
                st.info("No semantic retrieval evidence was recorded for this run.")
            with st.expander("SQLite memory hits"):
                st.json(run.get("memory", []))
        else:
            st.info("Run a multi-agent puzzle to inspect memory hits and retrieved examples.")
    with tab2:
        path = DATA / "store.sqlite"
        if not path.is_file():
            st.info("The first multi-agent run creates the local SQLite store.")
        else:
            try:
                with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=2)) as db:
                    rows = db.execute("SELECT namespace,key,updated,value FROM ta2_items ORDER BY updated DESC LIMIT 100").fetchall()
                st.caption("Most recent 100 stored records · read-only inspection")
                if rows:
                    st.dataframe(pd.DataFrame(rows, columns=["Namespace", "Key", "Updated", "Stored JSON"]),
                                 width="stretch", hide_index=True)
                else:
                    st.info("The store is empty.")
            except sqlite3.Error as exc:
                st.warning(f"Store unavailable · {exc}")
    with tab3:
        st.write("Compare the same puzzle with retrieval disabled, k=1 and k=3. Each run starts with a fresh thread and store.")
        preset = st.selectbox("Comparison puzzle", list(PRESETS), index=1)
        if st.button("Run Qwen retrieval comparison", type="primary"):
            results = []
            from ta2.tools import LocalOllama, ToolFailure
            try:
                LocalOllama(timeout=4, retries=0).ready()
                with tempfile.TemporaryDirectory() as tmp:
                    for label, k in [("Disabled", 0), ("k=1", 1), ("k=3", 3)]:
                        result = run_solver(PRESETS[preset], "multi", "model", data_dir=Path(tmp)/f"k{k}",
                                            rag=bool(k), k=k or 1, seed=42)
                        results.append({"configuration": label, "run": result})
            except (ToolFailure, ValueError, OSError, sqlite3.Error, RuntimeError) as exc:
                st.warning(f"Comparison stopped · {exc}")
            st.session_state["rag_comparison"] = results
        for sample in st.session_state.get("rag_comparison", []):
            run = sample["run"]
            with st.expander(f"{sample['configuration']} · {run['puzzle']} · {run['status']}"):
                st.json({key: run.get(key) for key in ["expression","certificate","evidence","metrics","errors"]})


def evaluation() -> None:
    st.title("Evaluation Lab")
    sources = {"Archived Qwen study": HISTORICAL,
               "Local reference benchmark": ROOT / "benchmarks/evidence/reference"}
    local_model = ROOT / "benchmarks/evidence/ollama"
    if (local_model / "metrics.csv").exists():
        sources["Local model benchmark"] = local_model
    which = st.radio("Evidence set", list(sources), horizontal=True)
    archive = which.startswith("Archived")
    base = sources[which]
    path = base / ("evaluation.csv" if archive else "metrics.csv")
    if not path.is_file():
        st.info("This benchmark has no saved results in this checkout.")
        return
    data = pd.read_csv(path)
    manifest = base / ("evaluation.manifest.json" if archive else "manifest.json")
    conditions = json.loads(manifest.read_text("utf-8")) if manifest.exists() else {}
    partial = conditions.get("completed") is False
    if partial:
        settings = 2 + len(conditions["policies"]) * len(conditions["rag_ks"])
        target = len(conditions["cases"]) * len(conditions["seeds"]) * settings
        st.warning(f"Partial benchmark · {len(data)} of {target} planned trials recorded. "
                   "The table shows individual observations. Comparative charts require a complete run.")
    st.caption(f"Saved execution evidence · {path.relative_to(ROOT)}")
    if archive:
        st.write("The original Windows study used Qwen2.5:3b on four solvable puzzles and one unsolvable control. "
                 "TA1 ToT used exact feasibility checks. TA2 Hybrid allowed an exact-search override.")
    elif base == local_model:
        failures = data["error"].notna().sum()
        st.write(f"This local model benchmark recorded {failures} rows with errors out of {len(data)}. "
                 "Inspect the status and error columns before interpreting model accuracy.")
    else:
        st.write("These local runs measure deterministic execution. Each system received the same five puzzles.")
    if not partial:
        solvable = data[data["expected_solvable"] == True]
        grouping = ["system", "rag_k"] if base == local_model else "system"
        summary = solvable.groupby(grouping, sort=False).agg(
            verified=("verified", "sum"), attempts=("verified", "size"),
            median_seconds=("wall_time_sec", "median"),
        )
        if base == local_model:
            summary.index = [f"{system} · k={k}" for system, k in summary.index]
        st.subheader("Verified answers on solvable cases")
        st.bar_chart(summary[["verified"]], color="#82d9d4", height=220)
        st.dataframe(summary.rename(columns={"verified":"Verified","attempts":"Solvable attempts",
                                             "median_seconds":"Median seconds (solvable)"}), width="stretch")
        st.caption("The unsolvable control is listed below. A timeout or a missing answer does not establish unsolvability.")
    case = st.selectbox("Inspect case", ["All cases", *data["case"].drop_duplicates().tolist()])
    subset = data if case == "All cases" else data[data["case"] == case]
    st.dataframe(subset, width="stretch", hide_index=True)
    if conditions:
        with st.expander("Measurement conditions"):
            st.json(conditions)
    st.download_button("Export benchmark CSV", path.read_bytes(), path.name, "text/csv")
    trace_path = base / ("evaluation.traces.json" if archive else "traces.json")
    if trace_path.is_file():
        st.download_button("Export benchmark traces", trace_path.read_bytes(), trace_path.name, "application/json")


def safety() -> None:
    from core.proof import audit
    from final_jury.safety import CASES, run_case, run_suite

    st.title("Safety Center")
    st.caption("Audit an expression or run controlled fault demonstrations against the solver.")
    first, second = st.tabs(["Proof auditor", "Fault demonstrations"])
    with first:
        preset = st.selectbox("Audit puzzle", list(PRESETS), index=2)
        cards = PRESETS[preset]
        st.write("**Cards**", " · ".join(map(str, cards)))
        expr = st.text_input("Expression", "8 / (3 - 8 / 3)", max_chars=256)
        if st.button("Check expression", type="primary"):
            st.session_state.last_audit = audit(expr, list(cards))
        if proof := st.session_state.get("last_audit"):
            st.caption(f"Audited input · {proof['puzzle']} · {proof['expression']}")
            certificate(proof)
    with second:
        case = st.selectbox("Controlled scenario", list(CASES), format_func=CASES.get)
        a, b, _ = st.columns([1, 1, 2])
        if a.button("Run scenario"):
            st.session_state.safety_rows = [run_case(case)]
        if b.button("Run all checks", type="primary"):
            with st.spinner("Running isolated checks…"):
                st.session_state.safety_rows = run_suite()
        rows = st.session_state.get("safety_rows", [])
        if rows:
            st.write(f"**{sum(row['passed'] for row in rows)} of {len(rows)} expected behaviors observed**")
            for row in rows:
                label = "Passed" if row["passed"] else "Failed"
                with st.expander(f"{label} · {row['title']}"):
                    st.write("**Method**", row["method"])
                    st.write("**Expected**", row["expected"])
                    st.write("**Observed**", row["observed"])
                    st.json(row["evidence"])
            st.download_button("Export safety results", json.dumps(rows, indent=2), "game24-safety.json", "application/json")


def jury() -> None:
    st.title("Jury Mode")
    hero("Five-minute demonstration", "Follow a fractional proof.",
         "Start a live deterministic workflow, trace the selected operations, then compare the saved model study.",
         PRESETS["Challenging"])
    a, b, _ = st.columns([1.4, 1.2, 1.3])
    if b.button("Load saved replay"):
        replay = ROOT / "traces/fractional-exact.json"
        st.session_state.last_run = json.loads(replay.read_text(encoding="utf-8"))
        st.session_state.run_origin = "Saved replay · traces/fractional-exact.json"
    if a.button("Run fractional demonstration", type="primary"):
        live_run(PRESETS["Challenging"], "multi", "exact", rag=False, max_hops=12)
    if run := st.session_state.get("last_run"):
        show_run(run)
    st.subheader("Presentation sequence")
    for time_slot, title, note, page in [
        ("0:00–0:45", "Set the problem", "Show how four input cards constrain the search.", "Mission Control"),
        ("0:45–2:00", "Audit the fractional result", "Run the demonstration above. Inspect a selected or pruned operation.", "Reasoning Tree"),
        ("2:00–3:00", "Follow the supervisor", "Inspect the hop count, role dispatch and proof decision.", "Agent Operations"),
        ("3:00–4:00", "Compare measured outcomes", "Open the archived Qwen study and check the unsolvable control.", "Evaluation Lab"),
        ("4:00–5:00", "Challenge the guard", "Change an operand in the proof auditor. End on the verdict and export the run.", "Safety Center"),
    ]:
        left, right = st.columns([3, 1])
        left.markdown(f"**{time_slot}　{title}**")
        left.caption(note)
        with right:
            navigation_button(page, page, key=f"guide_{page}")


st.set_page_config(page_title="GAME24 AI · Jury dashboard", page_icon="🃏", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)
with st.sidebar:
    st.markdown('<div class="identity"><i>24</i> GAME24 AI</div>', unsafe_allow_html=True)
    section = st.radio("Workspace", PAGES, key="workspace")
    st.divider()
    st.caption("Shriya Jitendra Shinde\n\nMIT ADT University, Pune\n\nAgentic AI · November 2026")
pages = dict(zip(PAGES, [mission, live, tree, operations, memory, evaluation, safety, jury]))
pages[section]()
