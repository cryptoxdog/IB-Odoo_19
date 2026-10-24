"""Linda PO issuance hooks on native ``purchase.order`` (WP01b, BRS-01-R001/R065).

Native ``button_approve`` is the only path into ``purchase``: manager-direct
``button_confirm`` calls it, and two-step approval calls it after ``to approve``.
Issuance is therefore observed after that method, never triggered by drafts,
``to approve``, imports or ``plasticos.transaction.action_activate``.
"""

from odoo import fields, models

from .linda_request import LINDA_MODE_LIVE, MATERIAL_PO_FIELDS

LOGISTICS_REQUEST = "plasticos.logistics.request"
ORDER_CANCEL = "cancel"


class PurchaseOrderInherit(models.Model):
    _inherit = "purchase.order"

    linda_request_ids = fields.One2many(
        LOGISTICS_REQUEST,
        "purchase_order_id",
        string="Linda Requests",
        readonly=True,
        help="Order-scoped Linda issuance evidence for this purchase order.",
    )

    def button_approve(self, force=False):
        previous_state = {order.id: order.state for order in self}
        res = super().button_approve(force=force)
        released = self.filtered(lambda order: previous_state.get(order.id) != "purchase" and order.state == "purchase")
        if released:
            self.env[LOGISTICS_REQUEST]._issue_purchase_orders(released)
        return res

    def write(self, vals):
        # A real cancellation is a successful move into ``cancel``. Native cancel refuses
        # locked or invoiced orders before writing, and a later failure rolls this back too.
        canceling = (
            self.filtered(lambda order: order.state != ORDER_CANCEL) if vals.get("state") == ORDER_CANCEL else ()
        )
        res = super().write(vals)
        if canceling:
            # Before the stale-queue sweep below: an issue that may already have reached the
            # party is settled first, so the sweep only cancels mail nobody ever received.
            self.env[LOGISTICS_REQUEST]._record_cancellations(canceling)
        if MATERIAL_PO_FIELDS.intersection(vals) and self.ids:
            self.env[LOGISTICS_REQUEST]._cancel_stale_for_orders(self)
        return res

    def _linda_owns_po_issuance(self):
        """True when Linda, not the legacy automation, sends the initial supplier PO."""
        return self.env[LOGISTICS_REQUEST]._linda_mode() == LINDA_MODE_LIVE
