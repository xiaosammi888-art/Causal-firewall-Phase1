from __future__ import annotations

from pathlib import Path

from causal_firewall.io import load_json, load_policy


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "CF-P1-001"


def load_configs():
    return (
        load_json(EXPERIMENT / "experiment_contract.json"),
        load_policy(EXPERIMENT / "access_policy.yaml"),
    )

