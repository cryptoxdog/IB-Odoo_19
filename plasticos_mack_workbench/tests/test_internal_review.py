"""Regression coverage for Odoo-native Mack internal review requests."""

from datetime import timedelta

import psycopg2.errors

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import tagged
from odoo.tools import mute_logger


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

    def _second_internal_reviewer(self):
        return self.env["res.users"].create(
            {
                "name": "Second Mack Reviewer",
                "login": "mack-second-reviewer",
                "email": "mack-second-reviewer@example.com",
            }
        )

    def test_replay_after_routing_change_returns_stored_receipt_without_consulting_routing(self):
        """F190-01: the stored receipt owns replay truth once routing config moves on."""
        intake = self._canonical_intake()
        values = self._request_values(intake, key="mack-review-policy-drift-key")
        first = self.Review.create(values)
        other_reviewer = self._second_internal_reviewer()

        self.config.write({"internal_reviewer_id": other_reviewer.id})
        replay = self.Review.create(values)

        self.assertEqual(replay, first)
        self.assertEqual(replay.reviewer_id, self.reviewer)
        self.assertEqual(replay.route_policy_revision, first.route_policy_revision)
        # Routing is not consulted at all on replay: with no active route the stored
        # receipt still answers, while a first creation under the same conditions
        # keeps failing closed.
        self.config.write({"active": False})
        try:
            self.assertEqual(self.Review.create(values), first)
            with self.assertRaises(ValidationError):
                self.Review.create(self._request_values(intake, key="mack-review-policy-drift-unrouted-key"))
        finally:
            self.config.write({"active": True})
        # A genuinely new request resolves the *current* routing policy.
        fresh = self.Review.create(self._request_values(intake, key="mack-review-policy-drift-fresh-key"))
        self.assertEqual(fresh.reviewer_id, other_reviewer)
        self.assertEqual(self.Review.search_count([("idempotency_key", "=", "mack-review-policy-drift-key")]), 1)

    def test_server_owned_provenance_cannot_be_supplied_by_the_caller(self):
        intake = self._canonical_intake()
        base = self._request_values(intake, key="mack-review-forged-provenance-key")
        other_company = self.env["res.company"].create({"name": "Mack Forged Company"})
        forgeries = (
            {"reviewer_id": self.env.user.id},
            {"requester_id": self.reviewer.id},
            {"route_policy_key": "mack_workbench_internal_reviewer/v0"},
            {"route_policy_revision": "caller-chosen"},
            {"activity_id": False},
            {"company_id": other_company.id},
            {"state": "cancelled"},
            {"delivery_mode": "email"},
            {"name": "MIR/FORGED"},
        )
        for forged in forgeries:
            with self.subTest(forged=forged), self.assertRaises(AccessError):
                self.Review.create(dict(base, **forged))
        self.assertEqual(self.Review.search_count([("idempotency_key", "=", base["idempotency_key"])]), 0)
        # Echoing the server's own values is harmless; the receipt is still server-bound.
        echoed = self.Review.create(dict(base, company_id=self.env.company.id, state="requested"))
        self.assertEqual(echoed.company_id, self.env.company)
        self.assertEqual(echoed.requester_id, self.env.user)

    @mute_logger("odoo.sql_db")
    def test_unique_collision_inside_create_converges_on_the_stored_receipt(self):
        """F190-01: a session whose pre-check missed the row still gets the winner back."""
        intake = self._canonical_intake()
        values = self._request_values(intake, key="mack-review-collision-key")
        first = self.Review.create(values)
        activity_count = len(intake.activity_ids)
        material = self.Review._caller_request_material(values)

        # Drive the insert path directly, exactly as the loser of a two-session race
        # does after its search missed: the INSERT takes the unique violation, the
        # savepoint is rolled back, and the stored receipt is re-queried and compared.
        winner = self.Review._create_first_receipt(self.env.company, material)

        self.assertEqual(winner, first)
        self.assertEqual(self.Review.search_count([("idempotency_key", "=", "mack-review-collision-key")]), 1)
        self.assertEqual(len(intake.activity_ids), activity_count)
        with self.assertRaises(ValidationError):
            self.Review._create_first_receipt(self.env.company, dict(material, reason="Different material."))

    @mute_logger("odoo.sql_db")
    def test_database_refuses_a_second_active_route_when_the_python_constraint_is_bypassed(self):
        """F190-02: PostgreSQL, not the Python constraint, is the one-active-route authority."""
        company = self.env.company
        shadow = self.Config.create(
            {
                "name": "Shadow Route",
                "company_id": company.id,
                "internal_reviewer_id": self.reviewer.id,
                "active": False,
            }
        )
        self.env.flush_all()
        self.env.cr.execute(
            "SELECT indexdef FROM pg_indexes WHERE indexname = %s",
            ("plasticos_mack_workbench_config_unique_active_route_per_company",),
        )
        row = self.env.cr.fetchone()
        self.assertTrue(row, "partial unique index on (company_id) WHERE active is not installed")
        self.assertIn("WHERE (active IS TRUE)", row[0])

        with self.assertRaises(psycopg2.errors.UniqueViolation), self.env.cr.savepoint():
            # Raw SQL bypasses @api.constrains on purpose: only the index can refuse this.
            self.env.cr.execute("UPDATE plasticos_mack_workbench_config SET active = TRUE WHERE id = %s", (shadow.id,))
        self.assertEqual(self.Config.search_count([("company_id", "=", company.id), ("active", "=", True)]), 1)
        self.assertEqual(self.Config.get_active_config(company=company), self.config)

    def test_completing_and_deleting_the_linked_activity_keeps_the_receipt_immutable(self):
        """U190-01: activity completion and deletion never route a write through the guard."""
        intake = self._canonical_intake()
        request = self.Review.create(self._request_values(intake, key="mack-review-activity-lifecycle-key"))
        activity = request.activity_id
        self.assertTrue(activity)

        # Odoo 19 completes an activity by archiving it (mail.activity._action_done ->
        # action_archive); the receipt keeps its link and receives no write.
        activity.action_feedback(feedback="Reviewed in Odoo.")
        self.assertTrue(activity.exists())
        self.assertFalse(activity.active)
        self.assertEqual(request.activity_id, activity)

        # Deleting the activity is answered by the FK's ON DELETE SET NULL inside
        # PostgreSQL, not by an ORM write against the immutable receipt.
        activity.unlink()
        request.invalidate_recordset(["activity_id"])
        self.assertFalse(request.activity_id)
        self.assertEqual(request.state, "requested")
        with self.assertRaises(AccessError):
            request.write({"reason": "Still immutable."})
        with self.assertRaises(AccessError):
            request.write({"activity_id": False})

    def test_operator_group_user_can_create_a_request(self):
        """The operator role (create + read, no write ACL) must be able to file a request."""
        operator = self.env["res.users"].create(
            {
                "name": "Mack Operator",
                "login": "mack-operator",
                "email": "mack-operator@example.com",
                "group_ids": [(4, self.env.ref("plasticos_mack_workbench.group_mack_workbench_operator").id)],
            }
        )
        intake = self._canonical_intake()
        request = self.Review.with_user(operator).create(self._request_values(intake, key="mack-review-operator-key"))
        self.assertEqual(request.requester_id, operator)
        self.assertEqual(request.reviewer_id, self.reviewer)
        self.assertTrue(request.activity_id)
        with self.assertRaises(AccessError):
            request.with_user(operator).write({"reason": "Operators cannot edit receipts."})
