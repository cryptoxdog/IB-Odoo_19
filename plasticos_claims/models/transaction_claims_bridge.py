from odoo import api, fields, models


class PlasticosTransactionClaimsBridge(models.Model):
    """Adds claim_ids reverse + smart-button nav to transaction."""

    _inherit = "plasticos.transaction"

    claim_ids = fields.One2many(
        "plasticos.claim",
        "transaction_id",
        string="Claims",
        help="QC cases, chargebacks, and penalty claims.",
    )
    claim_count = fields.Integer(
        compute="_compute_claim_count",
        string="Claim Count",
    )

    @api.depends("claim_ids")
    def _compute_claim_count(self):
        for rec in self:
            rec.claim_count = len(rec.claim_ids)

    def action_view_claims(self):
        """Open claims linked to this transaction."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Claims — {self.name}",
            "res_model": "plasticos.claim",
            "view_mode": "list,form",
            "domain": [("transaction_id", "=", self.id)],
            "context": {"default_transaction_id": self.id},
        }
