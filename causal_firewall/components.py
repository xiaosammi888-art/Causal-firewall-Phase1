"""Deterministic Study 0 components."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Iterable

from .hashing import sha256_json
from .models import BuildContext, PacketBuildResult, PolicyDecision, TaggedField
from .policy import PolicyEngine


class Randomizer:
    ARMS = ("human_allocation", "random_allocation")

    @staticmethod
    def assign(assignment_seed: int) -> str:
        return random.Random(assignment_seed).choice(Randomizer.ARMS)


class PopulationBuilder:
    """Generate the persona before treatment assignment and make it replayable."""

    @staticmethod
    def build(persona_seed: int) -> dict[str, Any]:
        participant_id = f"P-{persona_seed:08d}"
        return {
            "participant_id": participant_id,
            "adult": True,
            "decision_context": "anonymous_one_shot",
            "persona_seed": persona_seed,
        }

    @staticmethod
    def pre_treatment_hash(persona: dict[str, Any]) -> str:
        return sha256_json(persona)


class PacketBuilder:
    def __init__(
        self,
        contract: dict[str, Any],
        policy_engine: PolicyEngine,
    ):
        self.contract = contract
        self.policy_engine = policy_engine
        packet = contract["participant_packet"]
        self.ordered_fields = tuple(packet["ordered_fields"])
        self.required_fields = tuple(packet["required_fields"])

    def build(
        self,
        fields: Iterable[TaggedField],
        context: BuildContext,
    ) -> PacketBuildResult:
        decisions: list[PolicyDecision] = []
        visible: dict[str, Any] = {}
        for field in fields:
            decision = self.policy_engine.decide(field, context)
            decisions.append(decision)
            if decision.allowed:
                if field.field_id in visible:
                    decisions.append(
                        PolicyDecision(
                            field_id=field.field_id,
                            allowed=False,
                            reason="duplicate_field_fail_closed",
                            effective_label=decision.effective_label,
                            provenance=field.provenance,
                        )
                    )
                    visible.pop(field.field_id, None)
                    continue
                visible[field.field_id] = field.value

        missing = tuple(name for name in self.required_fields if name not in visible)
        if missing:
            return PacketBuildResult(
                status="blocked",
                packet={},
                packet_hash=None,
                decisions=tuple(decisions),
                missing_required=missing,
            )

        packet = {name: visible[name] for name in self.ordered_fields}
        return PacketBuildResult(
            status="ready",
            packet=packet,
            packet_hash=sha256_json(packet),
            decisions=tuple(decisions),
        )


@dataclass
class OutcomeLock:
    legal_choices: set[str]
    coding: dict[str, int]
    _choice: str | None = None
    _discard_reward: int | None = None

    @property
    def locked(self) -> bool:
        return self._choice is not None

    def commit(self, choice: str) -> dict[str, int | str]:
        if self.locked:
            raise RuntimeError("outcome_already_locked")
        if choice not in self.legal_choices:
            raise ValueError("illegal_choice")
        self._choice = choice
        self._discard_reward = self.coding[choice]
        return self.snapshot()

    def snapshot(self) -> dict[str, int | str]:
        if not self.locked:
            raise RuntimeError("outcome_not_locked")
        return {
            "choice": self._choice,  # type: ignore[dict-item]
            "discard_reward": self._discard_reward,  # type: ignore[dict-item]
        }

    def attempt_modify(self, choice: str, actor: str) -> None:
        raise RuntimeError(f"outcome_locked:{actor}:{choice}")

