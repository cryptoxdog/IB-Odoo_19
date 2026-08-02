"""Link match results to auditable Gate match runs."""

from odoo import fields, models


class PlasticosMatchResultRunLink(models.Model):
    _inherit = "plasticos.match.result"

    match_run_id = fields.Many2one(
        "plasticos.match.run",
        string="Match Run",
        index=True,
        ondelete="set null",
    )
