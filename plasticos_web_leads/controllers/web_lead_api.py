import json
import logging

from odoo import http
from odoo.exceptions import ConcurrencyError, UserError, ValidationError
from odoo.http import Response, request

from ..adapters.base import EVENT_SUBMITTED, InboundRequest
from ..adapters.registry import get_adapter

_logger = logging.getLogger(__name__)

STATUS_OK = "ok"
STATUS_IGNORED = "ignored"
STATUS_REJECTED = "rejected"


class WebLeadController(http.Controller):
    """REST endpoint for provider-neutral web lead admission.

    One generic route admits every registered provider. The Cognito webhook
    path remains as an alias that selects the ``cognito`` adapter.

    Authentication: the adapter reads ``?access_token=``, ``Authorization:
    Bearer``, or ``X-API-Key`` and compares it to the API key stored on
    plasticos.web.lead.config.

    Security note: Routes use auth="none" (public API). Token validation
    is enforced via _authenticate() before any write. sudo() is used
    only after successful token validation.

    Note on get_config() + sudo(): get_config() may create a default singleton
    record if none exists. This creation is intentional (singleton pattern) and
    is safe because it happens only under sudo() after the token has been
    validated. No write access is exposed to unauthenticated callers.
    """

    @staticmethod
    def _inbound_request(req) -> InboundRequest:
        """Project the HTTP call into the port's transport object."""
        httprequest = req.httprequest
        return InboundRequest(
            headers=httprequest.headers,
            query=httprequest.args,
            raw_body=httprequest.get_data() or b"",
        )

    @staticmethod
    def _authenticate(req, adapter):
        """Validate presented tokens against stored web-lead API key(s).

        Returns (True, config) on success or (False, error_msg) on failure.
        sudo() is used to read config — this is the only ORM access before auth
        is confirmed.

        Matching strategy: accept the call if any presented token equals the
        api_key on ANY active config row (read via SQL). The Settings form and
        get_config() are supposed to be a singleton, but orphan duplicate rows
        have caused "wizard showed key → API Invalid API key" mismatches.
        """
        inbound = WebLeadController._inbound_request(req)
        tokens = adapter.presented_tokens(inbound)
        if not tokens:
            return False, "Missing API token (expected access_token, Bearer, or X-API-Key)."

        # sudo() required here: public endpoint cannot read config without elevation.
        Config = req.env["plasticos.web.lead.config"].sudo()
        config = Config.get_config()

        if not config.is_active:
            return False, "Web lead endpoint is currently disabled."

        # SQL read bypasses field-level groups= masking and compares against every
        # row so a key written on the Settings form record still authenticates even
        # if an older orphan config is what search([], limit=1) would return.
        req.env.cr.execute(
            """
            SELECT id, api_key
            FROM plasticos_web_lead_config
            WHERE COALESCE(is_active, TRUE) IS TRUE
              AND api_key IS NOT NULL
              AND BTRIM(api_key) <> ''
            ORDER BY id ASC
            """
        )
        rows = req.env.cr.fetchall()
        if not rows:
            return False, "API key not configured on the server."

        matched_id = None
        for row_id, stored in rows:
            stored_key = (stored or "").strip()
            if stored_key and adapter.authenticate(inbound, secret=stored_key):
                matched_id = row_id
                break

        if matched_id is None:
            # Safe diagnostic: lengths only — never log the raw key.
            presented_lens = [len(token) for token in tokens]
            stored_lens = [len((stored or "").strip()) for _id, stored in rows]
            _logger.warning(
                "Web lead auth mismatch: presented_lens=%s stored_lens=%s config_ids=%s",
                presented_lens,
                stored_lens,
                [row_id for row_id, _stored in rows],
            )
            return False, "Invalid API key."

        matched = Config.browse(matched_id)
        return True, matched

    # readonly=False: Odoo 19 defaults auth="none" routes to a read-only cursor
    # and only retries read/write when ReadOnlySqlTransaction escapes the
    # controller. These handlers translate exceptions into JSON responses, so
    # without the explicit declaration every admission would fail with
    # "cannot execute INSERT in a read-only transaction" as a 500.
    @http.route(
        "/api/v1/web-lead/inbound/<string:provider_key>",
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
        readonly=False,
    )
    def receive_inbound(self, provider_key, **kwargs):
        """Admit one provider submission through the registered adapter."""
        return self._receive_inbound(provider_key)

    @http.route(
        "/api/v1/cognito-webhook",
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
        readonly=False,
    )
    def receive_cognito_webhook(self, **kwargs):
        """Alias that selects the Cognito Forms adapter."""
        return self._receive_inbound("cognito")

    def _receive_inbound(self, provider_key):
        """Shared admission: parse, resolve adapter, authenticate, then admit."""
        try:
            body = json.loads(request.httprequest.get_data(as_text=True) or "")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self._json_error(400, "Request body must be valid JSON.")
        if not isinstance(body, dict) or not body:
            return self._json_error(400, "Request body must be a JSON object.")

        try:
            adapter = get_adapter(provider_key)
        except ValueError as exc:
            return self._json_error(404, str(exc))

        ok, result = self._authenticate(request, adapter)
        if not ok:
            _logger.warning("Inbound auth failed for provider %s: %s", provider_key, result)
            return self._json_error(401, result)

        WebLead = request.env["plasticos.web.lead"].sudo()  # sudo after token validation
        try:
            event, lead = WebLead.admit_inbound(provider_key, body)
        except (UserError, ValidationError) as exc:
            _logger.warning("Inbound payload rejected for provider %s: %s", provider_key, exc)
            lead = WebLead.record_rejected_inbound(provider_key, body, str(exc))
            return self._json_response(
                200,
                {
                    "status": STATUS_REJECTED,
                    "message": str(exc),
                    "web_lead_id": lead.id,
                    "lead_id": lead.lead_id,
                    "state": lead.state,
                },
            )
        except ConcurrencyError:
            raise
        except Exception:
            _logger.exception("Unhandled error admitting provider %s", provider_key)
            return self._json_error(500, "Internal server error. Please try again later.")

        if event.kind != EVENT_SUBMITTED:
            return self._json_response(200, {"status": STATUS_IGNORED, "event": event.kind})

        response_data = {
            "status": STATUS_OK,
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
            "Inbound %s → lead %s: decision=%s, state=%s",
            provider_key,
            lead.lead_id,
            lead.decision,
            lead.state,
        )
        return self._json_response(200, response_data)

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
