from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    enrichment_run_ids = fields.One2many(
        "plasticos.enrichment.run",
        "partner_id",
        string="Enrichment Runs",
    )
    enrichment_source_ids = fields.One2many(
        "plasticos.enrichment.source",
        "partner_id",
        string="Enrichment Sources",
    )
