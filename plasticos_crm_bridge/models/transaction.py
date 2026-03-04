from odoo import fields, models


class PlasticosTransactionCrmBridge(models.Model):
    _inherit = "plasticos.transaction"

    crm_lead_id = fields.Many2one(
        "crm.lead",
        string="CRM Lead",
        index=True,
        ondelete="set null",
        help="Optional CRM lead backlink for traceability.",
    )
