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

Typed sources (S4, C04): booking issue/amend/cancel, load dispatch
acknowledgement notice/escalation and document chase are obligations on the
same request owner. They carry ``source_kind``/``source_res_id``, an accepted
``source_revision_key`` and an immutable, audience-safe payload snapshot, and
never a fabricated PO/SO. A source kind resolves only through a registered
resolver (``_linda_source_resolvers``); Export registers ``booking`` by normal
``_inherit``. Without it the request is ``not_available``. Linda is the only
sender of this mail (BRS-EXP-03-R005, operator decision 2026-11-11).
"""

import hashlib
import json
import logging
from datetime import timedelta
from typing import NamedTuple

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, LockError, UserError, ValidationError
from odoo.tools import email_normalize

from .linda_approval import linda_stopped

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
        "source_kind",
        "source_model",
        "source_res_id",
        "source_revision_key",
        "operation_key",
        "source_payload_snapshot",
        "template_xmlid",
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


# Frozen command-result status (TECHNICAL_CONTRACT_v2.7: applied | already_applied | stale |
# blocked | ambiguous | not_available). A resolver verdict, not a Selection value.
COMMAND_APPLIED = "applied"


def _plain(text, **values):
    """Untranslated party-facing text: a snapshot must not change with the worker's language."""
    return text % values if values else text


class TypedSpec(NamedTuple):
    """A typed-source purpose: the source kind it belongs to and its native template."""

    source_kind: str
    template: str


BOOKING_ISSUE_TEMPLATE = "plasticos_logistics.mail_template_linda_booking_issue"
BOOKING_AMEND_TEMPLATE = "plasticos_logistics.mail_template_linda_booking_amend"
BOOKING_CANCEL_TEMPLATE = "plasticos_logistics.mail_template_linda_booking_cancel"
LOAD_ACK_NOTICE_TEMPLATE = "plasticos_logistics.mail_template_linda_load_ack_notice"
LOAD_ACK_ESCALATION_TEMPLATE = "plasticos_logistics.mail_template_linda_load_ack_escalation"
DOCUMENT_CHASE_TEMPLATE = "plasticos_logistics.mail_template_linda_document_chase"

SOURCE_BOOKING = "booking"
SOURCE_LOAD = "load"
TYPED_SPECS = {
    "booking_issue": TypedSpec(SOURCE_BOOKING, BOOKING_ISSUE_TEMPLATE),
    "booking_amend": TypedSpec(SOURCE_BOOKING, BOOKING_AMEND_TEMPLATE),
    "booking_cancel": TypedSpec(SOURCE_BOOKING, BOOKING_CANCEL_TEMPLATE),
    "load_ack_notice": TypedSpec(SOURCE_LOAD, LOAD_ACK_NOTICE_TEMPLATE),
    "load_ack_escalation": TypedSpec(SOURCE_LOAD, LOAD_ACK_ESCALATION_TEMPLATE),
    "document_chase": TypedSpec(SOURCE_LOAD, DOCUMENT_CHASE_TEMPLATE),
}
BOOKING_PURPOSES = tuple(purpose for purpose, spec in TYPED_SPECS.items() if spec.source_kind == SOURCE_BOOKING)
# Dispatch acknowledgement clock (BRS-EXP-10-R004, V10): anchored on the actual
# confirmed send (``dispatch_sent``), never on scheduling or queueing.
ACK_NOTICE_AFTER = timedelta(hours=2)
ACK_ESCALATION_AFTER = timedelta(hours=4)
# An external document chase is sent only when the operator approved it.
DOCUMENT_CHASE_PARAM = "plasticos_logistics.linda_document_chase"
# Resolver refusals that mean a configuration gap, logged by the sweep instead of skipped silently.
LOGGED_SKIP_REASONS = frozenset({"sender_email_missing", "recipient_email_invalid", "audience_company_mismatch"})
# The obligation sweep visits at most this many loads per lane per run, rotating by id.
LOAD_SWEEP_BATCH = 200
# Pre-S11 ir.config_parameter prefix of the sweep cursor; read only by the 19.0.1.14.24 migration.
LOAD_SWEEP_CURSOR = "plasticos_logistics.linda_load_sweep_cursor"
# Load states in which an unacknowledged dispatch is still a live obligation.
ACK_LOAD_STATES = ("dispatched", "scheduled")
# Load states in which a delivered load may still owe its carrier documents.
CHASE_LOAD_STATES = ("delivered", "closed")


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
            ("booking_issue", "Booking Issue"),
            ("booking_amend", "Booking Amendment"),
            ("booking_cancel", "Booking Cancellation"),
            ("load_ack_notice", "Dispatch Acknowledgement Reminder"),
            ("load_ack_escalation", "Dispatch Acknowledgement Escalation"),
            ("document_chase", "Carrier Document Chase"),
            ("earlier_option_available", "Earlier Delivery Option"),
            ("ready_slot_far", "Ready With a Far Slot"),
            ("needs_delivery_slot", "Delivery Slot Needed"),
            ("dock_rule_unverified", "Dock Rule Unverified"),
            ("site_hours_unknown", "Site Hours Unknown"),
            ("weight_unknown", "Full Weight Unknown"),
            ("export_cutoff_notice", "Export Cutoff Notice"),
            ("booking_roll_request", "Booking Roll Request"),
        ],
        required=True,
        readonly=True,
        help="External obligation this request evidences.",
    )
    source_kind = fields.Selection(
        [(SOURCE_BOOKING, "Export Booking"), (SOURCE_LOAD, "Logistics Load")],
        readonly=True,
        index="btree_not_null",
        help="Typed source of a booking, acknowledgement or document-chase obligation; empty for PO/SO.",
    )
    source_model = fields.Char(
        readonly=True,
        help="Native model of the typed source, as its registered resolver names it. Replies thread there.",
    )
    source_res_id = fields.Integer(readonly=True, index="btree_not_null", help="Id of the typed source record.")
    source_revision_key = fields.Char(
        readonly=True,
        help="Accepted source revision this obligation was prepared from. A later revision is a new obligation.",
    )
    operation_key = fields.Char(
        readonly=True,
        index="btree_not_null",
        help="Caller idempotency key; a retry with the same key and payload is already applied.",
    )
    source_payload_snapshot = fields.Text(
        readonly=True,
        help="Immutable audience-safe facts the message renders: subject, lines and exact attachment ids.",
    )
    template_xmlid = fields.Char(readonly=True, help="Native mail template that rendered this obligation.")
    snapshot_subject = fields.Char(compute="_compute_snapshot_render", help="Subject frozen in the snapshot.")
    snapshot_body_html = fields.Html(
        compute="_compute_snapshot_render",
        sanitize=False,
        help="Escaped rendering of the frozen snapshot; never re-read from the live source.",
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
        "CHECK((purpose IN ('po_issue', 'po_cancel') AND purchase_order_id IS NOT NULL AND sale_order_id IS NULL"
        " AND source_kind IS NULL)"
        " OR (purpose IN ('so_issue', 'so_cancel') AND sale_order_id IS NOT NULL AND purchase_order_id IS NULL"
        " AND source_kind IS NULL)"
        " OR (purpose IN ('booking_issue', 'booking_amend', 'booking_cancel') AND source_kind = 'booking'"
        " AND purchase_order_id IS NULL AND sale_order_id IS NULL AND source_model IS NOT NULL"
        " AND source_res_id IS NOT NULL AND source_revision_key IS NOT NULL)"
        " OR (purpose IN ('load_ack_notice', 'load_ack_escalation', 'document_chase',"
        " 'earlier_option_available', 'ready_slot_far', 'needs_delivery_slot', 'dock_rule_unverified',"
        " 'site_hours_unknown', 'weight_unknown', 'export_cutoff_notice', 'booking_roll_request')"
        " AND source_kind = 'load'"
        " AND purchase_order_id IS NULL AND sale_order_id IS NULL AND source_model IS NOT NULL"
        " AND source_res_id IS NOT NULL AND source_revision_key IS NOT NULL))",
        "A Linda request has exactly one source, matching its purpose: a PO, an SO, or one typed source.",
    )
    # Typed obligation identity: company, source, purpose, accepted revision and audience.
    # source_kind is NOT NULL in this branch (CHECK above), so no NULL gap opens the index.
    _unique_typed_obligation = models.UniqueIndex(
        "(company_id, source_kind, source_res_id, purpose, source_revision_key, partner_id)"
        " WHERE source_kind IS NOT NULL"
    )
    _unique_typed_operation = models.UniqueIndex(
        "(company_id, source_kind, operation_key) WHERE source_kind IS NOT NULL AND operation_key IS NOT NULL"
    )

    @api.constrains("company_id", "purchase_order_id", "sale_order_id")
    def _check_company_matches_source_order(self):
        for request in self:
            if request.source_kind:
                # A typed source's company is validated by its resolver when the obligation is recorded.
                continue
            order = request._source_order()
            if order.company_id != request.company_id:
                raise ValidationError(_("A Linda request's company must be its source order's company."))

    @api.depends("purpose", "purchase_order_id", "sale_order_id", "revision")
    def _compute_display_name(self):
        labels = dict(self._fields["purpose"].selection)
        for request in self:
            if request.source_kind:
                label = request._snapshot().get("reference") or f"{request.source_kind} {request.source_res_id}"
            else:
                label = request._source_order().name or ""
            request.display_name = f"{label} · {labels.get(request.purpose, '')} r{request.revision}"

    def _snapshot(self):
        """The frozen payload snapshot as a dict; an empty dict for PO/SO rows."""
        self.ensure_one()
        try:
            data = json.loads(self.source_payload_snapshot or "{}")
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}

    @api.depends("source_payload_snapshot")
    def _compute_snapshot_render(self):
        for request in self:
            snapshot = request._snapshot()
            request.snapshot_subject = snapshot.get("subject") or False
            parts = []
            for paragraph in snapshot.get("paragraphs") or []:
                parts.append(Markup("<p>%s</p>") % escape(paragraph))
            rows = [
                Markup(
                    "<tr><td style='padding: 6px; border: 1px solid #ddd;'><strong>%s</strong></td>"
                    "<td style='padding: 6px; border: 1px solid #ddd;'>%s</td></tr>"
                )
                % (escape(label), escape(value))
                for label, value in snapshot.get("lines") or []
            ]
            if rows:
                parts.append(
                    Markup("<table style='border-collapse: collapse; margin: 12px 0;'>%s</table>")
                    % Markup("").join(rows)
                )
            for closing in snapshot.get("closing") or []:
                parts.append(Markup("<p>%s</p>") % escape(closing))
            request.snapshot_body_html = Markup("").join(parts) if parts else False

    def _source_order(self):
        """The exact native order this request evidences; empty for a typed source."""
        self.ensure_one()
        spec = ISSUE_SPECS.get(self.purpose) or CANCEL_SPECS.get(self.purpose)
        return self[spec.order_field] if spec else self.env[PURCHASE_ORDER]

    def _source_lock_target(self):
        """``(model, id)`` of the source row a send claim locks before this request row."""
        self.ensure_one()
        if self.source_kind:
            return self.source_model, self.source_res_id
        order = self._source_order()
        return order._name, order.id

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
        # R7: archiving Linda pauses her; it never turns her mode off. She keeps owning issuance (the
        # legacy sender never takes over), obligations still queue, replies are still recorded, and her
        # queued mail is withheld at send time until she is reactivated.
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
        if self.purpose in TYPED_SPECS:
            return self._typed_block_reason()
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
        if linda_stopped(self.env):
            # R3: Linda is archived; her queued mail stays out of the batch, untouched, until she is reactivated.
            withheld = self.search([("mail_id", "in", mails.ids)]).mail_id.filtered(lambda m: m.state == "outgoing")
            return withheld, sendable, held
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

    # ── Typed sources: resolvers (S4, C04) ───────────────────
    # A resolver returns ``{"status": "applied", ...}`` with ``company`` (res.company),
    # ``partner`` (res.partner), ``recipient_email``, ``model``, ``res_id``,
    # ``revision_key``, ``snapshot`` (dict with ``subject``), ``attachment_ids``
    # (exact original ir.attachment ids) and ``source_fingerprint``; or a non-applied
    # status (``stale``, ``blocked``, ``ambiguous``, ``not_available``) with ``reason``.

    @api.model
    def _linda_source_resolvers(self):
        """``source_kind`` -> resolver. The downstream Export addon adds ``booking`` by ``_inherit``."""
        return {SOURCE_LOAD: self._linda_resolve_load_source}

    @api.model
    def _linda_source_models(self):
        """Native model -> ``source_kind`` whose replies Linda may attribute. Export adds its booking model."""
        return {"plasticos.load": SOURCE_LOAD}

    @api.model
    def _linda_resolve(self, source_kind, purpose, res_id, audience_partner, **params):
        """Resolve one typed source through its registered resolver, or report it unavailable."""
        resolver = self._linda_source_resolvers().get(source_kind)
        if not resolver:
            return {"status": "not_available", "reason": f"no_resolver_for_{source_kind}"}
        if TYPED_SPECS.get(purpose, TypedSpec(None, None)).source_kind != source_kind:
            return {"status": "not_available", "reason": "purpose_not_of_source_kind"}
        result = resolver(purpose, res_id, audience_partner, **params) or {}
        if result.get("status") != COMMAND_APPLIED:
            return {"status": result.get("status") or "blocked", "reason": result.get("reason") or "unresolved"}
        if not result.get("company") or not result.get("partner") or not result.get("snapshot", {}).get("subject"):
            return {"status": "blocked", "reason": "resolver_incomplete"}
        partner = result["partner"]
        if partner != audience_partner:
            return {"status": "blocked", "reason": "audience_not_permitted"}
        if partner.company_id and partner.company_id != result["company"]:
            return {"status": "blocked", "reason": "audience_company_mismatch"}
        if not email_normalize(result.get("recipient_email") or ""):
            return {"status": "blocked", "reason": "recipient_email_invalid"}
        if not email_normalize(result["company"].email or ""):
            # The sender is the source company; no other company or user stands in for it.
            return {"status": "blocked", "reason": "sender_email_missing"}
        return result

    @api.model
    def _typed_fingerprint(self, resolved):
        """Hash of everything this obligation commits to: source, revision, audience, snapshot, files."""
        payload = [
            resolved["company"].id,
            resolved["model"],
            resolved["res_id"],
            resolved["revision_key"],
            resolved["partner"].id,
            email_normalize(resolved["recipient_email"] or ""),
            resolved["snapshot"],
            sorted(resolved.get("attachment_ids") or []),
            resolved.get("source_fingerprint") or "",
        ]
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()

    # ── Typed sources: Logistics load (ACK notice/escalation, document chase) ──

    @api.model
    def _load_audiences(self, load, purpose):
        """Who a load obligation is addressed to. The carrier always; ops only on escalation."""
        partners = self.env[RES_PARTNER]
        if load.carrier_id:
            partners |= load.carrier_id
        if purpose == "load_ack_escalation":
            ops = load.transaction_id.user_id.partner_id or load.company_id.partner_id
            if ops and ops != load.carrier_id:
                partners |= ops
        return partners

    @api.model
    def _utc_label(self, value):
        """A clock rendered with its zone named. No local timezone is guessed (V10)."""
        return f"{fields.Datetime.to_string(value)} UTC" if value else ""

    @api.model
    def _scale_ticket_chase_reason(self, load):
        """Why no carrier document chase is due for this load now, or ``False``.

        Documents owns the scale-ticket status and its timing (``scale_ticket_rule.xml``:
        overdue after 2 business days). Linda only reads that status; it never re-times
        the rule and never writes a reminder flag. Without Documents nothing is chased.
        """
        params = self.env["ir.config_parameter"].sudo()  # sudo: operators who chase cannot read ir.config_parameter
        approved = (params.get_param(DOCUMENT_CHASE_PARAM) or "").strip().lower()
        if approved not in ("1", "true", "on"):
            return "document_chase_not_approved"
        if "scale_ticket_reminder_sent" not in load._fields:
            return "documents_status_not_available"
        checker = getattr(self.env["plasticos.transaction"], "_load_has_current_scale_ticket", None)
        if checker is None:
            return "documents_status_not_available"
        if load.state not in CHASE_LOAD_STATES:
            return "load_not_delivered"
        if not load.actual_delivery_at:
            return "actual_delivery_unknown"
        if not load.scale_ticket_reminder_sent:
            return "documents_reminder_not_due"
        return self._scale_ticket_evidence_status(load, checker)

    @api.model
    def _scale_ticket_evidence_status(self, load, checker):
        """Whether a current scale ticket already covers this load.

        Documents owns the tag and the evidence check. Without it, nothing is chased.
        """
        return "documents_status_not_available"

    @api.model
    def _linda_resolve_load_source(self, purpose, res_id, audience_partner, **params):
        load = self.env["plasticos.load"].browse(res_id).exists()
        if not load:
            return {"status": "not_available", "reason": "load_not_found"}
        if not load.company_id:
            return {"status": "blocked", "reason": "company_missing"}
        if audience_partner not in self._load_audiences(load, purpose):
            return {"status": "blocked", "reason": "audience_not_permitted"}
        carrier = load.carrier_id.name or ""
        route = [
            (_plain("Load"), load.name or ""),
            (_plain("Pickup"), load.pickup_partner_id.city or load.pickup_partner_id.name or ""),
            (_plain("Delivery"), load.delivery_partner_id.city or load.delivery_partner_id.name or ""),
        ]
        if purpose in ("load_ack_notice", "load_ack_escalation"):
            if not load.dispatch_sent:
                return {"status": "blocked", "reason": "dispatch_not_confirmed_sent"}
            if load.dispatch_acknowledged:
                return {"status": "blocked", "reason": "dispatch_acknowledged"}
            if load.state not in ACK_LOAD_STATES:
                return {"status": "blocked", "reason": "load_not_awaiting_acknowledgement"}
            due = load.dispatch_sent + (ACK_NOTICE_AFTER if purpose == "load_ack_notice" else ACK_ESCALATION_AFTER)
            if fields.Datetime.now() < due:
                return {"status": "blocked", "reason": "not_due"}
            revision_key = f"dispatch_sent:{fields.Datetime.to_string(load.dispatch_sent)}"
            sent = self._utc_label(load.dispatch_sent)
            if purpose == "load_ack_notice":
                snapshot = dict(
                    reference=load.name,
                    subject=_plain("Please confirm dispatch %(load)s", load=load.name),
                    paragraphs=[
                        _plain("We sent the dispatch packet for load %(load)s at %(sent)s.", load=load.name, sent=sent),
                        _plain("Please reply to this email to confirm you received it."),
                        _plain("This is a reminder only. The dispatch packet is not attached again."),
                    ],
                    lines=route + [(_plain("Dispatch sent"), sent)],
                )
            else:
                snapshot = dict(
                    reference=load.name,
                    subject=_plain("ESCALATION: dispatch %(load)s not acknowledged", load=load.name),
                    paragraphs=[
                        _plain(
                            "The dispatch for load %(load)s sent at %(sent)s to %(carrier)s has not been acknowledged.",
                            load=load.name,
                            sent=sent,
                            carrier=carrier,
                        ),
                        _plain("Please confirm receipt by replying to this email. The packet is not attached again."),
                    ],
                    lines=route + [(_plain("Carrier"), carrier), (_plain("Dispatch sent"), sent)],
                )
        elif purpose == "document_chase":
            reason = self._scale_ticket_chase_reason(load)
            if reason:
                return {"status": "blocked", "reason": reason}
            revision_key = f"scale_ticket:{fields.Datetime.to_string(load.actual_delivery_at)}"
            snapshot = dict(
                reference=load.name,
                category="scale_ticket",
                subject=_plain("Scale tickets needed for load %(load)s", load=load.name),
                paragraphs=[
                    _plain(
                        "Load %(load)s was delivered at %(delivered)s. We have not received its scale tickets.",
                        load=load.name,
                        delivered=self._utc_label(load.actual_delivery_at),
                    ),
                    _plain("Please reply with the light and heavy third-party certified scale tickets for this load."),
                ],
                lines=route + [(_plain("Delivered"), self._utc_label(load.actual_delivery_at))],
            )
        else:
            return {"status": "not_available", "reason": "purpose_not_of_source_kind"}
        snapshot.update(closing=[load.company_id.name or ""])
        return {
            "status": "applied",
            "company": load.company_id,
            "partner": audience_partner,
            "recipient_email": email_normalize(audience_partner.email or "") or "",
            "model": load._name,
            "res_id": load.id,
            "revision_key": revision_key,
            "snapshot": snapshot,
            "attachment_ids": [],
            "source_fingerprint": revision_key,
        }

    # ── Typed sources: record, queue, recheck ────────────────

    def _lock_source(self, model, res_id):
        """Take the source row lock first: the same order revision acceptance and send claims use."""
        record = self.env[model].browse(res_id).exists()
        if record:
            record.lock_for_update(allow_referencing=True)
        return record

    def _record_typed(self, purpose, resolved, operation_key=False, expected_source_fingerprint=False):
        """Record and queue one typed obligation from an applied resolver verdict.

        Identity is company + source + purpose + accepted revision + audience. A
        repeated poll or retry of the same obligation returns ``already_applied``.
        A new revision cancels an older unclaimed request of the same audience;
        an older request already claimed (or unknown) is kept as history and the
        new revision is held, because bytes that may have left are never unsent
        or replayed (V06).
        """
        if linda_stopped(self.env):
            return {"status": "blocked", "reason": "linda_stopped"}
        mode = self._linda_mode()
        if mode == LINDA_MODE_OFF or any(self.env.context.get(key) for key in NON_RELEASE_CONTEXT_KEYS):
            return {"status": "not_available", "reason": "linda_not_active"}
        spec = TYPED_SPECS[purpose]
        if expected_source_fingerprint and expected_source_fingerprint != resolved.get("source_fingerprint"):
            return {"status": "stale", "reason": "source_payload_changed"}
        try:
            with self.env.cr.savepoint():
                source = self._lock_source(resolved["model"], resolved["res_id"])
        except LockError:
            # A concurrent revision or send claim holds the source; the caller retries later.
            return {"status": "blocked", "reason": "source_busy"}
        if not source:
            return {"status": "not_available", "reason": "source_not_found"}
        fingerprint = self._typed_fingerprint(resolved)
        company, partner = resolved["company"], resolved["partner"]
        if operation_key:
            prior = self.search(
                [
                    ("company_id", "=", company.id),
                    ("source_kind", "=", spec.source_kind),
                    ("operation_key", "=", operation_key),
                ],
                limit=1,
            )
            if prior:
                if prior.payload_fingerprint == fingerprint and prior.purpose == purpose:
                    return {"status": "already_applied", "record_id": prior.id}
                return {"status": "stale", "record_id": prior.id, "reason": "operation_key_reused"}
        scope = [
            ("company_id", "=", company.id),
            ("source_kind", "=", spec.source_kind),
            ("source_res_id", "=", resolved["res_id"]),
            ("purpose", "=", purpose),
            ("partner_id", "=", partner.id),
        ]
        existing = self.search([*scope, ("source_revision_key", "=", resolved["revision_key"])], limit=1)
        if existing:
            if existing.payload_fingerprint == fingerprint:
                return {"status": "already_applied", "record_id": existing.id}
            return {"status": "stale", "record_id": existing.id, "reason": "revision_payload_changed"}
        history = self.search(scope, order="revision desc")
        open_requests = history.filtered(lambda request: request.state in ("queued", "unknown", "exception"))
        in_flight = open_requests.filtered(
            lambda request: request.state in ("unknown", "exception") or request.send_attempt_count
        )
        (open_requests - in_flight)._cancel_queued("superseded_by_revision")
        block_reason = False
        if in_flight:
            block_reason = "prior_send_outcome_unknown"
        elif not self.env.ref(spec.template, raise_if_not_found=False):
            block_reason = "template_missing"
        attachments = self.env["ir.attachment"].browse(resolved.get("attachment_ids") or []).exists()
        if len(attachments) != len(set(resolved.get("attachment_ids") or [])):
            block_reason = block_reason or "attachment_missing"
        outcome = "blocked" if block_reason else ("shadow" if mode == LINDA_MODE_SHADOW else "queued")
        snapshot = dict(resolved["snapshot"], attachment_ids=sorted(attachments.ids))
        request = self.create(
            {
                "company_id": company.id,
                "purpose": purpose,
                "source_kind": spec.source_kind,
                "source_model": resolved["model"],
                "source_res_id": resolved["res_id"],
                "source_revision_key": resolved["revision_key"],
                "operation_key": operation_key or False,
                "source_payload_snapshot": json.dumps(snapshot, sort_keys=True, default=str),
                "template_xmlid": spec.template,
                "partner_id": partner.id,
                "recipient_email": email_normalize(resolved["recipient_email"] or ""),
                "revision": (history[:1].revision or 0) + 1,
                "payload_fingerprint": fingerprint,
                "state": outcome,
                "state_reason": block_reason,
            }
        )
        if outcome == "blocked":
            _logger.info("Linda %s blocked for %s %s: %s", purpose, spec.source_kind, resolved["res_id"], block_reason)
            return {"status": "blocked", "record_id": request.id, "reason": block_reason}
        request._queue_typed_mail(outcome, attachments)
        if request.state == "blocked":
            return {"status": "blocked", "record_id": request.id, "reason": request.state_reason}
        return {"status": "applied", "record_id": request.id}

    def _queue_typed_mail(self, outcome, attachments):
        """Render the frozen snapshot through the purpose's native template and queue it once.

        State transitions: a render failure writes state to blocked with reason render_failed.
        """
        self.ensure_one()
        template = self.env.ref(TYPED_SPECS[self.purpose].template, raise_if_not_found=False)
        mail_id = False
        try:
            with self.env.cr.savepoint():
                subject = template._render_field("subject", self.ids)[self.id]
                if outcome == "queued":
                    mail_id = template.send_mail(
                        self.id,
                        force_send=False,
                        email_values={
                            "email_to": self.recipient_email,
                            "recipient_ids": [],
                            "email_cc": False,
                            "auto_delete": False,
                            # Replies thread on the source record, not on this evidence row.
                            "model": self.source_model,
                            "res_id": self.source_res_id,
                            "attachment_ids": [(4, attachment.id) for attachment in attachments],
                        },
                    )
        except Exception:
            _logger.exception("Linda %s could not be rendered or queued for request %s", self.purpose, self.id)
            self.write({"state": "blocked", "state_reason": "render_failed"})
            return
        self.write({"subject": subject, "mail_id": mail_id, "queued_at": mail_id and fields.Datetime.now()})

    def _typed_block_reason(self):
        """Re-resolve the typed source at send time; any drift withholds the queued mail."""
        self.ensure_one()
        if not self.env.ref(TYPED_SPECS[self.purpose].template, raise_if_not_found=False):
            return "template_missing"
        snapshot = self._snapshot()
        resolved = self._linda_resolve(
            self.source_kind,
            self.purpose,
            self.source_res_id,
            self.partner_id,
            revision_key=self.source_revision_key,
            attachment_ids=snapshot.get("attachment_ids") or [],
            recheck=True,
        )
        if resolved["status"] != COMMAND_APPLIED:
            return resolved.get("reason") or resolved["status"]
        if resolved["company"] != self.company_id or resolved["partner"] != self.partner_id:
            return "party_changed"
        if email_normalize(resolved["recipient_email"] or "") != self.recipient_email:
            return "party_changed"
        if resolved["revision_key"] != self.source_revision_key:
            return "source_revision_changed"
        if self._typed_fingerprint(resolved) != self.payload_fingerprint:
            return "payload_changed"
        return False

    # ── Frozen command (TECHNICAL_CONTRACT_v2.7 target_command_signatures[11]) ──

    @api.model
    def request_booking_correspondence(
        self,
        booking_id,
        accepted_revision_id,
        purpose,
        audience_partner_id,
        recipient_email,
        attachment_original_ids,
        source_payload_fingerprint,
        operation_key,
    ):
        """Linda's one sender for booking issue/amend/cancel mail (BRS-EXP-03-R005, BRS-EXP-10-R002).

        Export only assembles context: the registered ``booking`` resolver proves the
        accepted revision, audience, attachments and payload. Without that resolver
        (Export not installed) the answer is ``not_available``. Returns
        ``applied | already_applied | stale | blocked | ambiguous | not_available``.
        """
        if purpose not in BOOKING_PURPOSES:
            return {"status": "not_available", "reason": f"unknown booking purpose {purpose!r}"}
        if not operation_key:
            return {"status": "blocked", "reason": "operation_key_required"}
        partner = self.env[RES_PARTNER].browse(audience_partner_id).exists()
        if not partner:
            return {"status": "blocked", "reason": "audience_not_found"}
        resolved = self._linda_resolve(
            SOURCE_BOOKING,
            purpose,
            booking_id,
            partner,
            accepted_revision_id=accepted_revision_id,
            recipient_email=recipient_email,
            attachment_ids=list(attachment_original_ids or []),
        )
        if resolved["status"] != COMMAND_APPLIED:
            return {"status": resolved["status"], "reason": resolved.get("reason")}
        if email_normalize(recipient_email or "") != email_normalize(resolved["recipient_email"] or ""):
            return {"status": "blocked", "reason": "recipient_not_audience"}
        if sorted(attachment_original_ids or []) != sorted(resolved.get("attachment_ids") or []):
            return {"status": "stale", "reason": "attachments_changed"}
        evidence = self.sudo()  # sudo: Linda records request evidence; the resolver already proved the caller's source
        return evidence._record_typed(purpose, resolved, operation_key, source_payload_fingerprint)

    # ── Load obligation sweep (five-minute ACK job) ──────────

    @api.model
    def _load_sweep_page(self, domain, lane):
        """One bounded page of eligible loads, rotating by id so every load is visited in turn.

        Recording an obligation changes nothing in the eligibility domain, so a fixed
        "oldest first" page would revisit the same loads forever and starve the rest.
        A persisted id cursor (``plasticos.linda.sweep.cursor``, one per lane and company)
        continues after the last load seen and wraps to the start.
        """
        Load = self.env["plasticos.load"]
        batch = int(self.env.context.get("linda_load_sweep_batch") or LOAD_SWEEP_BATCH)
        # Test seam (S6, C06-SCOPE-3): a test narrows the sweep to its own loads. Absent
        # in production, where the domain is unchanged. Private method: not RPC-callable.
        scope = self.env.context.get("linda_load_sweep_ids")
        if scope is not None:
            domain = [*domain, ("id", "in", [int(load_id) for load_id in scope])]
        cursors = self.env["plasticos.linda.sweep.cursor"].sudo()  # sudo: the cron user holds no group on its cursor
        cursor = cursors._get_position(lane)
        page = Load.search([*domain, ("id", ">", cursor)], order="id asc", limit=batch)
        if len(page) < batch:
            page |= Load.search(
                [*domain, ("id", "<=", cursor), ("id", "not in", page.ids)], order="id asc", limit=batch - len(page)
            )
        cursors._set_position(lane, (page[-1:].id or 0) if len(page) == batch else 0)
        return page

    @api.model
    def _run_load_obligations(self, loads=None):
        """Record due ACK notices/escalations and approved document chases; withhold expired ones.

        Each obligation is recorded once per purpose, revision and audience however
        often the job polls. A queued obligation whose source no longer needs it
        (acknowledged, evidence received, state moved) is canceled before any claim.
        """
        if linda_stopped(self.env):
            # R3: no sweep, no cursor move, no request while Linda is archived.
            return [{"status": "blocked", "reason": "linda_stopped"}]
        Load = self.env["plasticos.load"]
        now = fields.Datetime.now()
        if loads is None:
            loads = self._load_sweep_page(
                [
                    ("dispatch_sent", "!=", False),
                    ("dispatch_sent", "<=", now - ACK_NOTICE_AFTER),
                    ("dispatch_acknowledged", "=", False),
                    ("state", "in", list(ACK_LOAD_STATES)),
                ],
                "ack",
            )
            if "scale_ticket_reminder_sent" in Load._fields:
                loads |= self._load_sweep_page(
                    [
                        ("scale_ticket_reminder_sent", "=", True),
                        ("actual_delivery_at", "!=", False),
                        ("state", "in", list(CHASE_LOAD_STATES)),
                    ],
                    "chase",
                )
        results = []
        for load in loads:
            for purpose in ("load_ack_notice", "load_ack_escalation", "document_chase"):
                for partner in self._load_audiences(load, purpose):
                    resolved = self._linda_resolve(SOURCE_LOAD, purpose, load.id, partner)
                    if resolved["status"] != COMMAND_APPLIED:
                        if resolved.get("reason") in LOGGED_SKIP_REASONS:
                            # A configuration gap must not be silent; ids and reason codes only, no PII.
                            _logger.info(
                                "Linda %s not recorded for load %s partner %s: %s",
                                purpose,
                                load.id,
                                partner.id,
                                resolved["reason"],
                            )
                        continue
                    with self.env.cr.savepoint():
                        results.append(self._record_typed(purpose, resolved))
        queued = self.search([("source_kind", "=", SOURCE_LOAD), ("state", "=", "queued")])
        for request in queued:
            if not request.send_attempt_count and (reason := request._current_block_reason()):
                request._cancel_queued(reason)
        return results
