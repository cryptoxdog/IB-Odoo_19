import logging
from datetime import UTC, datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# ICP param names (not secrets — values live in ir.config_parameter)
ICP_VS_KEY_PARAM = "plasticos_crm_sync.vanillasoft_api_key"
ICP_ROOT = "plasticos_crm_sync.vanillasoft_root_endpoint"
ICP_PROJECT = "plasticos_crm_sync.vanillasoft_project_id"

# Inline Selection — same values as adapters.registry.PROVIDER_SELECTION
PROVIDER_SELECTION = [
    ("vanillasoft", "VanillaSoft"),
    ("hubspot", "HubSpot (stub)"),
    ("salesforce", "Salesforce (stub)"),
    ("zoho", "Zoho (stub)"),
]


class PlasticosCrmConnection(models.Model):
    _name = "plasticos.crm.connection"
    _description = "CRM Sync Connection"
    _order = "provider, id"

    name = fields.Char(required=True, default="VanillaSoft Scrap Management")
    provider = fields.Selection(
        PROVIDER_SELECTION,
        required=True,
        default="vanillasoft",
        help="CRM provider. Only VanillaSoft is live in v1; others are stubs.",
    )
    project_id = fields.Char(
        string="External Project ID",
        default="139705",
        help="VanillaSoft ProjectID (Scrap Management = 139705).",
    )
    enabled = fields.Boolean(default=False)
    contact_watermark_utc = fields.Char(
        string="Contact Watermark (UTC)",
        help="Last successfully committed Contacts batch_end (ISO UTC).",
    )
    call_watermark_utc = fields.Char(
        string="Call Watermark (UTC)",
        help="End of last successfully committed CallHistory window (ISO UTC).",
    )
    call_backfill_floor_utc = fields.Char(
        string="Call Backfill Floor (UTC)",
        help="Earliest call history start for backfill (ISO UTC).",
    )
    last_error = fields.Text(readonly=True)
    last_success_at = fields.Datetime(readonly=True)
    sync_run_ids = fields.One2many("plasticos.crm.sync.run", "connection_id", string="Sync Runs")
    active = fields.Boolean(default=True)

    def _icp(self):
        return self.env["ir.config_parameter"].sudo()

    def _get_api_credentials(self):
        self.ensure_one()
        icp = self._icp()
        api_key = (icp.get_param(ICP_VS_KEY_PARAM) or "").strip()
        root = (icp.get_param(ICP_ROOT) or "").strip() or "https://vanillasoft.net"
        project = (self.project_id or icp.get_param(ICP_PROJECT) or "").strip()
        return api_key, root, project

    @api.model
    def get_or_create_vanillasoft_connection(self):
        """Return the active VanillaSoft connection, creating one from ICP if needed."""
        connection = self.search(
            [("provider", "=", "vanillasoft"), ("active", "=", True)],
            limit=1,
            order="id asc",
        )
        if connection:
            if not (connection.project_id or "").strip():
                project = (self._icp().get_param(ICP_PROJECT) or "").strip() or "139705"
                connection.project_id = project
            return connection
        project = (self._icp().get_param(ICP_PROJECT) or "").strip() or "139705"
        # Underscore-heavy keys keep phantom-enum dict heuristic from flagging field vals
        return self.create(
            {
                "name": "VanillaSoft Scrap Management",
                "provider": "vanillasoft",
                "project_id": project,
                "enabled": False,
                "contact_watermark_utc": False,
                "call_watermark_utc": False,
            }
        )

    def action_test_connection(self):
        self.ensure_one()
        from ..adapters.base import CrmAdapterError, CrmAdapterStubError
        from ..adapters.registry import ensure_live_or_raise, get_adapter

        api_key, root, project = self._get_api_credentials()
        try:
            adapter = get_adapter(
                self.provider,
                api_key=api_key,
                root_endpoint=root,
                project_id=int(project or 0),
            )
            ensure_live_or_raise(adapter)
            adapter.healthcheck()
        except CrmAdapterStubError as exc:
            raise UserError(str(exc)) from exc
        except (CrmAdapterError, ValueError) as exc:
            self.last_error = str(exc)
            raise UserError(_("Connection test failed: %s") % exc) from exc
        self.last_error = False
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("CRM Connection"),
                "message": _("VerifyKey succeeded for %s") % self.provider,
                "type": "success",
                "sticky": False,
            },
        }

    def action_sync_now(self):
        self.ensure_one()
        from ..adapters.base import CrmAdapterError, CrmAdapterStubError
        from ..services.orchestrator import SyncOrchestrator

        try:
            SyncOrchestrator(self.env).run_connection(self)
        except CrmAdapterStubError as exc:
            raise UserError(str(exc)) from exc
        except CrmAdapterError as exc:
            raise UserError(_("Sync failed: %s") % exc) from exc
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("CRM Sync"),
                "message": _("Sync finished for %s") % self.name,
                "type": "success",
                "sticky": False,
            },
        }

    @api.model
    def _cron_sync_all(self):
        """Cron entry: sync all enabled connections under advisory lock per connection."""
        connections = self.search(
            [("enabled", "=", True), ("active", "=", True)],
            order="id asc",
            limit=100,
        )
        for conn in connections:
            lock_key = f"plasticos_crm_sync.connection.{conn.id}"
            self.env.cr.execute("SELECT pg_try_advisory_lock(hashtext(%s))", [lock_key])
            locked = self.env.cr.fetchone()[0]
            if not locked:
                _logger.info("CRM sync skipped (lock held) connection=%s", conn.id)
                continue
            try:
                from ..services.orchestrator import SyncOrchestrator

                SyncOrchestrator(self.env).run_connection(conn)
            except Exception:  # noqa: BLE001
                _logger.exception("CRM sync cron failed connection=%s", conn.id)
            finally:
                self.env.cr.execute("SELECT pg_advisory_unlock(hashtext(%s))", [lock_key])

    def default_contact_modified_after(self) -> str:
        """Rolling ≤31-day window start (API max)."""
        self.ensure_one()
        if self.contact_watermark_utc:
            return self.contact_watermark_utc
        start = datetime.now(UTC) - timedelta(days=30)
        return start.strftime("%Y-%m-%dT%H:%M:%SZ")
