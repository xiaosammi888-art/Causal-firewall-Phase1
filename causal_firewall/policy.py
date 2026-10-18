"""Deterministic information-flow policy engine."""

from __future__ import annotations

from typing import Any

from .models import BuildContext, PolicyDecision, TaggedField


class PolicyEngine:
    def __init__(self, policy: dict[str, Any]):
        self.policy = policy
        self.registry = policy["field_registry"]
        self.allowed_labels = set(policy["respondent_allowed_labels"])
        self.label_rank = policy["label_rank"]

    def effective_label(self, field: TaggedField) -> str | None:
        labels = [field.label, *field.lineage_labels]
        if any(label is None for label in labels):
            return None
        if not labels:
            return None
        unknown = [label for label in labels if label not in self.label_rank]
        if unknown:
            return None
        return max(labels, key=lambda label: self.label_rank[label])

    def decide(self, field: TaggedField, context: BuildContext) -> PolicyDecision:
        if field.field_id not in self.registry:
            return self._deny(field, "unknown_field", None)

        if field.label is None:
            return self._deny(field, "missing_label_fail_closed", None)

        effective = self.effective_label(field)
        if effective is None:
            return self._deny(field, "invalid_or_lost_lineage_label", None)

        registered = self.registry[field.field_id]
        declared_label = registered["label"]
        if declared_label not in self.label_rank:
            return self._deny(field, "registry_label_unknown", effective)

        # A field may become more restrictive through derivation, but it may
        # never become less restrictive than the registry declaration.
        if self.label_rank[effective] < self.label_rank[declared_label]:
            return self._deny(field, "label_downgrade", effective)
        if self.label_rank[declared_label] > self.label_rank[effective]:
            effective = declared_label

        if effective not in self.allowed_labels:
            return self._deny(field, "label_not_visible_to_respondent", effective)

        if context.outcome_locked:
            return self._deny(field, "respondent_write_after_outcome_lock", effective)

        scope_decision = self._check_scope(field, context)
        if scope_decision is not None:
            return self._deny(field, scope_decision, effective)

        return PolicyDecision(
            field_id=field.field_id,
            allowed=True,
            reason="allowed",
            effective_label=effective,
            provenance=field.provenance,
        )

    def _check_scope(self, field: TaggedField, context: BuildContext) -> str | None:
        expected_scope = self.registry[field.field_id]["arm_scope"]
        if field.arm_scope != expected_scope:
            return "scope_mismatch"
        if expected_scope == "current_arm" and field.source_arm != context.current_arm:
            return "wrong_arm"
        if expected_scope == "participant" and field.participant_id != context.participant_id:
            return "wrong_participant"
        if expected_scope in {"opposite_arm", "study", "session", "run"}:
            return "scope_not_visible_to_respondent"
        return None

    @staticmethod
    def _deny(
        field: TaggedField,
        reason: str,
        effective_label: str | None,
    ) -> PolicyDecision:
        return PolicyDecision(
            field_id=field.field_id,
            allowed=False,
            reason=reason,
            effective_label=effective_label,
            provenance=field.provenance,
        )

