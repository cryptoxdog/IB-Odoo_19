"""HTTP contract for the provider-neutral inbound port."""

from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import patch

from odoo.tests import HttpCase, tagged

from ..adapters import registry
from ..adapters.base import EVENT_SUBMITTED, PACKET_SCHEMA_VERSION, InboundEvent, WebLeadAdapter, WebLeadPacket

_API_KEY = "test-web-lead-api-key-not-a-real-secret"


class _BodySigningAdapter(WebLeadAdapter):
    """A provider that signs the body with the shared secret and presents no bearer token."""

    provider_key = "signed"
    attachment_allowed_hosts = ("example.test",)

    def classify_event(self, payload):
        return InboundEvent(
            provider=self.provider_key,
            kind=EVENT_SUBMITTED,
            provider_external_id=str(payload.get("id") or ""),
            payload=payload,
        )

    def to_packet(self, payload):
        external_id = str(payload.get("id") or "")
        return WebLeadPacket(
            schema_version=PACKET_SCHEMA_VERSION,
            provider=self.provider_key,
            provider_external_id=external_id,
            idempotency_key=f"SG-{external_id}",
            submitted_at=None,
            company_name=str(payload.get("company") or ""),
            contact_name="",
            contact_email="",
            contact_phone="",
            pickup_location_text="",
            pickup_postal_code="",
            material_description=str(payload.get("material") or ""),
            material_composition_text="",
            source_description="",
            contaminants_text="",
            quantity_text="",
            weight_per_load_text="",
            frequency_text="",
            attachments=(),
            raw_payload=dict(payload),
        )

    @classmethod
    def sample_payload(cls):
        return {"id": "1", "company": "Signed Co", "material": "HDPE regrind"}

    def authenticate(self, request, *, secret):
        expected = hmac.new(secret.encode(), request.raw_body, hashlib.sha256).hexdigest()
        presented = (request.headers.get("X-Signature") or "").strip()
        return bool(secret) and hmac.compare_digest(presented, expected)


def _envelope(number="9001", action="Submit", attachments=None):
    body = {
        "Form": {"Id": "1", "Name": "Seller Intake"},
        "Entry": {"Number": number, "DateSubmitted": "2026-09-21T12:00:00Z", "Action": action},
        "YourBusinessCompanyName": "Inbound Co",
        "WhatIsIt": "HDPE regrind",
    }
    if attachments is not None:
        body["UploadPhotosOfYourScrapUpTo10"] = attachments
    return body


@tagged("post_install", "-at_install", "plasticos", "web_lead", "api")
class TestWebLeadInboundHttp(HttpCase):
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

    def _post(self, path, body, *, token=_API_KEY, query_token=False):
        url = path
        headers = {"Content-Type": "application/json"}
        if query_token:
            url = f"{path}?access_token={token}"
        elif token:
            headers["Authorization"] = f"Bearer {token}"
        return self.url_open(url, data=json.dumps(body), headers=headers)

    def test_query_token_admits_cognito_submission(self):
        response = self._post("/api/v1/web-lead/inbound/cognito", _envelope(), query_token=True)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["lead_id"], "CG-9001")
        lead = self.env["plasticos.web.lead"].browse(body["web_lead_id"])
        self.assertEqual(lead.provider_key, "cognito")
        self.assertEqual(lead.lead_id, "CG-9001")

    def test_cognito_alias_with_bearer_replays_the_same_lead(self):
        first = self._post("/api/v1/web-lead/inbound/cognito", _envelope(number="9002"), query_token=True)
        second = self._post("/api/v1/cognito-webhook", _envelope(number="9002"))
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(first.json()["web_lead_id"], second.json()["web_lead_id"])

    def test_wrong_token_is_rejected(self):
        response = self._post("/api/v1/web-lead/inbound/cognito", _envelope(), token="wrong", query_token=True)
        self.assertEqual(response.status_code, 401, response.text)

    def test_unknown_provider_is_not_found(self):
        response = self._post("/api/v1/web-lead/inbound/nope", _envelope(), query_token=True)
        self.assertEqual(response.status_code, 404, response.text)

    def test_retired_agent_route_is_gone(self):
        response = self._post("/api/v1/web-lead", _envelope())
        self.assertEqual(response.status_code, 404, response.text)

    def test_update_event_is_ignored_without_creating_a_lead(self):
        before = self.env["plasticos.web.lead"].search_count([("lead_id", "=", "CG-9003")])
        response = self._post(
            "/api/v1/web-lead/inbound/cognito",
            _envelope(number="9003", action="Update"),
            query_token=True,
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "ignored")
        self.assertEqual(self.env["plasticos.web.lead"].search_count([("lead_id", "=", "CG-9003")]), before)

    def test_invalid_attachment_is_stored_as_rejected(self):
        attachments = [
            {"Id": "dup", "Name": "a.jpg", "File": "https://www.cognitoforms.com/fa/a"},
            {"Id": "dup", "Name": "b.jpg", "File": "https://www.cognitoforms.com/fa/b"},
        ]
        response = self._post(
            "/api/v1/web-lead/inbound/cognito",
            _envelope(number="9004", attachments=attachments),
            query_token=True,
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["status"], "rejected")
        lead = self.env["plasticos.web.lead"].browse(body["web_lead_id"])
        self.assertEqual(lead.state, "error")
        self.assertTrue(lead.error_message)

    def test_non_object_json_is_a_client_error(self):
        response = self.url_open(
            f"/api/v1/web-lead/inbound/cognito?access_token={_API_KEY}",
            data=json.dumps(["not", "an", "object"]),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 400, response.text)

    def test_body_signing_adapter_authenticates_without_a_bearer_token(self):
        """Authentication is the adapter's: a signed body with no token reaches admit, a bad signature is 401."""
        body = json.dumps({"id": "sig-1", "company": "Signed Co", "material": "HDPE regrind"}).encode()
        signature = hmac.new(_API_KEY.encode(), body, hashlib.sha256).hexdigest()
        with patch.dict(registry._ADAPTERS, {"signed": _BodySigningAdapter()}):
            good = self.url_open(
                "/api/v1/web-lead/inbound/signed",
                data=body,
                headers={"Content-Type": "application/json", "X-Signature": signature},
            )
            bad = self.url_open(
                "/api/v1/web-lead/inbound/signed",
                data=body,
                headers={"Content-Type": "application/json", "X-Signature": "0" * 64},
            )
            none = self.url_open(
                "/api/v1/web-lead/inbound/signed",
                data=body,
                headers={"Content-Type": "application/json"},
            )
        self.assertEqual(good.status_code, 200, good.text)
        self.assertEqual(good.json()["status"], "ok")
        self.assertEqual(good.json()["lead_id"], "SG-sig-1")
        self.assertEqual(bad.status_code, 401, bad.text)
        self.assertEqual(none.status_code, 401, none.text)

    def test_repeated_invalid_delivery_is_one_rejection_row(self):
        attachments = [
            {"Id": "dup", "Name": "a.jpg", "File": "https://www.cognitoforms.com/fa/a"},
            {"Id": "dup", "Name": "b.jpg", "File": "https://www.cognitoforms.com/fa/b"},
        ]
        first = self._post(
            "/api/v1/web-lead/inbound/cognito", _envelope(number="9005", attachments=attachments), query_token=True
        )
        second = self._post(
            "/api/v1/web-lead/inbound/cognito", _envelope(number="9005", attachments=attachments), query_token=True
        )
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(first.json()["status"], "rejected")
        self.assertEqual(first.json()["web_lead_id"], second.json()["web_lead_id"])
        self.assertEqual(first.json()["lead_id"], "REJ-cognito-9005")
        self.assertEqual(self.env["plasticos.web.lead"].search_count([("provider_external_id", "=", "9005")]), 1)
