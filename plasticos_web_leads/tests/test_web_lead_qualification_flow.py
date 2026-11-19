"""Live HOT / REVIEW / COLD routing side effects (ADR-016, 2026-11-11 amendment).

The commercial model is never called: ``evaluate_economic_opportunity`` is
patched with a deterministic recommendation that cites only evidence keys the
pipeline actually supplied. These tests prove what each final disposition
creates, and what it must not create.
"""

from __future__ import annotations

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from .test_broker_one_pass import economic_assessment_patch, one_pass_orchestration


def _payload(external_id, *, material="HDPE pellets", quantity="", weight="", source="Manufacturing production scrap"):
    payload = {
        "Entry": {"Number": external_id},
        "YourBusinessCompanyName": f"Seller {external_id}",
        "DescribeYourMaterial": material,
        "WhatIsTheSourceOfThisMaterial": source,
        "WhatIsTheQuantity": quantity,
        "AreThereAnyContaminants": "none",
    }
    if weight:
        payload["WeightPerLoad"] = weight
    return payload


def _recommend(disposition, *, suitability="supported", signal="strong", confidence=0.9):
    """A provider-shaped v2 assessment that cites the first supplied evidence keys."""

    def fake(**kwargs):
        signals = kwargs.get("qualification_signals") or {}
        refs = sorted(signals.get("evidence_refs") or {})[:3]
        return {
            "schema_version": "web-lead-economic-assessment/v2",
            "status": "assessed",
            "assessment": {
                "recommended_disposition": disposition,
                "opportunity_signal": signal,
                "confidence": confidence,
                "material_suitability": suitability,
                "commercial_rationale": "deterministic test recommendation",
                "supporting_evidence_refs": refs,
                "contradictory_evidence_refs": [],
                "missing_information": [],
                "recommended_clarification": ["Confirm pounds per load."],
                "clarifications": ["Confirm pounds per load."],
                "validation_issues": [],
            },
        }

    return fake


def _unavailable(**_kwargs):
    return {"status": "unavailable", "reason": "economic_provider_failed"}


@tagged("post_install", "-at_install", "plasticos", "web_lead", "qualification")
class TestLiveQualificationRouting(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.WebLead = cls.env["plasticos.web.lead"]
        cls.Activity = cls.env["mail.activity"]
        cls.config = cls.env["plasticos.web.lead.config"].sudo().get_config()
        cls.reviewer = cls.env.ref("base.user_admin")
        cls.config.write(
            {
                "ai_enabled": False,
                "vision_enabled": False,
                "hot_intake_reviewer_id": cls.reviewer.id,
                "attachment_allowed_hosts": False,
                "qualification_mode": "live",
            }
        )

    def _admit(self, payload, recommend):
        with economic_assessment_patch(side_effect=recommend):
            return self.WebLead.create_from_cognito(payload)

    def _lead_activities(self, lead):
        return self.Activity.search([("res_model", "=", "plasticos.web.lead"), ("res_id", "=", lead.id)])

    # WL-01 / WL-13
    def test_hot_creates_exactly_one_intake_and_one_review_handoff(self):
        lead = self._admit(_payload("Q-HOT-001", weight="40000 lbs"), _recommend("hot"))
        self.assertEqual(lead.decision, "hot")
        self.assertEqual(lead.state, "intake_created")
        self.assertEqual(lead.intake_id.quantity_per_load_lbs, 40000)
        qualification = lead.decision_reasons["qualification"]
        self.assertEqual(qualification["model_recommendation"], "hot")
        self.assertEqual(qualification["final_disposition"], "hot")
        self.assertEqual(qualification["routing_mode"], "live")
        handoffs = self.Activity.search(
            [
                ("res_model", "=", "plasticos.intake"),
                ("res_id", "=", lead.intake_id.id),
                ("user_id", "=", self.reviewer.id),
            ]
        )
        self.assertEqual(len(handoffs), 1)
        intake = lead.intake_id
        lead._process_hot_lead_triage(dict(lead.ai_analysis), self.config)
        self.assertEqual(lead.intake_id, intake)
        self.assertEqual(self.env["plasticos.intake"].search_count([("source_lead_id", "=", lead.id)]), 1)

    # WL-04 / WL-17 / R3
    def test_review_keeps_the_lead_assigns_work_and_creates_no_commercial_records(self):
        lead = self._admit(
            _payload("Q-REV-001", quantity="Two truckloads every month"), _recommend("hot", signal="strong")
        )
        if one_pass_orchestration():
            # Unknown per-load weight stays HOT and does not open an intake.
            self.assertEqual(lead.decision, "hot")
        else:
            self.assertEqual(lead.decision, "review")
        self.assertEqual(lead.state, "review_pending")
        self.assertEqual(lead.review_status, "clarification_required")
        self.assertFalse(lead.intake_id)
        self.assertFalse(lead.partner_id)
        self.assertFalse(getattr(lead, "crm_lead_id", False))
        self.assertEqual(lead.estimated_lbs_per_load, 0)
        qualification = lead.decision_reasons["qualification"]
        self.assertEqual(qualification["model_recommendation"], "hot")
        if one_pass_orchestration():
            self.assertFalse(qualification["overridden"])
            self.assertEqual(qualification["review_priority"], "normal")
        else:
            self.assertTrue(qualification["overridden"])
            self.assertEqual(qualification["review_priority"], "high")
        activities = self._lead_activities(lead)
        self.assertEqual(len(activities), 1)
        self.assertEqual(activities.user_id, self.reviewer)
        self.assertEqual(lead.mack_review_state, "queued")
        lead._route_review_lead(self.config)
        self.assertEqual(len(self._lead_activities(lead)), 1, "Review work is deduplicated.")

    # WL-18
    def test_review_without_reviewer_is_a_visible_blocked_handoff(self):
        self.config.hot_intake_reviewer_id = False
        lead = self._admit(_payload("Q-REV-002", quantity="Two truckloads every month"), _recommend("review"))
        self.assertEqual(lead.state, "review_pending")
        self.assertEqual(lead.mack_review_state, "blocked")
        self.assertFalse(self._lead_activities(lead))

    # WL-02
    def test_cold_creates_no_commercial_records(self):
        lead = self._admit(_payload("Q-COLD-001", material="Steel scrap", weight="50000 lbs"), _recommend("hot"))
        self.assertEqual(lead.decision, "cold")
        self.assertEqual(lead.state, "skipped")
        self.assertFalse(lead.intake_id)
        self.assertFalse(self._lead_activities(lead))
        self.assertIn("nonplastic_only:steel", lead.decision_reasons["qualification"]["hard_exclusions"])

    # WL-11
    def test_unavailable_assessment_is_review_never_silent_cold(self):
        lead = self._admit(_payload("Q-UNAV-001", weight="40000 lbs"), _unavailable)
        self.assertEqual(lead.decision, "review")
        self.assertEqual(lead.state, "review_pending")
        self.assertFalse(lead.intake_id)
        with economic_assessment_patch(side_effect=_recommend("hot")):
            lead.action_retry_triage()
        self.assertEqual(lead.decision, "hot")
        self.assertTrue(lead.intake_id)

    # WL-12
    def test_duplicate_webhook_is_one_lead_and_one_intake(self):
        first = self._admit(_payload("Q-DUP-001", weight="40000 lbs"), _recommend("hot"))
        second = self._admit(_payload("Q-DUP-001", weight="40000 lbs"), _recommend("hot"))
        self.assertEqual(first, second)
        self.assertEqual(self.env["plasticos.intake"].search_count([("source_lead_id", "=", first.id)]), 1)

    # F3 / WL-13 / WL-17
    def test_promotion_requires_rationale_and_verified_weight_and_is_idempotent(self):
        lead = self._admit(_payload("Q-PROMO-001", quantity="Two truckloads every month"), _recommend("review"))
        with self.assertRaises(UserError):
            lead.action_promote_to_hot()
        lead.review_notes = "Seller confirmed 40,000 lb per truckload by phone."
        with self.assertRaises(UserError):
            lead.action_promote_to_hot()
        self.assertFalse(lead.intake_id)
        lead.estimated_lbs_per_load = 40000
        lead.action_promote_to_hot()
        self.assertEqual(lead.decision, "hot")
        self.assertEqual(lead.state, "intake_created")
        self.assertEqual(lead.intake_id.quantity_per_load_lbs, 40000)
        override = lead.decision_reasons["manual_override"]
        self.assertEqual(override["previous_decision"], "review")
        self.assertEqual(override["actor_id"], self.env.user.id)
        self.assertFalse(self._lead_activities(lead).filtered(lambda a: a.summary.startswith("Clarify REVIEW")))
        with self.assertRaises(UserError):
            lead.action_promote_to_hot()
        self.assertEqual(self.env["plasticos.intake"].search_count([("source_lead_id", "=", lead.id)]), 1)

    def test_reject_after_review_closes_the_review_as_cold(self):
        lead = self._admit(_payload("Q-REJ-001", quantity="Two truckloads every month"), _recommend("review"))
        lead.review_notes = "Seller is a hobbyist."
        lead.action_reject_after_review()
        self.assertEqual(lead.decision, "cold")
        self.assertEqual(lead.state, "skipped")
        self.assertEqual(lead.review_status, "rejected")
        self.assertEqual(lead.decision_reasons["manual_override"]["decision"], "cold")

    # WL-20
    def test_commercial_approval_from_review_is_denied(self):
        lead = self._admit(_payload("Q-APPR-001", quantity="Two truckloads every month"), _recommend("review"))
        with self.assertRaises(UserError):
            lead.action_approve_for_commercial_preparation()
        self.assertFalse(lead.review_snapshot_ids)


@tagged("post_install", "-at_install", "plasticos", "web_lead", "qualification")
class TestShadowAndAssessmentRecovery(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.WebLead = cls.env["plasticos.web.lead"]
        cls.config = cls.env["plasticos.web.lead.config"].sudo().get_config()
        cls.config.write(
            {
                "ai_enabled": False,
                "vision_enabled": False,
                "hot_intake_reviewer_id": cls.env.ref("base.user_admin").id,
                "attachment_allowed_hosts": False,
                "qualification_mode": "shadow",
            }
        )

    def test_shadow_records_the_qualification_without_changing_routing(self):
        with economic_assessment_patch(side_effect=_recommend("hot")):
            lead = self.WebLead.create_from_cognito(_payload("Q-SHADOW-001", quantity="Two truckloads every month"))
        qualification = lead.decision_reasons["qualification"]
        self.assertEqual(qualification["routing_mode"], "shadow")
        self.assertEqual(lead.decision, qualification["legacy_decision"])
        if one_pass_orchestration():
            self.assertEqual(qualification["final_disposition"], "hot")
            self.assertEqual(lead.state, "review_pending")
            self.assertFalse(lead.intake_id)
        else:
            self.assertEqual(qualification["final_disposition"], "review")
            self.assertNotEqual(lead.state, "review_pending")

    # WL-14 / WL-19 / G1 / G2
    def test_assessment_retry_after_intake_unblocks_approval_and_keeps_snapshots_immutable(self):
        with economic_assessment_patch(side_effect=_unavailable):
            lead = self.WebLead.create_from_cognito(_payload("Q-RETRY-001", weight="40000 lbs"))
        self.assertEqual(lead.decision, "hot")
        intake = lead.intake_id
        self.assertTrue(intake)
        with self.assertRaises(UserError):
            lead.action_approve_for_commercial_preparation()

        with economic_assessment_patch(side_effect=_recommend("hot")):
            lead.action_retry_economic_assessment()
        self.assertEqual(lead.evidence_bundle["economic_assessment"]["status"], "assessed")
        self.assertEqual(lead.evidence_bundle["economic_assessment_history"][0]["status"], "unavailable")
        self.assertEqual(lead.intake_id, intake)
        self.assertEqual(lead.decision, "hot")

        lead.action_approve_for_commercial_preparation()
        snapshot = lead.review_snapshot_ids
        self.assertEqual(len(snapshot), 1)
        content_hash = snapshot.content_hash

        with economic_assessment_patch(side_effect=_recommend("review")):
            lead.action_retry_economic_assessment()
        self.assertEqual(snapshot.content_hash, content_hash)
        self.assertEqual(lead.review_snapshot_ids, snapshot)
        self.assertEqual(self.env["plasticos.intake"].search_count([("source_lead_id", "=", lead.id)]), 1)

    def test_retry_without_intake_points_to_reassessment(self):
        lead = self.WebLead.create({"lead_id": "Q-RETRY-NOINTAKE", "company_name": "No Intake Co"})
        with self.assertRaises(UserError):
            lead.action_retry_economic_assessment()


@tagged("post_install", "-at_install", "plasticos", "web_lead", "qualification")
class TestQualificationHandoffIntegrity(TransactionCase):
    """Review findings 1, 3, 4, and 5 on PR #464."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.WebLead = cls.env["plasticos.web.lead"]
        cls.Activity = cls.env["mail.activity"]
        cls.config = cls.env["plasticos.web.lead.config"].sudo().get_config()
        cls.reviewer = cls.env.ref("base.user_admin")
        cls.config.write(
            {
                "ai_enabled": False,
                "vision_enabled": False,
                "hot_intake_reviewer_id": cls.reviewer.id,
                "attachment_allowed_hosts": False,
                "qualification_mode": "live",
            }
        )
        cls.read_only_user = cls.env["res.users"].create(
            {
                "name": "Read-only Web Lead Reviewer",
                "login": "web-lead-read-only-reviewer",
                "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
            }
        )

    def _admit(self, payload, recommend):
        with economic_assessment_patch(side_effect=recommend):
            return self.WebLead.create_from_cognito(payload)

    # Finding 1
    def test_reviewer_who_cannot_edit_web_leads_is_a_blocked_handoff(self):
        self.assertFalse(self.WebLead.with_user(self.read_only_user).has_access("write"))
        self.config.hot_intake_reviewer_id = self.read_only_user
        lead = self._admit(_payload("Q-ACL-001", quantity="Two truckloads every month"), _recommend("review"))
        self.assertEqual(lead.state, "review_pending")
        self.assertEqual(lead.mack_review_state, "blocked")
        self.assertIn("cannot edit web leads", lead.mack_review_reason)
        self.assertFalse(self.Activity.search([("res_model", "=", "plasticos.web.lead"), ("res_id", "=", lead.id)]))

    # Finding 3
    def test_seller_named_polymer_reaches_the_intake_and_unknown_source_stays_empty(self):
        lead = self._admit(
            _payload("Q-POLY-001", material="Clean HDPE bottles, baled", weight="40000 lbs", source=""),
            _recommend("hot"),
        )
        self.assertEqual(lead.decision, "hot")
        self.assertEqual(lead.ai_analysis["polymer"], "HDPE")
        self.assertEqual(lead.ai_analysis["polymer_source"], "seller_text")
        self.assertEqual(lead.intake_id.polymer_id.code.upper(), "HDPE")
        self.assertFalse(lead.intake_id.source_type_id)

    # Finding 4
    def test_retriage_assesses_broker_corrections_and_keeps_the_submission(self):
        lead = self._admit(_payload("Q-CORR-001", quantity="Two truckloads every month"), _recommend("hot"))
        self.assertEqual(lead.state, "review_pending")
        submitted = dict(lead.canonical_payload)
        lead.write({"quantity_text": "Two truckloads every month, 40,000 lbs each"})
        with economic_assessment_patch(side_effect=_recommend("hot")):
            lead.action_retry_triage()
        self.assertEqual(lead.decision, "hot")
        self.assertEqual(lead.intake_id.quantity_per_load_lbs, 40000)
        self.assertEqual(dict(lead.canonical_payload), submitted)
        corrections = lead.evidence_bundle["broker_corrections"]
        self.assertEqual(corrections["quantity_text"]["submitted"], "Two truckloads every month")
        self.assertEqual(corrections["quantity_text"]["corrected"], "Two truckloads every month, 40,000 lbs each")

    # Finding 5
    def test_context_cannot_open_the_processed_lead_write_guard(self):
        lead = self._admit(_payload("Q-GUARD-001", weight="40000 lbs"), _recommend("hot"))
        self.assertEqual(lead.state, "intake_created")
        original = dict(lead.evidence_bundle)
        for context_key in ("web_lead_assessment_recovery",):
            with self.assertRaises(UserError):
                lead.with_context(**{context_key: True}).write({"evidence_bundle": {"forged": True}})
        self.assertEqual(dict(lead.evidence_bundle), original)
        with economic_assessment_patch(side_effect=_recommend("review")):
            lead.action_retry_economic_assessment()
        self.assertEqual(lead.evidence_bundle["seller"], original["seller"])
        self.assertEqual(lead.evidence_bundle["quantity"], original["quantity"])
        self.assertEqual(lead.decision, "hot")
