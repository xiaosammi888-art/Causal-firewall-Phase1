#!/usr/bin/env python3
"""Run the frozen no-API audit for pilot CF-P1-001."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from causal_firewall.audit import run_audit
from causal_firewall.io import load_json, load_policy


def main() -> int:
    experiment = ROOT / "experiments" / "CF-P1-001"
    contract = load_json(experiment / "experiment_contract.json")
    policy = load_policy(experiment / "access_policy.yaml")
    output = ROOT / "artifacts" / "CF-P1-001" / "no_api_audit"
    rows = run_audit(contract, policy, output)

    firewall_rows = [
        row for row in rows if row["architecture"] == "D_labeled_causal_firewall"
    ]
    passed = sum(row["meets_firewall_standard"] == "true" for row in firewall_rows)
    print(f"Study: {contract['identity']['study_id']}")
    print(f"Firewall gates passed: {passed}/{len(firewall_rows)}")
    print(f"Audit report: {output / 'audit_report.csv'}")
    return 0 if passed == len(firewall_rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())

