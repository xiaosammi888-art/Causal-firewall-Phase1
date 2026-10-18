from __future__ import annotations

import json
import unittest

from causal_firewall.architectures import make_architectures
from causal_firewall.components import PopulationBuilder
from causal_firewall.faults import build_fault_cases
from causal_firewall.materials import clean_fields
from causal_firewall.models import BuildContext

from support import load_configs


class FaultTests(unittest.TestCase):
    def setUp(self):
        self.contract, self.policy = load_configs()
        self.persona = PopulationBuilder.build(1701)
        self.arm = "human_allocation"
        self.fields = clean_fields(self.contract, self.persona, self.arm)
        self.context = BuildContext(
            participant_id=self.persona["participant_id"],
            current_arm=self.arm,
            session_id="fresh-test",
        )
        self.architectures = make_architectures(self.contract, self.policy)
        self.c_arch = self.architectures[2]
        self.d_arch = self.architectures[3]
        self.faults = build_fault_cases(self.fields, self.contract)

    def test_clean_c_and_d_packets_are_byte_equivalent(self):
        clean = self.faults[0]
        c_result = self.c_arch.build(clean.fields, self.context)
        d_result = self.d_arch.build(clean.fields, self.context)
        self.assertEqual(c_result.status, "ready")
        self.assertEqual(d_result.status, "ready")
        self.assertEqual(c_result.packet, d_result.packet)
        self.assertEqual(c_result.packet_hash, d_result.packet_hash)

    def test_firewall_blocks_all_injected_information(self):
        clean_result = self.d_arch.build(self.faults[0].fields, self.context)
        serialized_canaries = set(self.contract["canaries"].values())
        for fault in self.faults[1:7]:
            with self.subTest(fault=fault.code):
                result = self.d_arch.build(fault.fields, self.context)
                self.assertEqual(result.status, "ready")
                self.assertEqual(result.packet_hash, clean_result.packet_hash)
                packet = json.dumps(result.packet, sort_keys=True)
                self.assertFalse(any(token in packet for token in serialized_canaries))

    def test_label_loss_fails_closed(self):
        result = self.d_arch.build(self.faults[7].fields, self.context)
        self.assertEqual(result.status, "blocked")
        self.assertIn("common_scenario", result.missing_required)

    def test_labels_add_protection_beyond_manual_whitelist(self):
        c_failures = 0
        d_failures = 0
        clean_hash = self.d_arch.build(self.faults[0].fields, self.context).packet_hash
        for fault in self.faults[1:7]:
            c_result = self.c_arch.build(fault.fields, self.context)
            d_result = self.d_arch.build(fault.fields, self.context)
            c_failures += c_result.packet_hash != clean_hash
            d_failures += d_result.packet_hash != clean_hash
        self.assertGreater(c_failures, d_failures)
        self.assertEqual(d_failures, 0)


if __name__ == "__main__":
    unittest.main()

