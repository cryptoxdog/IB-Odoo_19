"""Linda order-scoped request evidence — PO issuance slice (WP01b).

A ``po_issue`` request is valid with only a company and an exact purchase order:
no sale order, ``plasticos.transaction`` or ``plasticos.load`` is required
(BRS-01-R002, BRS-02-R010, SUPERSESSION). The obligation identity is
company + PO + supplier + purpose + revision (BRS-02-R013); the payload
fingerprint only detects change and never grants a second send on its own.

Queued is not sent: ``state`` becomes ``sent`` only after native Odoo Mail
reports the ``mail.mail`` as sent. A send attempt whose outcome was never
recorded becomes ``unknown`` and is not retried automatically.
"""

import hashlib
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import email_normalize

_logger = logging.getLogger(__name__)

RES_COMPANY = "res.company"
RES_PARTNER = "res.partner"
PURCHASE_ORDER = "purchase.order"
MAIL_MAIL = "mail.mail"

LINDA_MODE_PARAM = "plasticos_logistics.linda_mode"
LINDA_MODES = ("off", "shadow", "live")
PO_ISSUE_TEMPLATE = "plasticos_logistics.mail_template_linda_po_issue"

# Context keys under which an order transition is not a live native release.
NON_RELEASE_CONTEXT_KEYS = ("import_mode", "install_mode", "skip_automations")

# A later release with an identical payload never re-sends while the latest
# request holds the obligation in one of these states.
HOLDING_STATES = ("queued", "sent", "exception", "unknown")

# purchase.order fields whose change can make a queued, unsent issue stale.
MATERIAL_PO_FIELDS = frozenset(
    {
        "state",
        "company_id",
        "partner_id",
        "currency_id",
        "order_line",
        "payment_term_id",
        "incoterm_id",
        "date_planned",
        "dest_address_id",
        "picking_type_id",
        "partner_ref",
    }
)

# Identity of an obligation; immutable once recorded.
IDENTITY_FIELDS = frozenset(
    {"company_id", "purpose", "purchase_order_id", "partner_id", "revision", "payload_fingerprint"}
)


class PlasticosLogisticsRequest(models.Model):
    _name = "plasticos.logistics.request"
    _description = "Linda Logistics Request"
    _order = "id desc"
    _rec_name = "purchase_order_id"

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
        [("po_issue", "PO Issuance")],
        required=True,
        readonly=True,
        help="External obligation this request evidences.",
    )
    purchase_order_id = fields.Many2one(
        PURCHASE_ORDER,
        string="Purchase Order",
        required=True,
        readonly=True,
        index=True,
        ondelete="restrict",
        help="Exact native purchase order the supplier issue belongs to.",
    )
    partner_id = fields.Many2one(
        RES_PARTNER,
        string="Supplier",
        required=True,
        readonly=True,
        index=True,
        ondelete="restrict",
        help="Supplier of the purchase order at release time.",
    )
    recipient_email = fields.Char(
        readonly=True,
        help="Normalized supplier address the issue was addressed to.",
    )
    revision = fields.Integer(
        required=True,
        readonly=True,
        help="Business revision of this obligation; a new one exists only after a new native release.",
    )
    payload_fingerprint = fields.Char(
        required=True,
        readonly=True,
        help="SHA-256 of the supplier-facing commercial payload at release time.",
    )
    subject = fields.Char(readonly=True, help="Rendered subject of the supplier message.")
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
        help="Native mail.mail carrying the supplier message.",
    )
    send_attempt_count = fields.Integer(readonly=True, help="Native send attempts started for this mail.")
    queued_at = fields.Datetime(readonly=True)
    sent_at = fields.Datetime(readonly=True)

    _unique_obligation_revision = models.Constraint(
        "UNIQUE(company_id, purchase_order_id, partner_id, purpose, revision)",
        "A Linda request already exists for this company, order, party, purpose and revision.",
    )

    # ── Evidence integrity ───────────────────────────────────

    def write(self, vals):
        if IDENTITY_FIELDS.intersection(vals):
            raise UserError(_("Linda request identity is immutable; record a new revision instead."))
        return super().write(vals)

    def unlink(self):
        raise UserError(_("Linda request evidence is append-only and cannot be deleted."))

    # ── Mode and release eligibility ─────────────────────────

    @api.model
    def _linda_mode(self):
        """Configured Linda mode; anything unrecognized fails closed to ``off``."""
        # sudo: reading one system parameter; purchase users have no ir.config_parameter access.
        value = self.env["ir.config_parameter"].sudo().get_param(LINDA_MODE_PARAM, "off")
        mode = (value or "off").strip().lower()
        return mode if mode in LINDA_MODES else "off"

    @api.model
    def _po_fingerprint(self, order):
        """Hash of everything the supplier-facing PO message and PDF commit to."""
        partner = order.partner_id
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
        payload = {
            "company": order.company_id.id,
            "order": order.id,
            "partner": partner.id,
            "recipient": email_normalize(partner.email or "") or "",
            "currency": order.currency_id.id,
            "payment_term": order.payment_term_id.id,
            "incoterm": order.incoterm_id.id,
            "date_planned": fields.Datetime.to_string(order.date_planned) if order.date_planned else "",
            "dest_address": order.dest_address_id.id,
            "picking_type": order.picking_type_id.id if "picking_type_id" in order._fields else False,
            "partner_ref": order.partner_ref or "",
            "amount_total": order.amount_total,
            "lines": lines,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()

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
        if order.dest_address_id:
            # The native PO PDF prints the dropship address, which is buyer-side identity.
            return "dropship_destination_disclosed"
        if not order.order_line.filtered(lambda line: not line.display_type):
            return "order_lines_missing"
        if not self.env.ref(PO_ISSUE_TEMPLATE, raise_if_not_found=False):
            return "template_missing"
        return False

    # ── Issuance ─────────────────────────────────────────────

    @api.model
    def _issue_purchase_orders(self, orders):
        """Record and queue the supplier issue for orders that just reached native ``purchase``.

        Called only after a live native release. Off mode and non-release contexts
        record nothing; shadow records evidence without creating any mail.
        """
        mode = self._linda_mode()
        if mode == "off" or any(self.env.context.get(key) for key in NON_RELEASE_CONTEXT_KEYS):
            return self.browse()
        requests = self.browse()
        for order in orders:
            requests |= self._issue_purchase_order(order, mode)
        return requests

    def _issue_purchase_order(self, order, mode):
        fingerprint = self._po_fingerprint(order)
        block_reason = self._po_block_reason(order)
        outcome = "blocked" if block_reason else ("shadow" if mode == "shadow" else "queued")

        # A queued issue that no longer matches the order must never leave the queue.
        stale = self.search(
            [("purchase_order_id", "=", order.id), ("purpose", "=", "po_issue"), ("state", "=", "queued")]
        ).filtered(lambda request: request.payload_fingerprint != fingerprint)
        stale._cancel_queued("superseded_by_release")

        partner = order.partner_id
        if not partner:
            _logger.warning("Linda PO issue skipped for %s: no supplier on the order", order.name)
            return self.browse()
        latest = self.search(
            [
                ("company_id", "=", order.company_id.id),
                ("purchase_order_id", "=", order.id),
                ("partner_id", "=", partner.id),
                ("purpose", "=", "po_issue"),
            ],
            order="revision desc",
            limit=1,
        )
        if latest.payload_fingerprint == fingerprint and (latest.state in HOLDING_STATES or latest.state == outcome):
            return latest

        values = {
            "company_id": order.company_id.id,
            "purpose": "po_issue",
            "purchase_order_id": order.id,
            "partner_id": partner.id,
            "recipient_email": email_normalize(partner.email or "") or False,
            "revision": latest.revision + 1,
            "payload_fingerprint": fingerprint,
            "state": outcome,
            "state_reason": block_reason,
        }
        if outcome == "blocked":
            _logger.info("Linda PO issue blocked for %s: %s", order.name, block_reason)
            return self.create(values)

        template = self.env.ref(PO_ISSUE_TEMPLATE)
        values["subject"] = template._render_field("subject", order.ids)[order.id]
        if outcome == "shadow":
            return self.create(values)

        request = self.create(values)
        mail_id = template.send_mail(
            order.id,
            force_send=False,
            email_values={
                "email_to": request.recipient_email,
                "recipient_ids": [],
                "email_cc": False,
                "auto_delete": False,
            },
        )
        request.write({"mail_id": mail_id, "queued_at": fields.Datetime.now()})
        return request

    # ── Queue protection and reconciliation ──────────────────

    def _cancel_queued(self, reason):
        """Cancel queued requests and their unsent mail. Sent history is never touched."""
        queued = self.filtered(lambda request: request.state == "queued")
        outgoing = queued.mail_id.filtered(lambda mail: mail.state == "outgoing")
        # sudo: only Linda's own unsent mail is canceled; mail.mail is not writable by purchase users.
        outgoing.sudo().write({"state": "cancel", "failure_reason": f"linda:{reason}"})
        queued.write({"state": "canceled", "state_reason": reason})

    def _current_block_reason(self):
        """Why this queued request may no longer be delivered, or ``False``."""
        self.ensure_one()
        order = self.purchase_order_id
        if self._linda_mode() != "live":
            return "mode_not_live"
        reason = self._po_block_reason(order)
        if reason:
            return reason
        if order.company_id != self.company_id or order.partner_id != self.partner_id:
            return "party_changed"
        if self._po_fingerprint(order) != self.payload_fingerprint:
            return "payload_changed"
        return False

    @api.model
    def _cancel_stale_for_orders(self, orders):
        """Cancel queued issues of these orders that no longer match their current payload."""
        queued = self.search([("purchase_order_id", "in", orders.ids), ("state", "=", "queued")])
        for request in queued:
            reason = request._current_block_reason()
            if reason:
                request._cancel_queued(reason)

    @api.model
    def _guard_mails_before_send(self, mails):
        """Recheck each Linda mail at send time; returns True when evidence was written.

        A mail whose request already recorded a send attempt without an outcome is
        uncertain: it may have reached the supplier, so it is not sent again.
        """
        requests = self.search([("mail_id", "in", mails.ids)])
        touched = False
        for request in requests:
            mail = request.mail_id
            if mail.state != "outgoing" or request.state in ("sent", "canceled", "blocked", "shadow"):
                continue
            touched = True
            if request.state == "queued" and request.send_attempt_count:
                # sudo: the queue may run as any user; this cancels only the uncertain Linda mail.
                mail.sudo().write({"state": "cancel", "failure_reason": "linda:prior_send_outcome_unknown"})
                request.write({"state": "unknown", "state_reason": "prior_send_outcome_unknown"})
                continue
            reason = request._current_block_reason()
            if reason:
                request.write({"state": "queued"})
                request._cancel_queued(reason)
                continue
            # First attempt, or a person explicitly retried a failed/unknown delivery.
            request.write(
                {"state": "queued", "state_reason": False, "send_attempt_count": request.send_attempt_count + 1}
            )
        return touched

    @api.model
    def _reconcile_mails(self, mails):
        """Mirror the native outcome of these mails onto their requests."""
        for request in self.search([("mail_id", "in", mails.ids)]):
            mail = request.mail_id
            if mail.state == "sent" and request.state != "sent":
                request.write({"state": "sent", "state_reason": False, "sent_at": fields.Datetime.now()})
            elif mail.state == "exception" and request.state != "exception":
                reason = mail.failure_type or "unknown"
                request.write({"state": "exception", "state_reason": reason})
            elif mail.state == "cancel" and request.state == "queued":
                request.write({"state": "canceled", "state_reason": "mail_canceled"})
