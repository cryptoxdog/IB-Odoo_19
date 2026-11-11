"""Minimal self-tests and adversarial corruption witnesses for pack schema checks."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

root = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("validate_pack", root / "validate_pack.py")
assert spec and spec.loader
validate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validate)


class HarvestTests(unittest.TestCase):
    def test_schema_positive(self):
        self.assertEqual(validate.validate(), 0)

    def test_missing_case_id_rejected(self):
        vals = validate.lines("candidates/18_broker_capabilities.jsonl")
        vals[0]["source_refs"][0]["archive_member"] = "fictitious-source"
        files = {
            item["member"]: item["sha256"]
            for item in validate.data("evidence/source_identity.json")["archive_text_members"]
        }
        with self.assertRaises(AssertionError):
            validate.check_sources(vals, files)

    def test_wrong_digest_rejected(self):
        vals = validate.lines("candidates/12_rejection_meanings.jsonl")
        vals[0]["source"]["member_sha256"] = "0" * 64
        files = {
            item["member"]: item["sha256"]
            for item in validate.data("evidence/source_identity.json")["archive_text_members"]
        }
        with self.assertRaises(AssertionError):
            validate.check_sources(vals, files)

    def test_unknown_sop_never_admitted(self):
        coaches = validate.lines("candidates/56_coaching_scenarios.jsonl")
        self.assertEqual(len(coaches), 56)
        self.assertEqual(len({item["cluster_id"] for item in coaches}), 20)
        self.assertTrue(all(item["status"] == "CANDIDATE_ONLY" for item in coaches))

    def test_evaluation_is_not_a_claim_of_execution(self):
        tests = validate.lines("evaluation/adversarial_acceptance_cases.jsonl")
        self.assertTrue(all(item["status"] == "PROPOSED_NOT_RUN" for item in tests))


if __name__ == "__main__":
    unittest.main()
