from odoo import _, fields, models
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    plasticos_partner_import_corporate_csv = fields.Char(
        string="Corporate CSV Path",
        config_parameter="plasticos_partner_import.default_corporate_csv",
        help="Optional absolute path on the server. Empty = module default CSV.",
    )
    plasticos_partner_import_facility_csv = fields.Char(
        string="Facility CSV Path",
        config_parameter="plasticos_partner_import.default_facility_csv",
        help="Optional absolute path on the server. Empty = module default CSV.",
    )

    def action_plasticos_partner_import_run_cietrade(self):
        self.ensure_one()
        self.set_values()
        try:
            counts = self.env["plasticos.partner.import.service"].run_cietrade_default_import()
        except Exception as exc:
            if isinstance(exc, UserError):
                raise
            raise UserError(_("cieTrade partner import failed: %s") % exc) from exc
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("cieTrade Partner Import"),
                "message": _(
                    "Import finished: %(corporates)s corporates, %(facilities)s facilities, %(contacts)s contacts"
                )
                % {
                    "corporates": counts.get("corporates", 0),
                    "facilities": counts.get("facilities", 0),
                    "contacts": counts.get("contacts", 0),
                },
                "type": "success",
                "sticky": False,
            },
        }
