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
LINDA_MODE_OFF = "off"
LINDA_MODE_SHADOW = "shadow"
LINDA_MODE_LIVE = "live"
LINDA_MODES = (LINDA_MODE_OFF, LINDA_MODE_SHADOW, LINDA_MODE_LIVE)
PO_ISSUE_TEMPLATE = "plasticos_logistics.mail_template_linda_po_issue"

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
        "date_order",
        "user_id",
        "fiscal_position_id",
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
        value = self.env["ir.config_parameter"].sudo().get_param(LINDA_MODE_PARAM, LINDA_MODE_OFF)
        mode = (value or LINDA_MODE_OFF).strip().lower()
        return mode if mode in LINDA_MODES else LINDA_MODE_OFF

    @api.model
    def _po_fingerprint(self, order):
        """Hash of everything the supplier-facing PO message and PDF commit to."""
        partner = order.partner_id
        # The PDF prints the supplier block, so its address is part of the payload.
        supplier_block = [
            partner.name or "",
            partner.street or "",
            partner.street2 or "",
            partner.zip or "",
            partner.city or "",
            partner.state_id.id,
            partner.country_id.id,
            partner.vat or "",
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
            fields.Datetime.to_string(order.date_planned) if order.date_planned else "",
            fields.Datetime.to_string(order.date_order) if order.date_order else "",
            order.user_id.id,
            order.fiscal_position_id.id,
            supplier_block,
            order.dest_address_id.id,
            order.picking_type_id.id if "picking_type_id" in order._fields else False,
            order.partner_ref or "",
            order.amount_total,
            lines,
        ]
        return hashlib.sha256(json.dumps(payload, default=str).encode()).hexdigest()

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
        if mode == LINDA_MODE_OFF or any(self.env.context.get(key) for key in NON_RELEASE_CONTEXT_KEYS):
            return self.browse()
        # sudo: evidence bookkeeping only. Roles allowed to confirm a PO (purchase, sales rep,
        # logistics) differ, and a missing evidence right must not roll back a native approval.
        # Company, PO and supplier are copied from the exact order; nothing is chosen.
        evidence = self.sudo()
        requests = self.browse()
        for order in orders:
            requests |= evidence._issue_purchase_order(order, mode)
        return requests

    def _issue_purchase_order(self, order, mode):
        fingerprint = self._po_fingerprint(order)
        block_reason = self._po_block_reason(order)
        outcome = "blocked" if block_reason else ("shadow" if mode == LINDA_MODE_SHADOW else "queued")

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

        request = self.create(values)
        # Rendered and queued as the releasing user (order.env), not as superuser.
        # Presence was checked by _po_block_reason ("template_missing").
        template = order.env.ref(PO_ISSUE_TEMPLATE, raise_if_not_found=False)
        mail_id = False
        try:
            with self.env.cr.savepoint():
                subject = template._render_field("subject", order.ids)[order.id]
                if outcome == "queued":
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
        except Exception:
            # A render or queue failure blocks only this issue, never the native approval.
            _logger.exception("Linda PO issue could not be rendered or queued for %s", order.name)
            request.write({"state": "blocked", "state_reason": "render_failed"})
            return request
        request.write({"subject": subject, "mail_id": mail_id, "queued_at": mail_id and fields.Datetime.now()})
        return request

    # ── Queue protection and reconciliation ──────────────────

    def _cancel_queued(self, reason):
        """Cancel queued requests and their unsent mail. Sent history is never touched."""
        # sudo: mail.mail is readable and writable only by system users, and the caller may be
        # any user editing or canceling the PO. Only Linda's own unsent mail is touched.
        queued = self.sudo().filtered(lambda request: request.state == "queued")
        outgoing = queued.mail_id.filtered(lambda mail: mail.state == "outgoing")
        outgoing.write({"state": "cancel", "failure_reason": f"linda:{reason}"})
        queued.write({"state": "canceled", "state_reason": reason})

    def _current_block_reason(self):
        """Why this queued request may no longer be delivered, or ``False``."""
        self.ensure_one()
        order = self.purchase_order_id
        if self._linda_mode() != LINDA_MODE_LIVE:
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
        # sudo: same evidence scope as issuance; the PO editor may hold no right on requests.
        queued = self.sudo().search([("purchase_order_id", "in", orders.ids), ("state", "=", "queued")])
        for request in queued:
            reason = request._current_block_reason()
            if reason:
                request._cancel_queued(reason)

    @api.model
    def _guard_mails_before_send(self, mails):
        """Recheck each Linda mail at send time.

        Returns ``(withheld, sendable)``: Linda mails that must not reach native
        sending (now canceled) and Linda mails cleared to send. A mail whose
        request already recorded an attempt without an outcome is uncertain: it
        may have reached the supplier, so it is not sent again.
        """
        withheld = sendable = self.env[MAIL_MAIL]
        for request in self.search([("mail_id", "in", mails.ids)]):
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
            elif reason := request._current_block_reason():
                request.write({"state": "queued"})
                request._cancel_queued(reason)
                withheld |= mail
            else:
                # First attempt, or a person explicitly retried a failed/unknown delivery.
                request.write({"state": "queued", "state_reason": False})
                sendable |= mail
        return withheld, sendable

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
