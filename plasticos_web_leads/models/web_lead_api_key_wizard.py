"""One-shot display of a newly generated web-lead API key (copy-friendly)."""

from odoo import fields, models


class PlasticosWebLeadApiKeyWizard(models.TransientModel):
    _name = "plasticos.web.lead.api.key.wizard"
    _description = "Show new Web Lead API Key"

    config_id = fields.Many2one("plasticos.web.lead.config", string="Configuration", ondelete="restrict")
    api_key = fields.Char(
        string="New API Key",
        readonly=True,
        help="Copy this value now. Admins can also reveal the stored key later on Web Lead Config.",
    )
