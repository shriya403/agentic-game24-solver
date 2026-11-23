"""Read-only verification of TA1 files against object IDs from git ls-tree."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "audit" / "pinned-ta1.json"


def git_blob(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()


def compare(directory: Path) -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows = []
    for relative, record in manifest["files"].items():
        path = directory / relative
        actual = normalized = None
        status = "missing"
        if path.is_file():
            content = path.read_bytes()
            actual = git_blob(content)
            normalized = git_blob(content.replace(b"\r\n", b"\n")) if record["text"] else None
            status = "exact" if actual == record["blob"] else (
                "line_endings_only" if normalized == record["blob"] else "content_changed"
            )
        rows.append(dict(path=relative, status=status, expected=record["blob"],
                         raw=actual, lf_normalized=normalized))
    return dict(commit=manifest["commit"], files=rows,
                summary={s: sum(r["status"] == s for r in rows) for s in
                         ("exact", "line_endings_only", "content_changed", "missing")})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, nargs="?", default=ROOT / "ta1")
    report = compare(parser.parse_args().directory)
    print(json.dumps(report, indent=2))
    return int(any(report["summary"][s] for s in ("content_changed", "missing")))


if __name__ == "__main__":
    raise SystemExit(main())
