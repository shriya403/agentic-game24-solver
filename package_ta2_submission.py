"""Package an inspectable TA1/TA2 jury submission without inventing a report.

Run from the project root:
python package_ta2_submission.py --name GroupNN_LYAIA5_Game24_TA2

Replace the example group/division with the actual faculty roster entry.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parent
BASE = (
    "README.md", "app.py", "game24", "tests", "requirements.txt",
    "pyproject.toml", "run_experiment.py", "docs/REPORT.md",
    "docs/VIVA.md", "docs/SUBMISSION_CHECKLIST.md",
    "results/deterministic_baseline.csv", "Agentic_Game24_Jury_Deck.pptx",
)
EXTENDED = (
    "README.md", "docs", "app.py", "app_ta2.py", "game24", "ta2", "tests",
    "tests_ta2", "requirements.txt", "requirements-ta2.txt",
    "pyproject.toml", "run_experiment.py", "run_ta2_acceptance.py",
    "run_ta2_evaluation.py",
)


def copy_selected(paths, destination):
    for relative in paths:
        source = ROOT / relative
        if not source.exists():
            raise FileNotFoundError(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="Faculty-assigned GroupNN_Division_Topic_TA2")
    parser.add_argument("--output", default="submissions")
    args = parser.parse_args()
    if (Path(args.name).name != args.name or not args.name.endswith("_TA2")
            or any(c in args.name for c in "\\/:*?\"<>|")):
        parser.error("Use one safe folder name ending in _TA2, with the correct group/division")
    target = ROOT / args.output / args.name
    if target.exists():
        parser.error(f"Destination already exists; choose a new output directory: {target}")
    (target / "ta1").mkdir(parents=True)
    (target / "ta2").mkdir(parents=True)
    (target / "traces").mkdir(parents=True)
    copy_selected(BASE, target / "ta1")
    copy_selected(EXTENDED, target / "ta2")
    source_results = ROOT / "results"
    copied_traces = []
    for source in sorted(source_results.glob("ta2-*")):
        if source.is_dir():
            shutil.copytree(source, target / "traces" / source.name)
            copied_traces.append(source.name)
    shutil.copy2(source_results / "deterministic_baseline.csv",
                 target / "traces" / "deterministic_baseline.csv")
    report_found = (ROOT / "report.pdf").is_file()
    if report_found:
        shutil.copy2(ROOT / "report.pdf", target / "report.pdf")
    else:
        (target / "REPORT_REQUIRED.txt").write_text(
            "Faculty requires a student-authored report.pdf (at most four pages). "
            "Do not submit this package as complete until it is added.\n",
            encoding="utf-8",
        )
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                         capture_output=True, text=True, check=False).stdout.strip()
    (target / "MANIFEST.json").write_text(json.dumps({
        "git_revision": sha, "baseline_commit": "02a6e7d69e5d1cdc614ca04e46e686b907617bb7",
        "ta1_root_files_untouched": True, "traces": copied_traces,
        "report_pdf_present": report_found,
        "note": "Saved traces are prior runs; rerun on the submitted version before claiming final validation."
    }, indent=2), encoding="utf-8")
    (target / "README_SUBMISSION.txt").write_text(
        "TA1 frozen baseline: ta1/; TA2 extension and launch: ta2/.\n"
        "From ta2/: python -m pip install -r requirements-ta2.txt; "
        "python -m ta2.cli ingest; python -m streamlit run app_ta2.py\n"
        "Trace files are in traces/. Include your own report.pdf before submission.\n",
        encoding="utf-8",
    )
    archive = target.with_suffix(".zip")
    with ZipFile(archive, "w", ZIP_DEFLATED) as zf:
        for file in sorted(target.rglob("*")):
            if file.is_file():
                zf.write(file, arcname=file.relative_to(target.parent))
    print(json.dumps({
        "folder": str(target), "zip": str(archive), "report_pdf_present": report_found,
        "saved_trace_sets": copied_traces,
        "status": "packaged; REPORT REQUIRED" if not report_found else "packaged; verify final tests",
    }, indent=2))


if __name__ == "__main__":
    main()
