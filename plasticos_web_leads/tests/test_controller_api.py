"""Controller / API endpoint tests for plasticos_web_leads.

Tests cover:
  - Authentication (Bearer token validation)
  - POST /api/v1/web-lead (legacy agent endpoint)
  - POST /api/v1/cognito-webhook (raw Cognito form)
  - GET  /api/v1/web-lead/health (health check)
  - Input validation (missing fields, malformed JSON)
  - Endpoint disabled handling
"""

import json

from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install", "plasticos", "controller")
class TestWebLeadController(HttpCase):
    """HTTP-level tests for the web lead REST API."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Config = cls.env["plasticos.web.lead.config"].sudo()
        cls.config = Config.get_config()
        cls.config.write({"api_key": "test-api-key-12345", "is_active": True})

    def _post_json(self, url, data, token=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return self.url_open(url, data=json.dumps(data), headers=headers)

    # ─── Authentication ──────────────────────────────────────

    def test_auth_missing_header(self):
        """Request without Authorization header returns 401."""
        resp = self._post_json("/api/v1/web-lead", {"lead_id": "WL1", "decision": "Hot"})
        self.assertEqual(resp.status_code, 401)

    def test_auth_empty_bearer(self):
        """Empty Bearer token returns 401."""
        resp = self._post_json("/api/v1/web-lead", {"lead_id": "WL1", "decision": "Hot"}, token="")
        self.assertEqual(resp.status_code, 401)

    def test_auth_invalid_key(self):
        """Wrong API key returns 401."""
        resp = self._post_json("/api/v1/web-lead", {"lead_id": "WL1", "decision": "Hot"}, token="wrong")
        self.assertEqual(resp.status_code, 401)
        self.assertIn("Invalid", resp.json().get("error", ""))

    def test_auth_endpoint_disabled(self):
        """Disabled endpoint returns 401."""
        self.config.write({"is_active": False})
        try:
            resp = self._post_json(
                "/api/v1/web-lead",
                {"lead_id": "WL1", "decision": "Hot"},
                token="test-api-key-12345",
            )
            self.assertEqual(resp.status_code, 401)
            self.assertIn("disabled", resp.json().get("error", "").lower())
        finally:
            self.config.write({"is_active": True})

    def test_auth_valid_key_succeeds(self):
        """Valid Bearer token passes authentication (not 401)."""
        resp = self._post_json("/api/v1/web-lead", {"lead_id": "WL-OK", "decision": "Cold"}, token="test-api-key-12345")
        self.assertNotEqual(resp.status_code, 401)

    # ─── Input Validation ────────────────────────────────────

    def test_empty_body_returns_error(self):
        """Empty POST body returns 400."""
        resp = self._post_json("/api/v1/web-lead", {}, token="test-api-key-12345")
        self.assertIn(resp.status_code, (400, 422))

    def test_malformed_json_returns_400(self):
        """Non-JSON body returns 400."""
        headers = {"Content-Type": "application/json", "Authorization": "Bearer test-api-key-12345"}
        resp = self.url_open("/api/v1/web-lead", data=b"not json{{{", headers=headers)
        self.assertEqual(resp.status_code, 400)

    def test_missing_lead_id_returns_422(self):
        """Missing lead_id returns 422."""
        resp = self._post_json("/api/v1/web-lead", {"decision": "Hot"}, token="test-api-key-12345")
        self.assertEqual(resp.status_code, 422)

    def test_missing_decision_returns_422(self):
        """Missing decision returns 422."""
        resp = self._post_json("/api/v1/web-lead", {"lead_id": "WL-X"}, token="test-api-key-12345")
        self.assertEqual(resp.status_code, 422)

    # ─── Successful Lead Processing ──────────────────────────

    def test_cold_lead_skipped(self):
        """Cold lead is received and marked as skipped."""
        resp = self._post_json(
            "/api/v1/web-lead",
            {
                "lead_id": "WL-COLD-1",
                "decision": "Cold",
                "decision_reasons": ["no_volume"],
                "raw_payload": {"company": "Test Corp"},
            },
            token="test-api-key-12345",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["state"], "skipped")

    def test_hot_lead_creates_intake(self):
        """Hot lead creates web lead + partner + intake."""
        resp = self._post_json(
            "/api/v1/web-lead",
            {
                "lead_id": "WL-HOT-1",
                "decision": "Hot",
                "decision_reasons": ["high_volume"],
                "raw_payload": {
                    "company": "Hot LLC",
                    "email": "h@t.com",
                    "material_type": "HDPE",
                    "form": "Bales",
                    "quantity_lbs": 40000,
                },
            },
            token="test-api-key-12345",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn(body["state"], ("intake_created", "received"))

    # ─── Cognito Webhook ─────────────────────────────────────

    def test_cognito_webhook_requires_auth(self):
        resp = self._post_json("/api/v1/cognito-webhook", {"Name": "Test"})
        self.assertEqual(resp.status_code, 401)

    def test_cognito_webhook_valid(self):
        resp = self._post_json(
            "/api/v1/cognito-webhook",
            {
                "Name": "Cognito Corp",
                "Email": "c@t.com",
                "Material": "PP",
                "Form": "Regrind",
            },
            token="test-api-key-12345",
        )
        self.assertEqual(resp.status_code, 200)

    # ─── Health Check ────────────────────────────────────────

    def test_health_check(self):
        resp = self.url_open("/api/v1/web-lead/health")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("status", resp.json())
