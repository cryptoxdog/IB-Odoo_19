from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError

_SAL_SOURCE_STATES = ("delivered", "invoiced", "closed")


class PlasticosTransactionLoadBridge(models.Model):
    """A transaction owns zero or more loads. The stored parent is on the load."""

    _inherit = "plasticos.transaction"

    load_ids = fields.One2many(
        "plasticos.load",
        "transaction_id",
        string="Loads",
        help="Logistics loads whose stored parent is this transaction.",
    )
    load_count = fields.Integer(compute="_compute_load_count")

    def _pickup_partners_from_loads(self):
        """Pickup partners stored on this transaction's loads."""
        return self.load_ids.mapped("pickup_partner_id")

    @api.depends("load_ids")
    def _compute_load_count(self):
        for rec in self:
            rec.load_count = len(rec.load_ids)

    def action_view_loads(self):
        """Open this transaction's loads. An empty set stays an empty set."""
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": "Loads",
            "res_model": "plasticos.load",
            "view_mode": "list,form",
            "domain": [("transaction_id", "=", self.id)],
            "context": {"default_transaction_id": self.id},
        }
        if len(self.load_ids) == 1:
            action["view_mode"] = "form"
            action["res_id"] = self.load_ids.id
        return action

    def _reconcile_new_transaction_loads(self, records):
        self.env["plasticos.load"]._reconcile_unlinked_for_transactions(records)

    def _lock_loads_for_party_write(self, vals):
        if not {"supplier_id", "buyer_id", "sale_order_id"} & set(vals):
            return
        load_model = self.env["plasticos.load"]
        # Lock sale order, then the transaction. The reverse order deadlocks
        # with a load create that already holds the sale order.
        sale_ids = set(self.mapped("sale_order_id").ids)
        if vals.get("sale_order_id"):
            sale_ids.add(vals["sale_order_id"])
        load_model._lock_rows("sale_order", sale_ids)
        load_model._lock_rows("plasticos_transaction", self.ids)
        self.invalidate_recordset(["sale_order_id", "load_ids"])

    def _refuse_loaded_sale_reassignment(self, vals):
        if "sale_order_id" not in vals:
            return
        new_sale_id = vals.get("sale_order_id") or False
        for rec in self:
            if rec.sale_order_id.id != new_sale_id and rec.load_ids:
                raise ValidationError(
                    f"Transaction {rec.name} has linked loads. "
                    "Its sale order cannot be reassigned until the loads are lawfully resolved."
                )

    def _reconcile_loads_after_party_write(self, vals):
        if {"supplier_id", "buyer_id", "sale_order_id"} & set(vals):
            self.env["plasticos.load"]._reconcile_unlinked_for_transactions(self)

    def _refuse_unlink_with_loads(self, rec):
        if rec.load_ids:
            raise UserError("Cannot delete a transaction that still has loads.")

    def _lock_load_membership_for_milestone(self, rec):
        """Serialize a milestone with load attach, reparent, and unlink.

        Lock order is the sale order, then the transaction, then loads already
        linked. The transaction lock lasts until this cursor ends. Membership
        changes bump the parent row, so an earlier REPEATABLE READ snapshot
        fails instead of advancing against loads it cannot see.
        """
        load_model = self.env["plasticos.load"]
        if rec.sale_order_id:
            load_model._lock_rows("sale_order", [rec.sale_order_id.id])
        load_model._lock_rows("plasticos_transaction", [rec.id])
        rec.invalidate_recordset(["state", "sale_order_id", "load_ids"])
        load_model._lock_rows("plasticos_load", rec.load_ids.ids)
        rec.load_ids.invalidate_recordset(["state", "transaction_id"])

    def action_same_as_last(self):
        """Copy the last completed deal as one new draft deal and change only the dates.

        The copy is a complete deal: one new draft transaction owns the copied
        draft sale order, every copied draft purchase order, and one draft load
        per source load (carrier and freight rate kept). The copied sale order
        points at that transaction, so confirming it later compiles no second
        one; each copied purchase order names the copied sale order in
        ``origin``, as the purchase confirm link expects. Buyer, supplier,
        materials, prices, carrier, and freight rate stay as they were. Nothing
        is confirmed, posted, or given a booking fingerprint.

        A copy whose deal is still open refuses another copy of the same source.
        The source row is locked and bumped first, so a concurrent second click
        fails with a serialization error, is retried, and then finds that copy.
        """
        self.ensure_one()
        source = self._latest_completed_deal()
        if not source.sale_order_id or not source.purchase_order_ids:
            raise UserError("Same As Last needs a completed deal with a sale order and a purchase order.")
        if not source.supplier_id or not source.buyer_id:
            raise UserError("Same As Last needs a completed deal with both a supplier and a buyer.")
        self._lock_same_as_last_source(source)
        marker = f"SAL:{source.sale_order_id.id}"
        open_copy = self.env["sale.order"].search(
            [
                ("origin", "=", marker),
                ("state", "!=", "cancel"),
                "|",
                ("transaction_id", "=", False),
                ("transaction_id.state", "not in", (*_SAL_SOURCE_STATES, "cancelled")),
            ],
            limit=1,
        )
        if open_copy:
            raise UserError(f"Same As Last drafts for this deal already exist ({open_copy.name}).")
        now = fields.Datetime.now()
        sale_default = {"origin": marker, "date_order": now, "transaction_id": False}
        # plasticos_automation's approval must be earned again; a copied flag would skip the threshold.
        if "approved" in source.sale_order_id._fields:
            sale_default["approved"] = False
        new_sale = source.sale_order_id.copy(default=sale_default)
        new_sale.write({"origin": marker, "date_order": now})
        new_purchases = source.purchase_order_ids.copy(default={"origin": new_sale.name, "date_order": now})
        new_purchases.write({"origin": new_sale.name, "date_order": now})
        vals = new_sale._transaction_vals(False, "")
        vals.update(
            {
                "supplier_id": source.supplier_id.id,
                "carrier_id": source.carrier_id.id,
                "purchase_order_ids": [Command.set(new_purchases.ids)],
                "product_id": source.product_id.id or vals.get("product_id"),
                "quantity": source.quantity,
                "uom_id": source.uom_id.id,
                "unit_price": source.unit_price,
                "freight_rate": source.freight_rate,
                "delivery_term": source.delivery_term,
                "pickup_dock_rule": source.pickup_dock_rule,
            }
        )
        deal = self.env["plasticos.transaction"].create(vals)
        new_sale.transaction_id = deal.id
        load_vals = [
            {
                "sale_order_id": new_sale.id,
                "transaction_id": deal.id,
                "carrier_id": load.carrier_id.id,
                "rate_amount": load.rate_amount,
                "rate_currency_id": load.rate_currency_id.id,
            }
            for load in source.load_ids.sorted("id")
        ]
        if load_vals:
            self.env["plasticos.load"].create(load_vals)
        return {
            "type": "ir.actions.act_window",
            "name": "Same As Last",
            "res_model": "plasticos.transaction",
            "res_id": deal.id,
            "view_mode": "form",
            "target": "current",
        }

    def _lock_same_as_last_source(self, source):
        """Serialize Same As Last on one source deal.

        ``FOR UPDATE`` alone does not show a copy committed after this cursor's
        REPEATABLE READ snapshot. Bumping the locked row makes the later of two
        concurrent copies fail with a serialization error, which Odoo retries.
        The load model's membership epoch already locks and bumps a transaction row.
        """
        self.env["plasticos.load"]._touch_membership_epoch([source.id])

    def _latest_completed_deal(self):
        """Newest delivered, invoiced, or closed transaction in this company."""
        company = (self.sale_order_id.company_id if self.sale_order_id else False) or self.env.company
        source = self.search(
            [("state", "in", _SAL_SOURCE_STATES), ("sale_order_id.company_id", "=", company.id)],
            order="id desc",
            limit=1,
        )
        if not source:
            raise UserError("No completed deal is available for Same As Last.")
        return source

    def _refuse_lagging_loads(self, rec, milestone, message):
        """A transaction milestone requires every linked load to have reached it.

        A transaction with no loads keeps its existing workflow, including a PO-only deal.
        """
        self._lock_load_membership_for_milestone(rec)
        if not rec.load_ids:
            return
        blocking = self.env["plasticos.load"]._loads_blocking_milestone(rec.load_ids, milestone)
        if blocking:
            names = ", ".join(blocking.mapped("name"))
            raise UserError(f"{message} Still open: {names}.")
