#!/usr/bin/env python3
"""Run every zero-cost reproducibility gate distributed with the repository."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> None:
    print("Running:", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    python = sys.executable
    run([python, "-m", "unittest", "discover", "-s", "tests", "-v"])
    run([python, "scripts/run_no_api_audit.py"])
    run([python, "scripts/run_provider_dry_run.py"])
    run([python, "scripts/run_behavioral_smoke_v2_dry_run.py"])
    run([python, "scripts/verify_public_release.py"])
    print("All offline reproduction gates passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
