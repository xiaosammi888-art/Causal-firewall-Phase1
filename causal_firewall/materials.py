"""Compile a frozen contract into tagged fields."""

from __future__ import annotations

from typing import Any

from .models import TaggedField


def clean_fields(
    contract: dict[str, Any],
    persona: dict[str, Any],
    arm: str,
) -> list[TaggedField]:
    participant_id = persona["participant_id"]
    materials = contract["materials"]
    return [
        TaggedField(
            field_id="participant_role",
            value=materials["participant_role"],
            label="PARTICIPANT_VISIBLE",
            provenance=("experiment_contract.materials.participant_role",),
            stage="behavior_generation",
            arm_scope="common",
        ),
        TaggedField(
            field_id="persona_state",
            value=persona,
            label="PARTICIPANT_SELF",
            provenance=("population_builder",),
            stage="pre_treatment",
            arm_scope="participant",
            participant_id=participant_id,
        ),
        TaggedField(
            field_id="common_scenario",
            value=materials["common_scenario"],
            label="PARTICIPANT_VISIBLE",
            provenance=("experiment_contract.materials.common_scenario",),
            stage="behavior_generation",
            arm_scope="common",
        ),
        TaggedField(
            field_id="current_stimulus",
            value=materials["arms"][arm]["stimulus"],
            label="PARTICIPANT_VISIBLE",
            provenance=(f"experiment_contract.materials.arms.{arm}.stimulus",),
            stage="behavior_generation",
            arm_scope="current_arm",
            source_arm=arm,
        ),
        TaggedField(
            field_id="response_schema",
            value={
                **materials["response_schema"],
                "properties": {
                    "choice": {
                        "type": "string",
                        "enum": materials["arms"][arm]["legal_choices"],
                    }
                },
            },
            label="PARTICIPANT_VISIBLE",
            provenance=("experiment_contract.materials.response_schema",),
            stage="behavior_generation",
            arm_scope="common",
        ),
    ]

