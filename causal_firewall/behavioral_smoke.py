"""Build and audit the 24-cell behavioral-smoke request matrix offline."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .architectures import make_architectures
from .components import PopulationBuilder
from .hashing import canonical_json, sha256_json
from .materials import clean_fields
from .models import BuildContext, TaggedField
from .providers import OpenAIResponsesDryRunAdapter, validate_stateless_request


MODEL_SNAPSHOT = "gpt-5.4-mini-2026-03-17"
DRY_RUN_PERSONA_SEED = 1901


def cue_field(
    smoke_contract: dict[str, Any],
    *,
    architecture: str,
    cue: str,
) -> TaggedField | None:
    value = smoke_contract["cue_definitions"][cue]
    if value is None:
        return None
    field_id = smoke_contract["architecture_cue_carriers"][architecture]["field_id"]
    if field_id == "hypothesis_text":
        return TaggedField(
            field_id=field_id,
            value=value,
            label="RESEARCH_RESTRICTED",
            provenance=("experiment_contract.research_restricted.hypothesis_text",),
            stage="design",
            arm_scope="study",
        )
    if field_id == "handoff_history":
        return TaggedField(
            field_id=field_id,
            value=value,
            label="RESEARCH_RESTRICTED",
            provenance=("hypothesis_text", "agent_handoff"),
            stage="handoff",
            arm_scope="study",
            lineage_labels=("RESEARCH_RESTRICTED",),
        )
    if field_id == "summary_context":
        return TaggedField(
            field_id=field_id,
            value=value,
            label="PARTICIPANT_VISIBLE",
            provenance=("hypothesis_text", "summary_agent"),
            stage="handoff",
            arm_scope="study",
            lineage_labels=("RESEARCH_RESTRICTED",),
        )
    raise ValueError(f"unsupported_cue_carrier:{field_id}")


def run_architecture_request_dry_run(
    contract: dict[str, Any],
    policy: dict[str, Any],
    smoke_contract: dict[str, Any],
    output_root: str | Path,
) -> Path:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = Path(output_root) / run_id
    requests_dir = output / "requests"
    requests_dir.mkdir(parents=True, exist_ok=False)

    persona = PopulationBuilder.build(DRY_RUN_PERSONA_SEED)
    architectures = {item.name: item for item in make_architectures(contract, policy)}
    adapter = OpenAIResponsesDryRunAdapter(model_snapshot=MODEL_SNAPSHOT)
    rows: list[dict[str, Any]] = []

    for arm in smoke_contract["factors"]["arms"]:
        context = BuildContext(
            participant_id=persona["participant_id"],
            current_arm=arm,
            session_id=f"behavioral-smoke-dry-run-{run_id}-{arm}",
        )
        for cue in smoke_contract["factors"]["hypothesis_cues"]:
            for architecture_name in smoke_contract["factors"]["architectures"]:
                fields = clean_fields(contract, persona, arm)
                extra = cue_field(
                    smoke_contract,
                    architecture=architecture_name,
                    cue=cue,
                )
                if extra is not None:
                    fields.append(extra)
                result = architectures[architecture_name].build(fields, context)
                if result.status != "ready":
                    raise RuntimeError(
                        f"dry_run_packet_blocked:{arm}:{cue}:{architecture_name}"
                    )
                prepared = adapter.prepare(
                    result,
                    study_id=contract["identity"]["study_id"],
                    contract_version=contract["identity"]["contract_version"],
                )
                body = copy.deepcopy(prepared.body)
                body["metadata"].update(
                    {
                        "run_class": "architecture_request_dry_run",
                        "architecture": architecture_name,
                        "cue": cue,
                    }
                )
                serialized_visible = canonical_json(prepared.model_visible_payload)
                canary_present = contract["canaries"]["hypothesis"] in serialized_visible
                carrier = smoke_contract["architecture_cue_carriers"][architecture_name][
                    "field_id"
                ]
                carrier_present = carrier in result.packet
                state_violations = validate_stateless_request(prepared)
                row = {
                    "study_id": contract["identity"]["study_id"],
                    "run_id": run_id,
                    "arm": arm,
                    "cue": cue,
                    "architecture": architecture_name,
                    "carrier_field": carrier,
                    "carrier_present": carrier_present,
                    "canary_present": canary_present,
                    "packet_hash": result.packet_hash,
                    "model_visible_hash": prepared.model_visible_hash,
                    "request_hash": sha256_json(body),
                    "state_violations": state_violations,
                }
                rows.append(row)
                filename = f"{arm}__{cue}__{architecture_name}.json"
                with (requests_dir / filename).open("w", encoding="utf-8") as handle:
                    json.dump(
                        {
                            "dry_run": True,
                            "network_calls": 0,
                            "audit": row,
                            "body": body,
                        },
                        handle,
                        ensure_ascii=False,
                        sort_keys=True,
                        indent=2,
                    )
                    handle.write("\n")

    gates: dict[str, bool] = {}
    gates["cell_count_24"] = len(rows) == 24
    gates["all_stateless"] = all(not row["state_violations"] for row in rows)

    no_cue = [row for row in rows if row["cue"] == "none"]
    no_cue_groups: dict[str, set[str]] = {}
    for row in no_cue:
        no_cue_groups.setdefault(row["arm"], set()).add(row["model_visible_hash"])
    gates["no_cue_byte_equivalence"] = all(
        len(hashes) == 1 for hashes in no_cue_groups.values()
    )

    d_rows = [
        row for row in rows if row["architecture"] == "D_labeled_causal_firewall"
    ]
    d_hashes: dict[str, set[str]] = {}
    for row in d_rows:
        d_hashes.setdefault(row["arm"], set()).add(row["model_visible_hash"])
    gates["d_cue_hash_invariance"] = all(
        len(hashes) == 1 for hashes in d_hashes.values()
    )
    gates["d_zero_canary"] = all(not row["canary_present"] for row in d_rows)
    gates["d_zero_carrier"] = all(not row["carrier_present"] for row in d_rows)

    exposed_rows = [
        row
        for row in rows
        if row["architecture"] != "D_labeled_causal_firewall"
        and row["cue"] != "none"
    ]
    gates["abc_cues_reachable"] = all(
        row["canary_present"] and row["carrier_present"] for row in exposed_rows
    )

    summary = {
        "study_id": contract["identity"]["study_id"],
        "run_id": run_id,
        "run_class": "architecture_request_dry_run",
        "network_calls": 0,
        "model_snapshot": MODEL_SNAPSHOT,
        "persona_seed": DRY_RUN_PERSONA_SEED,
        "cells": len(rows),
        "gates": gates,
        "gates_passed": sum(gates.values()),
        "gates_total": len(gates),
        "ready_for_paid_matrix_probe": all(gates.values()),
        "smoke_contract_hash": sha256_json(smoke_contract),
        "experiment_contract_hash": sha256_json(contract),
        "policy_hash": sha256_json(policy),
    }
    with (output / "manifest.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    with (output / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")
    return output

