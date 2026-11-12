from odoo import api, models
from odoo.exceptions import UserError

HISTORICAL_ERP_MOVE_PREFIXES = ("legacy_erp_outinv_", "legacy_erp_ininv_", "legacy_erp_ledger_")
# Moves whose origin is resolved to a transaction before posting.
_ORIGIN_MOVE_TYPES = ("out_invoice", "in_invoice", "in_refund")


class AccountMove(models.Model):
    _inherit = "account.move"

    # action_post: resolve each customer invoice / vendor bill / vendor credit to at most one
    #   transaction (company-scoped SO or PO name, transaction number, delivery order number),
    #   refuse before the native post (ambiguous origin, documents, closed trade), then link.
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

        The name must start with one of the three historical prefixes. A SQL
        LIKE search is not used, because underscore matches any character.
        The historical and cutover roles may never share source XMLIDs.
        """
        if not self:
            return set()
        markers = (
            self.env["ir.model.data"]
            .sudo()  # sudo: core grants ir.model.data to group_erp_manager; reads legacy invoice markers
            .search(
                [
                    ("module", "=", "plasticos_transaction"),
                    ("model", "=", "account.move"),
                    ("res_id", "in", self.ids),
                ]
            )
        )
        return {marker.res_id for marker in markers if marker.name.startswith(HISTORICAL_ERP_MOVE_PREFIXES)}

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

    def _missing_invoice_documents(self, transaction):
        """Documents addon blocks posting when required files are missing."""
        return False

    def _origin_orders(self, model, moves):
        """Orders named by a move origin, per ``(company id, name)``. Every match is kept."""
        orders_by_key = {}
        names = list({move.invoice_origin for move in moves})
        if not names:
            return orders_by_key
        orders = self.env[model].search([("name", "in", names), ("company_id", "in", moves.company_id.ids)])
        for order in orders:
            orders_by_key.setdefault((order.company_id.id, order.name), []).append(order)
        return orders_by_key

    def _origin_numbered_transactions(self, moves, payables):
        """Transactions named by a move origin: by transaction number, or by delivery order number.

        The transaction number is unique. A delivery order number is read from
        the transaction's own stored ``do_number`` and is accepted on payables only.
        """
        Transaction = self.env["plasticos.transaction"]
        by_number = {}
        for transaction in Transaction.search([("name", "in", list({move.invoice_origin for move in moves}))]):
            by_number.setdefault(transaction.name, []).append(transaction)
        by_delivery = {}
        delivery_numbers = list({move.invoice_origin for move in payables})
        if delivery_numbers:
            for transaction in Transaction.search([("do_number", "in", delivery_numbers)]):
                by_delivery.setdefault(transaction.do_number, []).append(transaction)
        return by_number, by_delivery

    def _resolve_origin_transactions(self):
        """Resolve each customer invoice, vendor bill and vendor credit to at most one transaction.

        Returns ``(transaction_by_move, ambiguous_by_move)``. The origin must be
        exactly one reference in the move's company: a sale order name or a
        transaction number, and for payables also a purchase order name or a
        delivery order number. A name that matches more than one order, a
        purchase order held by more than one transaction, or references that
        lead to different transactions are ambiguous: no transaction is
        resolved and the reason is returned. An origin that matches nothing
        resolves nothing.
        """
        transaction_by_move = {}
        ambiguous_by_move = {}
        moves = self.filtered(lambda move: move.move_type in _ORIGIN_MOVE_TYPES and move.invoice_origin)
        if not moves:
            return transaction_by_move, ambiguous_by_move
        payables = moves.filtered(lambda move: move.move_type != "out_invoice")
        sales = self._origin_orders("sale.order", moves)
        purchases = self._origin_orders("purchase.order", payables)
        transactions_by_purchase = {}
        purchase_ids = [order.id for orders in purchases.values() for order in orders]
        if purchase_ids:
            holders = self.env["plasticos.transaction"].search([("purchase_order_ids", "in", purchase_ids)])
            for holder in holders:
                for purchase in holder.purchase_order_ids:
                    transactions_by_purchase.setdefault(purchase.id, []).append(holder)
        by_number, by_delivery = self._origin_numbered_transactions(moves, payables)
        for move in moves:
            origin = move.invoice_origin
            key = (move.company_id.id, origin)
            payable = move.move_type != "out_invoice"
            found = self.env["plasticos.transaction"]
            sale_orders = sales.get(key, [])
            purchase_orders = purchases.get(key, []) if payable else []
            if len(sale_orders) > 1:
                ambiguous_by_move[move.id] = f"more than one sale order is named {origin}"
                continue
            if len(purchase_orders) > 1:
                ambiguous_by_move[move.id] = f"more than one purchase order is named {origin}"
                continue
            if sale_orders:
                found |= sale_orders[0].transaction_id
            if purchase_orders:
                holders = transactions_by_purchase.get(purchase_orders[0].id, [])
                if len(holders) > 1:
                    ambiguous_by_move[move.id] = f"purchase order {origin} belongs to more than one transaction"
                    continue
                found = found.union(*holders)
            numbered = by_number.get(origin, []) + (by_delivery.get(origin, []) if payable else [])
            for transaction in numbered:
                sale_company = transaction.sale_order_id.company_id
                if not sale_company or sale_company == move.company_id:
                    found |= transaction
            if len(found) > 1:
                ambiguous_by_move[move.id] = f"{origin} leads to more than one transaction"
            elif found:
                transaction_by_move[move.id] = found
        return transaction_by_move, ambiguous_by_move

    def _transaction_link_field(self, transaction):
        """The transaction field that holds this move.

        A payable from the transaction's carrier is a freight bill. Any other
        payable is a vendor bill. When the carrier is also the supplier the
        role cannot be told apart and the payable stays a vendor bill.
        """
        self.ensure_one()
        if self.move_type == "out_invoice":
            return "customer_invoice_id"
        carrier = transaction.carrier_id.commercial_partner_id
        supplier = transaction.supplier_id.commercial_partner_id
        if carrier and carrier != supplier and self.commercial_partner_id == carrier:
            return "freight_bill_ids"
        return "vendor_bill_ids"

    def _lock_resolved_transactions(self, transaction_by_move):
        """Serialize this post with a concurrent close or link of the same transactions.

        The row lock is held until commit. A transaction changed by another
        request since this one began fails here with a serialization error,
        which Odoo retries against fresh state, so the checks and the link
        below never act on a stale closed state or invoice pointer.
        """
        transaction_ids = sorted({transaction.id for transaction in transaction_by_move.values()})
        if transaction_ids:
            # Justification: atomic row lock; the checks below must not read a stale transaction.
            self.env.cr.execute(
                "SELECT id FROM plasticos_transaction WHERE id IN %s ORDER BY id FOR NO KEY UPDATE",
                [tuple(transaction_ids)],
            )

    def _existing_transaction_links(self):
        """Transactions that already hold each move as invoice, vendor bill or freight bill."""
        linked_by_move = {}
        if not self.ids:
            return linked_by_move
        holders = self.env["plasticos.transaction"].search(
            [
                "|",
                "|",
                ("customer_invoice_id", "in", self.ids),
                ("vendor_bill_ids", "in", self.ids),
                ("freight_bill_ids", "in", self.ids),
            ]
        )
        wanted = set(self.ids)
        for holder in holders:
            held = set((holder.customer_invoice_id | holder.vendor_bill_ids | holder.freight_bill_ids).ids)
            for move_id in held & wanted:
                linked_by_move.setdefault(move_id, []).append(holder)
        return linked_by_move

    def _plan_transaction_links(self, transaction_by_move):
        """Decide every link before the native post. Nothing is written here.

        Returns ``(links, skipped)``: ``links`` maps a move id to the
        ``(transaction, field)`` it will be attached to after posting;
        ``skipped`` maps a move id to the reason no link is made. A
        transaction's customer invoice is never replaced, and a bill another
        transaction holds is never moved.
        """
        links = {}
        skipped = {}
        linked_by_move = self._existing_transaction_links()
        invoice_claims = {}
        for move in self:
            transaction = transaction_by_move.get(move.id)
            if not transaction:
                continue
            holders = linked_by_move.get(move.id, [])
            if any(holder != transaction for holder in holders):
                skipped[move.id] = "it is already linked to another transaction"
                continue
            if holders:
                continue
            field = move._transaction_link_field(transaction)
            if move.move_type == "out_invoice":
                current = transaction.customer_invoice_id
                claimed = invoice_claims.get(transaction.id)
                if current or claimed:
                    holder_name = (current or claimed).display_name
                    skipped[move.id] = (
                        f"transaction {transaction.display_name} already has customer invoice {holder_name}"
                    )
                    continue
                invoice_claims[transaction.id] = move
            links[move.id] = (transaction, field)
        return links, skipped

    def action_post(self):
        """Post invoice/bill. Every refusal is raised BEFORE the native post.

        Customer invoices, vendor bills and vendor credits whose origin
        resolves to exactly one transaction pass the document check and the
        closed-trade check first. An origin that names more than one order or
        transaction is refused. An origin that names nothing posts natively
        with no link. The link itself is bookkeeping written after the post;
        only writes proven acceptable beforehand are made, so it cannot roll a
        posted move back.
        """
        if self._historical_source_ids():
            raise UserError("Archived ERP invoices, vendor bills and credits cannot be posted.")
        transaction_by_move, ambiguous_by_move = self._resolve_origin_transactions()
        for rec in self:
            reason = ambiguous_by_move.get(rec.id)
            if reason:
                raise UserError(
                    f"Cannot post {rec.display_name or 'this document'}: origin {rec.invoice_origin} is ambiguous "
                    f"({reason}). Correct the origin so it names exactly one order or transaction."
                )
        self._lock_resolved_transactions(transaction_by_move)

        # Pre-check compliance BEFORE posting (prevents side effects on rollback)
        for rec in self:
            transaction = transaction_by_move.get(rec.id)
            if transaction and rec.move_type == "out_invoice":
                if transaction.state == "closed":
                    raise UserError("A new invoice cannot be attached to a historically closed trade.")
                if self._missing_invoice_documents(transaction):
                    raise UserError("Missing required documents for invoice posting.")
            elif transaction:
                if transaction.state == "closed":
                    raise UserError("A new vendor bill cannot be attached to a closed trade.")
                if self._missing_invoice_documents(transaction):
                    raise UserError("Missing required documents for vendor bill posting.")

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

        links, skipped = self._plan_transaction_links(transaction_by_move)

        # Now safe to post
        res = super().action_post()

        # Link moves to transactions AFTER successful post
        for rec in self:
            if rec.id in links:
                transaction, field = links[rec.id]
                value = rec.id if rec.move_type == "out_invoice" else [(4, rec.id)]
                # The link is bookkeeping derived from the posted document; every gate above ran as the user.
                transaction.sudo().write({field: value})  # sudo: system link write after user-evaluated gates
            reason = skipped.get(rec.id)
            if reason:
                rec.message_post(
                    body=f"Posted without a transaction link: {reason}.",
                    message_type="comment",
                    subtype_xmlid="mail.mt_note",
                )

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
