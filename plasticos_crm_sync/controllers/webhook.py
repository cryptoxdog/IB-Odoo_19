"""Authenticated VanillaSoft Outgoing Web Lead webhook."""

from __future__ import annotations

import hmac
import json
import logging

from odoo import http
from odoo.http import Response, request

_logger = logging.getLogger(__name__)

ICP_WEBHOOK_PARAM = "plasticos_crm_sync.webhook_token"  # ICP key name, not a secret
SUCCESS_BODY = "OK"


class PlasticosCrmSyncWebhook(http.Controller):
    @http.route(
        "/plasticos/crm_sync/vanillasoft/weblead",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def vanillasoft_weblead(self, **kwargs):
        token = self._extract_token(request)
        expected = (request.env["ir.config_parameter"].sudo().get_param(ICP_WEBHOOK_PARAM) or "").strip()
        if not expected or not token or not hmac.compare_digest(token, expected):
            return Response("Unauthorized", status=401, mimetype="text/plain")

        try:
            raw = request.httprequest.get_data(as_text=True) or ""
            payload = json.loads(raw) if raw.strip() else dict(kwargs)
        except json.JSONDecodeError:
            payload = dict(kwargs)

        contact_id = self._extract_contact_id(payload)
        if not contact_id:
            _logger.warning("CRM webhook missing ContactID")
            return Response("Missing ContactID", status=400, mimetype="text/plain")

        # Elevation happens only after the token gate above. `Environment` has no
        # `sudo()` — that is a recordset method — so the elevated environment is
        # built with `env(su=True)`, and the connection is resolved through it so
        # one environment carries the whole privileged path.
        env = request.env(su=True)
        connection = env["plasticos.crm.connection"].get_or_create_vanillasoft_connection()

        try:
            from ..services.orchestrator import SyncOrchestrator

            SyncOrchestrator(env).upsert_contact_external_id(connection, contact_id)
        except Exception:  # noqa: BLE001
            _logger.exception("CRM webhook sync failed contact=%s", contact_id)
            return Response("Error", status=500, mimetype="text/plain")

        return Response(SUCCESS_BODY, status=200, mimetype="text/plain")

    @staticmethod
    def _extract_token(req) -> str:
        q = req.httprequest.args.get("token") or ""
        if q:
            return q.strip()
        header = req.httprequest.headers.get("X-Plasticos-Webhook-Token") or ""
        if header:
            return header.strip()
        auth = req.httprequest.headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        return ""

    @staticmethod
    def _extract_contact_id(payload) -> str:
        if not isinstance(payload, dict):
            return ""
        for key in (
            "ContactID",
            "contact_id",
            "contactId",
            "ContactId",
            "id",
        ):
            val = payload.get(key)
            if val is not None and str(val).strip():
                return str(val).strip()
        # Nested contact object
        nested = payload.get("contact") or payload.get("Contact")
        if isinstance(nested, dict):
            for key in ("ContactID", "contact_id", "id"):
                val = nested.get(key)
                if val is not None and str(val).strip():
                    return str(val).strip()
        return ""
