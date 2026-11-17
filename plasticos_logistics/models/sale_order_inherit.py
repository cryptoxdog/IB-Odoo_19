from odoo import api, fields, models

from .delivery_address_default import HistoryRow, last_used_delivery, latest_row_per_customer
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

    @api.depends("partner_id")
    def _compute_partner_shipping_id(self):
        """Default the delivery address to the customer's last-used one (C1 operator decision).

        Native Odoo 19 computes ``partner_shipping_id`` (stored, editable,
        precomputed) from ``partner_id.address_get(['delivery'])``. This keeps that
        result unless the customer's most recent non-cancelled order carries an
        active delivery address of the same commercial partner and a compatible
        company. A value given explicitly at create, or chosen by the user, is
        never recomputed here: the compute only runs when the customer changes.
        History is read with one search for the whole batch.
        """
        super()._compute_partner_shipping_id()
        orders = self.filtered("partner_id")
        if not orders:
            return
        commercial_ids = orders.partner_id.commercial_partner_id.ids
        own_ids = [order_id for order_id in self._origin.ids if order_id]
        domain = [
            ("partner_id.commercial_partner_id", "in", commercial_ids),
            ("state", "!=", ORDER_CANCEL),
        ]
        if own_ids:
            domain.append(("id", "not in", own_ids))
        history = self.env["sale.order"].search_fetch(
            domain,
            ["partner_id", "partner_shipping_id", "date_order"],
            order="date_order desc, id desc",
            limit=1 if len(commercial_ids) == 1 else None,
        )
        rows = (
            HistoryRow(
                commercial_partner_id=prior.partner_id.commercial_partner_id.id,
                shipping_id=prior.partner_shipping_id.id,
                shipping_active=bool(prior.partner_shipping_id.active),
                shipping_commercial_partner_id=prior.partner_shipping_id.commercial_partner_id.id,
                shipping_company_id=prior.partner_shipping_id.company_id.id or None,
            )
            for prior in history
        )
        latest = latest_row_per_customer(rows, commercial_ids)
        shipping_model = self.env["res.partner"]
        for order in orders:
            shipping_id = last_used_delivery(
                order.partner_id.commercial_partner_id.id,
                order.company_id.id or None,
                latest,
            )
            if shipping_id:
                order.partner_shipping_id = shipping_model.browse(shipping_id)

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

    def action_cancel(self):
        """Notice the buyer only after native cancel guards have succeeded.

        ``action_cancel`` refuses a locked order before ``_action_cancel``
        writes the state. A raw ``write({'state': 'cancel'})`` does not pass
        that guard and must not queue a cancellation notice.
        """
        res = super().action_cancel()
        cancelled = self.filtered(lambda order: order.state == ORDER_CANCEL)
        if cancelled:
            self.env[LOGISTICS_REQUEST]._record_cancellations(cancelled)
        return res

    def write(self, vals):
        res = super().write(vals)
        if MATERIAL_SO_FIELDS.intersection(vals) and self.ids:
            self.env[LOGISTICS_REQUEST]._cancel_stale_for_orders(self)
        return res

    def _linda_owns_so_issuance(self):
        """True when Linda, not the legacy automation, sends the initial buyer SO."""
        return self.env[LOGISTICS_REQUEST]._linda_mode() == LINDA_MODE_LIVE
