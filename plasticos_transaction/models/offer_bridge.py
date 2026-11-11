from odoo import fields, models


class PlasticosOfferTxBridge(models.Model):
    """Adds transaction_id back-link to offer (set when offer is accepted)."""

    _inherit = "plasticos.offer"

    transaction_id = fields.Many2one(
        "plasticos.transaction",
        string="Transaction",
        index=True,
        tracking=True,
        ondelete="set null",
        help="Transaction created when this offer was accepted.",
    )

    def _plasticos_post_close_fields(self):
        # The transaction back-link is the one field an accepted offer still admits.
        return tuple(super()._plasticos_post_close_fields()) + ("transaction_id",)

    def _plasticos_link_transaction(self, transaction):
        """Server-side back-link after the compiler ran; the only write an accepted offer admits.

        ``plasticos.offer.write`` freezes closed offers except for the fields
        named by ``_plasticos_post_close_fields``.
        """
        for rec in self:
            if rec.transaction_id:
                continue
            rec.write({"transaction_id": transaction.id})

    def action_view_transaction(self):
        """Navigate to the transaction created from this offer."""
        self.ensure_one()
        if not self.transaction_id:
            return
        return {
            "type": "ir.actions.act_window",
            "name": f"Transaction — {self.transaction_id.name}",
            "res_model": "plasticos.transaction",
            "view_mode": "form",
            "res_id": self.transaction_id.id,
        }
