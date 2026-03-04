from odoo import api, fields, models


class PlasticosLoadDocsBridge(models.Model):
    """Adds document_ids reverse + smart-button nav to load."""

    _inherit = "plasticos.load"

    document_ids = fields.One2many(
        "plasticos.document",
        "load_id",
        string="Documents",
        help="BOLs, weight tickets, and other documents for this load.",
    )
    document_count = fields.Integer(
        compute="_compute_document_count",
        string="Document Count",
    )

    @api.depends("document_ids")
    def _compute_document_count(self):
        for rec in self:
            rec.document_count = len(rec.document_ids)

    def action_view_documents(self):
        """View documents linked to this load."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Documents — {self.name}",
            "res_model": "plasticos.document",
            "view_mode": "list,form",
            "domain": [("load_id", "=", self.id)],
            "context": {"default_load_id": self.id},
        }
