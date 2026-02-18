import json
import logging

from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class WebLeadController(http.Controller):
    """REST endpoint for the lead_intake agent to push HOT leads.

    Authentication: Bearer token in the Authorization header must
    match the API key stored in plasticos.web.lead.config.

    Endpoint:  POST /api/v1/web-lead
    Content-Type: application/json

    The agent sends the full LeadEnvelope as JSON. The controller
    validates auth, delegates to the model, and returns a JSON
    response with the created record IDs.
    """

    # ─────────────────────────────────────────────────────────
    # Auth helper
    # ─────────────────────────────────────────────────────────

    @staticmethod
    def _authenticate(req):
        """Validate the Bearer token against the stored API key.

        Returns (True, config) on success or (False, error_msg) on failure.
        """
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
    # POST /api/v1/web-lead
    # ─────────────────────────────────────────────────────────

    @http.route(
        "/api/v1/web-lead",
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def receive_web_lead(self, **kwargs):
        """Receive a lead from the lead_intake agent.

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
                "intake_id": 17,        // null if COLD
                "partner_id": 5,         // null if COLD
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
            _logger.warning("Web lead auth failure: %s", result)
            return self._json_error(401, result)

        # Validate required fields
        lead_id = body.get("lead_id")
        if not lead_id:
            return self._json_error(422, "Missing required field: lead_id")

        decision = body.get("decision")
        if not decision:
            return self._json_error(422, "Missing required field: decision")

        # Delegate to model
        try:
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

            _logger.info(
                "Web lead %s processed: state=%s", lead_id, lead.state,
            )
            return self._json_response(200, response_data)

        except Exception as exc:
            _logger.exception("Unhandled error processing web lead %s", lead_id)
            return self._json_error(500, f"Internal error: {exc}")

    # ─────────────────────────────────────────────────────────
    # GET /api/v1/web-lead/health
    # ─────────────────────────────────────────────────────────

    @http.route(
        "/api/v1/web-lead/health",
        type="http",
        auth="none",
        methods=["GET"],
        csrf=False,
    )
    def health_check(self, **kwargs):
        """Simple health check — no auth required."""
        try:
            Config = request.env["plasticos.web.lead.config"].sudo()
            config = Config.get_config()
            return self._json_response(200, {
                "status": "ok",
                "endpoint_active": config.is_active,
                "api_key_configured": bool(config.api_key),
            })
        except Exception as exc:
            return self._json_error(500, f"Health check failed: {exc}")

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
