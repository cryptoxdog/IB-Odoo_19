from odoo import api, models
from odoo.exceptions import UserError

HISTORICAL_ERP_MOVE_PREFIXES = ("legacy_erp_outinv_", "legacy_erp_ininv_", "legacy_erp_ledger_")


class AccountMove(models.Model):
    _inherit = "account.move"

    # action_post: resolve each customer invoice / vendor bill to at most one transaction
    #   (company-scoped SO or PO origin), refuse before the native post (documents, closed
    #   trade), then link. An ambiguous origin or an occupied link posts without linking.
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

    def _resolve_origin_transactions(self):
        """Resolve each customer invoice and vendor bill to at most one transaction.

        Returns ``(transaction_by_move, ambiguous_by_move)``. The origin must be
        exactly one order name in the move's company. A name that matches more
        than one order, or a purchase order held by more than one transaction,
        is ambiguous: no transaction is resolved and the reason is returned.
        An origin that matches nothing resolves nothing.
        """
        transaction_by_move = {}
        ambiguous_by_move = {}
        moves = self.filtered(lambda move: move.move_type in ("out_invoice", "in_invoice") and move.invoice_origin)
        if not moves:
            return transaction_by_move, ambiguous_by_move
        sales = self._origin_orders("sale.order", moves)
        bills_without_sale = moves.filtered(
            lambda move: move.move_type == "in_invoice" and (move.company_id.id, move.invoice_origin) not in sales
        )
        purchases = self._origin_orders("purchase.order", bills_without_sale)
        transactions_by_purchase = {}
        purchase_ids = [order.id for orders in purchases.values() for order in orders]
        if purchase_ids:
            holders = self.env["plasticos.transaction"].search([("purchase_order_ids", "in", purchase_ids)])
            for holder in holders:
                for purchase in holder.purchase_order_ids:
                    transactions_by_purchase.setdefault(purchase.id, []).append(holder)
        for move in moves:
            key = (move.company_id.id, move.invoice_origin)
            sale_orders = sales.get(key)
            if sale_orders:
                if len(sale_orders) > 1:
                    ambiguous_by_move[move.id] = f"more than one sale order is named {move.invoice_origin}"
                elif sale_orders[0].transaction_id:
                    transaction_by_move[move.id] = sale_orders[0].transaction_id
                continue
            purchase_orders = purchases.get(key)
            if not purchase_orders:
                continue
            if len(purchase_orders) > 1:
                ambiguous_by_move[move.id] = f"more than one purchase order is named {move.invoice_origin}"
                continue
            holders = transactions_by_purchase.get(purchase_orders[0].id, [])
            if len(holders) > 1:
                ambiguous_by_move[move.id] = (
                    f"purchase order {move.invoice_origin} belongs to more than one transaction"
                )
            elif holders:
                transaction_by_move[move.id] = holders[0]
        return transaction_by_move, ambiguous_by_move

    def _lock_resolved_transactions(self, transaction_by_move):
        """Serialize this post with a concurrent close or link of the same transactions.

        The row lock is held until commit. A transaction changed by another
        request since this one began fails here with a serialization error,
        which Odoo retries against fresh state, so the checks and the link
        below never act on a stale closed state or invoice pointer.
        """
        transaction_ids = sorted({transaction.id for transaction in transaction_by_move.values()})
        if transaction_ids:
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
        transaction it will be attached to after posting; ``skipped`` maps a
        move id to the reason no link is made. A transaction's customer invoice
        is never replaced, and a bill another transaction holds is never moved.
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
            links[move.id] = transaction
        return links, skipped

    def action_post(self):
        """Post invoice/bill. Every refusal is raised BEFORE the native post.

        Customer invoices and vendor bills that resolve to exactly one
        transaction (sale or purchase order origin, in the move's company) pass
        the document check and the closed-trade check first. Linking after the
        post only performs writes that were proven acceptable beforehand, so
        link bookkeeping cannot roll a posted move back. An ambiguous origin or
        a link that would replace existing lineage posts natively, creates no
        link, and leaves a note on the move.
        """
        if self._historical_source_ids():
            raise UserError("Archived ERP invoices, vendor bills and credits cannot be posted.")
        transaction_by_move, ambiguous_by_move = self._resolve_origin_transactions()
        self._lock_resolved_transactions(transaction_by_move)

        # Pre-check compliance BEFORE posting (prevents side effects on rollback)
        for rec in self:
            transaction = transaction_by_move.get(rec.id)
            if transaction and rec.move_type == "out_invoice":
                if transaction.state == "closed":
                    raise UserError("A new invoice cannot be attached to a historically closed trade.")
                if self._missing_invoice_documents(transaction):
                    raise UserError("Missing required documents for invoice posting.")
            if transaction and rec.move_type == "in_invoice":
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
        targets = self.env["plasticos.transaction"].union(*links.values())
        if targets:
            # The link write below must be allowed; refuse now, not after the post.
            targets.check_access("write")

        # Now safe to post
        res = super().action_post()

        # Link moves to transactions AFTER successful post
        for rec in self:
            transaction = links.get(rec.id)
            if transaction and rec.move_type == "out_invoice":
                transaction.customer_invoice_id = rec.id
            elif transaction:
                transaction.vendor_bill_ids = [(4, rec.id)]
            reason = ambiguous_by_move.get(rec.id) or skipped.get(rec.id)
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
