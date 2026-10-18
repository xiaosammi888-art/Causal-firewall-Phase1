from __future__ import annotations

import unittest

from causal_firewall.components import PopulationBuilder
from causal_firewall.hashing import sha256_json

from support import load_configs


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.contract, self.policy = load_configs()

    def test_required_packet_fields_are_registered(self):
        required = set(self.contract["participant_packet"]["required_fields"])
        registered = set(self.policy["field_registry"])
        self.assertLessEqual(required, registered)

    def test_outcome_coding_covers_all_legal_choices(self):
        legal = {
            choice
            for arm in self.contract["materials"]["arms"].values()
            for choice in arm["legal_choices"]
        }
        coding = set(self.contract["outcomes"]["discard_reward"]["coding"])
        self.assertEqual(legal, coding)

    def test_persona_hash_is_arm_invariant(self):
        persona = PopulationBuilder.build(42)
        human_hash = PopulationBuilder.pre_treatment_hash(persona)
        random_hash = PopulationBuilder.pre_treatment_hash(persona)
        self.assertEqual(human_hash, random_hash)
        self.assertEqual(human_hash, sha256_json(persona))

    def test_normalized_source_material_is_hash_locked(self):
        material_hash = self.contract["source"]["normalized_material_sha256"]
        self.assertEqual(len(material_hash), 64)
        int(material_hash, 16)


if __name__ == "__main__":
    unittest.main()
