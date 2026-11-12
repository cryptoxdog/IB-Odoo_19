"""Linda inbound response evidence — replies to Linda PO/SO mail (WP02, PARTIAL).

Native Odoo Mail owns the incoming message, its original MIME copy and its
attachments. A response only records which exact Linda request the message
answers, as proven by the native original's ``In-Reply-To`` / ``References``
headers, and the outcome of deterministic validation (BRS-02-R009..R014).

Nothing here changes an order, load, picking, mail queue or transaction. A
response is candidate evidence; without provider-authenticated sender
evidence the best outcome is ``identity_unverified``, never an accepted
commitment. Free-form text is not interpreted: the native Odoo AI server
action that would extract candidates is not available on this runtime, so
such replies stay ``unresolved`` (``ai_not_run``) and no substitute
inference is used (BRS-02-R062, SUPERSESSION 2026-10-25).

Typed sources (S4, V07): a reply on a registered typed source (a Logistics load,
or Export's booking once it registers its model) is recorded on its own branch
with ``source_kind``/``source_res_id`` and no fabricated order. A From match is
not authentication; booking text stays candidate evidence and never accepts
booking terms, READY, verification, stock or payment. An unregistered model is
not Linda's conversation and records nothing.
"""

import email
import email.policy
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import email_normalize, html2plaintext
from odoo.tools.mail import unfold_references

from .linda_request import CANCEL_SPECS, ISSUE_SPECS, LINDA_MODE_OFF, TYPED_SPECS

_logger = logging.getLogger(__name__)

RES_COMPANY = "res.company"
PURCHASE_ORDER = "purchase.order"
SALE_ORDER = "sale.order"
MAIL_MESSAGE = "mail.message"
LOGISTICS_REQUEST = "plasticos.logistics.request"

# Native fetchmail "Keep Original" attaches the full MIME source under this name.
ORIGINAL_EMAIL_NAME = "original_email.eml"
# Orders Linda issues; replies on any other record are not Linda's conversation.
ORDER_FIELDS = {PURCHASE_ORDER: "purchase_order_id", SALE_ORDER: "sale_order_id"}

# The only standardized replies handled without interpretation: the whole new
# (unquoted, unsigned) text must be exactly one of these, case-insensitively.
STANDARD_REPLIES = dict(
    (
        ("confirmed", "order_acknowledged"),
        ("confirm", "order_acknowledged"),
        ("not ready", "not_ready"),
    )
)
# RFC 3676 signature delimiter: the sender's text ends at this exact line.
SIGNATURE_DELIMITER = "-- "
TEXT_PLAIN = "text/plain"
TEXT_HTML = "text/html"
# Lines where the sender's new text ends and quoted or forwarded history begins.
QUOTE_START = re.compile(
    r"^(>|on .+ wrote:$|-{2,}\s*original message\s*-{2,}|_{8,}$|from:\s|sent:\s)",
    re.IGNORECASE,
)
FORWARD_MARKERS = re.compile(r"(-{5,}\s*forwarded message|begin forwarded message)", re.IGNORECASE)
FORWARD_SUBJECT = re.compile(r"^\s*(fwd?|fw)\s*:", re.IGNORECASE)


class PlasticosLogisticsResponse(models.Model):
    _name = "plasticos.logistics.response"
    _description = "Linda Logistics Response"
    _order = "id desc"

    company_id = fields.Many2one(
        RES_COMPANY,
        string="Company",
        required=True,
        readonly=True,
        index=True,
        ondelete="restrict",
        help="Company of the order the native mail gateway routed the reply to.",
    )
    mail_message_id = fields.Many2one(
        MAIL_MESSAGE,
        string="Incoming Message",
        required=True,
        readonly=True,
        index=True,
        ondelete="restrict",
        help="The exact native incoming message; its original and attachments stay on it.",
    )
    purchase_order_id = fields.Many2one(
        PURCHASE_ORDER,
        string="Purchase Order",
        readonly=True,
        index="btree_not_null",
        ondelete="restrict",
        help="Purchase order the native gateway routed the reply to.",
    )
    sale_order_id = fields.Many2one(
        SALE_ORDER,
        string="Sale Order",
        readonly=True,
        index="btree_not_null",
        ondelete="restrict",
        help="Sale order the native gateway routed the reply to.",
    )
    request_id = fields.Many2one(
        LOGISTICS_REQUEST,
        string="Answered Request",
        readonly=True,
        index="btree_not_null",
        ondelete="restrict",
        help="The exact Linda request the original's In-Reply-To/References name; never the latest one.",
    )
    source_kind = fields.Selection(
        [("booking", "Export Booking"), ("load", "Logistics Load")],
        readonly=True,
        index="btree_not_null",
        help="Typed source the native gateway routed the reply to; empty for PO/SO replies.",
    )
    source_res_id = fields.Integer(readonly=True, help="Id of the typed source record.")
    request_revision = fields.Integer(readonly=True, help="Revision of the answered request.")
    email_from = fields.Char(related="mail_message_id.email_from", string="From")
    binding = fields.Selection(
        [
            ("current", "Current Request"),
            ("stale", "Stale Request"),
            ("ambiguous", "Ambiguous"),
            ("unbound", "Unbound"),
        ],
        required=True,
        readonly=True,
        help="Which Linda request the native message ancestry proves this reply answers.",
    )
    interpretation = fields.Selection(
        [
            ("deterministic", "Standard Reply"),
            ("ai_not_run", "Free-form, AI Not Run"),
            ("not_interpreted", "Not Interpreted"),
        ],
        required=True,
        readonly=True,
    )
    candidate_kind = fields.Selection(
        [("order_acknowledged", "Order Acknowledged"), ("not_ready", "Not Ready")],
        readonly=True,
        help="Candidate meaning of a standardized reply; never an accepted business fact.",
    )
    disposition = fields.Selection(
        [
            ("identity_unverified", "Identity Unverified"),
            ("unresolved", "Unresolved"),
            ("unattributed", "Unattributed"),
            ("stale", "Stale"),
            ("unbound", "Unbound"),
        ],
        required=True,
        readonly=True,
        index=True,
        help="Deterministic validation outcome. No disposition is an accepted commitment: "
        "sender authentication is not available, so a matching reply stays identity_unverified.",
    )
    reason = fields.Char(readonly=True, help="Machine-readable reason for the binding or disposition.")

    _unique_message = models.Constraint(
        "UNIQUE(mail_message_id)",
        "A Linda response already exists for this message.",
    )
    _check_exactly_one_order = models.Constraint(
        "CHECK((source_kind IS NULL AND (purchase_order_id IS NOT NULL) != (sale_order_id IS NOT NULL))"
        " OR (source_kind IS NOT NULL AND source_res_id IS NOT NULL"
        " AND purchase_order_id IS NULL AND sale_order_id IS NULL))",
        "A Linda response belongs to exactly one purchase order, sale order or typed source.",
    )

    @api.depends("mail_message_id", "disposition")
    def _compute_display_name(self):
        labels = dict(self._fields["disposition"].selection)
        for response in self:
            order = response.purchase_order_id or response.sale_order_id
            label = order.name or (f"{response.source_kind} {response.source_res_id}" if response.source_kind else "")
            response.display_name = f"{label} · {labels.get(response.disposition, '')}"

    # ── Evidence integrity ───────────────────────────────────
    # Responses are recorded only by Linda's inbound handler under sudo() and never change.

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_("Linda response evidence is recorded by Linda only."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            raise AccessError(_("Linda response evidence is recorded by Linda only."))
        raise UserError(_("Linda response evidence is append-only."))

    def unlink(self):
        raise UserError(_("Linda response evidence is append-only and cannot be deleted."))

    # ── Inbound handling ─────────────────────────────────────

    @api.model
    def _record_incoming(self, messages):
        """Record one response per new incoming email on a Linda-issued order.

        Called by the native ``mail.message`` creation automation with exactly
        the messages just created, never by reading an order's chatter. Off
        mode records nothing. A message already recorded is returned as is.
        """
        if self.env[LOGISTICS_REQUEST]._linda_mode() == LINDA_MODE_OFF:
            return self.browse()
        # Native Odoo 19 template mail uses message_type ``email_outgoing``.
        # The automation domain and the predicate below keep that outgoing
        # message out of reply evidence. An inbound ``email`` row that lacks
        # the original MIME copy stays unbound (``original_not_retained``).
        # A composer path that posts message_type ``email`` for mail Linda
        # itself sent was not reproduced on this head, so that case stays Unknown.
        evidence = self.sudo()  # sudo: gateway records Linda evidence a follower may not write
        responses = self.browse()
        typed_models = evidence.env[LOGISTICS_REQUEST]._linda_source_models()
        for message in messages.sudo():  # sudo: gateway reads the new message when the follower cannot
            if message.message_type != "email":
                continue
            if message.model in typed_models:
                responses |= evidence._record_typed_incoming(message, typed_models[message.model])
                continue
            if message.model not in ORDER_FIELDS:
                continue
            existing = evidence.search([("mail_message_id", "=", message.id)], limit=1)
            if existing:
                responses |= existing
                continue
            order = (
                self.env[message.model]
                .sudo()  # sudo: gateway reads the order named by the message
                .browse(message.res_id)
                .exists()
            )
            order_field = ORDER_FIELDS[message.model]
            if not order or not evidence.env[LOGISTICS_REQUEST].search_count([(order_field, "=", order.id)]):
                continue
            responses |= evidence._record_message(message, order, order_field)
        return responses

    def _record_typed_incoming(self, message, source_kind):
        """Record one reply on a registered typed source that Linda actually wrote to."""
        existing = self.search([("mail_message_id", "=", message.id)], limit=1)
        if existing:
            return existing
        source = self.env[message.model].browse(message.res_id).exists()
        requests = self.env[LOGISTICS_REQUEST]
        if not source or not requests.search_count(
            [("source_kind", "=", source_kind), ("source_res_id", "=", source.id), ("source_model", "=", source._name)]
        ):
            return self.browse()
        original = self._native_original(message)
        request, binding, reason = self._bind_typed(message, source_kind, source, original)
        company = request.company_id or (source.company_id if "company_id" in source._fields else False)
        if not company:
            return self.browse()
        values = {
            "company_id": company.id,
            "mail_message_id": message.id,
            "source_kind": source_kind,
            "source_res_id": source.id,
            "request_id": request.id,
            "request_revision": request.revision,
            "binding": binding,
        }
        values.update(self._validate(message, request, binding, reason, original))
        return self.create(values)

    def _bind_typed(self, message, source_kind, source, original):
        """Which typed Linda request this reply answers, from its own header ancestry only."""
        no_request = self.env[LOGISTICS_REQUEST]
        if original is None:
            return no_request, "unbound", "original_not_retained"
        in_reply_to = (original.get("In-Reply-To") or "").strip()
        references = [ref.strip() for ref in unfold_references(original.get("References") or "")]
        known = [ref for ref in [in_reply_to, *references] if ref]
        requests = no_request.search([("mail_id.message_id", "in", known)]) if known else no_request
        if not requests:
            return no_request, "unbound", "no_linda_ancestor"
        direct = requests.filtered(lambda request: request.mail_id.message_id == in_reply_to)
        if direct:
            request = direct
        elif len(requests) == 1:
            request = requests
        else:
            return no_request, "ambiguous", "multiple_linda_ancestors"
        if (
            request.purpose not in TYPED_SPECS
            or request.source_kind != source_kind
            or request.source_model != source._name
            or request.source_res_id != source.id
        ):
            return no_request, "unbound", "ancestor_on_other_source"
        if request.purpose == "booking_cancel":
            return request, "stale", "reply_to_cancellation_notice"
        if request.state == "canceled":
            return request, "stale", "request_canceled"
        newer = no_request.search_count(
            [
                ("source_kind", "=", source_kind),
                ("source_res_id", "=", source.id),
                ("purpose", "=", request.purpose),
                ("partner_id", "=", request.partner_id.id),
                ("revision", ">", request.revision),
            ]
        )
        if newer:
            return request, "stale", "newer_revision_issued"
        return request, "current", False

    def _record_message(self, message, order, order_field):
        original = self._native_original(message)
        request, binding, reason = self._bind(message, order, order_field, original)
        values = {
            "company_id": order.company_id.id,
            "mail_message_id": message.id,
            order_field: order.id,
            "request_id": request.id,
            "request_revision": request.revision,
            "binding": binding,
        }
        values.update(self._validate(message, request, binding, reason, original))
        return self.create(values)

    @api.model
    def _native_original(self, message):
        """The native Keep Original MIME copy of exactly this message, or ``None``.

        A sender-supplied attachment cannot stand in for it: the copy must be
        the only one and carry this message's own Message-ID.
        """
        copies = message.attachment_ids.filtered(lambda attachment: attachment.name == ORIGINAL_EMAIL_NAME)
        if len(copies) != 1:
            return None
        original = email.message_from_bytes(copies.raw or b"", policy=email.policy.compat32)
        if (original.get("Message-ID") or "").strip() != (message.message_id or "").strip():
            return None
        return original

    def _bind(self, message, order, order_field, original):
        """Which Linda request this reply answers, from its own header ancestry only."""
        no_request = self.env[LOGISTICS_REQUEST]
        if original is None:
            return no_request, "unbound", "original_not_retained"
        in_reply_to = (original.get("In-Reply-To") or "").strip()
        references = [ref.strip() for ref in unfold_references(original.get("References") or "")]
        known = [ref for ref in [in_reply_to, *references] if ref]
        requests = no_request.search([("mail_id.message_id", "in", known)]) if known else no_request
        if not requests:
            return no_request, "unbound", "no_linda_ancestor"
        direct = requests.filtered(lambda request: request.mail_id.message_id == in_reply_to)
        if direct:
            request = direct
        elif len(requests) == 1:
            request = requests
        else:
            # Several Linda messages referenced and none replied to directly: native routing
            # would pick the latest; Linda keeps the reply unresolved instead.
            return no_request, "ambiguous", "multiple_linda_ancestors"
        if request[order_field] != order:
            return no_request, "unbound", "ancestor_on_other_order"
        if request.purpose in CANCEL_SPECS:
            return request, "stale", "reply_to_cancellation_notice"
        if request.purpose in ISSUE_SPECS and (request.cycle_closed or request.state == "canceled"):
            return request, "stale", "issue_cycle_closed"
        return request, "current", False

    def _validate(self, message, request, binding, reason, original):
        """Deterministic disposition; candidate meaning only for current, attributable replies."""
        not_interpreted = {"interpretation": "not_interpreted", "candidate_kind": False}
        if binding in ("unbound", "ambiguous"):
            return {**not_interpreted, "disposition": "unbound", "reason": reason}
        if binding == "stale":
            return {**not_interpreted, "disposition": "stale", "reason": reason}
        if email_normalize(message.email_from or "") != request.recipient_email:
            return {**not_interpreted, "disposition": "unattributed", "reason": "sender_not_issue_recipient"}
        text = self._original_text(original)
        if FORWARD_SUBJECT.match(message.subject or "") or FORWARD_MARKERS.search(text):
            return {**not_interpreted, "disposition": "unattributed", "reason": "forwarded"}
        new_lines = []
        for line in text.splitlines():
            stripped = line.strip()
            # RFC 3676 signature delimiter "-- ", or the start of quoted/forwarded history.
            if line.rstrip("\r") == SIGNATURE_DELIMITER or QUOTE_START.match(stripped):
                break
            if stripped:
                new_lines.append(stripped)
        kind = STANDARD_REPLIES.get(new_lines[0].rstrip(".!").strip().lower()) if len(new_lines) == 1 else None
        if not kind:
            return {
                "interpretation": "ai_not_run",
                "candidate_kind": False,
                "disposition": "unresolved",
                "reason": "free_form_ai_unavailable",
            }
        # Ancestry and From match the issue, but no provider-authenticated sender evidence
        # exists, so this is candidate evidence and never an accepted commitment.
        return {
            "interpretation": "deterministic",
            "candidate_kind": kind,
            "disposition": "identity_unverified",
            "reason": "sender_unauthenticated",
        }

    @api.model
    def _original_text(self, original):
        """Plain text the sender wrote, from the native original copy."""
        for part in original.walk():
            if part.get_content_type() == TEXT_PLAIN and not part.get_filename():
                return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
        for part in original.walk():
            if part.get_content_type() == TEXT_HTML and not part.get_filename():
                html = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
                return html2plaintext(html)
        return ""
