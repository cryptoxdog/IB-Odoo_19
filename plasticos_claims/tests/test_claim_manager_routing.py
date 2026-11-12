"""Unresolved claim work goes to a claims manager, never to a sales user or the cron user."""

from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged

from .common import create_claims_manager

CLAIM_LOGGER = "odoo.addons.plasticos_claims.models.claim"
MANAGER_GROUP = "plasticos_claims.group_claims_manager"


@tagged("post_install", "-at_install", "plasticos", "claims")
class TestClaimManagerRouting(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Claim = cls.env["plasticos.claim"]
        cls.manager = create_claims_manager(cls.env, login="claims_routing_manager_a")
        cls.second_manager = create_claims_manager(cls.env, login="claims_routing_manager_b")
        cls.sales_rep = cls.env["res.users"].create(
            {
                "name": "Routing Sales Rep",
                "login": "claims_routing_sales_rep",
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("plasticos_claims.group_claims_user").id,
                        ],
                    )
                ],
            }
        )
        cls.cron_user = cls.env.ref("plasticos_base.user_system_cron")
        cls.cron_user.write({"group_ids": [(4, cls.env.ref(MANAGER_GROUP).id)]})
        cls.tx = cls._create_transaction(name="TX-TEST-CLM-ROUTE", user_id=cls.sales_rep.id)

    def _activities(self, claim, summary):
        return self.env["mail.activity"].search(
            [("res_model", "=", "plasticos.claim"), ("res_id", "=", claim.id), ("summary", "=", summary)]
        )

    def _no_manager(self):
        return patch.object(type(self.Claim), "_claims_manager_reviewer", lambda claims: self.env["res.users"])

    def _claim_pictures_document(self):
        tag = self.env["plasticos.document.tag"].search([("code", "=", "claim_pics")], limit=1)
        if not tag:
            tag = self.env["plasticos.document.tag"].create({"name": "Claim Pics", "code": "claim_pics"})
        attachment = self.env["ir.attachment"].create(
            {"name": "route.txt", "datas": "cGlj", "res_model": "plasticos.document", "res_id": 0}
        )
        return self.env["plasticos.document"].create(
            {
                "name": "Routing pic",
                "tag_id": tag.id,
                "res_model": "plasticos.transaction",
                "res_id": self.tx.id,
                "transaction_id": self.tx.id,
                "attachment_id": attachment.id,
            }
        )

    # ── reviewer resolution ──────────────────────────────────
    def test_reviewer_is_an_eligible_manager_and_stable(self):
        reviewer = self.Claim._claims_manager_reviewer()
        self.assertEqual(len(reviewer), 1)
        self.assertTrue(reviewer.has_group(MANAGER_GROUP))
        self.assertTrue(reviewer.active)
        self.assertFalse(reviewer.share)
        self.assertLessEqual(reviewer.id, self.manager.id)
        self.assertLess(reviewer.id, self.second_manager.id)
        self.assertEqual(self.Claim._claims_manager_reviewer(), reviewer)
        self.assertEqual(self.Claim.with_user(self.cron_user)._claims_manager_reviewer(), reviewer)
        self.assertEqual(self.Claim.with_user(self.sales_rep)._claims_manager_reviewer(), reviewer)

    def test_reviewer_is_never_the_cron_user_or_a_sales_user(self):
        self.assertTrue(self.cron_user.has_group(MANAGER_GROUP))
        reviewer = self.Claim._claims_manager_reviewer()
        self.assertNotEqual(reviewer, self.cron_user)
        self.assertNotEqual(reviewer, self.sales_rep)

    def test_archived_manager_is_skipped(self):
        first = self.Claim._claims_manager_reviewer()
        first.active = False
        replacement = self.Claim._claims_manager_reviewer()
        self.assertTrue(replacement)
        self.assertNotEqual(replacement, first)
        self.assertGreater(replacement.id, first.id)

    # ── escalation ───────────────────────────────────────────
    def test_escalation_activity_goes_to_the_manager(self):
        claim = self._create_claim(transaction=self.tx)
        reviewer = self.Claim._claims_manager_reviewer()
        claim.with_user(self.cron_user).action_escalate(reason="SLA")
        activities = self._activities(claim, f"Escalated Claim: {claim.name}")
        self.assertEqual(len(activities), 1)
        self.assertEqual(activities.user_id, reviewer)

    def test_escalation_without_a_manager_is_logged_and_noted(self):
        claim = self._create_claim(transaction=self.tx)
        with self._no_manager(), self.assertLogs(CLAIM_LOGGER, level="ERROR") as captured:
            claim.with_user(self.cron_user).action_escalate(reason="SLA")
        self.assertEqual(claim.state, "escalated")
        self.assertIn(claim.name, captured.output[0])
        self.assertFalse(
            self.env["mail.activity"].search([("res_model", "=", "plasticos.claim"), ("res_id", "=", claim.id)])
        )
        self.assertTrue(claim.message_ids.filtered(lambda message: "Not routed" in (message.body or "")))

    # ── auto-created claim ───────────────────────────────────
    def test_document_claim_is_assigned_to_the_manager_not_the_salesperson(self):
        reviewer = self.Claim._claims_manager_reviewer()
        document = self._claim_pictures_document()
        claim = self.Claim.search([("source_document_id", "=", document.id)])
        self.assertEqual(len(claim), 1)
        self.assertEqual(claim.transaction_id.user_id, self.sales_rep)
        self.assertEqual(claim.assignee_id, reviewer)
        activities = self.env["mail.activity"].search(
            [("res_model", "=", "plasticos.claim"), ("res_id", "=", claim.id)]
        )
        self.assertEqual(activities.mapped("user_id"), reviewer)
        self.assertEqual(activities.mapped("summary"), [f"New Claim Created: {claim.name}"])

    def test_document_claim_without_a_manager_is_logged_noted_and_unassigned(self):
        with self._no_manager(), self.assertLogs(CLAIM_LOGGER, level="ERROR"):
            document = self._claim_pictures_document()
        claim = self.Claim.search([("source_document_id", "=", document.id)])
        self.assertEqual(len(claim), 1)
        self.assertFalse(claim.assignee_id)
        self.assertFalse(
            self.env["mail.activity"].search([("res_model", "=", "plasticos.claim"), ("res_id", "=", claim.id)])
        )
        self.assertTrue(claim.message_ids.filtered(lambda message: "Not routed" in (message.body or "")))

    # ── reminders ────────────────────────────────────────────
    def test_reminder_for_an_unassigned_claim_goes_to_the_manager_under_cron(self):
        claim = self._create_claim(transaction=self.tx, state="in_progress")
        reviewer = self.Claim._claims_manager_reviewer()
        claim.with_user(self.cron_user)._create_reminder_activity()
        activities = self._activities(claim, f"Open Claim Reminder: {claim.name}")
        self.assertEqual(len(activities), 1)
        self.assertEqual(activities.user_id, reviewer)

    def test_reminder_keeps_an_explicit_assignee(self):
        claim = self._create_claim(transaction=self.tx, state="in_progress", assignee_id=self.second_manager.id)
        claim.with_user(self.cron_user)._create_reminder_activity()
        activities = self._activities(claim, f"Open Claim Reminder: {claim.name}")
        self.assertEqual(activities.user_id, self.second_manager)

    def test_reminder_without_assignee_or_manager_is_logged_and_noted(self):
        claim = self._create_claim(transaction=self.tx, state="in_progress")
        with self._no_manager(), self.assertLogs(CLAIM_LOGGER, level="ERROR"):
            claim.with_user(self.cron_user)._create_reminder_activity()
        self.assertFalse(self._activities(claim, f"Open Claim Reminder: {claim.name}"))
        self.assertTrue(claim.message_ids.filtered(lambda message: "Not routed" in (message.body or "")))
