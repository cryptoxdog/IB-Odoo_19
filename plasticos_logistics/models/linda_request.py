"""Linda order-scoped request evidence — PO and SO issuance (WP01b).

A ``po_issue`` request is valid with only a company and an exact purchase order;
an ``so_issue`` request with only a company and an exact sale order. No
counterpart order, ``plasticos.transaction`` or ``plasticos.load`` is required
(BRS-01-R002, BRS-02-R010, SUPERSESSION). The obligation identity is
company + source order + party + purpose + revision (BRS-02-R013); the payload
fingerprint only detects change and never grants a second send on its own.

Queued is not sent: ``state`` becomes ``sent`` only after native Odoo Mail
reports the ``mail.mail`` as sent. A send attempt whose outcome was never
recorded becomes ``unknown`` and is not retried automatically.
"""

import hashlib
import json
import logging
from typing import NamedTuple

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import email_normalize

_logger = logging.getLogger(__name__)

RES_COMPANY = "res.company"
RES_PARTNER = "res.partner"
PURCHASE_ORDER = "purchase.order"
SALE_ORDER = "sale.order"
MAIL_MAIL = "mail.mail"

LINDA_MODE_PARAM = "plasticos_logistics.linda_mode"
LINDA_MODE_OFF = "off"
LINDA_MODE_SHADOW = "shadow"
LINDA_MODE_LIVE = "live"
LINDA_MODES = (LINDA_MODE_OFF, LINDA_MODE_SHADOW, LINDA_MODE_LIVE)
PO_ISSUE_TEMPLATE = "plasticos_logistics.mail_template_linda_po_issue"
PO_ISSUE_DROPSHIP_TEMPLATE = "plasticos_logistics.mail_template_linda_po_issue_dropship"
SUPPLIER_PO_REPORT = "plasticos_logistics.report_purchaseorder_supplier"
SO_ISSUE_TEMPLATE = "plasticos_logistics.mail_template_linda_so_issue"
PO_CANCEL_TEMPLATE = "plasticos_logistics.mail_template_linda_po_cancel"
SO_CANCEL_TEMPLATE = "plasticos_logistics.mail_template_linda_so_cancel"

# Context keys under which an order transition is not a live native release.
NON_RELEASE_CONTEXT_KEYS = ("import_mode", "install_mode", "skip_automations")

# A later release with an identical payload never re-sends while the latest
# request holds the obligation in one of these states.
HOLDING_STATES = ("queued", "sent", "exception", "unknown")
# Request states whose obligation is closed: their mail must never leave again.
CLOSED_STATES = ("sent", "canceled", "blocked", "shadow")
# Native failure types that prove the message was not delivered. Anything else,
# including Odoo's generic "unknown", may have reached the supplier.
UNDELIVERED_FAILURE_TYPES = frozenset(
    {"mail_email_invalid", "mail_email_missing", "mail_from_invalid", "mail_from_missing", "mail_smtp"}
)

# purchase.order fields whose change can make a queued, unsent issue stale: every
# order field purchase.report_purchaseorder (and purchase_stock's block) renders.
MATERIAL_PO_FIELDS = frozenset(
    {
        "state",
        "company_id",
        "partner_id",
        "currency_id",
        "order_line",
        "payment_term_id",
        "incoterm_id",
        "incoterm_location",
        "note",
        "date_planned",
        "date_order",
        "user_id",
        "fiscal_position_id",
        "dest_address_id",
        "picking_type_id",
        "partner_ref",
    }
)

# sale.order fields whose change can make a queued, unsent issue stale: every
# order field sale.report_saleorder (and sale_stock's incoterm block) renders.
MATERIAL_SO_FIELDS = frozenset(
    {
        "state",
        "company_id",
        "partner_id",
        "partner_invoice_id",
        "partner_shipping_id",
        "currency_id",
        "order_line",
        "payment_term_id",
        "incoterm",
        "incoterm_location",
        "note",
        "client_order_ref",
        "commitment_date",
        "validity_date",
        "user_id",
        "fiscal_position_id",
        "signed_by",
    }
)

# Identity of an obligation; immutable once recorded.
IDENTITY_FIELDS = frozenset(
    {
        "company_id",
        "purpose",
        "purchase_order_id",
        "sale_order_id",
        "partner_id",
        "revision",
        "payload_fingerprint",
        "origin_request_id",
    }
)


class IssueSpec(NamedTuple):
    """How one purpose finds its source order, payload, eligibility and template."""

    order_model: str
    order_field: str
    template: str
    fingerprint: str
    block_reason: str


ISSUE_SPECS = {
    "po_issue": IssueSpec(
        PURCHASE_ORDER, "purchase_order_id", PO_ISSUE_TEMPLATE, "_po_fingerprint", "_po_block_reason"
    ),
    "so_issue": IssueSpec(SALE_ORDER, "sale_order_id", SO_ISSUE_TEMPLATE, "_so_fingerprint", "_so_block_reason"),
}


class CancelSpec(NamedTuple):
    """A cancellation notice purpose: the issue it follows up on and its template."""

    issue_purpose: str
    order_field: str
    template: str


CANCEL_SPECS = {
    "po_cancel": CancelSpec("po_issue", "purchase_order_id", PO_CANCEL_TEMPLATE),
    "so_cancel": CancelSpec("so_issue", "sale_order_id", SO_CANCEL_TEMPLATE),
}
CANCEL_PURPOSE_BY_ISSUE = {spec.issue_purpose: purpose for purpose, spec in CANCEL_SPECS.items()}


class PlasticosLogisticsRequest(models.Model):
    _name = "plasticos.logistics.request"
    _description = "Linda Logistics Request"
    _order = "id desc"

    company_id = fields.Many2one(
        RES_COMPANY,
        string="Company",
        required=True,
        readonly=True,
        index=True,
        ondelete="restrict",
        help="Company of the source order; never inferred from a transaction or load.",
    )
    purpose = fields.Selection(
        [
            ("po_issue", "PO Issuance"),
            ("so_issue", "SO Issuance"),
            ("po_cancel", "PO Cancellation"),
            ("so_cancel", "SO Cancellation"),
        ],
        required=True,
        readonly=True,
        help="External obligation this request evidences.",
    )
    purchase_order_id = fields.Many2one(
        PURCHASE_ORDER,
        string="Purchase Order",
        readonly=True,
        index=True,
        ondelete="restrict",
        help="Exact native purchase order of a po_issue or po_cancel; empty for any other purpose.",
    )
    sale_order_id = fields.Many2one(
        SALE_ORDER,
        string="Sale Order",
        readonly=True,
        index="btree_not_null",
        ondelete="restrict",
        help="Exact native sale order of an so_issue or so_cancel; empty for any other purpose.",
    )
    partner_id = fields.Many2one(
        RES_PARTNER,
        string="Party",
        required=True,
        readonly=True,
        index=True,
        ondelete="restrict",
        help="Supplier of the PO or buyer of the SO at release time.",
    )
    recipient_email = fields.Char(
        readonly=True,
        help="Normalized party address the issue was addressed to.",
    )
    revision = fields.Integer(
        required=True,
        readonly=True,
        help="Business revision of this obligation; a new one exists only after a new native release.",
    )
    payload_fingerprint = fields.Char(
        required=True,
        readonly=True,
        help="SHA-256 of the party-facing commercial payload at release time.",
    )
    subject = fields.Char(readonly=True, help="Rendered subject of the party message.")
    state = fields.Selection(
        [
            ("blocked", "Blocked"),
            ("shadow", "Shadow"),
            ("queued", "Queued"),
            ("sent", "Sent"),
            ("exception", "Delivery Failed"),
            ("unknown", "Outcome Unknown"),
            ("canceled", "Canceled"),
        ],
        required=True,
        readonly=True,
        default="queued",
        index=True,
        help="Queued is not sent: Sent is recorded only after native mail transport reports it.",
    )
    state_reason = fields.Char(readonly=True, help="Machine-readable reason for blocked, failed or canceled.")
    mail_id = fields.Many2one(
        MAIL_MAIL,
        string="Outgoing Mail",
        readonly=True,
        index="btree_not_null",
        ondelete="set null",
        help="Native mail.mail carrying the party message.",
    )
    send_attempt_count = fields.Integer(
        default=0,
        readonly=True,
        help="Native send attempts started for this mail. Empty stored values count as zero.",
    )
    origin_request_id = fields.Many2one(
        "plasticos.logistics.request",
        string="Canceled Issue",
        readonly=True,
        index="btree_not_null",
        ondelete="restrict",
        help="The issue this cancellation notice follows up on; its recipient is the notice's audience.",
    )
    cycle_closed = fields.Boolean(
        readonly=True,
        help="A native cancellation ended this issue's release cycle; the next native release issues anew.",
    )
    queued_at = fields.Datetime(readonly=True)
    sent_at = fields.Datetime(readonly=True)

    _unique_obligation_revision = models.Constraint(
        "UNIQUE(company_id, purchase_order_id, partner_id, purpose, revision)",
        "A Linda request already exists for this company, order, party, purpose and revision.",
    )
    # PostgreSQL treats NULLs as distinct, so the PO constraint above never binds an SO
    # row (purchase_order_id is NULL there): SO identity needs its own constraint.
    _unique_so_obligation_revision = models.Constraint(
        "UNIQUE(company_id, sale_order_id, partner_id, purpose, revision)",
        "A Linda request already exists for this company, sale order, party, purpose and revision.",
    )
    _check_exactly_one_source_order = models.Constraint(
        "CHECK((purpose IN ('po_issue', 'po_cancel') AND purchase_order_id IS NOT NULL AND sale_order_id IS NULL)"
        " OR (purpose IN ('so_issue', 'so_cancel') AND sale_order_id IS NOT NULL AND purchase_order_id IS NULL))",
        "A Linda request has exactly one source order, matching its purpose.",
    )

    @api.constrains("company_id", "purchase_order_id", "sale_order_id")
    def _check_company_matches_source_order(self):
        for request in self:
            order = request._source_order()
            if order.company_id != request.company_id:
                raise ValidationError(_("A Linda request's company must be its source order's company."))

    @api.depends("purpose", "purchase_order_id", "sale_order_id", "revision")
    def _compute_display_name(self):
        labels = dict(self._fields["purpose"].selection)
        for request in self:
            order = request._source_order()
            request.display_name = f"{order.name or ''} · {labels.get(request.purpose, '')} r{request.revision}"

    def _source_order(self):
        """The exact native order this request evidences."""
        self.ensure_one()
        spec = ISSUE_SPECS.get(self.purpose) or CANCEL_SPECS.get(self.purpose)
        return self[spec.order_field] if spec else self.env[PURCHASE_ORDER]

    # ── Evidence integrity ───────────────────────────────────
    # Requests are written only by Linda's own issuance, cancellation and mail-transport
    # code, all of which runs under sudo(). Access rights let users read evidence; they
    # never let anyone forge a request or move its state, recipient or mail link.

    def _check_evidence_writer(self):
        if not self.env.su:
            raise AccessError(_("Linda request evidence is recorded by Linda only."))

    @api.model_create_multi
    def create(self, vals_list):
        self._check_evidence_writer()
        return super().create(vals_list)

    def write(self, vals):
        self._check_evidence_writer()
        if IDENTITY_FIELDS.intersection(vals):
            raise UserError(_("Linda request identity is immutable; record a new revision instead."))
        return super().write(vals)

    def unlink(self):
        raise UserError(_("Linda request evidence is append-only and cannot be deleted."))

    # ── Mode and release eligibility ─────────────────────────

    @api.model
    def _linda_mode(self):
        """Configured Linda mode; anything unrecognized fails closed to ``off``."""
        value = (
            self.env["ir.config_parameter"]
            .sudo()  # sudo: purchase users cannot read ir.config_parameter
            .get_param(LINDA_MODE_PARAM, LINDA_MODE_OFF)
        )
        mode = (value or LINDA_MODE_OFF).strip().lower()
        return mode if mode in LINDA_MODES else LINDA_MODE_OFF

    @api.model
    def _po_fingerprint(self, order):
        """Hash of everything the supplier-facing PO message and PDF commit to.

        Covers every field the native purchase.report_purchaseorder renders, so a
        queued PDF that no longer matches the order is never delivered. The one
        exception is ``date_approve``: it is release metadata that every
        reconfirmation renews, and it cannot change while a mail is queued.
        """
        partner = order.partner_id
        warehouse_partner = (
            order.picking_type_id.warehouse_id.partner_id if "picking_type_id" in order._fields else False
        )

        def address(contact):
            if not contact:
                return []
            return [
                contact.name or "",
                contact.street or "",
                contact.street2 or "",
                contact.zip or "",
                contact.city or "",
                contact.state_id.id,
                contact.country_id.id,
                contact.vat or "",
                contact.phone or "",
            ]

        lines = [
            [
                line.id,
                line.display_type or "",
                line.product_id.id,
                line.name or "",
                line.product_qty,
                line.product_uom_id.id,
                line.price_unit,
                line.discount,
                sorted(line.tax_ids.ids),
                fields.Datetime.to_string(line.date_planned) if line.date_planned else "",
            ]
            for line in order.order_line.sorted("id")
        ]
        # Positional, not keyed: the order of this list is part of the fingerprint contract.
        payload = [
            order.company_id.id,
            order.id,
            partner.id,
            email_normalize(partner.email or "") or "",
            order.currency_id.id,
            order.payment_term_id.id,
            order.incoterm_id.id,
            order.incoterm_location or "",
            str(order.note or ""),
            fields.Datetime.to_string(order.date_planned) if order.date_planned else "",
            fields.Datetime.to_string(order.date_order) if order.date_order else "",
            order.user_id.id,
            order.fiscal_position_id.id,
            order.company_id.name or "",
            partner.lang or "",
            address(partner),
            address(warehouse_partner),
            order.dest_address_id.id,
            address(order.dest_address_id),
            order.picking_type_id.id if "picking_type_id" in order._fields else False,
            order.partner_ref or "",
            order.amount_untaxed,
            order.amount_tax,
            order.amount_total,
            lines,
        ]
        return hashlib.sha256(json.dumps(payload, default=str).encode()).hexdigest()

    @api.model
    def _po_issue_template_xmlid(self, order):
        """Dropship issues attach the supplier copy. Every other PO keeps the native report."""
        if order.dest_address_id:
            return PO_ISSUE_DROPSHIP_TEMPLATE
        return PO_ISSUE_TEMPLATE

    @api.model
    def _supplier_dropship_report_reason(self, order):
        """Why this dropship PO's attached report is unsafe, or ``False``.

        The native purchase report prints ``dest_address_id`` as the shipping
        address, so a dropship issue may attach only
        ``plasticos_logistics.report_purchaseorder_supplier``. Linda renders
        that report and blocks this send when the buyer delivery identity is
        present or the report cannot be read. Presence of ``dest_address_id``
        alone is not a route ban.
        """
        dest = order.dest_address_id
        if not dest:
            return False
        template = self.env.ref(PO_ISSUE_DROPSHIP_TEMPLATE, raise_if_not_found=False)
        reports = template.report_template_ids if template else self.env["ir.actions.report"]
        if not reports:
            return "dropship_report_unproven"
        markers = []
        for value in (dest.name, dest.street, dest.street2, dest.city, dest.zip, dest.phone):
            text = (value or "").strip()
            if len(text) >= 4:
                markers.append(text)
        if not markers:
            return "dropship_report_unproven"
        for report in reports:
            if report.report_name != SUPPLIER_PO_REPORT:
                return "dropship_report_discloses_buyer_delivery"
            try:
                rendered, _report_type = self.env["ir.actions.report"]._render_qweb_html(report.report_name, order.ids)
            except Exception:  # noqa: BLE001 - an unreadable report fails this send closed
                _logger.exception("Linda could not render the supplier PO report for %s", order.name)
                return "dropship_report_unproven"
            html = rendered.decode("utf-8", "replace") if isinstance(rendered, bytes) else str(rendered)
            if any(marker in html for marker in markers):
                return "dropship_report_discloses_buyer_delivery"
        return False

    @api.model
    def _po_block_reason(self, order):
        """Why this exact order may not be issued now, or ``False``. Blocks only this order."""
        if order.state != "purchase":
            return "order_not_confirmed"
        if not order.company_id:
            return "company_missing"
        partner = order.partner_id
        if not partner:
            return "supplier_missing"
        if partner.company_id and partner.company_id != order.company_id:
            return "supplier_company_mismatch"
        if not email_normalize(partner.email or ""):
            return "supplier_email_invalid"
        dropship_reason = self._supplier_dropship_report_reason(order)
        if dropship_reason:
            return dropship_reason
        if not order.order_line.filtered(lambda line: not line.display_type):
            return "order_lines_missing"
        if not self.env.ref(self._po_issue_template_xmlid(order), raise_if_not_found=False):
            return "template_missing"
        return False

    @api.model
    def _so_fingerprint(self, order):
        """Hash of everything the buyer-facing SO message and PDF commit to.

        Covers every field the native sale.report_saleorder renders, so a queued
        PDF that no longer matches the order is never delivered. The one
        exception is ``date_order``: native confirmation stamps it with the
        confirmation time, so on a confirmed SO it is release metadata, and
        including it would turn an unchanged reconfirmation into a resend.
        """
        partner = order.partner_id

        def address(contact):
            if not contact:
                return []
            return [
                contact.id,
                contact.name or "",
                contact.street or "",
                contact.street2 or "",
                contact.zip or "",
                contact.city or "",
                contact.state_id.id,
                contact.country_id.id,
                contact.vat or "",
                contact.phone or "",
            ]

        def stamp(value):
            return fields.Datetime.to_string(value) if value else ""

        lines = [
            [
                line.id,
                line.display_type or "",
                line.product_id.id,
                line.name or "",
                line.product_uom_qty,
                line.product_uom_id.id,
                line.price_unit,
                line.discount,
                sorted(line.tax_ids.ids),
                line.is_downpayment,
            ]
            for line in order.order_line.sorted("id")
        ]
        # Positional, not keyed: the order of this list is part of the fingerprint contract.
        payload = [
            order.company_id.id,
            order.company_id.name or "",
            order.id,
            email_normalize(partner.email or "") or "",
            partner.lang or "",
            address(partner),
            address(order.partner_invoice_id),
            address(order.partner_shipping_id),
            order.currency_id.id,
            order.payment_term_id.id,
            str(order.payment_term_id.note or ""),
            order.incoterm.id if "incoterm" in order._fields else False,
            (order.incoterm_location or "") if "incoterm_location" in order._fields else "",
            str(order.note or ""),
            order.client_order_ref or "",
            stamp(order.commitment_date),
            str(order.validity_date or ""),
            order.user_id.id,
            order.fiscal_position_id.id,
            order.signed_by or "",
            order.amount_untaxed,
            order.amount_tax,
            order.amount_total,
            lines,
        ]
        return hashlib.sha256(json.dumps(payload, default=str).encode()).hexdigest()

    @api.model
    def _so_block_reason(self, order):
        """Why this exact sale order may not be issued to its buyer now, or ``False``."""
        if order.state != "sale":
            return "order_not_confirmed"
        if not order.company_id:
            return "company_missing"
        buyer = order.partner_id
        if not buyer:
            return "buyer_missing"
        if buyer.company_id and buyer.company_id != order.company_id:
            return "buyer_company_mismatch"
        if not email_normalize(buyer.email or ""):
            return "buyer_email_invalid"
        if not order.order_line.filtered(lambda line: not line.display_type):
            return "order_lines_missing"
        if not self.env.ref(SO_ISSUE_TEMPLATE, raise_if_not_found=False):
            return "template_missing"
        return False

    # ── Issuance ─────────────────────────────────────────────

    @api.model
    def _issue_purchase_orders(self, orders):
        """Record and queue the supplier issue for orders that just reached native ``purchase``.

        Called only after a live native release. Off mode and non-release contexts
        record nothing; shadow records evidence without creating any mail.
        """
        return self._issue_orders(orders, "po_issue")

    @api.model
    def _issue_sale_orders(self, orders):
        """Record and queue the buyer issue for orders that just reached native ``sale``."""
        return self._issue_orders(orders, "so_issue")

    @api.model
    def _issue_orders(self, orders, purpose):
        mode = self._linda_mode()
        if mode == LINDA_MODE_OFF or any(self.env.context.get(key) for key in NON_RELEASE_CONTEXT_KEYS):
            return self.browse()
        evidence = self.sudo()  # sudo: order confirm records Linda evidence without rolling back approval
        requests = self.browse()
        for order in orders:
            requests |= evidence._issue_order(order, mode, purpose)
        return requests

    def _issue_order(self, order, mode, purpose):
        spec = ISSUE_SPECS[purpose]
        fingerprint = getattr(self, spec.fingerprint)(order)
        block_reason = getattr(self, spec.block_reason)(order)
        outcome = "blocked" if block_reason else ("shadow" if mode == LINDA_MODE_SHADOW else "queued")

        # A queued issue that no longer matches the order must never leave the queue.
        stale = self.search(
            [(spec.order_field, "=", order.id), ("purpose", "=", purpose), ("state", "=", "queued")]
        ).filtered(lambda request: request.payload_fingerprint != fingerprint)
        stale._cancel_queued("superseded_by_release")

        partner = order.partner_id
        if not partner:
            _logger.warning("Linda %s skipped for %s: no party on the order", purpose, order.name)
            return self.browse()
        latest = self.search(
            [
                ("company_id", "=", order.company_id.id),
                (spec.order_field, "=", order.id),
                ("partner_id", "=", partner.id),
                ("purpose", "=", purpose),
            ],
            order="revision desc",
            limit=1,
        )
        # Inside one release cycle the same payload never issues twice. After a native
        # cancellation closed the cycle, a new native release is a new issue even when the
        # terms are identical (operator decision 2026-10-24, SUPERSESSION).
        same_cycle = latest and not latest.cycle_closed
        if (
            same_cycle
            and latest.payload_fingerprint == fingerprint
            and (latest.state in HOLDING_STATES or latest.state == outcome)
        ):
            return latest

        values = {
            "company_id": order.company_id.id,
            "purpose": purpose,
            spec.order_field: order.id,
            "partner_id": partner.id,
            "recipient_email": email_normalize(partner.email or "") or False,
            "revision": latest.revision + 1,
            "payload_fingerprint": fingerprint,
            "state": outcome,
            "state_reason": block_reason,
        }
        if outcome == "blocked":
            _logger.info("Linda %s blocked for %s: %s", purpose, order.name, block_reason)
            return self.create(values)

        request = self.create(values)
        # Rendered and queued as the releasing user (order.env), not as superuser.
        # Presence was checked by the purpose's block reason ("template_missing").
        template_xmlid = self._po_issue_template_xmlid(order) if purpose == "po_issue" else spec.template
        template = order.env.ref(template_xmlid, raise_if_not_found=False)
        mail_id = False
        try:
            with self.env.cr.savepoint():
                subject = template._render_field("subject", order.ids)[order.id]
                if outcome == "queued":
                    # report_pdf_no_attachment: a PDF cached on the order is not this revision.
                    mail_id = template.with_context(report_pdf_no_attachment=True).send_mail(
                        order.id,
                        force_send=False,
                        email_values={
                            "email_to": request.recipient_email,
                            "recipient_ids": [],
                            "email_cc": False,
                            "auto_delete": False,
                        },
                    )
        except Exception:
            # A render or queue failure blocks only this issue, never the native approval.
            _logger.exception("Linda %s could not be rendered or queued for %s", purpose, order.name)
            request.write({"state": "blocked", "state_reason": "render_failed"})
            return request
        request.write({"subject": subject, "mail_id": mail_id, "queued_at": mail_id and fields.Datetime.now()})
        return request

    # ── Native cancellation ──────────────────────────────────

    @api.model
    def _cancel_block_reason(self, cancel_purpose, recipient_email):
        """Why a cancellation notice to this historical address may not go out, or ``False``."""
        if not email_normalize(recipient_email or ""):
            return "recipient_unattributable"
        if not self.env.ref(CANCEL_SPECS[cancel_purpose].template, raise_if_not_found=False):
            return "template_missing"
        return False

    @api.model
    def _record_cancellations(self, orders):
        """Record a successful native cancellation of these orders.

        Closes each order's open release cycle, settles in-flight issues as
        unknown, and queues one cancellation notice per audience that was, or
        may have been, sent the issue. The audience is the original issue's own
        party and address, never the order's current contact. Off mode and
        non-release contexts send nothing; the cycle still closes.
        """
        issue_purpose = next(purpose for purpose, spec in ISSUE_SPECS.items() if spec.order_model == orders._name)
        order_field = ISSUE_SPECS[issue_purpose].order_field
        cancel_purpose = CANCEL_PURPOSE_BY_ISSUE[issue_purpose]
        mode = self._linda_mode()
        notify = mode != LINDA_MODE_OFF and not any(self.env.context.get(key) for key in NON_RELEASE_CONTEXT_KEYS)
        evidence = self.sudo()  # sudo: cancellation records Linda evidence without undoing the cancel
        notices = self.browse()
        for order in orders:
            issues = evidence.search(
                [(order_field, "=", order.id), ("purpose", "=", issue_purpose), ("cycle_closed", "=", False)],
                order="revision desc",
            )
            in_flight = issues.filtered(lambda issue: issue.state == "queued" and issue.send_attempt_count)
            in_flight.mail_id.filtered(lambda mail: mail.state == "outgoing").write(
                {"state": "cancel", "failure_reason": "linda:prior_send_outcome_unknown"}
            )
            in_flight.write({"state": "unknown", "state_reason": "prior_send_outcome_unknown"})
            communicated = issues.filtered(
                lambda issue: issue.state == "sent" or (issue.state == "unknown" and issue.send_attempt_count)
            )
            issues.write({"cycle_closed": True})
            if not notify:
                continue
            audiences = set()
            for origin in communicated:
                audience = (origin.partner_id.id, origin.recipient_email)
                if audience in audiences:
                    continue
                audiences.add(audience)
                notices |= evidence._queue_cancellation_notice(order, origin, cancel_purpose, mode)
        return notices

    def _queue_cancellation_notice(self, order, origin, cancel_purpose, mode):
        spec = CANCEL_SPECS[cancel_purpose]
        existing = self.search([("purpose", "=", cancel_purpose), ("origin_request_id", "=", origin.id)], limit=1)
        if existing:
            return existing
        block_reason = self._cancel_block_reason(cancel_purpose, origin.recipient_email)
        outcome = "blocked" if block_reason else ("shadow" if mode == LINDA_MODE_SHADOW else "queued")
        event = json.dumps([cancel_purpose, origin.id, origin.revision, origin.recipient_email or ""])
        request = self.create(
            {
                "company_id": origin.company_id.id,
                "purpose": cancel_purpose,
                spec.order_field: order.id,
                "partner_id": origin.partner_id.id,
                "recipient_email": origin.recipient_email,
                "revision": origin.revision,
                "payload_fingerprint": hashlib.sha256(event.encode()).hexdigest(),
                "origin_request_id": origin.id,
                "state": outcome,
                "state_reason": block_reason,
            }
        )
        if outcome == "blocked":
            _logger.info("Linda %s blocked for %s: %s", cancel_purpose, order.name, block_reason)
            return request
        template = order.env.ref(spec.template, raise_if_not_found=False)
        mail_id = False
        try:
            with self.env.cr.savepoint():
                subject = template._render_field("subject", order.ids)[order.id]
                if outcome == "queued":
                    mail_id = template.with_context(report_pdf_no_attachment=True).send_mail(
                        order.id,
                        force_send=False,
                        email_values={
                            "email_to": origin.recipient_email,
                            "recipient_ids": [],
                            "email_cc": False,
                            "auto_delete": False,
                        },
                    )
        except Exception:
            # A notice failure is recorded; the native cancellation already happened and stays.
            _logger.exception("Linda %s could not be rendered or queued for %s", cancel_purpose, order.name)
            request.write({"state": "blocked", "state_reason": "render_failed"})
            return request
        request.write({"subject": subject, "mail_id": mail_id, "queued_at": mail_id and fields.Datetime.now()})
        return request

    # ── Queue protection and reconciliation ──────────────────

    def _cancel_queued(self, reason):
        """Cancel queued requests that were never handed to SMTP.

        An attempt whose outcome is still open is ``unknown``, not ``canceled``:
        the message may have reached the party. Native cancellation reads that
        unknown row and queues the notice. A raw state write does not.
        Sent history is never touched.
        """
        queued = self.filtered(lambda request: request.state == "queued")
        uncertain = queued.filtered(lambda request: request.send_attempt_count)
        fresh = queued - uncertain
        if uncertain:
            uncertain.mail_id.filtered(lambda mail: mail.state == "outgoing").write(
                {"state": "cancel", "failure_reason": "linda:prior_send_outcome_unknown"}
            )
            uncertain.write({"state": "unknown", "state_reason": "prior_send_outcome_unknown"})
        outgoing = fresh.mail_id.filtered(lambda mail: mail.state == "outgoing")
        outgoing.write({"state": "cancel", "failure_reason": f"linda:{reason}"})
        fresh.write({"state": "canceled", "state_reason": reason})

    def _current_block_reason(self):
        """Why this queued request may no longer be delivered, or ``False``."""
        self.ensure_one()
        if self._linda_mode() != LINDA_MODE_LIVE:
            return "mode_not_live"
        if self.purpose in CANCEL_SPECS:
            # A notice reports a past cancellation event: a later reopen of the order does
            # not make it stale, so only its own audience and template are rechecked.
            return self._cancel_block_reason(self.purpose, self.recipient_email)
        spec = ISSUE_SPECS[self.purpose]
        order = self._source_order()
        reason = getattr(self, spec.block_reason)(order)
        if reason:
            return reason
        if order.company_id != self.company_id or order.partner_id != self.partner_id:
            return "party_changed"
        if getattr(self, spec.fingerprint)(order) != self.payload_fingerprint:
            return "payload_changed"
        return False

    @api.model
    def _cancel_stale_for_orders(self, orders):
        """Cancel queued issues of these orders that no longer match their current payload."""
        order_field = next(spec.order_field for spec in ISSUE_SPECS.values() if spec.order_model == orders._name)
        queued = self.sudo().search(  # sudo: the order editor may hold no right on Linda requests
            [(order_field, "in", orders.ids), ("state", "=", "queued")]
        )
        for request in queued:
            reason = request._current_block_reason()
            if reason:
                request._cancel_queued(reason)

    @api.model
    def _guard_mails_before_send(self, mails):
        """Recheck each Linda mail at send time.

        Returns ``(withheld, sendable, held)``: Linda mails that must not reach
        native sending, Linda mails cleared to send, and issue mails held back
        because an earlier cancellation notice to the same party is not yet
        confirmed sent. Same-batch selection is not delivery. Unknown, failed,
        and blocked notices keep the hold, and an uncertain notice is not retried.
        """
        withheld = sendable = held = self.env[MAIL_MAIL]
        # Ascending mail id, the order native sending uses, so a notice clears before its reissue.
        for request in self.search([("mail_id", "in", mails.ids)]).sorted(lambda request: request.mail_id.id):
            mail = request.mail_id
            if mail.state != "outgoing":
                continue
            if request.state in CLOSED_STATES:
                mail.write({"state": "cancel", "failure_reason": "linda:obligation_closed"})
                withheld |= mail
            elif request.state == "queued" and request.send_attempt_count:
                mail.write({"state": "cancel", "failure_reason": "linda:prior_send_outcome_unknown"})
                request.write({"state": "unknown", "state_reason": "prior_send_outcome_unknown"})
                withheld |= mail
            elif request.state in ("unknown", "exception"):
                # Do not auto-retry, and do not cancel the mail: that reconcile
                # path would relabel the request and drop the reissue hold.
                withheld |= mail
            elif reason := request._current_block_reason():
                request.write({"state": "queued"})
                request._cancel_queued(reason)
                withheld |= mail
            elif request._pending_cancellation_notices():
                # Confirmed delivery releases the reissue. Being selected beside
                # the notice in this batch does not.
                held |= mail
            else:
                # First attempt, or a person explicitly retried a failed/unknown delivery.
                request.write({"state": "queued", "state_reason": False})
                sendable |= mail
        return withheld, sendable, held

    def _pending_cancellation_notices(self):
        """Notices this issue must not overtake until one is confirmed sent.

        Shadow notices are not a delivery obligation. Queued, unknown, failed,
        and blocked notices are. A later queue run does not treat them as done.
        """
        self.ensure_one()
        cancel_purpose = CANCEL_PURPOSE_BY_ISSUE.get(self.purpose)
        if not cancel_purpose:
            return self.browse()
        order_field = CANCEL_SPECS[cancel_purpose].order_field
        return self.search(
            [
                ("purpose", "=", cancel_purpose),
                (order_field, "=", self._source_order().id),
                ("state", "in", ("queued", "unknown", "exception", "blocked")),
                ("id", "<", self.id),
                "|",
                ("partner_id", "=", self.partner_id.id),
                ("recipient_email", "=", self.recipient_email),
            ]
        )

    @api.model
    def _mark_attempt(self, mail):
        """Record that this mail is about to be handed to SMTP."""
        request = self.search([("mail_id", "=", mail.id)], limit=1)
        request.write({"send_attempt_count": request.send_attempt_count + 1})

    @api.model
    def _reconcile_mails(self, mails, failure_type=None):
        """Mirror the native outcome of these mails onto requests still awaiting one.

        ``failure_type`` is the value native post-processing reports; its
        connection-failure path does not write it onto the mail itself.
        """
        for request in self.search([("mail_id", "in", mails.ids), ("state", "=", "queued")]):
            mail = request.mail_id
            if mail.state == "sent":
                request.write({"state": "sent", "state_reason": False, "sent_at": fields.Datetime.now()})
            elif mail.state == "exception":
                reason = failure_type or mail.failure_type or "unknown"
                undelivered = reason in UNDELIVERED_FAILURE_TYPES
                request.write({"state": "exception" if undelivered else "unknown", "state_reason": reason})
            elif mail.state == "cancel":
                request.write({"state": "canceled", "state_reason": "mail_canceled"})

    @api.model
    def _mark_interrupted(self, mails):
        """A send that raised before native post-processing has an unknown outcome."""
        for request in self.search([("mail_id", "in", mails.ids), ("state", "=", "queued")]):
            if request.mail_id.state == "exception":
                request.write({"state": "unknown", "state_reason": "send_interrupted"})
