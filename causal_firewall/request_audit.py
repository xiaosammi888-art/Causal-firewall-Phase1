"""Audit exact provider request bodies in dry-run mode."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .architectures import make_architectures
from .components import PopulationBuilder
from .faults import build_fault_cases
from .hashing import canonical_json, sha256_json
from .materials import clean_fields
from .models import BuildContext
from .providers import (
    OpenAIResponsesDryRunAdapter,
    RequestPreparationError,
    validate_stateless_request,
)


def _hits(value: Any, tokens: set[str]) -> list[str]:
    text = canonical_json(value)
    return sorted(token for token in tokens if token in text)


def _forbidden_field_hits(value: Any, policy: dict[str, Any]) -> list[str]:
    text = canonical_json(value)
    allowed = set(policy["respondent_allowed_labels"])
    forbidden_ids = {
        field_id
        for field_id, rule in policy["field_registry"].items()
        if rule["label"] not in allowed
    }
    return sorted(field_id for field_id in forbidden_ids if field_id in text)


def run_request_audit(
    contract: dict[str, Any],
    policy: dict[str, Any],
    output_dir: str | Path,
    *,
    model_snapshot: str = "DRY_RUN_MODEL_NOT_SELECTED",
    persona_seed: int = 1701,
    arm: str = "human_allocation",
) -> list[dict[str, Any]]:
    output = Path(output_dir)
    sendable_dir = output / "sendable"
    quarantine_dir = output / "quarantine"
    sendable_dir.mkdir(parents=True, exist_ok=True)
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    persona = PopulationBuilder.build(persona_seed)
    context = BuildContext(
        participant_id=persona["participant_id"],
        current_arm=arm,
        session_id="fresh-request-audit",
    )
    clean = clean_fields(contract, persona, arm)
    faults = build_fault_cases(clean, contract)
    architectures = make_architectures(contract, policy)
    adapter = OpenAIResponsesDryRunAdapter(model_snapshot=model_snapshot)
    canaries = set(contract["canaries"].values())

    d_clean_result = architectures[-1].build(faults[0].fields, context)
    d_clean_request = adapter.prepare(
        d_clean_result,
        study_id=contract["identity"]["study_id"],
        contract_version=contract["identity"]["contract_version"],
    )
    d_clean_visible_hash = d_clean_request.model_visible_hash

    rows: list[dict[str, Any]] = []
    for architecture in architectures:
        for fault in faults:
            packet_result = architecture.build(fault.fields, context)
            prepared = None
            preparation_error = ""
            try:
                prepared = adapter.prepare(
                    packet_result,
                    study_id=contract["identity"]["study_id"],
                    contract_version=contract["identity"]["contract_version"],
                )
            except RequestPreparationError as exc:
                preparation_error = str(exc)

            expected_block = fault.code == "F7"
            if prepared is None:
                request_canaries: list[str] = []
                model_canaries: list[str] = []
                forbidden_transport: list[str] = []
                forbidden_model: list[str] = []
                state_violations: list[str] = []
                matches_clean = False
                request_hash = ""
                model_visible_hash = ""
            else:
                request_canaries = _hits(prepared.body, canaries)
                model_canaries = _hits(prepared.model_visible_payload, canaries)
                forbidden_transport = _forbidden_field_hits(prepared.body, policy)
                forbidden_model = _forbidden_field_hits(
                    prepared.model_visible_payload, policy
                )
                state_violations = validate_stateless_request(prepared)
                matches_clean = prepared.model_visible_hash == d_clean_visible_hash
                request_hash = prepared.request_hash
                model_visible_hash = prepared.model_visible_hash

                filename = f"{architecture.name}__{fault.code}.json"
                safe_to_stage = (
                    architecture.name == "D_labeled_causal_firewall"
                    and not request_canaries
                    and not model_canaries
                    and not forbidden_transport
                    and not forbidden_model
                    and not state_violations
                    and matches_clean
                )
                target = (sendable_dir if safe_to_stage else quarantine_dir) / filename
                with target.open("w", encoding="utf-8") as handle:
                    json.dump(
                        {
                            "dry_run": True,
                            "network_enabled": False,
                            "provider": prepared.provider,
                            "endpoint": prepared.endpoint,
                            "request_hash": prepared.request_hash,
                            "model_visible_hash": prepared.model_visible_hash,
                            "body": prepared.body,
                        },
                        handle,
                        ensure_ascii=False,
                        sort_keys=True,
                        indent=2,
                    )
                    handle.write("\n")

            meets_request_standard = (
                prepared is None and expected_block
            ) or (
                prepared is not None
                and not expected_block
                and not request_canaries
                and not model_canaries
                and not forbidden_transport
                and not forbidden_model
                and not state_violations
                and matches_clean
            )
            rows.append(
                {
                    "study_id": contract["identity"]["study_id"],
                    "provider": adapter.provider,
                    "model_snapshot": model_snapshot,
                    "architecture": architecture.name,
                    "fault_code": fault.code,
                    "packet_status": packet_result.status,
                    "request_prepared": str(prepared is not None).lower(),
                    "preparation_error": preparation_error,
                    "request_hash": request_hash,
                    "model_visible_hash": model_visible_hash,
                    "matches_clean_firewall_visible_request": str(matches_clean).lower(),
                    "transport_canary_hits": "|".join(request_canaries),
                    "model_canary_hits": "|".join(model_canaries),
                    "transport_forbidden_fields": "|".join(forbidden_transport),
                    "model_forbidden_fields": "|".join(forbidden_model),
                    "state_violations": "|".join(state_violations),
                    "meets_request_standard": str(meets_request_standard).lower(),
                }
            )

    report = output / "provider_request_audit.csv"
    with report.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    d_rows = [
        row for row in rows if row["architecture"] == "D_labeled_causal_firewall"
    ]
    summary = {
        "study_id": contract["identity"]["study_id"],
        "provider": adapter.provider,
        "endpoint": adapter.endpoint,
        "model_snapshot": model_snapshot,
        "network_calls": 0,
        "request_rows": len(rows),
        "firewall_request_gates_passed": sum(
            row["meets_request_standard"] == "true" for row in d_rows
        ),
        "firewall_request_gates_total": len(d_rows),
        "clean_model_visible_hash": d_clean_visible_hash,
        "contract_hash": sha256_json(contract),
        "policy_hash": sha256_json(policy),
        "sendable_directory_rule": (
            "Only D requests with zero transport/model-visible violations are staged."
        ),
        "interpretation": (
            "Dry-run serialization evidence only. No provider accepted or executed "
            "these requests."
        ),
    }
    with (output / "provider_request_summary.json").open(
        "w", encoding="utf-8"
    ) as handle:
        json.dump(summary, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")
    return rows

