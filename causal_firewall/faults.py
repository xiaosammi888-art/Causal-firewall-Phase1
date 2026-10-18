"""Pre-registered F0-F7 workflow faults."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .models import TaggedField


@dataclass(frozen=True)
class FaultCase:
    code: str
    name: str
    fields: tuple[TaggedField, ...]
    expected_firewall_status: str


def build_fault_cases(
    clean: list[TaggedField],
    contract: dict[str, Any],
) -> tuple[FaultCase, ...]:
    canaries = contract["canaries"]

    def injected(
        field_id: str,
        value: Any,
        label: str,
        provenance: tuple[str, ...],
        stage: str,
        scope: str,
        lineage: tuple[str, ...] = (),
    ) -> TaggedField:
        return TaggedField(
            field_id=field_id,
            value=value,
            label=label,
            provenance=provenance,
            stage=stage,
            arm_scope=scope,
            lineage_labels=lineage,
        )

    cases = [
        FaultCase("F0", "clean", tuple(clean), "ready"),
        FaultCase(
            "F1",
            "shared_history",
            tuple(clean)
            + (
                injected(
                    "handoff_history",
                    f"Opposite-arm material {canaries['other_arm']}",
                    "RESEARCH_RESTRICTED",
                    ("other_arm_stimulus", "handoff_memory"),
                    "handoff",
                    "opposite_arm",
                ),
            ),
            "ready",
        ),
        FaultCase(
            "F2",
            "summary_contamination",
            tuple(clean)
            + (
                injected(
                    "summary_context",
                    f"Expected direction embedded in summary {canaries['hypothesis']}",
                    "PARTICIPANT_VISIBLE",
                    ("hypothesis_text", "summary_agent"),
                    "handoff",
                    "study",
                    lineage=("RESEARCH_RESTRICTED",),
                ),
            ),
            "ready",
        ),
        FaultCase(
            "F3",
            "session_reuse",
            tuple(clean)
            + (
                injected(
                    "session_context",
                    "Reused session contains a prior arm transcript CFSESSION3",
                    "SYSTEM_ONLY",
                    ("execution_manager", "prior_session"),
                    "execution",
                    "session",
                ),
            ),
            "ready",
        ),
        FaultCase(
            "F4",
            "retry_contamination",
            tuple(clean)
            + (
                injected(
                    "retry_context",
                    "Retry carries the previous response and prior context CFRETRY4",
                    "SYSTEM_ONLY",
                    ("retry_manager", "failed_attempt"),
                    "execution",
                    "session",
                ),
            ),
            "ready",
        ),
        FaultCase(
            "F5",
            "tool_leakage",
            tuple(clean)
            + (
                injected(
                    "tool_context",
                    f"Human benchmark returned by tool {canaries['human_benchmark']}",
                    "PARTICIPANT_VISIBLE",
                    ("human_benchmark", "tool_result"),
                    "execution",
                    "study",
                    lineage=("EMBARGOED_RESULT",),
                ),
            ),
            "ready",
        ),
        FaultCase(
            "F6",
            "auditor_backflow",
            tuple(clean)
            + (
                injected(
                    "audit_feedback",
                    "Auditor reports a likely policy violation CFAUDIT6",
                    "AUDIT_ONLY",
                    ("leakage_auditor",),
                    "audit_after_lock",
                    "run",
                ),
            ),
            "ready",
        ),
    ]

    label_loss_fields = tuple(
        replace(field, label=None)
        if field.field_id == "common_scenario"
        else field
        for field in clean
    )
    cases.append(
        FaultCase(
            "F7",
            "label_loss",
            label_loss_fields,
            "blocked",
        )
    )
    return tuple(cases)

