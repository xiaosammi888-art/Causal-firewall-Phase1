#!/usr/bin/env python3
"""Generate and audit the redesigned 288-row plan with zero API calls."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from causal_firewall.behavioral_smoke_v2 import run_behavioral_smoke_v2_dry_run
from causal_firewall.io import load_json, load_policy


def main() -> int:
    experiment = ROOT / "experiments" / "CF-P1-001"
    output = run_behavioral_smoke_v2_dry_run(
        load_json(experiment / "experiment_contract.json"),
        load_policy(experiment / "access_policy.yaml"),
        load_json(experiment / "behavioral_smoke_contract_v0.2.0.json"),
        ROOT / "artifacts" / "CF-P1-001" / "behavioral_smoke_v2_dry_run",
    )
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    print(f"V2 dry-run gates passed: {summary['gates_passed']}/{summary['gates_total']}")
    print(f"Scheduled request rows: {summary['scheduled_rows']}")
    print(f"Design cells: {summary['design_cells']}")
    print(f"Network calls: {summary['network_calls']}")
    print(
        "Ready for temperature compatibility gate: "
        f"{summary['ready_for_temperature_compatibility_gate']}"
    )
    print(f"Artifacts: {output}")
    return 0 if summary["ready_for_temperature_compatibility_gate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
