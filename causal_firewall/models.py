"""Shared immutable data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TaggedField:
    field_id: str
    value: Any
    label: str | None
    provenance: tuple[str, ...]
    stage: str
    arm_scope: str
    participant_id: str | None = None
    source_arm: str | None = None
    lineage_labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class BuildContext:
    participant_id: str
    current_arm: str
    stage: str = "behavior_generation"
    outcome_locked: bool = False
    session_id: str | None = None


@dataclass(frozen=True)
class PolicyDecision:
    field_id: str
    allowed: bool
    reason: str
    effective_label: str | None
    provenance: tuple[str, ...]


@dataclass(frozen=True)
class PacketBuildResult:
    status: str
    packet: dict[str, Any]
    packet_hash: str | None
    decisions: tuple[PolicyDecision, ...] = field(default_factory=tuple)
    missing_required: tuple[str, ...] = field(default_factory=tuple)

    @property
    def denied_fields(self) -> tuple[str, ...]:
        return tuple(d.field_id for d in self.decisions if not d.allowed)

    @property
    def allowed_fields(self) -> tuple[str, ...]:
        return tuple(d.field_id for d in self.decisions if d.allowed)

