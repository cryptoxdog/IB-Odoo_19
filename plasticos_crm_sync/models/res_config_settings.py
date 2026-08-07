from odoo import _, fields, models
from odoo.exceptions import UserError

from .crm_connection import ICP_PROJECT, ICP_VS_KEY_PARAM


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    plasticos_crm_sync_vanillasoft_api_key = fields.Char(
        string="VanillaSoft API Key",
        config_parameter="plasticos_crm_sync.vanillasoft_api_key",
        help="Project Integration Key. Stored in system parameters; never commit to git.",
    )
    plasticos_crm_sync_vanillasoft_root_endpoint = fields.Char(
        string="VanillaSoft Root Endpoint",
        config_parameter="plasticos_crm_sync.vanillasoft_root_endpoint",
        help="e.g. https://vanillasoft.net (WSPubAPI path is appended automatically).",
    )
    plasticos_crm_sync_vanillasoft_project_id = fields.Char(
        string="VanillaSoft Project ID",
        config_parameter="plasticos_crm_sync.vanillasoft_project_id",
        help="Scrap Management ProjectID is 139705.",
    )
    plasticos_crm_sync_webhook_token = fields.Char(
        string="CRM Sync Webhook Token",
        config_parameter="plasticos_crm_sync.webhook_token",
        help="Shared secret for Outgoing Web Lead URL (?token=…).",
    )

    def action_plasticos_crm_sync_run_vanillasoft(self):
        """One-shot / manual API sync from Settings (not CSV import)."""
        self.ensure_one()
        self.set_values()
        icp = self.env["ir.config_parameter"].sudo()
        api_key = (self.plasticos_crm_sync_vanillasoft_api_key or icp.get_param(ICP_VS_KEY_PARAM) or "").strip()
        project = (self.plasticos_crm_sync_vanillasoft_project_id or icp.get_param(ICP_PROJECT) or "").strip()
        if not api_key:
            raise UserError(_("Set the VanillaSoft API Key before running API sync."))
        if not project:
            raise UserError(_("Set the VanillaSoft Project ID before running API sync."))

        connection = self.env["plasticos.crm.connection"].get_or_create_vanillasoft_connection()
        connection.action_sync_now()

        run = self.env["plasticos.crm.sync.run"].search(
            [("connection_id", "=", connection.id)],
            order="id desc",
            limit=1,
        )
        if run:
            return {
                "type": "ir.actions.act_window",
                "name": _("CRM Sync Run"),
                "res_model": "plasticos.crm.sync.run",
                "view_mode": "form",
                "res_id": run.id,
                "target": "current",
            }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("CRM Sync"),
                "message": _("VanillaSoft API sync finished for %s") % connection.name,
                "type": "success",
                "sticky": False,
            },
        }
