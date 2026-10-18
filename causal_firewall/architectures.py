"""Architectures A-D used in Study 0."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterable

from .hashing import sha256_json
from .models import BuildContext, PacketBuildResult, PolicyDecision, TaggedField
from .policy import PolicyEngine
from .components import PacketBuilder


class Architecture(ABC):
    name: str

    @abstractmethod
    def build(
        self,
        fields: Iterable[TaggedField],
        context: BuildContext,
    ) -> PacketBuildResult:
        raise NotImplementedError


class UncontrolledArchitecture(Architecture):
    """A/B: all handoff fields enter the model-visible packet."""

    def __init__(self, name: str):
        self.name = name

    def build(self, fields: Iterable[TaggedField], context: BuildContext) -> PacketBuildResult:
        del context
        packet: dict[str, Any] = {}
        decisions: list[PolicyDecision] = []
        for field in fields:
            packet[field.field_id] = field.value
            decisions.append(
                PolicyDecision(
                    field_id=field.field_id,
                    allowed=True,
                    reason="no_enforcement",
                    effective_label=field.label,
                    provenance=field.provenance,
                )
            )
        return PacketBuildResult(
            status="ready",
            packet=packet,
            packet_hash=sha256_json(packet),
            decisions=tuple(decisions),
        )


class ManualWhitelistArchitecture(Architecture):
    """C: fresh context plus field-name whitelist, without label inheritance."""

    name = "C_fresh_context_manual_whitelist"

    def __init__(self, contract: dict[str, Any]):
        self.ordered = tuple(contract["participant_packet"]["ordered_fields"])
        self.required = tuple(contract["participant_packet"]["required_fields"])
        # These operational fields represent plausible whitelist growth during
        # maintenance. C checks names but cannot inspect inherited provenance.
        self.whitelist = set(self.ordered) | {
            "handoff_history",
            "summary_context",
            "session_context",
            "retry_context",
            "tool_context",
            "audit_feedback",
        }

    def build(self, fields: Iterable[TaggedField], context: BuildContext) -> PacketBuildResult:
        del context
        visible: dict[str, Any] = {}
        decisions: list[PolicyDecision] = []
        for field in fields:
            allowed = field.field_id in self.whitelist
            decisions.append(
                PolicyDecision(
                    field_id=field.field_id,
                    allowed=allowed,
                    reason="manual_whitelist" if allowed else "not_whitelisted",
                    effective_label=field.label,
                    provenance=field.provenance,
                )
            )
            if allowed:
                visible[field.field_id] = field.value
        missing = tuple(name for name in self.required if name not in visible)
        if missing:
            return PacketBuildResult(
                status="blocked",
                packet={},
                packet_hash=None,
                decisions=tuple(decisions),
                missing_required=missing,
            )
        packet = {name: visible[name] for name in self.ordered}
        for name in sorted(visible.keys() - set(self.ordered)):
            packet[name] = visible[name]
        return PacketBuildResult(
            status="ready",
            packet=packet,
            packet_hash=sha256_json(packet),
            decisions=tuple(decisions),
        )


class FirewallArchitecture(Architecture):
    name = "D_labeled_causal_firewall"

    def __init__(self, contract: dict[str, Any], policy: dict[str, Any]):
        self.builder = PacketBuilder(contract, PolicyEngine(policy))

    def build(self, fields: Iterable[TaggedField], context: BuildContext) -> PacketBuildResult:
        return self.builder.build(fields, context)


def make_architectures(
    contract: dict[str, Any],
    policy: dict[str, Any],
) -> tuple[Architecture, ...]:
    return (
        UncontrolledArchitecture("A_monolithic_prompt"),
        UncontrolledArchitecture("B_default_multi_agent"),
        ManualWhitelistArchitecture(contract),
        FirewallArchitecture(contract, policy),
    )

