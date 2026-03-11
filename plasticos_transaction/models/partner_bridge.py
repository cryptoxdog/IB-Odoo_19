from odoo import api, fields, models

PLASTICOS_TRANSACTION = "plasticos.transaction"


class ResPartnerTxBridge(models.Model):
    """Adds PlasticOS transaction count and navigation to partner."""

    _inherit = "res.partner"

    transaction_as_supplier_ids = fields.One2many(
        PLASTICOS_TRANSACTION,
        "supplier_id",
        string="Transactions (Supplier)",
    )
    transaction_as_buyer_ids = fields.One2many(
        PLASTICOS_TRANSACTION,
        "buyer_id",
        string="Transactions (Buyer)",
    )
    plasticos_transaction_count = fields.Integer(
        compute="_compute_plasticos_transaction_count",
        string="Transaction Count",
    )

    @api.depends("transaction_as_supplier_ids", "transaction_as_buyer_ids")
    def _compute_plasticos_transaction_count(self):
        for rec in self:
            rec.plasticos_transaction_count = len(rec.transaction_as_supplier_ids) + len(rec.transaction_as_buyer_ids)

    def action_view_plasticos_transactions(self):
        """View all transactions where this partner is supplier or buyer."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Transactions — {self.name}",
            "res_model": PLASTICOS_TRANSACTION,
            "view_mode": "list,form",
            "domain": [
                "|",
                ("supplier_id", "=", self.id),
                ("buyer_id", "=", self.id),
            ],
        }
