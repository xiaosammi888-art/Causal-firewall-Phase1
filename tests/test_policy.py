from __future__ import annotations

import unittest

from causal_firewall.models import BuildContext, TaggedField
from causal_firewall.policy import PolicyEngine

from support import load_configs


class PolicyTests(unittest.TestCase):
    def setUp(self):
        _, policy = load_configs()
        self.engine = PolicyEngine(policy)
        self.context = BuildContext(participant_id="P-1", current_arm="human_allocation")

    def test_visible_current_arm_field_is_allowed(self):
        field = TaggedField(
            field_id="current_stimulus",
            value="legal",
            label="PARTICIPANT_VISIBLE",
            provenance=("source_material",),
            stage="behavior_generation",
            arm_scope="current_arm",
            source_arm="human_allocation",
        )
        self.assertTrue(self.engine.decide(field, self.context).allowed)

    def test_wrong_arm_is_denied(self):
        field = TaggedField(
            field_id="current_stimulus",
            value="other arm",
            label="PARTICIPANT_VISIBLE",
            provenance=("source_material",),
            stage="behavior_generation",
            arm_scope="current_arm",
            source_arm="random_allocation",
        )
        decision = self.engine.decide(field, self.context)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "wrong_arm")

    def test_restricted_lineage_cannot_be_downgraded(self):
        field = TaggedField(
            field_id="summary_context",
            value="hidden hypothesis",
            label="PARTICIPANT_VISIBLE",
            provenance=("hypothesis_text", "summary_agent"),
            stage="handoff",
            arm_scope="study",
            lineage_labels=("RESEARCH_RESTRICTED",),
        )
        decision = self.engine.decide(field, self.context)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.effective_label, "RESEARCH_RESTRICTED")

    def test_missing_label_fails_closed(self):
        field = TaggedField(
            field_id="common_scenario",
            value="scenario",
            label=None,
            provenance=("source_material",),
            stage="behavior_generation",
            arm_scope="common",
        )
        decision = self.engine.decide(field, self.context)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "missing_label_fail_closed")


if __name__ == "__main__":
    unittest.main()

