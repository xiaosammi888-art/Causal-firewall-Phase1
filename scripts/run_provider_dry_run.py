#!/usr/bin/env python3
"""Serialize and audit exact provider request bodies without network calls."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from causal_firewall.io import load_json, load_policy
from causal_firewall.request_audit import run_request_audit


def main() -> int:
    experiment = ROOT / "experiments" / "CF-P1-001"
    contract = load_json(experiment / "experiment_contract.json")
    policy = load_policy(experiment / "access_policy.yaml")
    output = ROOT / "artifacts" / "CF-P1-001" / "provider_dry_run"
    rows = run_request_audit(contract, policy, output)
    d_rows = [
        row for row in rows if row["architecture"] == "D_labeled_causal_firewall"
    ]
    passed = sum(row["meets_request_standard"] == "true" for row in d_rows)
    print(f"Provider dry-run gates passed: {passed}/{len(d_rows)}")
    print(f"Network calls: 0")
    print(f"Request audit: {output / 'provider_request_audit.csv'}")
    return 0 if passed == len(d_rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())

