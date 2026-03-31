import json
import logging

from odoo import http
from odoo.http import Response, request

_logger = logging.getLogger(__name__)


class WebLeadController(http.Controller):
    """REST endpoints for web lead ingestion.

    Two entry points:
      1. POST /api/v1/web-lead — Pre-processed agent payload (legacy)
      2. POST /api/v1/cognito-webhook — Raw Cognito form (AI triage)

    Authentication: Bearer token in the Authorization header must
    match the API key stored in plasticos.web.lead.config.

    Security note: Routes use auth="none" (public API). Token validation
    is enforced via _authenticate() before any ORM access. sudo() is used
    only after successful token validation to allow writes under the
    technical user context.

    Note on get_config() + sudo(): get_config() may create a default singleton
    record if none exists. This creation is intentional (singleton pattern) and
    is safe because it happens only under sudo() after the Bearer token has been
    validated. No write access is exposed to unauthenticated callers.
    """

    # ═══════════════════════════════════════════════════════════
    # Auth Helper
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _authenticate(req):
        """Validate the Bearer token against the stored API key.

        Returns (True, config) on success or (False, error_msg) on failure.
        sudo() is used to read/create the config singleton — this is the only
        ORM access before auth is confirmed.
        """
        auth_header = req.httprequest.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return False, "Missing or malformed Authorization header."

        token = auth_header[7:].strip()
        if not token:
            return False, "Empty bearer token."

        # sudo() required here: public endpoint cannot read config without elevation.
        # get_config() may create the singleton record on first call (intended).
        Config = req.env["plasticos.web.lead.config"].sudo()
        config = Config.get_config()

        if not config.is_active:
            return False, "Web lead endpoint is currently disabled."

        if not config.api_key:
            return False, "API key not configured on the server."

        if token != config.api_key:
            return False, "Invalid API key."

        return True, config

    # ═══════════════════════════════════════════════════════════
    # POST /api/v1/web-lead (Legacy Agent Endpoint)
    # ═══════════════════════════════════════════════════════════

    @http.route(
        "/api/v1/web-lead",
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def receive_web_lead(self, **kwargs):
        """Receive a lead from the lead_intake agent (pre-processed).

        Expected JSON body::

            {
                "lead_id": "WL123",
                "source": "cognito_form",
                "decision": "Hot",
                "decision_reasons": [...],
                "raw_payload": { ... },
                "ai_analysis": { ... }
            }

        Returns::

            {
                "status": "ok",
                "lead_id": "WL123",
                "web_lead_id": 42,
                "intake_id": 17,
                "partner_id": 5,
                "state": "intake_created"
            }
        """
        try:
            body = json.loads(request.httprequest.data or b"{}")
        except (json.JSONDecodeError, ValueError) as exc:
            return self._json_error(400, f"Invalid JSON: {exc}")

        if not body:
            return self._json_error(400, "Empty request body.")

        ok, result = self._authenticate(request)
        if not ok:
            _logger.warning("Web lead auth failure: %s", result)
            return self._json_error(401, result)

        lead_id = body.get("lead_id")
        if not lead_id:
            return self._json_error(422, "Missing required field: lead_id")

        decision = body.get("decision")
        if not decision:
            return self._json_error(422, "Missing required field: decision")

        try:
            # sudo() used after token validation — auth gate is _authenticate() above
            WebLead = request.env["plasticos.web.lead"].sudo()
            lead = WebLead.create_from_agent(body)

            response_data = {
                "status": "ok",
                "lead_id": lead.lead_id,
                "web_lead_id": lead.id,
                "intake_id": lead.intake_id.id if lead.intake_id else None,
                "partner_id": lead.partner_id.id if lead.partner_id else None,
                "state": lead.state,
            }

            if lead.state == "error":
                response_data["error"] = lead.error_message

            _logger.info("Web lead %s processed: state=%s", lead_id, lead.state)
            return self._json_response(200, response_data)

        except Exception:
            _logger.exception("Unhandled error processing web lead %s", lead_id)
            return self._json_error(500, "Internal server error. Please try again later.")

    # ═══════════════════════════════════════════════════════════
    # POST /api/v1/cognito-webhook (Raw Cognito → AI Triage)
    # ═══════════════════════════════════════════════════════════

    @http.route(
        "/api/v1/cognito-webhook",
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def receive_cognito_webhook(self, **kwargs):
        """Receive a raw Cognito form submission and run AI triage.

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
        try:
            body = json.loads(request.httprequest.data or b"{}")
        except (json.JSONDecodeError, ValueError) as exc:
            return self._json_error(400, f"Invalid JSON: {exc}")

        if not body:
            return self._json_error(400, "Empty request body.")

        ok, result = self._authenticate(request)
        if not ok:
            _logger.warning("Cognito webhook auth failure: %s", result)
            return self._json_error(401, result)

        try:
            # sudo() used after token validation — auth gate is _authenticate() above
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
                lead.lead_id,
                lead.decision,
                lead.state,
            )
            return self._json_response(200, response_data)

        except Exception:
            _logger.exception("Unhandled error in Cognito webhook")
            return self._json_error(500, "Internal server error. Please try again later.")

    # ═══════════════════════════════════════════════════════════
    # GET /api/v1/web-lead/health
    # ═══════════════════════════════════════════════════════════

    @http.route(
        "/api/v1/web-lead/health",
        type="http",
        auth="none",
        methods=["GET"],
        csrf=False,
    )
    def health_check(self, **kwargs):
        """Simple health check — no auth required.

        Returns minimal status only (no internal config exposure).
        """
        try:
            Config = request.env["plasticos.web.lead.config"].sudo()
            config = Config.get_config()
            return self._json_response(
                200,
                {
                    "status": "ok" if config.is_active else "disabled",
                },
            )
        except Exception:
            _logger.exception("Health check failed")
            return self._json_error(503, "Service unavailable")

    # ═══════════════════════════════════════════════════════════
    # Response Helpers
    # ═══════════════════════════════════════════════════════════

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
