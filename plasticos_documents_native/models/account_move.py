"""Fail-closed review of digitized and emailed vendor bills.

Extraction is the native Odoo pipeline (``account_invoice_extract`` over
``iap_extract``). This file extracts nothing. It refuses to post a vendor bill
that came from digitization or email until its header, total, duplicate check
and reference are sound, and it never lets such a bill post without a person.

Every method overridden here except ``_save_form`` is defined by Community
``account``. ``_save_form`` belongs to ``account_invoice_extract``; when that
module's override is not below this one the extracted total is simply not
captured, and the guard then asks a manager to enter it.
"""

import logging

from odoo import fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

GUARDED_BILL_TYPES = ("in_invoice", "in_refund")
# iap_extract/models/extract_mixin.py: states in which the extraction result is on the bill.
EXTRACT_NOT_REQUESTED = "no_extract_requested"
EXTRACT_FINISHED_STATES = ("waiting_validation", "to_validate", "done")
BILL_REVIEW_SUMMARY = "Digitized vendor bill needs manager review"


class AccountMove(models.Model):
    _inherit = "account.move"

    plasticos_document_total = fields.Monetary(
        string="Document Total",
        currency_field="currency_id",
        copy=False,
        tracking=True,
        groups="plasticos_security_base.group_operations_manager,base.group_system",
        help="Total printed on the vendor's document. Digitization records the extracted total; "
        "an Operations Manager may correct it from the document. A digitized or emailed vendor bill "
        "posts only when its lines and tax add up to this amount.",
    )

    # ── Scope ────────────────────────────────────────────────
    def _plasticos_is_digitized_bill(self):
        """A vendor bill or refund that came from digitization or from an email."""
        self.ensure_one()
        if self.move_type not in GUARDED_BILL_TYPES:
            return False
        if self.invoice_source_email:
            return True
        return "extract_state" in self._fields and self.extract_state not in (False, EXTRACT_NOT_REQUESTED)

    # ── Reference matching (B5) ──────────────────────────────
    def _plasticos_reference_resolution(self):
        """Resolve the email, file name and bill reference to one transaction. Writes nothing."""
        self.ensure_one()
        service = self.env["plasticos.document.sync"]
        email = service._origin_email(self)
        filename = self.sudo().message_main_attachment_id.name  # sudo: the bill's own file name only
        sources, quoted = service._email_sources(email, filename)
        if self.ref:
            sources.append(("bill reference", self.ref))
        return email, service.resolve_references(self.company_id, sources, quoted)

    def _plasticos_origin_name(self, found):
        """The order name the transaction resolver reads: the matched SO or PO, else the transaction's."""
        for _label, model, token, _record in found["matches"]:
            if model in ("sale.order", "purchase.order"):
                return token
        subject = found["subject"]
        if subject is None or subject._name != "plasticos.transaction":
            return False
        if subject.sale_order_id:
            return subject.sale_order_id.name
        orders = subject.purchase_order_ids
        return orders.name if len(orders) == 1 else False

    def _plasticos_apply_reference_match(self):
        """Fill an empty ``invoice_origin`` on a draft bill from exactly one resolved reference.

        A non-empty origin is never overwritten and a posted bill is never touched.
        A conflict leaves the origin empty; the posting guard reports it.
        """
        for move in self:
            if move.state != "draft" or move.invoice_origin or not move._plasticos_is_digitized_bill():
                continue
            email, found = move._plasticos_reference_resolution()
            if found["status"] != "one":
                continue
            origin = move._plasticos_origin_name(found)
            if not origin:
                continue
            move.with_context(skip_is_manually_modified=True).write({"invoice_origin": origin})
            source = f"email {email.message_id or email.id}" if email else "no email"
            move.message_post(
                body=f"Source document set to {origin} from {source}. {found['detail']}",
                message_type="notification",
                subtype_xmlid="mail.mt_note",
            )

    def _message_post_after_hook(self, message, msg_vals):
        result = super()._message_post_after_hook(message, msg_vals)
        if message.message_type == "email":
            self._plasticos_apply_reference_match()
        return result

    def _save_form(self, ocr_results):
        """Record the extracted total and read the extracted reference. Extraction itself is native."""
        parent = getattr(super(), "_save_form", None)
        if parent is None:
            return None
        result = parent(ocr_results)
        self._plasticos_record_extracted_total(ocr_results)
        self._plasticos_apply_reference_match()
        return result

    def _plasticos_record_extracted_total(self, ocr_results):
        """Store the total the extraction read from the document. No total read means nothing stored."""
        total = (ocr_results or {}).get("total", {}).get("selected_value", {}).get("content")
        if isinstance(total, bool) or not isinstance(total, int | float) or not total:
            return
        for move in self:
            if move.move_type in GUARDED_BILL_TYPES and move.state == "draft":
                # The field is manager-only. This stores what the document says; it decides nothing.
                recorder = move.sudo()  # sudo: record the extracted total on a manager-only field
                recorder.with_context(skip_is_manually_modified=True).write({"plasticos_document_total": total})

    # ── Posting guard (B4) ───────────────────────────────────
    def _plasticos_bill_block_reasons(self):
        """Why this digitized or emailed vendor bill may not post. Empty when it may. Writes nothing."""
        self.ensure_one()
        if not self._plasticos_is_digitized_bill():
            return []
        reasons = []
        if "extract_state" not in self._fields:
            reasons.append("Bill digitization is not installed, so the extraction cannot be confirmed.")
        elif self.extract_state == EXTRACT_NOT_REQUESTED:
            reasons.append("The bill was not sent for digitization.")
        elif self.extract_state not in EXTRACT_FINISHED_STATES:
            label = dict(self._fields["extract_state"].selection).get(self.extract_state, self.extract_state)
            reasons.append(f"Digitization is not finished or failed ({label}).")
        if not self.partner_id:
            reasons.append("The vendor is missing.")
        if not self.ref:
            reasons.append("The bill reference is missing.")
        if not self.invoice_date:
            reasons.append("The bill date is missing.")
        currency = self.currency_id or self.company_currency_id
        document_total = self.sudo().plasticos_document_total  # sudo: read-only check of a manager-only field
        computed = sum(self.invoice_line_ids.mapped("price_subtotal")) + self.amount_tax
        if not document_total:
            reasons.append("The document total is not recorded. An Operations Manager must enter it from the document.")
        elif currency.compare_amounts(computed, document_total) != 0:
            reasons.append(
                f"Lines and tax add up to {currency.format(computed)}, "
                f"but the document total is {currency.format(document_total)}."
            )
        if self.duplicated_ref_ids:
            names = ", ".join(self.duplicated_ref_ids.mapped(lambda m: m.name or m.ref or str(m.id)))
            reasons.append(f"A possible duplicate bill exists: {names}.")
        _email, found = self._plasticos_reference_resolution()
        if found["status"] == "conflicting":
            reasons.append(found["detail"])
        return reasons

    def _plasticos_blocked_bills(self):
        """``[(move, reasons)]`` for the draft bills in ``self`` that may not post."""
        blocked = []
        for move in self:
            if move.state != "draft":
                continue
            reasons = move._plasticos_bill_block_reasons()
            if reasons:
                blocked.append((move, reasons))
        return blocked

    def action_post(self):
        """Hold a blocked digitized bill in draft with one manager activity; post the rest.

        The check runs on every post. Nothing is defaulted or corrected here.
        """
        blocked = self._plasticos_blocked_bills()
        if not blocked:
            return super().action_post()
        service = self.env["plasticos.document.sync"]
        held = self.browse()
        lines = []
        for move, reasons in blocked:
            held |= move
            note = " ".join(reasons)
            service._schedule_manager_activity(move, BILL_REVIEW_SUMMARY, note)
            lines.append(f"{move.display_name}: {note}")
            _logger.warning("Vendor bill %s held in draft: %s", move.id, note)
        remaining = self - held
        result = super(AccountMove, remaining).action_post() if remaining else False
        if result:
            return result
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "danger",
                "sticky": True,
                "title": "Vendor bill not posted",
                "message": "\n".join(lines),
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def _post(self, soft=True):
        """Backstop for every path that posts without ``action_post``."""
        blocked = self._plasticos_blocked_bills()
        if blocked:
            raise UserError(
                "\n".join(f"{move.display_name}: {' '.join(reasons)}" for move, reasons in blocked)
                + "\nAn Operations Manager must review the bill before it is posted."
            )
        return super()._post(soft=soft)

    def _autopost_bill(self):
        """A digitized or emailed vendor bill never posts without a person."""
        self.ensure_one()
        if self._plasticos_is_digitized_bill():
            return None
        return super()._autopost_bill()
