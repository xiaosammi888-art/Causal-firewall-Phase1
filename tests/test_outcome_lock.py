from __future__ import annotations

import unittest

from causal_firewall.components import OutcomeLock


class OutcomeLockTests(unittest.TestCase):
    def setUp(self):
        self.lock = OutcomeLock(
            legal_choices={"tal", "gal", "discard"},
            coding={"tal": 0, "gal": 0, "discard": 1},
        )

    def test_choice_is_deterministically_encoded(self):
        self.assertEqual(
            self.lock.commit("discard"),
            {"choice": "discard", "discard_reward": 1},
        )

    def test_second_commit_is_rejected(self):
        self.lock.commit("tal")
        with self.assertRaisesRegex(RuntimeError, "outcome_already_locked"):
            self.lock.commit("discard")

    def test_retry_audit_and_analysis_cannot_modify(self):
        original = self.lock.commit("gal")
        for actor in ("retry", "audit", "analysis"):
            with self.subTest(actor=actor):
                with self.assertRaisesRegex(RuntimeError, "outcome_locked"):
                    self.lock.attempt_modify("discard", actor)
                self.assertEqual(self.lock.snapshot(), original)


if __name__ == "__main__":
    unittest.main()

