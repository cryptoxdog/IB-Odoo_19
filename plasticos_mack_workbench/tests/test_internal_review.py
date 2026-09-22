"""Regression coverage for Odoo-native Mack internal review requests."""

from datetime import timedelta

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "plasticos", "mack_workbench")
class TestMackInternalReview(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing(
            "plasticos.mack.internal.review",
            "plasticos.web.lead",
            "plasticos.intake",
        )
        cls.Review = cls.env["plasticos.mack.internal.review"]
        cls.WebLead = cls.env["plasticos.web.lead"]
        cls.config = cls.env["plasticos.web.lead.config"].sudo().get_config()
        cls.reviewer = cls.env.ref("base.user_admin")
        cls.config.write({"hot_intake_reviewer_id": cls.reviewer.id})

    def _hot_intake(self, lead_id="MACK-REVIEW-001"):
        lead = self.WebLead.create_from_agent(
            {
                "lead_id": lead_id,
                "source": "cognito_form",
                "decision": "hot",
                "decision_reasons": ["qualified"],
                "raw_payload": {
                    "YourBusinessCompanyName": "Review Target Co",
                    "DescribeYourMaterial": "HDPE regrind",
                    "WhatIsTheQuantity": "40000 lbs per load",
                },
                "ai_analysis": {
                    "quantity": {"per_load_lbs": 40000, "loads_per_month": 2},
                    "frequency": {"frequency": "ongoing"},
                    "material": {"polymer": "hdpe", "form": "regrind"},
                },
            }
        )
        self.assertEqual(lead.decision, "hot")
        self.assertTrue(lead.intake_id)
        return lead.intake_id

    def _request_values(self, intake, key="mack-review-idempotency-001"):
        return {
            "intake_id": intake.id,
            "cwi_ref": "cwi_demo_001",
            "cwi_revision": 3,
            "decision_snapshot_hash": "a" * 64,
            "candidate_action": "request_match_intake",
            "reason": "Review commercial fit before an Odoo match request.",
            "risk_codes": ["COUNTERPARTY_UNRESOLVED"],
            "evidence_refs": [f"odoo:intake:{intake.id}@v1"],
            "priority": "2",
            "deadline": fields.Date.today() + timedelta(days=1),
            "idempotency_key": key,
        }

    def test_review_routes_to_configured_internal_user_once(self):
        intake = self._hot_intake()
        request = self.Review.create(self._request_values(intake))

        self.assertEqual(request.reviewer_id, self.reviewer)
        self.assertEqual(request.route_policy_key, "hot_web_lead_reviewer/v1")
        self.assertEqual(request.delivery_mode, "in_odoo_activity_only")
        self.assertTrue(request.activity_id)
        self.assertEqual(request.activity_id.user_id, self.reviewer)
        self.assertEqual(request.activity_id.res_model, "plasticos.intake")
        self.assertEqual(request.activity_id.res_id, intake.id)
        self.assertEqual(request.candidate_action, "request_match_intake")
        self.assertEqual(request.state, "requested")
        self.assertEqual(len(intake.mack_review_request_ids), 1)
        self.assertTrue(any(request.name in body.body for body in intake.message_ids))

    def test_identical_retry_returns_prior_receipt_without_second_activity(self):
        intake = self._hot_intake("MACK-REVIEW-RETRY-001")
        values = self._request_values(intake, key="mack-review-retry-key")
        first = self.Review.create(values)
        second = self.Review.create(values)

        self.assertEqual(first, second)
        self.assertEqual(self.Review.search_count([("idempotency_key", "=", "mack-review-retry-key")]), 1)
        self.assertEqual(len(intake.activity_ids.filtered(lambda activity: activity.id == first.activity_id.id)), 1)

    def test_replay_material_or_caller_reviewer_cannot_change_routing(self):
        intake = self._hot_intake("MACK-REVIEW-BOUND-001")
        values = self._request_values(intake, key="mack-review-bound-key")
        self.Review.create(values)

        changed = dict(values, reason="A materially different reason")
        with self.assertRaises(ValidationError):
            self.Review.create(changed)
        with self.assertRaises(AccessError):
            self.Review.create(
                dict(values, idempotency_key="mack-review-caller-reviewer", reviewer_id=self.env.user.id)
            )

    def test_only_hot_web_lead_canonical_intake_is_eligible(self):
        intake = self._hot_intake("MACK-REVIEW-NONHOT-001")
        intake.write({"source_lead_id": False})
        with self.assertRaises(ValidationError):
            self.Review.create(self._request_values(intake, key="mack-review-nonhot-key"))
