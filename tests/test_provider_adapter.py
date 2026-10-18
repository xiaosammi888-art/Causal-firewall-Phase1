from __future__ import annotations

import json
import unittest

from causal_firewall.architectures import make_architectures
from causal_firewall.components import PopulationBuilder
from causal_firewall.faults import build_fault_cases
from causal_firewall.materials import clean_fields
from causal_firewall.models import BuildContext
from causal_firewall.providers import (
    OpenAIResponsesDryRunAdapter,
    RequestPreparationError,
    validate_stateless_request,
)

from support import load_configs


class ProviderAdapterTests(unittest.TestCase):
    def setUp(self):
        self.contract, self.policy = load_configs()
        persona = PopulationBuilder.build(1701)
        self.context = BuildContext(
            participant_id=persona["participant_id"],
            current_arm="human_allocation",
        )
        clean = clean_fields(self.contract, persona, "human_allocation")
        self.faults = build_fault_cases(clean, self.contract)
        self.architectures = make_architectures(self.contract, self.policy)
        self.adapter = OpenAIResponsesDryRunAdapter()

    def _prepare_d(self, fault_index: int):
        result = self.architectures[-1].build(
            self.faults[fault_index].fields, self.context
        )
        return self.adapter.prepare(
            result,
            study_id=self.contract["identity"]["study_id"],
            contract_version=self.contract["identity"]["contract_version"],
        )

    def test_request_is_stateless_and_tool_free(self):
        prepared = self._prepare_d(0)
        self.assertEqual(validate_stateless_request(prepared), [])
        self.assertFalse(prepared.network_enabled)
        self.assertNotIn("previous_response_id", prepared.body)
        self.assertNotIn("conversation", prepared.body)

    def test_structured_output_schema_is_preserved(self):
        prepared = self._prepare_d(0)
        format_spec = prepared.body["text"]["format"]
        self.assertEqual(format_spec["type"], "json_schema")
        self.assertTrue(format_spec["strict"])
        self.assertEqual(format_spec["schema"]["required"], ["choice"])
        self.assertFalse(format_spec["schema"]["additionalProperties"])

    def test_firewall_request_is_invariant_under_f1_to_f6(self):
        clean = self._prepare_d(0)
        for index in range(1, 7):
            with self.subTest(fault=self.faults[index].code):
                prepared = self._prepare_d(index)
                self.assertEqual(
                    prepared.model_visible_hash,
                    clean.model_visible_hash,
                )

    def test_no_canary_reaches_firewall_request(self):
        tokens = set(self.contract["canaries"].values())
        for index in range(0, 7):
            with self.subTest(fault=self.faults[index].code):
                prepared = self._prepare_d(index)
                serialized = json.dumps(prepared.body, sort_keys=True)
                self.assertFalse(any(token in serialized for token in tokens))

    def test_blocked_packet_cannot_be_serialized(self):
        result = self.architectures[-1].build(self.faults[7].fields, self.context)
        with self.assertRaisesRegex(RequestPreparationError, "packet_not_sendable"):
            self.adapter.prepare(
                result,
                study_id=self.contract["identity"]["study_id"],
                contract_version=self.contract["identity"]["contract_version"],
            )


if __name__ == "__main__":
    unittest.main()

