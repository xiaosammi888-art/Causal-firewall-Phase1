"""Generate and audit the redesigned 288-row behavioral-smoke plan offline."""

from __future__ import annotations

import copy
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .architectures import make_architectures
from .behavioral_smoke import cue_field
from .components import PopulationBuilder
from .hashing import canonical_json, sha256_json
from .materials import clean_fields
from .models import BuildContext
from .providers import OpenAIResponsesDryRunAdapter, validate_stateless_request


MODEL_SNAPSHOT = "gpt-5.4-mini-2026-03-17"


def _inference_payload(body: dict[str, Any]) -> dict[str, Any]:
    """Return all behavior-affecting request fields, excluding audit metadata."""

    return {key: value for key, value in body.items() if key != "metadata"}


def run_behavioral_smoke_v2_dry_run(
    contract: dict[str, Any],
    policy: dict[str, Any],
    smoke_contract: dict[str, Any],
    output_root: str | Path,
) -> Path:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = Path(output_root) / run_id
    output.mkdir(parents=True, exist_ok=False)

    sampling = smoke_contract["sampling"]
    persona = PopulationBuilder.build(sampling["canonical_persona_seed"])
    architectures = {item.name: item for item in make_architectures(contract, policy)}
    adapter = OpenAIResponsesDryRunAdapter(
        model_snapshot=MODEL_SNAPSHOT,
        temperature=float(smoke_contract["model"]["temperature"]),
    )

    templates: dict[tuple[str, str, str], dict[str, Any]] = {}
    for arm in smoke_contract["factors"]["arms"]:
        context = BuildContext(
            participant_id=persona["participant_id"],
            current_arm=arm,
            session_id=f"behavioral-smoke-v2-dry-run-{run_id}-{arm}",
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
                        f"v2_dry_run_packet_blocked:{arm}:{cue}:{architecture_name}"
                    )
                prepared = adapter.prepare(
                    result,
                    study_id=contract["identity"]["study_id"],
                    contract_version=contract["identity"]["contract_version"],
                )
                body = copy.deepcopy(prepared.body)
                body["metadata"].update(
                    {
                        "run_class": "behavioral_smoke_v2_dry_run",
                        "architecture": architecture_name,
                        "cue": cue,
                    }
                )
                carrier = smoke_contract["architecture_cue_carriers"][
                    architecture_name
                ]["field_id"]
                serialized_visible = canonical_json(prepared.model_visible_payload)
                templates[(arm, cue, architecture_name)] = {
                    "body": body,
                    "packet_hash": result.packet_hash,
                    "model_visible_hash": prepared.model_visible_hash,
                    "inference_payload_hash": sha256_json(_inference_payload(body)),
                    "carrier_field": carrier,
                    "carrier_present": carrier in result.packet,
                    "canary_present": contract["canaries"]["hypothesis"]
                    in serialized_visible,
                    "state_violations": validate_stateless_request(prepared),
                }

    schedule = [
        (replicate_id, arm, cue, architecture)
        for replicate_id in range(1, sampling["replicates_per_cell"] + 1)
        for arm in smoke_contract["factors"]["arms"]
        for cue in smoke_contract["factors"]["hypothesis_cues"]
        for architecture in smoke_contract["factors"]["architectures"]
    ]
    random.Random(sampling["call_order_seed"]).shuffle(schedule)

    rows: list[dict[str, Any]] = []
    request_path = output / "scheduled_requests.jsonl"
    with request_path.open("w", encoding="utf-8") as request_handle:
        for sequence, (replicate_id, arm, cue, architecture) in enumerate(
            schedule, start=1
        ):
            template = templates[(arm, cue, architecture)]
            body = copy.deepcopy(template["body"])
            body["metadata"].update(
                {
                    "dry_run": "true",
                    "run_id": run_id,
                    "sequence": str(sequence),
                    "replicate_id": str(replicate_id),
                }
            )
            row = {
                "sequence": sequence,
                "replicate_id": replicate_id,
                "arm": arm,
                "cue": cue,
                "architecture": architecture,
                "packet_hash": template["packet_hash"],
                "model_visible_hash": template["model_visible_hash"],
                "inference_payload_hash": template["inference_payload_hash"],
                "request_hash": sha256_json(body),
                "carrier_field": template["carrier_field"],
                "carrier_present": template["carrier_present"],
                "canary_present": template["canary_present"],
                "state_violations": template["state_violations"],
                "replicate_id_model_visible": False,
            }
            rows.append(row)
            request_handle.write(
                json.dumps(
                    {"dry_run": True, "network_calls": 0, "audit": row, "body": body},
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )

    cells: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (row["arm"], row["cue"], row["architecture"])
        cells.setdefault(key, []).append(row)

    d_by_arm: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row["architecture"] == "D_labeled_causal_firewall":
            d_by_arm.setdefault(row["arm"], []).append(row)

    no_cue_by_arm: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row["cue"] == "none":
            no_cue_by_arm.setdefault(row["arm"], []).append(row)

    exposed = [
        row
        for row in rows
        if row["architecture"] != "D_labeled_causal_firewall"
        and row["cue"] != "none"
    ]
    gates = {
        "scheduled_rows_288": len(rows) == 288,
        "design_cells_24": len(cells) == 24,
        "twelve_rows_per_cell": all(len(cell_rows) == 12 for cell_rows in cells.values()),
        "one_inference_hash_per_cell": all(
            len({row["inference_payload_hash"] for row in cell_rows}) == 1
            for cell_rows in cells.values()
        ),
        "replicate_ids_not_model_visible": all(
            not row["replicate_id_model_visible"] for row in rows
        ),
        "all_stateless": all(not row["state_violations"] for row in rows),
        "temperature_frozen": all(
            item["body"].get("temperature")
            == float(smoke_contract["model"]["temperature"])
            for item in templates.values()
        ),
        "d_inference_hash_invariant_across_cues": all(
            len({row["inference_payload_hash"] for row in arm_rows}) == 1
            for arm_rows in d_by_arm.values()
        ),
        "d_zero_canary": all(not row["canary_present"] for rows_ in d_by_arm.values() for row in rows_),
        "d_zero_carrier": all(not row["carrier_present"] for rows_ in d_by_arm.values() for row in rows_),
        "abc_cues_reachable": all(
            row["canary_present"] and row["carrier_present"] for row in exposed
        ),
        "no_cue_equivalent_across_architectures": all(
            len({row["inference_payload_hash"] for row in arm_rows}) == 1
            for arm_rows in no_cue_by_arm.values()
        ),
    }

    probe_cost = 0.006183
    projected_cost = probe_cost * (len(rows) / 24)
    summary = {
        "study_id": contract["identity"]["study_id"],
        "run_id": run_id,
        "run_class": "behavioral_smoke_v2_dry_run",
        "network_calls": 0,
        "model_snapshot": MODEL_SNAPSHOT,
        "temperature": smoke_contract["model"]["temperature"],
        "sampling_unit": sampling["unit"],
        "canonical_persona_seed": sampling["canonical_persona_seed"],
        "scheduled_rows": len(rows),
        "design_cells": len(cells),
        "unique_model_visible_hashes": len(
            {row["model_visible_hash"] for row in rows}
        ),
        "unique_inference_payload_hashes": len(
            {row["inference_payload_hash"] for row in rows}
        ),
        "gates": gates,
        "gates_passed": sum(gates.values()),
        "gates_total": len(gates),
        "ready_for_temperature_compatibility_gate": all(gates.values()),
        "projected_cost_from_24_call_probe_usd": round(projected_cost, 6),
        "projected_cost_with_2x_safety_factor_usd": round(projected_cost * 2, 6),
        "paid_cost_cap_usd": smoke_contract["phases"]["behavioral_smoke_v2"][
            "estimated_cost_cap_usd"
        ],
        "smoke_contract_hash": sha256_json(smoke_contract),
        "experiment_contract_hash": sha256_json(contract),
        "policy_hash": sha256_json(policy),
    }
    (output / "manifest.jsonl").write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
        ),
        encoding="utf-8",
    )
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return output
