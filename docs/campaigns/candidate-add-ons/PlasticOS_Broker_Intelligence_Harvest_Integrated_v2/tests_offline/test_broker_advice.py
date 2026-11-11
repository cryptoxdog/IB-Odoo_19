"""Executable source-level domain contract tests without an Odoo database.

These tests DO NOT claim Odoo ORM, registry or UI installation validation.
"""
import importlib.util
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, BASE / relative)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


reasoning = module("broker_reasoning", "plasticos_broker_intelligence/services/reasoning.py")
evidence = module("broker_evidence", "plasticos_broker_intelligence/services/evidence.py")
shadow = module("broker_shadow", "plasticos_broker_intelligence_web_leads/services/shadow.py")
rejection = module("broker_rejection", "plasticos_broker_intelligence_rejections/services/rejection.py")


class AdviceSafetyTest(unittest.TestCase):
    def setUp(self):
        self.facts = {"polymer": evidence.fact("PP", "reported"),
                      "mfi_value": evidence.fact(0.0, "recorded", zero_ambiguous=True),
                      "mfi_conditions": evidence.fact(None, "unavailable"),
                      "buyer_spec": evidence.fact(None, "unavailable")}
        self.approved = {
            "state": "approved", "applies_to": "intake", "stable_key": "test-1", "version": 1,
            "name": "PP material MFI", "reviewed_meaning": "Compare tested MFI only with buyer conditions",
            "topic_tags": "PP melt-flow", "prerequisite_keys": "mfi_value,mfi_conditions",
            "source_file": "verified.pdf", "source_sha256": "b" * 64, "source_selector": "p.1",
            "source_candidate_id": "test-1", "evidence_requirements": "Dated measurement plus conditions",
        }

    def test_missing_mfi_is_unknown_not_zero(self):
        self.assertEqual(self.facts["mfi_value"]["state"], "unknown")
        self.assertIsNone(self.facts["mfi_value"]["value"])

    def test_mfi_requires_conditions(self):
        val, cond = evidence.mfi_basis(12.0, None)
        self.assertEqual(val["value"], 12.0)
        self.assertEqual(cond["state"], "unknown")

    def test_mfi_rule_remains_deferred(self):
        out = reasoning.build_response("plasticos.intake", 7, "a", "PP MFI", self.facts, [self.approved])
        self.assertFalse(out["approved_knowledge"])
        self.assertEqual(out["deferred_knowledge"][0]["missing_prerequisites"],
                         ["mfi_value", "mfi_conditions"])

    def test_draft_not_advice(self):
        draft = dict(self.approved, state="draft")
        out = reasoning.build_response("plasticos.intake", 7, "a", "PP MFI", self.facts, [draft])
        self.assertEqual(out["approved_knowledge"], [])

    def test_retired_not_advice(self):
        retired = dict(self.approved, state="retired")
        self.assertEqual(reasoning.rank_approved("PP", self.facts, [retired], "intake"), [])

    def test_scope_filter(self):
        wrong = dict(self.approved, applies_to="offer")
        self.assertEqual(reasoning.rank_approved("PP", self.facts, [wrong], "intake"), [])

    def test_approved_still_does_not_trigger_commerce(self):
        known = dict(self.facts, mfi_value=evidence.fact(5.0, "measured"),
                     mfi_conditions=evidence.fact("test conditions", "reported"))
        out = reasoning.build_response("plasticos.intake", 7, "a", "PP MFI", known, [self.approved])
        self.assertTrue(out["approved_knowledge"])
        self.assertEqual(out["commercial_action"], "none")
        self.assertEqual(out["external_messages_sent"], 0)

    def test_citation_retains_source_digest(self):
        known = dict(self.facts, mfi_value=evidence.fact(5.0, "measured"),
                     mfi_conditions=evidence.fact("tested", "reported"))
        out = reasoning.build_response("plasticos.intake", 7, "a", "PP MFI", known, [self.approved])
        self.assertEqual(out["approved_knowledge"][0]["citation"]["sha256"], "b" * 64)

    def test_bad_citation_is_deferred_not_rendered(self):
        bad = dict(self.approved, source_sha256='wrong')
        out = reasoning.build_response('plasticos.intake', 1, 'rev', 'PP MFI', self.facts, [bad])
        self.assertFalse(out['approved_knowledge'])
        self.assertEqual(out['deferred_knowledge'][0]['reason'], 'source_citation_unavailable')

    def test_unsupported_owner_is_rejected(self):
        with self.assertRaises(ValueError):
            reasoning.build_response("res.partner", 1, "", "PP", {}, [])

    def test_no_live_price_inferred(self):
        out = reasoning.build_response("plasticos.offer", 9, "r", "Live HDPE price?", {}, [])
        self.assertEqual(out["commercial_action"], "none")
        self.assertIn("No live price", out["abstentions"][0])

    def test_conflicted_prerequisite_not_evidence(self):
        conflicted = dict(self.facts, mfi_value={"state": "conflicted", "value": 10})
        self.assertTrue(reasoning.rank_approved("PP MFI", conflicted, [self.approved], "intake")[0][1])

    def test_relevance_is_only_a_retrieval_hint(self):
        selected = reasoning.rank_approved("PP MFI", self.facts, [self.approved], "intake")
        self.assertTrue(selected)
        self.assertNotIn("approved", selected[0][0].get("state", "").replace("approved", ""))


class ObservationReplayIdentityTest(unittest.TestCase):
    def setUp(self):
        self.identity = {
            'source_model': 'plasticos.offer', 'source_id': 17,
            'source_revision': '2026-11-11 21:00:00',
            'scope_basis': 'operator_company', 'company_id': 1,
            'observation_type': 'rejection', 'actor_id': 9,
            'evidence_ref': 'buyer:email:1', 'observation': 'Rejected due to color',
        }

    def test_replay_is_deterministic(self):
        self.assertEqual(evidence.observation_identity(**self.identity),
                         evidence.observation_identity(**self.identity))

    def test_company_is_part_of_replay_identity(self):
        other = dict(self.identity, company_id=2)
        self.assertNotEqual(evidence.observation_identity(**self.identity),
                            evidence.observation_identity(**other))

    def test_delimiter_collision_is_not_a_replay(self):
        one = dict(self.identity, evidence_ref='a:b', observation='c')
        two = dict(self.identity, evidence_ref='a', observation='b:c')
        self.assertEqual(
            evidence.legacy_observation_identity(**{k: v for k, v in one.items() if k not in ('company_id', 'scope_basis')}),
            evidence.legacy_observation_identity(**{k: v for k, v in two.items() if k not in ('company_id', 'scope_basis')}),
        )
        self.assertNotEqual(evidence.observation_identity(**one), evidence.observation_identity(**two))


class WebLeadShadowTest(unittest.TestCase):
    def test_off_never_injects(self):
        for qualification in ("live", "shadow", "legacy"):
            self.assertFalse(shadow.can_inject("off", qualification))

    def test_shadow_only_when_pipeline_also_shadow(self):
        self.assertTrue(shadow.can_inject("shadow_only", "shadow"))
        self.assertFalse(shadow.can_inject("shadow_only", "live"))
        self.assertFalse(shadow.can_inject("shadow_only", "legacy"))

    def test_context_never_provides_fake_seller_evidence(self):
        sample = {"next_human_actions": ["Verify buyer conditions"],
                  "facts": {"buyer": {"value": "Secret customer"}}}
        result = shadow.context_from_advice(sample)
        self.assertFalse(result["allowed_to_change_routing"])
        self.assertEqual(result["seller_evidence_refs"], [])
        self.assertNotIn("Secret customer", str(result))


class RejectionTest(unittest.TestCase):
    def test_all_twelve_meanings_present(self):
        self.assertEqual(len(rejection.CODES), 12)
        self.assertEqual(len(set(rejection.CODES)), 12)

    def test_unreviewed_alias_abstains(self):
        result = evidence.reject_alias("R-01", rejection.CODES, {})
        self.assertIsNone(result["candidate_code"])
        self.assertFalse(result["approved"])

    def test_exact_code_is_only_proposed(self):
        result = evidence.reject_alias("METAL_PRESENT", rejection.CODES, {})
        self.assertEqual(result["candidate_code"], "METAL_PRESENT")
        self.assertFalse(result["approved"])

    def test_unknown_free_text_not_assigned_by_keyword(self):
        out = rejection.response("too much wet material", None)
        self.assertIsNone(out["proposed_code"])
        self.assertTrue(out["abstain"])

    def test_manual_choice_remains_unverified(self):
        out = rejection.response("film no longer processed", "NO_FILM_PROGRAM")
        self.assertEqual(out["proposed_code"], "NO_FILM_PROGRAM")
        self.assertFalse(out["verified_classification"])

    def test_rejection_never_excludes_or_rewrites_match(self):
        for out in (rejection.response("R-01", None),
                    rejection.response("WRONG_FORM", "WRONG_FORM", {"reviewed": True})):
            self.assertFalse(out["automatic_exclusion"])
            self.assertFalse(out["offer_transition"])
            self.assertFalse(out["matching_change"])

    def test_unknown_code_rejected(self):
        with self.assertRaises(ValueError):
            rejection.candidate_code("unknown", "FABRICATED")


if __name__ == "__main__":
    unittest.main()
