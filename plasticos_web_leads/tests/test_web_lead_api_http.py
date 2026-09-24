"""Public API contract of ``POST /api/v1/web-lead`` over real HTTP (F187-04)."""

from __future__ import annotations

import json

from odoo.tests import HttpCase, tagged

_API_KEY = "test-web-lead-api-key-not-a-real-secret"


@tagged("post_install", "-at_install", "plasticos", "web_lead", "api")
class TestLegacyWebLeadApi(HttpCase):
    def setUp(self):
        super().setUp()
        self.config = self.env["plasticos.web.lead.config"].sudo().get_config()
        self.config.write(
            {
                "api_key": _API_KEY,
                "is_active": True,
                "ai_enabled": False,
                "vision_enabled": False,
                "hot_intake_reviewer_id": self.env.ref("base.user_admin").id,
            }
        )

    def _post(self, body, token=_API_KEY):
        return self.url_open(
            "/api/v1/web-lead",
            data=json.dumps(body),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        )

    def test_legacy_payload_without_lead_id_is_accepted_with_generated_identity(self):
        response = self._post(
            {
                "decision": "Cold",
                "source": "api",
                "raw_payload": {"CompanyName": "Legacy Client", "DescribeYourMaterial": "PP purge"},
            }
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        self.assertTrue(body["lead_id"].startswith("WL-"), body)
        lead = self.env["plasticos.web.lead"].browse(body["web_lead_id"])
        self.assertEqual(lead.lead_id, body["lead_id"])
        self.assertNotEqual(lead.state, "error")

    def test_supplied_lead_id_is_preserved_and_idempotent(self):
        payload = {"lead_id": "API-IDEMP-001", "decision": "Cold", "raw_payload": {}}
        first = self._post(payload)
        second = self._post(payload)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(first.json()["web_lead_id"], second.json()["web_lead_id"])

    def test_invalid_payload_shapes_are_deterministic_4xx_not_500(self):
        self.assertEqual(self._post({"decision": "Cold", "lead_id": "   "}).status_code, 422)
        self.assertEqual(self._post({"decision": "Cold", "raw_payload": ["x"]}).status_code, 422)
        self.assertEqual(self._post({"lead_id": "API-NO-DECISION"}).status_code, 422)
        self.assertEqual(self._post(["not", "an", "object"]).status_code, 400)
        self.assertEqual(self._post({"decision": "Cold"}, token="wrong").status_code, 401)
