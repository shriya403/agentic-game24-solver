"""Bootstrap the jury dashboard with a project-local Python 3.12 environment."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if sys.version_info[:2] != (3, 12):
        print("Install Python 3.12 with the Windows Python launcher, then run run_final.bat.")
        return 1
    env = ROOT / ".venv"
    python = env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        print("Creating the Python 3.12 environment.", flush=True)
        venv.create(env, with_pip=True)
    version_check = [str(python), "-c", "import sys; sys.exit(sys.version_info[:2] != (3,12))"]
    if subprocess.run(version_check, cwd=ROOT).returncode:
        print("The existing .venv uses a different Python version. Rename it to preserve it and retry.")
        return 1
    requirements = ROOT / "requirements.txt"
    fingerprint = hashlib.sha256(requirements.read_bytes()).hexdigest()
    marker = env / "game24-requirements.sha256"
    if not marker.exists() or marker.read_text(encoding="ascii").strip() != fingerprint:
        subprocess.run([str(python), "-m", "pip", "install", "-r", str(requirements)],
                       cwd=ROOT, check=True)
        marker.write_text(fingerprint, encoding="ascii")
    return subprocess.call([str(python), "-m", "streamlit", "run", "final_jury/app.py",
                            *sys.argv[1:]], cwd=ROOT)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"Launch stopped. {error}", file=sys.stderr)
        raise SystemExit(1)
