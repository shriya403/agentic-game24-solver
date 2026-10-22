"""One-command TA2 acceptance run: tests, persistence/RAG demonstration, evaluation, report."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import uuid
from contextlib import ExitStack
from pathlib import Path

from run_ta2_evaluation import evaluate
from ta2.rag import ChromaRAG
from ta2.tools import LocalOllama, ToolFailure
from ta2.workflow import TA2Workflow


ROOT = Path(__file__).resolve().parent


def suite(directory, output):
    process = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", directory, "-v"],
                             cwd=ROOT, capture_output=True, text=True)
    log = process.stdout + process.stderr
    (output / f"{directory}.log").write_text(log, encoding="utf-8")
    count = re.search(r"Ran (\d+) tests?", log)
    if process.returncode or not count or int(count.group(1)) == 0:
        raise RuntimeError(f"{directory} did not pass; inspect {directory}.log")
    return int(count.group(1))


def memory_demo(output, offline, base_url, model):
    data = output / "memory-demo"
    client = None if offline else LocalOllama(base_url=base_url, model=model)
    with ExitStack() as resources:
        rag = None
        if client:
            client.ready()
            vectors = client.embed(["Exact arithmetic with fractional intermediate values"])
            generation = client.generate('Return exactly this JSON object: {"ready": true}')
            if generation.get("ready") is not True:
                raise ToolFailure("readiness", "Readiness generation schema did not match")
            rag = resources.enter_context(ChromaRAG(data / "chroma", client))
            rag.ingest([ROOT / "ta2/corpus/rules.md"])
        workflow = TA2Workflow(data, client=client, rag=rag, offline=offline, search_policy="hybrid")
        try:
            first = workflow.run([3,3,8,8], "continuity", namespace="group")
            if not first["valid"]:
                raise RuntimeError("Hybrid memory demonstration failed to produce a verified solution")
            workflow.run([3,3,8,8], "interrupted", namespace="group", interrupt_after=["evaluator"])
            if not workflow.snapshot("interrupted").next:
                raise RuntimeError("Expected an interrupted checkpoint")
        finally:
            workflow.close()

        # Resume in a distinct Python process, preserving the original mode/budget.
        child = r'''
import json,sys
from pathlib import Path
from contextlib import ExitStack
from ta2.tools import LocalOllama
from ta2.rag import ChromaRAG
from ta2.workflow import TA2Workflow
data,offline,url,model=sys.argv[1:]
offline=offline=='True'
client=None if offline else LocalOllama(base_url=url,model=model)
with ExitStack() as resources:
    rag=None if offline else resources.enter_context(ChromaRAG(Path(data)/'chroma',client))
    workflow=TA2Workflow(data,client=client,rag=rag,offline=offline,search_policy='hybrid')
    try:
        result=workflow.resume('interrupted')
        assert result['valid'],result['status']
        print(json.dumps(result))
    finally:
        workflow.close()
'''
        # Close Chroma before the child opens the same directory (Windows safety).
        if rag:
            rag.close()
        process = subprocess.run([sys.executable, "-c", child, str(data), str(offline), base_url, model],
                                 cwd=ROOT, capture_output=True, text=True, timeout=900)
        (output / "restart.log").write_text(process.stdout + process.stderr, encoding="utf-8")
        if process.returncode:
            raise RuntimeError("Cross-process resume failed; inspect restart.log")
        resumed = json.loads(process.stdout)
        if client:
            rag = resources.enter_context(ChromaRAG(data / "chroma", client))
        workflow = TA2Workflow(data, client=client, rag=rag, offline=offline, search_policy="hybrid")
        try:
            second = workflow.run([3,3,8,8], "continuity", namespace="group")
            other = workflow.run([3,3,8,8], "isolated", namespace="other")
            if len(second["history"]) != 2 or not second["memory"] or other["memory"]:
                raise RuntimeError("History/Store namespace isolation failed")
        finally:
            workflow.close()
        evidence = {"first": first, "resumed_in_new_process": resumed, "second_turn": second,
                    "isolated": other, "embedding_dimensions": len(vectors[0]) if client else None}
        (output / "memory-and-rag.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        return {"restart": "passed", "history": "2 turns", "store": "persisted and isolated",
                "rag": "real nomic embeddings and Chroma retrieval" if client else "unrun (offline)"}


def run(output, offline=False, runs=1, base_url="http://localhost:11434", model="qwen2.5:3b"):
    output = Path(output).resolve()
    # Never mix earlier measurements with new acceptance evidence.
    output.mkdir(parents=True, exist_ok=False)
    report = {"complete": False, "mode": "offline" if offline else "local-model", "requirements": {}}
    target = output / "acceptance.json"
    try:
        print("[1/4] Running frozen TA1 tests and TA2 acceptance tests...", flush=True)
        counts = {name: suite(name, output) for name in ("tests", "tests_ta2")}
        report["test_counts"] = counts
        print(f"Tests passed: {counts}", flush=True)
        print("[2/4] Demonstrating persisted threads, Store, restart and RAG...", flush=True)
        report["memory_demo"] = memory_demo(output, offline, base_url, model)
        print("[3/4] Evaluating five cases with explicit assistance labels...", flush=True)
        rows = evaluate(output / "evaluation.csv", offline=offline, runs=runs, model=model,
                        base_url=base_url, search_policy="model" if offline else "both",
                        progress=lambda message: print(message, flush=True))
        failures = [r for r in rows if r["status"] in ("fallback", "tool_failure")]
        assisted = [r for r in rows if r["system"] == ("TA2" if offline else "TA2_Hybrid")]
        assisted_ok = len(assisted) == 5*runs and all(
            r["verified"] if r["expected_solvable"] else r["status"] == "no_solution" for r in assisted)
        report["evaluation_rows"] = len(rows)
        report["evaluation_tool_failures"] = len(failures)
        report["requirements"] = {
            "1_thread_checkpointer": "passed: new-process resume, history and namespace isolation",
            "2_sqlite_store": "passed: durable CRUD and isolated verified memory",
            "3_chroma_nomic_rag": "unrun: real nomic in offline mode" if offline else "passed: real embeddings and source-bearing retrieval",
            "4_agent_roles": "passed: separate Proposer, Evaluator, mathematical Verifier nodes",
            "5_supervisor_max_hops": "passed: persisted budgets and complete verification cycles tested",
            "6_math_guardrails": "passed: exact validator, candidate checks and adversarial tests",
            "7_tool_failures": "passed: injected network/schema/embedding/Store failures and retries tested",
            "8_five_case_evaluation": f"completed: {len(rows)} rows; {len(failures)} tool failures"}
        report["hybrid_case_acceptance"] = assisted_ok
        report["complete"] = not offline and not failures and assisted_ok
        report["offline_validation_passed"] = offline and not failures and assisted_ok
        report["limitations"] = ["Exact instructor SOP not supplied; mapped to the eight requested requirements.",
                                  "Hybrid exact-search success is tool assistance, not Qwen-only reasoning.",
                                  "Model-only solving failures remain in the evaluation; no accuracy claim is inferred from test passes."]
        print("[4/4] Saving acceptance evidence and comparison report...", flush=True)
    except Exception as exc:
        report["error"] = str(exc)
        raise
    finally:
        target.write_text(json.dumps(report, indent=2), encoding="utf-8")
        lines = ["# TA2 acceptance report", "", f"Execution: {report['mode']}",
                 f"All eight capabilities validated with local models: {report['complete']}", ""]
        for key, value in report["requirements"].items():
            lines.append(f"- **{key}**: {value}")
        if "error" in report:
            lines += ["", "Blocked: " + report["error"]]
        lines += ["", "See evaluation.summary.md for actual solving outcomes; see individual logs for test evidence.",
                  "Formal SOP compliance requires the instructor's exact SOP, which was not provided."]
        (output / "ACCEPTANCE.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="results/ta2-acceptance-" + uuid.uuid4().hex[:8])
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--runs", type=int, choices=range(1,6), default=1)
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument("--model", default="qwen2.5:3b")
    args = parser.parse_args()
    try:
        report = run(args.output_dir, args.offline, args.runs, args.base_url, args.model)
    except Exception as exc:
        parser.exit(2, f"Acceptance blocked: {exc}\n")
    print(f"Evidence saved to {args.output_dir}")
    if not report["complete"] and not report.get("offline_validation_passed"):
        raise SystemExit(2)
    print("Offline validation passed; real models remain unrun." if args.offline else
          "All eight capability checks completed; inspect the evaluation for solving performance.")


if __name__ == "__main__":
    main()
