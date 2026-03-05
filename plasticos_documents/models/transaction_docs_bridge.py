from odoo import api, fields, models


class PlasticosTransactionDocsBridge(models.Model):
    """Adds document_ids reverse + smart-button nav to transaction."""

    _inherit = "plasticos.transaction"

    document_ids = fields.One2many(
        "plasticos.document",
        "transaction_id",
        string="Documents",
    )
    document_count = fields.Integer(
        compute="_compute_document_count",
        string="Document Count",
    )

    @api.depends("document_ids")
    def _compute_document_count(self):
        for rec in self:
            rec.document_count = len(rec.document_ids)

    @api.depends(
        "document_ids",
        "document_ids.verified",
        "document_ids.override",
        "document_ids.active",
        "document_ids.tag_id",
    )
    def _compute_compliance(self):
        """Override to add document_ids dependencies for auto-recompute."""
        return super()._compute_compliance()

    def action_view_documents(self):
        """Open documents linked to this transaction."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Documents — {self.name}",
            "res_model": "plasticos.document",
            "view_mode": "list,form",
            "domain": [("transaction_id", "=", self.id)],
            "context": {"default_transaction_id": self.id},
        }
