"""Evidence policy regression checks; Python-only, not Odoo runtime claims."""

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rules = load("evidence_rules", "plasticos_broker_intelligence/services/reasoning.py")
evidence = load("fact_rules", "plasticos_broker_intelligence/services/evidence.py")


class UnverifiedFactSafety(unittest.TestCase):
    def test_default_quantity_is_unknown_for_broker_action(self):
        fact = evidence.fact(36000, "recorded_default_possible", zero_ambiguous=True)
        result = rules.build_response("plasticos.intake", 7, "example", "", {"quantity_lbs": fact}, [])
        self.assertEqual(result["unknowns"], ["quantity_lbs"])
        self.assertTrue(result["abstentions"])
        self.assertTrue(any("quantity" in x.lower() for x in result["next_human_actions"]))

    def test_default_quantity_cannot_satisfy_prerequisite(self):
        item = {
            "state": "approved",
            "applies_to": "intake",
            "stable_key": "qty",
            "version": 1,
            "name": "Verify quantity first",
            "reviewed_meaning": "Quantity must be verified",
            "topic_tags": "quantity",
            "prerequisite_keys": "quantity_lbs",
            "source_file": "p",
            "source_sha256": "a" * 64,
            "source_selector": "row",
            "evidence_requirements": "verified scale ticket",
        }
        facts = {"quantity_lbs": evidence.fact(36000, "recorded_default_possible")}
        selected = rules.rank_approved("Verify quantity", facts, [item], "intake")
        self.assertEqual(selected[0][1], ["quantity_lbs"])

    def test_nonzero_unverified_quality_still_requires_observation(self):
        facts = {"moisture_pct": evidence.fact(0.5, "recorded_unverified")}
        output = rules.build_response("plasticos.intake", 1, "t", "moisture", facts, [])
        self.assertEqual(output["unknowns"], ["moisture_pct"])

    def test_missing_and_zero_moisture_have_no_inferred_measurement(self):
        for value in (None, False, 0, ""):
            self.assertIsNone(evidence.fact(value, "recorded_unverified", zero_ambiguous=True)["value"])


if __name__ == "__main__":
    unittest.main()
