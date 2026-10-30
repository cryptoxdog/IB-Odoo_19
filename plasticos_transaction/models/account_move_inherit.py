from odoo import api, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    # action_post: on posting, link move to transaction (SO -> tx) and enforce compliance
    #   before setting customer_invoice_id. Prevents posting customer invoice if tx missing docs.
    # button_cancel: prevent cancelling a move that is linked to a closed transaction
    #   (audit integrity: closed tx must not have its invoices/bills undone).

    def _find_linked_transactions(self, move_id):
        """Find transactions linked to a move via any bill type.

        Checks customer_invoice_id, vendor_bill_ids, AND freight_bill_ids.
        """
        return self.env["plasticos.transaction"].search(
            [
                "|",
                "|",
                ("customer_invoice_id", "=", move_id),
                ("vendor_bill_ids", "in", move_id),
                ("freight_bill_ids", "in", move_id),
            ]
        )

    def _historical_source_ids(self):
        """Identify archived originals by locked native import XMLIDs, not text refs.

        Reject false-positive SQL LIKE matches using a literal prefix check.
        The historical and cutover roles may never share source XMLIDs.
        """
        if not self:
            return set()
        markers = (
            self.env["ir.model.data"]
            .sudo()
            .search(
                [
                    ("module", "=", "plasticos_transaction"),
                    ("model", "=", "account.move"),
                    ("res_id", "in", self.ids),
                    "|",
                    "|",
                    ("name", "=like", "legacy_erp_outinv_%"),
                    ("name", "=like", "legacy_erp_ininv_%"),
                    ("name", "=like", "legacy_erp_ledger_%"),
                ]
            )
        )
        prefixes = ("legacy_erp_outinv_", "legacy_erp_ininv_", "legacy_erp_ledger_")
        return {marker.res_id for marker in markers if marker.name.startswith(prefixes)}

    def write(self, vals):
        protected = {
            "state",
            "invoice_line_ids",
            "line_ids",
            "partner_id",
            "company_id",
            "currency_id",
            "journal_id",
            "ref",
            "invoice_origin",
            "invoice_date",
            "invoice_date_due",
            "invoice_payment_term_id",
            "date",
            "payment_state",
            "reversed_entry_id",
        }
        if protected.intersection(vals) and self._historical_source_ids():
            raise UserError("Archived ERP source documents are read-only and cannot be posted or rewritten.")
        return super().write(vals)

    def button_cancel(self):
        if self._historical_source_ids():
            raise UserError("Archived ERP source documents cannot be cancelled.")
        for move in self:
            tx = self._find_linked_transactions(move.id)
            if tx.filtered(lambda t: t.state == "closed"):
                raise UserError("Cannot cancel invoice/bill linked to closed transaction.")
        return super().button_cancel()

    def action_post(self):
        """Post invoice/bill with compliance check BEFORE posting.

        Compliance check runs before super().action_post() to prevent side effects
        (webhooks, email notifications) from firing before potential rollback.
        """
        if self._historical_source_ids():
            raise UserError("Archived ERP invoices, vendor bills and credits cannot be posted.")
        service = self.env["plasticos.compliance.service"] if "plasticos.compliance.service" in self.env else None

        # Batch query: collect all invoice_origins for SO lookup
        out_invoice_origins = [
            rec.invoice_origin for rec in self if rec.move_type == "out_invoice" and rec.invoice_origin
        ]
        in_invoice_origins = [
            rec.invoice_origin for rec in self if rec.move_type == "in_invoice" and rec.invoice_origin
        ]
        all_origins = list(set(out_invoice_origins + in_invoice_origins))

        # Batch fetch SOs and POs
        so_by_name = {}
        po_by_name = {}
        if all_origins:
            sale_orders = self.env["sale.order"].search([("name", "in", all_origins)])
            so_by_name = {so.name: so for so in sale_orders}
            # For origins not found as SOs, try POs
            missing_origins = [o for o in in_invoice_origins if o not in so_by_name]
            if missing_origins:
                purchase_orders = self.env["purchase.order"].search([("name", "in", missing_origins)])
                po_by_name = {po.name: po for po in purchase_orders}

        # Pre-check compliance BEFORE posting (prevents side effects on rollback)
        for rec in self:
            if rec.move_type == "out_invoice" and rec.invoice_origin:
                so = so_by_name.get(rec.invoice_origin)
                if so and so.transaction_id and so.transaction_id.state == "closed":
                    raise UserError("A new invoice cannot be attached to a historically closed trade.")
                if so and so.transaction_id:
                    # An empty AbstractModel recordset is falsy: test for None, not truthiness.
                    if service is not None and not service.is_compliant(
                        "plasticos.transaction", so.transaction_id.id, purpose="invoice"
                    ):
                        raise UserError("Missing required documents for invoice posting.")

            # Block credit note post when reversed move is linked to closed transaction
            if rec.move_type in ("out_refund", "in_refund") and rec.reversed_entry_id:
                tx = self._find_linked_transactions(rec.reversed_entry_id.id)
                if tx.filtered(lambda t: t.state == "closed"):
                    raise UserError("Cannot post credit note for closed transaction.")

        # A separately approved cutoff opening item carries no commercial origin;
        # it must never create a trade linkage or bypass normal native posting.
        if "plasticos_cutover_opening" in self._fields:
            if self.filtered(lambda move: move.plasticos_cutover_opening and move.invoice_origin):
                raise UserError("Cutover opening items must not carry a commercial invoice origin.")
        # Now safe to post
        res = super().action_post()

        # Batch fetch transactions for POs (for vendor bill linking)
        po_ids = [po.id for po in po_by_name.values()]
        tx_by_po = {}
        if po_ids:
            transactions = self.env["plasticos.transaction"].search([("purchase_order_ids", "in", po_ids)])
            for tx in transactions:
                for po in tx.purchase_order_ids:
                    tx_by_po[po.id] = tx

        # Link moves to transactions AFTER successful post
        for rec in self:
            if rec.move_type == "out_invoice" and rec.invoice_origin:
                so = so_by_name.get(rec.invoice_origin)
                if so and so.transaction_id:
                    so.transaction_id.customer_invoice_id = rec.id

            if rec.move_type == "in_invoice" and rec.invoice_origin:
                # Try linking via Sale Order (if origin is SO name)
                so = so_by_name.get(rec.invoice_origin)
                if so and so.transaction_id:
                    so.transaction_id.vendor_bill_ids = [(4, rec.id)]
                else:
                    # Try linking via Purchase Order (if origin is PO name)
                    po = po_by_name.get(rec.invoice_origin)
                    if po and po.id in tx_by_po:
                        tx_by_po[po.id].vendor_bill_ids = [(4, rec.id)]

        return res

    def unlink(self):
        if self._historical_source_ids():
            raise UserError("Archived ERP source documents cannot be deleted.")
        for move in self:
            tx = self._find_linked_transactions(move.id)
            if tx.filtered(lambda t: t.state == "closed"):
                raise UserError("Cannot delete invoice/bill linked to closed transaction.")
        return super().unlink()


class AccountMoveLine(models.Model):
    """Protect source gross lines even when called outside account.move.write()."""

    _inherit = "account.move.line"

    def _reject_historical_source(self, move_ids):
        move_ids = set(move_ids)
        if not move_ids:
            return
        moves = self.env["account.move"].browse(list(move_ids)).exists()
        if moves._historical_source_ids():
            raise UserError("Historical ERP source journal lines are immutable.")

    @api.model_create_multi
    def create(self, vals_list):
        self._reject_historical_source([v["move_id"] for v in vals_list if v.get("move_id")])
        return super().create(vals_list)

    def write(self, vals):
        if vals:
            self._reject_historical_source(self.mapped("move_id").ids)
            if vals.get("move_id"):
                self._reject_historical_source([vals["move_id"]])
        return super().write(vals)

    def unlink(self):
        self._reject_historical_source(self.mapped("move_id").ids)
        return super().unlink()
