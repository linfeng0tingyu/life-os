from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path


MINIMUM_PYTHON = (3, 12)


def main() -> int:
    if sys.version_info < MINIMUM_PYTHON:
        print("Life OS requires Python 3.12 or newer.", file=sys.stderr)
        return 1

    project_root = Path(__file__).resolve().parents[1]
    requirements = project_root / "requirements.txt"
    marker = Path(sys.prefix) / ".life-os-requirements.sha256"
    expected_hash = hashlib.sha256(requirements.read_bytes()).hexdigest()

    dependencies_present = all(
        importlib.util.find_spec(name) is not None
        for name in ("flask", "flask_sqlalchemy")
    )
    marker_matches = marker.exists() and marker.read_text(
        encoding="utf-8"
    ).strip() == expected_hash

    if dependencies_present and marker_matches:
        print("Life OS dependencies are ready.")
        return 0

    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "-r",
        str(requirements),
    ]
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        print("Dependency installation failed.", file=sys.stderr)
        return completed.returncode

    marker.write_text(expected_hash + "\n", encoding="utf-8")
    print("Life OS dependencies installed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

