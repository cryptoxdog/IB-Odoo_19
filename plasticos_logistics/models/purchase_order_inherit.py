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

    def button_cancel(self):
        """Notice the supplier only after native cancel guards have succeeded.

        ``button_cancel`` refuses locked and invoiced orders before it writes.
        A raw ``write({'state': 'cancel'})`` does not pass those guards and
        must not queue a cancellation notice.
        """
        res = super().button_cancel()
        cancelled = self.filtered(lambda order: order.state == ORDER_CANCEL)
        if cancelled:
            self.env[LOGISTICS_REQUEST]._record_cancellations(cancelled)
        return res

    def write(self, vals):
        res = super().write(vals)
        if MATERIAL_PO_FIELDS.intersection(vals) and self.ids:
            self.env[LOGISTICS_REQUEST]._cancel_stale_for_orders(self)
        return res

    def _linda_owns_po_issuance(self):
        """True when Linda, not the legacy automation, sends the initial supplier PO."""
        return self.env[LOGISTICS_REQUEST]._linda_mode() == LINDA_MODE_LIVE
