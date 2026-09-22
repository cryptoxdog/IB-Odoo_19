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
            "plasticos.mack.workbench.config",
            "plasticos.intake",
        )
        cls.Review = cls.env["plasticos.mack.internal.review"]
        cls.Config = cls.env["plasticos.mack.workbench.config"]
        cls.reviewer = cls.env.ref("base.user_admin")
        cls.config = cls.Config.create(
            {
                "name": "Mack Workbench Test Route",
                "company_id": cls.env.company.id,
                "internal_reviewer_id": cls.reviewer.id,
            }
        )

    def _canonical_intake(self):
        intake = self._create_intake()
        self.assertTrue(intake)
        return intake

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

    def test_review_routes_any_canonical_intake_to_configured_internal_user_once(self):
        intake = self._canonical_intake()
        request = self.Review.create(self._request_values(intake))

        self.assertEqual(request.reviewer_id, self.reviewer)
        self.assertEqual(request.route_policy_key, "mack_workbench_internal_reviewer/v1")
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
        intake = self._canonical_intake()
        values = self._request_values(intake, key="mack-review-retry-key")
        first = self.Review.create(values)
        second = self.Review.create(values)

        self.assertEqual(first, second)
        self.assertEqual(self.Review.search_count([("idempotency_key", "=", "mack-review-retry-key")]), 1)
        self.assertEqual(len(intake.activity_ids.filtered(lambda activity: activity.id == first.activity_id.id)), 1)

    def test_batch_request_resolves_each_canonical_intake_once(self):
        first_intake = self._canonical_intake()
        second_intake = self._canonical_intake()

        requests = self.Review.create(
            [
                self._request_values(first_intake, key="mack-review-batch-one"),
                self._request_values(second_intake, key="mack-review-batch-two"),
            ]
        )

        self.assertEqual(len(requests), 2)
        self.assertEqual(set(requests.mapped("intake_id").ids), {first_intake.id, second_intake.id})
        self.assertTrue(all(request.activity_id for request in requests))

    def test_replay_material_or_caller_reviewer_cannot_change_routing(self):
        intake = self._canonical_intake()
        values = self._request_values(intake, key="mack-review-bound-key")
        self.Review.create(values)

        changed = dict(values, reason="A materially different reason")
        with self.assertRaises(ValidationError):
            self.Review.create(changed)
        with self.assertRaises(AccessError):
            self.Review.create(
                dict(values, idempotency_key="mack-review-caller-reviewer", reviewer_id=self.env.user.id)
            )

    def test_review_does_not_require_a_hot_web_lead_origin(self):
        intake = self._canonical_intake()
        request = self.Review.create(self._request_values(intake, key="mack-review-non-hot-key"))
        self.assertEqual(request.intake_id, intake)
        self.assertEqual(request.reviewer_id, self.reviewer)

    def test_missing_company_route_fails_closed(self):
        intake = self._canonical_intake()
        self.config.write({"active": False})
        try:
            with self.assertRaises(ValidationError):
                self.Review.create(self._request_values(intake, key="mack-review-no-route-key"))
        finally:
            self.config.write({"active": True})
