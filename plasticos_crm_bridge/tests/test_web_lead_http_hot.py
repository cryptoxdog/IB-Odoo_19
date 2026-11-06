"""A HOT submission through the real public webhook becomes one unassigned, non-Won opportunity.

The webhook route is ``auth="none"``, so the request environment has no user.
``TransactionCase`` tests run as a real superuser and cannot reproduce that:
every ``message_post`` there sees a singleton ``env.user``. These tests POST
through the controller, which is the only place the empty user exists.

The 2026-11-05 promotion rehearsal failed here with ``Expected singleton:
res.users()``: with no HOT Intake Reviewer configured (the state of a fresh
clone), the blocked-handoff note is posted before the CRM bridge runs.
AI and vision are disabled so classification is deterministic; the economic
evaluation is not mocked.
"""

import json

from odoo.tests import HttpCase, tagged

_API_KEY = "test-hot-webhook-api-key-not-a-real-secret"


def _hot_body(number):
    """The shape of tests/production-rehearsal/payloads/cognito_hot.json."""
    return {
        "Form": {"Id": "1", "Name": "Seller Intake"},
        "Entry": {"Number": number, "Action": ""},
        "YourBusinessCompanyName": "Grade Co",
        "Name": {"First": "Grade", "Last": "Co"},
        "Email": "rehearsal@grade-co.example.com",
        "Phone": "555-0190",
        "DescribeYourMaterial": "HDPE plastic pallets",
        "WhatIsTheSourceOfThisMaterial": "Manufacturing production scrap",
        "WhatIsTheQuantity": "2 loads per month",
        "WeightPerLoad": "40000 lbs",
        "AreThereAnyContaminants": "none",
        "UploadPhotosOfYourScrapUpTo10": [],
    }


@tagged("post_install", "-at_install", "plasticos", "crm_bridge", "web_lead", "api")
class TestWebLeadHttpHot(HttpCase):
    def setUp(self):
        super().setUp()
        self.config = self.env["plasticos.web.lead.config"].sudo().get_config()
        self.config.write(
            {
                "api_key": _API_KEY,
                "is_active": True,
                "ai_enabled": False,
                "vision_enabled": False,
                "hot_intake_reviewer_id": False,
            }
        )

    def _post(self, body):
        return self.url_open(
            "/api/v1/cognito-webhook",
            data=json.dumps(body),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {_API_KEY}"},
        )

    def _admit_hot(self, number):
        response = self._post(_hot_body(number))
        self.assertEqual(response.status_code, 200, response.text)
        receipt = response.json()
        self.assertEqual(receipt["status"], "ok", receipt)
        self.assertNotIn("error", receipt, receipt)
        self.assertEqual(receipt["decision"], "hot", receipt)
        self.assertEqual(receipt["state"], "intake_created", receipt)
        self.assertTrue(receipt["intake_id"], receipt)
        return receipt

    def _assert_one_unassigned_open_opportunity(self, receipt):
        lead = self.env["plasticos.web.lead"].browse(receipt["web_lead_id"])
        opportunities = (
            self.env["crm.lead"]
            .with_context(active_test=False)
            .search([("source_intake_id", "=", receipt["intake_id"])])
        )
        self.assertEqual(len(opportunities), 1)
        self.assertEqual(lead.crm_lead_id, opportunities)
        self.assertEqual(opportunities.type, "opportunity")
        self.assertFalse(opportunities.user_id)
        self.assertFalse(opportunities.stage_id.is_won)
        self.assertFalse(opportunities.partner_id)
        return lead, opportunities

    def test_hot_webhook_without_reviewer_creates_one_unassigned_open_opportunity(self):
        receipt = self._admit_hot("http-hot-no-reviewer")
        lead, _opportunity = self._assert_one_unassigned_open_opportunity(receipt)
        self.assertEqual(lead.mack_review_state, "blocked")
        self.assertTrue(lead.message_ids.filtered(lambda message: "review handoff is blocked" in (message.body or "")))

    def test_hot_webhook_with_reviewer_schedules_the_review(self):
        reviewer = self.env.ref("base.user_admin")
        self.config.write({"hot_intake_reviewer_id": reviewer.id})
        receipt = self._admit_hot("http-hot-reviewer")
        lead, _opportunity = self._assert_one_unassigned_open_opportunity(receipt)
        self.assertEqual(lead.mack_review_state, "queued")
        self.assertEqual(lead.intake_id.activity_ids.user_id, reviewer)

    def test_duplicate_hot_webhook_is_idempotent(self):
        first = self._admit_hot("http-hot-replay")
        _lead, opportunity = self._assert_one_unassigned_open_opportunity(first)

        response = self._post(_hot_body("http-hot-replay"))
        self.assertEqual(response.status_code, 200, response.text)
        second = response.json()
        self.assertEqual(second["web_lead_id"], first["web_lead_id"])
        self.assertEqual(second["intake_id"], first["intake_id"])
        _lead, replayed = self._assert_one_unassigned_open_opportunity(second)
        self.assertEqual(replayed, opportunity)
