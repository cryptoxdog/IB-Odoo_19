from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

PLASTICOS_TRANSACTION = "plasticos.transaction"


def _worksheet_numbers(origin: str | None) -> list[str]:
    """Worksheet numbers stored on ``origin``; one native order can serve several worksheets."""
    return [token.strip() for token in (origin or "").split(",") if token.strip()]


class SaleOrder(models.Model):
    _inherit = "sale.order"

    transaction_id = fields.Many2one(PLASTICOS_TRANSACTION, ondelete="restrict")

    def _prepare_confirmation_values(self):
        """A historical order (``import_mode``) keeps its source order date on confirmation."""
        values = super()._prepare_confirmation_values()
        if self.env.context.get("import_mode"):
            values.pop("date_order", None)
        return values

    def action_confirm(self):
        """Confirm the sale order and compile its transactions.

        A historical import (``import_mode``) compiles one transaction per
        worksheet number on ``origin``, named with the worksheet number. Every
        created historical transaction starts Closed. Source status is
        provenance only. Live sales retain the normal sequence and name and
        are activated.
        """
        res = super().action_confirm()
        if self.env.context.get("import_mode"):
            self._compile_worksheet_transactions()
            return res
        recs_needing_tx = self.filtered(lambda order: not order.transaction_id)
        if not recs_needing_tx:
            return res
        transactions = self.env[PLASTICOS_TRANSACTION]
        # One create for the whole batch; create() returns records in vals order.
        # Two orders in one batch may share an origin: the later one takes the
        # suffixed name and leaves the invoice, exactly as it would have once the
        # first transaction existed.
        vals_list = []
        names_taken = set()
        invoices_taken = set()
        for order in recs_needing_tx:
            worksheet = (order.origin or "").strip()
            vals = order._transaction_vals(False, worksheet)
            if vals.get("name") in names_taken:
                vals["name"] = f"{worksheet}-{order.name}"
            if vals.get("name"):
                names_taken.add(vals["name"])
            if vals.get("customer_invoice_id") in invoices_taken:
                vals.pop("customer_invoice_id")
            if vals.get("customer_invoice_id"):
                invoices_taken.add(vals["customer_invoice_id"])
            vals_list.append(vals)
        created = transactions.create(vals_list)
        for order, tx in zip(recs_needing_tx, created, strict=True):
            order.transaction_id = tx.id
            if tx.state == "draft":
                tx.action_activate()
            order._plasticos_link_accepted_offer(tx)
        return res

    # ── Native opportunity → draft sale order (offer acceptance hand-off) ──

    def _plasticos_require_opportunity_binding(self):
        """``sale.order.opportunity_id`` (sale_crm) is the only order binding; stop when it is missing."""
        if "opportunity_id" not in self._fields:
            raise UserError(
                _("sale.order has no opportunity_id: the sale_crm bridge is not installed, so no quotation is created.")
            )

    @api.model
    def _plasticos_draft_order_for_offer(self, offer, opportunity_id, material_profile):
        """Create or reuse the one draft sale order for an accepted offer on a native opportunity.

        The order is bound through native ``opportunity_id`` and carries the
        offer's sell terms on one line. Confirmation stays with the existing
        compiler (``action_confirm``), which creates the transaction; nothing is
        confirmed, posted or mailed here.
        """
        offer.ensure_one()
        self._plasticos_require_opportunity_binding()
        existing = self.search(
            [
                ("opportunity_id", "=", opportunity_id),
                ("origin", "=", offer.name),
                ("state", "in", ("draft", "sent")),
            ],
            order="id",
            limit=1,
        )
        if existing:
            return existing
        polymer = material_profile.polymer_id if material_profile else False
        if not polymer:
            raise UserError(_("Offer %s has no approved material profile with a polymer to sell.") % offer.name)
        template = polymer._purchase_product()
        product = template.product_variant_id
        if not product:
            raise UserError(_("Polymer %s has no sellable product variant.") % polymer.name)
        description = material_profile.display_name or product.display_name
        line_name = _(
            "%(material)s — %(qty)s lbs @ %(price)s/lb (offer %(offer)s)",
            material=description,
            qty=offer.quantity_lbs,
            price=offer.price_per_lb,
            offer=offer.name,
        )
        order = self.create(
            {
                "partner_id": offer.buyer_id.id,
                "opportunity_id": opportunity_id,
                "origin": offer.name,
                "order_line": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "name": line_name,
                            "product_uom_qty": offer.quantity_lbs or 0.0,
                            "price_unit": offer.price_per_lb or 0.0,
                        }
                    )
                ],
            }
        )
        order.message_post(
            body=_("Draft quotation created from accepted offer %s. Confirm to compile the transaction.") % offer.name,
            message_type="notification",
            subtype_xmlid="mail.mt_note",
        )
        return order

    def _plasticos_link_accepted_offer(self, transaction):
        """Back-link the accepted offer named in ``origin`` to the compiled transaction."""
        self.ensure_one()
        if not self.origin or "plasticos.offer" not in self.env:
            return
        offers = self.env["plasticos.offer"].search(
            [("name", "=", self.origin.strip()), ("state", "=", "accepted"), ("transaction_id", "=", False)]
        )
        if offers:
            offers._plasticos_link_transaction(transaction)

    def _compile_worksheet_transactions(self):
        """One transaction per worksheet on each confirmed order. Safe to call again.

        A worksheet whose name is already a transaction is left alone. When one
        worksheet carries several sale orders, the lowest-numbered order
        compiles it and the others are named in its log.
        """
        transactions = self.env[PLASTICOS_TRANSACTION]
        documents = self.env.context.get("erp_documents_by_origin") or {}
        confirmed = self.filtered(lambda order: order.state == "sale")
        worksheets = {worksheet for order in confirmed for worksheet in _worksheet_numbers(order.origin)}
        # One query for the worksheets that are already transactions; a worksheet
        # compiled below joins the set so the next order carrying it is skipped.
        compiled = set(transactions.search([("name", "in", list(worksheets))]).mapped("name")) if worksheets else set()
        for order in confirmed:
            for worksheet in _worksheet_numbers(order.origin):
                if worksheet in compiled:
                    continue
                sales = (documents.get(worksheet) or {}).get("sales") or []
                eligible = self.browse(sales).exists().filtered(lambda sale: sale.state == "sale").ids
                if eligible and order.id != min(eligible):
                    continue
                tx = transactions.with_context(import_mode=True).create(order._transaction_vals(True, worksheet))
                compiled.add(worksheet)
                if not order.transaction_id:
                    order.transaction_id = tx.id
                order._post_worksheet_note(tx, worksheet, sales)
                if tx.state == "draft":
                    tx.action_activate()

    def _transaction_vals(self, historical: bool, worksheet: str) -> dict:
        """Values the transaction compiler can read off this sale order for one worksheet."""
        self.ensure_one()
        vals = {
            "sale_order_id": self.id,
            "buyer_id": self.partner_id.id,
            "user_id": self._salesperson_id(),
            "product_id": self.order_line[:1].product_id.id,
        }
        if worksheet:
            assigned = (self.env.context.get("erp_salesperson_by_origin") or {}).get(worksheet)
            if assigned:
                vals["user_id"] = assigned
            carrier = (self.env.context.get("erp_carrier_by_origin") or {}).get(worksheet)
            if carrier:
                vals["carrier_id"] = carrier
            vals.update(self._worksheet_document_vals(worksheet))
        if historical:
            # Creation only. A replay that finds the worksheet name leaves the
            # existing row, including an authorized reopen, untouched.
            vals["legacy_erp_history"] = True
            vals["legacy_erp_status"] = (self.env.context.get("erp_raw_status_by_origin") or {}).get(worksheet, "")
            vals["state"] = "closed"
            if vals.get("name") == worksheet:
                freight = (self.env.context.get("erp_freight_by_origin") or {}).get(worksheet) or 0.0
                other = (self.env.context.get("erp_other_by_origin") or {}).get(worksheet) or 0.0
                if freight:
                    vals["freight_actual"] = freight
                if other:
                    vals["other_expenses"] = other
                self._lock_historical_commission(vals, worksheet)
        return vals

    def _lock_historical_commission(self, vals: dict, worksheet: str) -> None:
        """Store source commission amount without inventing a historical payment."""
        if "commission_locked" not in self.env[PLASTICOS_TRANSACTION]._fields:
            return
        amount = (self.env.context.get("erp_commission_by_origin") or {}).get(worksheet) or 0.0
        vals["commission_locked"] = True
        vals["commission_locked_amount"] = amount
        # A source commission amount is evidence, not an unpaid or paid liability.
        # Selection is intentionally unset; payout generation also excludes history.
        vals["commission_payout_state"] = False

    def _post_worksheet_note(self, transaction, worksheet: str, sales: list[int]) -> None:
        """Sticky note, speech bubble, second commission recipient, and sibling orders go on the transaction log."""
        parts = []
        note = (self.env.context.get("erp_note_by_origin") or {}).get(worksheet)
        if note:
            parts.append(note)
        slots = (self.env.context.get("erp_commission_slots_by_origin") or {}).get(worksheet) or []
        paid = [slot for slot in slots if slot.get("code") and slot.get("amount")]
        if len({slot["code"] for slot in paid}) > 1:
            parts.append(
                "Commission slots: "
                + "; ".join(f"slot {slot['slot']} {slot['code']} {slot['amount']:.2f}" for slot in paid)
            )
        siblings = self.browse([sale_id for sale_id in sales if sale_id != self.id]).exists()
        if siblings:
            parts.append("Worksheet also carries sale order(s): " + ", ".join(siblings.mapped("name")))
        if parts:
            transaction.message_post(body="\n\n".join(parts), message_type="comment", subtype_xmlid="mail.mt_note")

    def _salesperson_id(self) -> int | bool:
        """Partner salesperson. The import user is not a salesperson."""
        self.ensure_one()
        user = self.user_id
        bot = self.env.ref("base.user_root", raise_if_not_found=False)
        if not user or user == bot:
            return False
        return user.id

    def _worksheet_document_vals(self, worksheet: str) -> dict:
        """Purchase orders, supplier, invoice, and bills that belong to this worksheet.

        The import hands over the documents it realized for the worksheet. A
        live order without that context falls back to documents whose origin
        is exactly the worksheet number.
        """
        vals = {"name": self._worksheet_transaction_name(worksheet)}
        documents = (self.env.context.get("erp_documents_by_origin") or {}).get(worksheet)
        moves = self.env["account.move"]
        if documents is not None:
            purchases = self.env["purchase.order"].browse(documents.get("purchases") or []).exists()
            invoice = moves.browse([documents["invoice"]] if documents.get("invoice") else []).exists()
            bills = moves.browse(documents.get("bills") or []).exists()
            freight_bills = moves.browse(documents.get("freight_bills") or []).exists()
        else:
            purchases = self.env["purchase.order"].search([("origin", "=", worksheet)])
            found = moves.search(
                [
                    ("invoice_origin", "=", worksheet),
                    ("move_type", "in", ("out_invoice", "out_refund", "in_invoice", "in_refund")),
                    ("state", "!=", "cancel"),
                ]
            )
            invoice = found.filtered(lambda move: move.move_type in ("out_invoice", "out_refund"))[:1]
            bills = found.filtered(lambda move: move.move_type in ("in_invoice", "in_refund"))
            freight_bills = moves
        if purchases:
            vals["purchase_order_ids"] = [Command.set(purchases.ids)]
            supplier = purchases.filtered("partner_id")[:1].partner_id
            if supplier:
                vals["supplier_id"] = supplier.id
        if invoice and not self.env[PLASTICOS_TRANSACTION].search([("customer_invoice_id", "=", invoice.id)], limit=1):
            vals["customer_invoice_id"] = invoice.id
        if bills:
            vals["vendor_bill_ids"] = [Command.set(bills.ids)]
        if freight_bills:
            vals["freight_bill_ids"] = [Command.set(freight_bills.ids)]
        return vals

    def _worksheet_transaction_name(self, worksheet: str) -> str:
        """Worksheet number, or worksheet plus sale number when that name is taken."""
        taken = self.env[PLASTICOS_TRANSACTION].search([("name", "=", worksheet)], limit=1)
        if not taken:
            return worksheet
        return f"{worksheet}-{self.name}"
