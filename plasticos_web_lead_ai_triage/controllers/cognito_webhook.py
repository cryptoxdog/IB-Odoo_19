# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════
# Controller: POST /api/v1/cognito-webhook
# Purpose   : Direct Cognito Forms → Odoo ingestion endpoint.
#             Replaces the old SM-Web-Lead-Triage FastAPI service.
#             Raw Cognito JSON comes in, AI triage runs inside
#             Odoo, and the response confirms HOT/COLD + IDs.
# ═══════════════════════════════════════════════════════════
import json
import logging

from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class CognitoWebhookController(http.Controller):
    """REST endpoint for direct Cognito form webhooks.

    Authentication: Bearer token matching the API key in
    ``plasticos.web.lead.config``.

    Endpoint:  POST /api/v1/cognito-webhook
    Content-Type: application/json
    Body: raw Cognito form submission JSON.
    """

    # ─────────────────────────────────────────────────────────
    # Auth helper (reuses existing web.lead.config key)
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def _authenticate(req):
        """Validate bearer token against plasticos.web.lead.config."""
        auth_header = req.httprequest.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return False, "Missing or malformed Authorization header."
        token = auth_header[7:].strip()
        if not token:
            return False, "Empty bearer token."

        Config = req.env["plasticos.web.lead.config"].sudo()
        config = Config.get_config()
        if not config.is_active:
            return False, "Web lead endpoint is currently disabled."
        if not config.api_key:
            return False, "API key not configured on the server."
        if token != config.api_key:
            return False, "Invalid API key."
        return True, config

    # ─────────────────────────────────────────────────────────
    # POST /api/v1/cognito-webhook
    # ─────────────────────────────────────────────────────────
    @http.route(
        "/api/v1/cognito-webhook",
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def receive_cognito_webhook(self, **kwargs):
        """Receive a raw Cognito form submission and run the full
        AI triage pipeline inside Odoo.

        Expected JSON body: raw Cognito form fields (no pre-processing).

        Returns::

            {
                "status": "ok",
                "lead_id": "CG-abc123",
                "web_lead_id": 42,
                "decision": "hot",
                "intake_id": 17,
                "partner_id": 5,
                "state": "intake_created"
            }
        """
        # Parse JSON body
        try:
            body = json.loads(request.httprequest.data or b"{}")
        except (json.JSONDecodeError, ValueError) as exc:
            return self._json_error(400, f"Invalid JSON: {exc}")
        if not body:
            return self._json_error(400, "Empty request body.")

        # Authenticate
        ok, result = self._authenticate(request)
        if not ok:
            _logger.warning("Cognito webhook auth failure: %s", result)
            return self._json_error(401, result)

        # Delegate to model
        try:
            WebLead = request.env["plasticos.web.lead"].sudo()
            lead = WebLead.create_from_cognito(body)

            response_data = {
                "status": "ok",
                "lead_id": lead.lead_id,
                "web_lead_id": lead.id,
                "decision": lead.decision,
                "intake_id": lead.intake_id.id if lead.intake_id else None,
                "partner_id": lead.partner_id.id if lead.partner_id else None,
                "state": lead.state,
            }
            if lead.state == "error":
                response_data["error"] = lead.error_message

            _logger.info(
                "Cognito webhook → lead %s: decision=%s, state=%s",
                lead.lead_id, lead.decision, lead.state,
            )
            return self._json_response(200, response_data)

        except Exception as exc:
            _logger.exception("Unhandled error in Cognito webhook")
            return self._json_error(500, f"Internal error: {exc}")

    # ─────────────────────────────────────────────────────────
    # Response helpers
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def _json_response(status_code, data):
        return Response(
            json.dumps(data),
            status=status_code,
            content_type="application/json",
        )

    @staticmethod
    def _json_error(status_code, message):
        return Response(
            json.dumps({"status": "error", "message": message}),
            status=status_code,
            content_type="application/json",
        )
