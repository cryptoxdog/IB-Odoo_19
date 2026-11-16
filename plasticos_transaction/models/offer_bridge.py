from odoo import fields, models
from odoo.exceptions import UserError

CLOSED_OFFER_STATES = ("accepted", "rejected", "expired", "cancelled")


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
        # The transaction back-link is the one field a closed offer still admits; ``write``
        # narrows it to the first link of an accepted offer.
        return tuple(super()._plasticos_post_close_fields()) + ("transaction_id",)

    def _plasticos_transaction_link_error(self, value):
        """Why ``transaction_id`` may not become ``value`` on this closed offer, or None when it may.

        A closed offer admits ``transaction_id`` only as the first link of an
        accepted offer to an existing transaction compiled from this offer's sale
        order: the compiler binds the order to the offer through ``origin`` (see
        ``sale.order._plasticos_link_accepted_offer``) and the transaction to the
        order through ``sale_order_id``.
        """
        self.ensure_one()
        if isinstance(value, models.BaseModel):
            value = value.id
        transaction = self.env["plasticos.transaction"].browse(value or [])
        if self.state != "accepted":
            return f"the offer is {self.state}; only an accepted offer is linked to a transaction"
        if self.transaction_id:
            return f"it is already linked to transaction {self.transaction_id.display_name}"
        if not transaction or not transaction.exists():
            return "the link must name an existing transaction"
        origin = (transaction.sale_order_id.origin or "").strip()
        if origin != self.name:
            return f"transaction {transaction.display_name} was not compiled from this offer's sale order"
        return None

    def write(self, vals):
        """Freeze ``transaction_id`` on closed offers except for the first link of an accepted offer.

        ``plasticos.offer.write`` admits ``transaction_id`` on closed offers through
        ``_plasticos_post_close_fields``; this guard narrows that to the initial link.
        It checks every write that names ``transaction_id`` on an offer whose current
        state is closed, including one that also changes the state: then only the
        current value is admitted. Writing the current value again is a no-op.
        """
        if "transaction_id" in vals:
            for rec in self:
                if rec.state not in CLOSED_OFFER_STATES:
                    continue
                if not rec._plasticos_value_differs("transaction_id", vals["transaction_id"]):
                    continue
                if vals.get("state", rec.state) != rec.state:
                    reason = "the transaction link cannot change while the offer changes state"
                else:
                    reason = rec._plasticos_transaction_link_error(vals["transaction_id"])
                if reason:
                    raise UserError(
                        f"Cannot change the transaction of offer '{rec.name}' in state '{rec.state}': {reason}."
                    )
        return super().write(vals)

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
