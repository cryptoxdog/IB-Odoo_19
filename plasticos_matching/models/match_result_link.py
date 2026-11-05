"""Link match results to auditable Gate match runs."""

from odoo import fields, models


class PlasticosMatchResultRunLink(models.Model):
    _inherit = "plasticos.match.result"

    match_run_id = fields.Many2one(
        "plasticos.match.run",
        string="Match Run",
        index=True,
        ondelete="restrict",
        help="Gate run that produced this result. Lineage is preserved; the run cannot be deleted under it.",
    )
