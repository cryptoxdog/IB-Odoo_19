from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


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
        """Copy the last completed deal and change only the dates.

        Buyer, supplier, materials, prices, carrier, and freight rate stay as they
        were. Draft sale and purchase orders are not confirmed, and a missing
        booking fingerprint does not exclude the source. A second click finds the
        drafts already created and stops.
        """
        self.ensure_one()
        source = self._latest_completed_deal()
        if not source.sale_order_id or not source.purchase_order_ids:
            raise UserError("Same As Last needs a completed deal with a sale order and a purchase order.")
        marker = f"SAL:{source.sale_order_id.id}"
        existing = self.env["sale.order"].search(
            [("origin", "=", marker), ("state", "in", ("draft", "sent"))],
            limit=1,
        )
        if existing:
            raise UserError("Same As Last drafts for this deal already exist.")
        now = fields.Datetime.now()
        new_sale = source.sale_order_id.copy(default={"origin": marker, "date_order": now})
        new_sale.write({"origin": marker, "date_order": now})
        new_purchases = source.purchase_order_ids.copy(default={"origin": marker, "date_order": now})
        new_purchases.write({"origin": marker, "date_order": now})
        if len(source.load_ids) == 1:
            load = source.load_ids
            self.env["plasticos.load"].create(
                {
                    "sale_order_id": new_sale.id,
                    "carrier_id": load.carrier_id.id,
                    "rate_amount": load.rate_amount,
                    "rate_currency_id": load.rate_currency_id.id,
                }
            )
        return {
            "type": "ir.actions.act_window",
            "name": "Same As Last",
            "res_model": "sale.order",
            "res_id": new_sale.id,
            "view_mode": "form",
            "target": "current",
        }

    def _latest_completed_deal(self):
        """Newest delivered, invoiced, or closed transaction in this company."""
        company = (self.sale_order_id.company_id if self.sale_order_id else False) or self.env.company
        candidates = self.search([("state", "in", ("delivered", "invoiced", "closed"))], order="id desc")
        for transaction in candidates:
            transaction_company = transaction.sale_order_id.company_id or self.env.company
            if transaction_company == company:
                return transaction
        raise UserError("No completed deal is available for Same As Last.")

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
