from odoo import models


class PlasticosTransactionClaimsBridge(models.Model):
    """Smart-button navigation to claims from transaction.

    Note: claim_ids, claim_count, has_quality_claim, and compute methods
    are defined in transaction_claims.py. This file only adds navigation.
    """

    _inherit = "plasticos.transaction"

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
