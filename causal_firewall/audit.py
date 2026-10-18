"""No-API Study 0 audit runner."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .architectures import make_architectures
from .faults import build_fault_cases
from .hashing import canonical_json, sha256_json
from .materials import clean_fields
from .models import BuildContext, PacketBuildResult
from .components import PopulationBuilder


def _canary_hits(packet: dict[str, Any], canaries: dict[str, str]) -> list[str]:
    serialized = canonical_json(packet)
    return sorted(token for token in canaries.values() if token in serialized)


def _forbidden_reachable(result: PacketBuildResult, policy: dict[str, Any]) -> list[str]:
    registry = policy["field_registry"]
    allowed_labels = set(policy["respondent_allowed_labels"])
    reachable: list[str] = []
    for field_id in result.packet:
        registered = registry.get(field_id)
        if registered and registered["label"] not in allowed_labels:
            reachable.append(field_id)
        elif registered is None and field_id not in {
            "participant_role",
            "persona_state",
            "common_scenario",
            "current_stimulus",
            "response_schema",
        }:
            reachable.append(field_id)
    return sorted(reachable)


def run_audit(
    contract: dict[str, Any],
    policy: dict[str, Any],
    output_dir: str | Path,
    persona_seed: int = 1701,
    arm: str = "human_allocation",
) -> list[dict[str, Any]]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    persona = PopulationBuilder.build(persona_seed)
    fields = clean_fields(contract, persona, arm)
    context = BuildContext(
        participant_id=persona["participant_id"],
        current_arm=arm,
        session_id="fresh-CF-P1-001-1701-human",
    )
    architectures = make_architectures(contract, policy)
    faults = build_fault_cases(fields, contract)
    canaries = contract["canaries"]
    contract_hash = sha256_json(contract)
    policy_hash = sha256_json(policy)

    clean_d = architectures[-1].build(faults[0].fields, context)
    if clean_d.status != "ready" or clean_d.packet_hash is None:
        raise RuntimeError("clean_firewall_packet_failed")

    rows: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    manifests: list[dict[str, Any]] = []
    for architecture in architectures:
        for fault in faults:
            result = architecture.build(fault.fields, context)
            forbidden = _forbidden_reachable(result, policy)
            hits = _canary_hits(result.packet, canaries)
            expected_status = "blocked" if fault.code == "F7" else "ready"
            invariant_hash = (
                result.packet_hash == clean_d.packet_hash
                if fault.code != "F7"
                else result.status == "blocked"
            )
            meets_firewall_standard = (
                result.status == expected_status
                and not forbidden
                and not hits
                and invariant_hash
            )
            rows.append(
                {
                    "study_id": contract["identity"]["study_id"],
                    "contract_version": contract["identity"]["contract_version"],
                    "architecture": architecture.name,
                    "fault_code": fault.code,
                    "fault_name": fault.name,
                    "execution_status": result.status,
                    "packet_hash": result.packet_hash or "",
                    "matches_clean_firewall": str(result.packet_hash == clean_d.packet_hash).lower(),
                    "forbidden_reachable_count": len(forbidden),
                    "forbidden_fields": "|".join(forbidden),
                    "canary_hit_count": len(hits),
                    "canary_hits": "|".join(hits),
                    "missing_required": "|".join(result.missing_required),
                    "meets_firewall_standard": str(meets_firewall_standard).lower(),
                }
            )
            manifests.append(
                {
                    "study_id": contract["identity"]["study_id"],
                    "architecture": architecture.name,
                    "fault": fault.code,
                    "model_called": False,
                    "persona_seed": persona_seed,
                    "participant_id": persona["participant_id"],
                    "arm": arm,
                    "packet_hash": result.packet_hash,
                    "execution_status": result.status,
                    "contract_hash": contract_hash,
                    "policy_hash": policy_hash,
                    "normalized_material_hash": contract["source"]["normalized_material_sha256"],
                }
            )
            for decision in result.decisions:
                trace = asdict(decision)
                trace.update(
                    {
                        "study_id": contract["identity"]["study_id"],
                        "architecture": architecture.name,
                        "fault": fault.code,
                    }
                )
                traces.append(trace)

    with (output / "audit_report.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    with (output / "trace.jsonl").open("w", encoding="utf-8") as handle:
        for trace in traces:
            handle.write(json.dumps(trace, ensure_ascii=False, sort_keys=True) + "\n")

    with (output / "run_manifest.jsonl").open("w", encoding="utf-8") as handle:
        for manifest in manifests:
            handle.write(json.dumps(manifest, ensure_ascii=False, sort_keys=True) + "\n")

    with (output / "participant_packet.json").open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "study_id": contract["identity"]["study_id"],
                "architecture": architectures[-1].name,
                "fault": "F0",
                "contract_hash": contract_hash,
                "policy_hash": policy_hash,
                "packet_hash": clean_d.packet_hash,
                "packet": clean_d.packet,
            },
            handle,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        handle.write("\n")

    firewall_rows = [
        row for row in rows if row["architecture"] == "D_labeled_causal_firewall"
    ]
    summary = {
        "study_id": contract["identity"]["study_id"],
        "contract_version": contract["identity"]["contract_version"],
        "contract_hash": contract_hash,
        "policy_hash": policy_hash,
        "normalized_material_hash": contract["source"]["normalized_material_sha256"],
        "model_called": False,
        "architectures": len(architectures),
        "fault_cases": len(faults),
        "audit_rows": len(rows),
        "firewall_gates_passed": sum(
            row["meets_firewall_standard"] == "true" for row in firewall_rows
        ),
        "firewall_gates_total": len(firewall_rows),
        "interpretation": (
            "M2 deterministic structural verification only; this is not behavioral "
            "evidence and does not establish human fidelity."
        ),
    }
    with (output / "audit_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")

    return rows
