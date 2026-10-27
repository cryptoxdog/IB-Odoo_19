from odoo import fields, models

from .linda_request import LINDA_MODE_LIVE, MATERIAL_SO_FIELDS

LOGISTICS_REQUEST = "plasticos.logistics.request"
ORDER_CANCEL = "cancel"


class SaleOrderInherit(models.Model):
    _inherit = "sale.order"

    linda_request_ids = fields.One2many(
        LOGISTICS_REQUEST,
        "sale_order_id",
        string="Linda Requests",
        readonly=True,
        help="Order-scoped Linda issuance evidence for this sale order.",
    )

    def action_create_load(self):
        """Open load form with this sale order set as default."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "plasticos.load",
            "view_mode": "form",
            "target": "current",
            "context": {"default_sale_order_id": self.id},
        }

    def action_confirm(self):
        """Issue the buyer SO after the full native confirmation path succeeded (WP01b, BRS-01-R065).

        plasticos_automation's approval gate runs before this override and
        plasticos_transaction's compiler inside ``super()``; only orders that
        actually moved into ``sale`` here are issued. Native confirmation
        refuses orders already in ``sale``, so a replay never reaches this point.
        """
        previous_state = {order.id: order.state for order in self}
        res = super().action_confirm()
        released = self.filtered(lambda order: previous_state.get(order.id) != "sale" and order.state == "sale")
        if released:
            self.env[LOGISTICS_REQUEST]._issue_sale_orders(released)
        return res

    def _send_order_confirmation_mail(self):
        """Choose one buyer confirmation writer per order, including mixed sets.

        Native Sales owns send_email in off/shadow; Linda owns it in live.
        ``plasticos_logistics.linda_mode`` is one database parameter, not a
        per-company flag: live mode suppresses native confirmation for every
        company until an operator splits that owner. Payment-success mail is a
        different method and is not suppressed. Import, install, and skip
        contexts send nothing.
        """
        if any(self.env.context.get(key) for key in ("import_mode", "install_mode", "skip_automations")):
            return None
        native_owned = self.filtered(lambda so: not so._linda_owns_so_issuance())
        if native_owned:
            return super(SaleOrderInherit, native_owned)._send_order_confirmation_mail()
        return None

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
        if MATERIAL_SO_FIELDS.intersection(vals) and self.ids:
            self.env[LOGISTICS_REQUEST]._cancel_stale_for_orders(self)
        return res

    def _linda_owns_so_issuance(self):
        """True when Linda, not the legacy automation, sends the initial buyer SO."""
        return self.env[LOGISTICS_REQUEST]._linda_mode() == LINDA_MODE_LIVE
