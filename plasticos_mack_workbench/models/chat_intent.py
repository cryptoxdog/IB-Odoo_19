"""Immutable, server-resolved Odoo chatter intent receipts for Mack."""

from __future__ import annotations

import hashlib

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

_ALLOWED_INTENT_KINDS = frozenset({"consult", "draft_edit", "prepare_request"})
_MAX_ATTACHMENT_REFS = 32
_MAX_MESSAGE_BODY_BYTES = 32_768
_RECEIPT_STATE = "recorded"


def _sha256_text(value: str) -> str:
    """Return the stable digest for a server-read text value."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _required_positive_int(value: object, *, label: str) -> int:
    """Reject non-integer or non-positive caller-supplied record locators."""
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValidationError(_("%s must be a positive integer.") % label)
    return value


def _validated_attachment_ids(value: object) -> list[int]:
    """Normalize bounded attachment locators without accepting attachment evidence."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationError(_("Attachment references must be a list."))
    if len(value) > _MAX_ATTACHMENT_REFS:
        raise ValidationError(_("Attachment references exceed the maximum number of values."))

    attachment_ids: list[int] = []
    for item in value:
        attachment_id = _required_positive_int(item, label="Attachment reference")
        if attachment_id in attachment_ids:
            raise ValidationError(_("Attachment references must not contain duplicates."))
        attachment_ids.append(attachment_id)
    return attachment_ids


class PlasticosMackChatIntentReceipt(models.Model):
    """One immutable record of an authenticated user's native Odoo chat intent.

    A receipt is conversation evidence only. It does not authorize, queue, or execute
    commercial work; it never mutates the intake, CWI, matching state, activity state,
    order state, or any external system.
    """

    _name = "plasticos.mack.chat.intent.receipt"
    _description = "Mack Chat Intent Receipt"
    _inherit = ["mail.thread"]
    _order = "create_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(
        string="Intent Receipt",
        required=True,
        readonly=True,
        copy=False,
        default="New",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
        index=True,
        ondelete="restrict",
    )
    actor_user_id = fields.Many2one(
        "res.users",
        string="Recorded For User",
        required=True,
        readonly=True,
        index=True,
        ondelete="restrict",
    )
    actor_partner_id = fields.Many2one(
        "res.partner",
        string="Recorded For Partner",
        required=True,
        readonly=True,
        index=True,
        ondelete="restrict",
    )
    intake_id = fields.Many2one(
        "plasticos.intake",
        string="Canonical Intake",
        required=True,
        readonly=True,
        index=True,
        ondelete="restrict",
    )
    source_message_id = fields.Many2one(
        "mail.message",
        string="Native Odoo Source Message",
        required=True,
        readonly=True,
        index=True,
        ondelete="restrict",
    )
    source_message_date = fields.Datetime(required=True, readonly=True, copy=False)
    source_message_body_sha256 = fields.Char(required=True, readonly=True, copy=False, index=True)
    attachment_refs = fields.Json(string="Verified Attachment References", required=True, readonly=True, copy=False)
    intent_kind = fields.Selection(
        selection=[(kind, kind.replace("_", " ").title()) for kind in sorted(_ALLOWED_INTENT_KINDS)],
        required=True,
        readonly=True,
        index=True,
    )
    canonical_write_date = fields.Datetime(
        string="Observed Canonical Write Date",
        required=True,
        readonly=True,
        copy=False,
        help="Server-observed read snapshot only; this is not compare-and-set protection.",
    )
    idempotency_key = fields.Char(required=True, readonly=True, copy=False, index=True)
    state = fields.Selection(
        [("recorded", "Recorded")],
        required=True,
        readonly=True,
        default=_RECEIPT_STATE,
        tracking=True,
    )

    _unique_name = models.Constraint("unique(name)", "Intent receipt reference must be unique.")
    _unique_company_source_message = models.Constraint(
        "unique(company_id, source_message_id)",
        "An intent receipt already exists for this company and source message.",
    )

    @api.constrains(
        "actor_user_id",
        "actor_partner_id",
        "intake_id",
        "source_message_id",
        "source_message_date",
        "source_message_body_sha256",
        "attachment_refs",
        "intent_kind",
        "canonical_write_date",
        "idempotency_key",
        "state",
    )
    def _check_receipt_shape(self):
        for receipt in self:
            if receipt.intent_kind not in _ALLOWED_INTENT_KINDS:
                raise ValidationError(_("Intent kind is invalid."))
            if receipt.state != _RECEIPT_STATE:
                raise ValidationError(_("Only the recorded receipt state is allowed."))
            if not receipt.source_message_date or not receipt.canonical_write_date:
                raise ValidationError(_("Server-observed source and canonical timestamps are required."))
            if len(receipt.source_message_body_sha256 or "") != 64:
                raise ValidationError(_("Source message digest must be a SHA-256 digest."))
            if not (receipt.idempotency_key or "").strip() or len(receipt.idempotency_key) > 256:
                raise ValidationError(_("Idempotency key is required and must be at most 256 characters."))
            if not isinstance(receipt.attachment_refs, list):
                raise ValidationError(_("Verified attachment references must be a list."))
            if len(receipt.attachment_refs) > _MAX_ATTACHMENT_REFS:
                raise ValidationError(_("Verified attachment references exceed the maximum number of values."))
            for attachment_ref in receipt.attachment_refs:
                if not isinstance(attachment_ref, dict):
                    raise ValidationError(_("Each verified attachment reference must be an object."))
                if set(attachment_ref) != {"attachment_id", "checksum"}:
                    raise ValidationError(_("Verified attachment reference fields are invalid."))
                if not isinstance(attachment_ref["attachment_id"], int) or isinstance(
                    attachment_ref["attachment_id"], bool
                ):
                    raise ValidationError(_("Verified attachment reference ID is invalid."))
                if attachment_ref["checksum"] is not None and not isinstance(attachment_ref["checksum"], str):
                    raise ValidationError(_("Verified attachment checksum is invalid."))

    @api.model_create_multi
    def create(self, vals_list):
        """Deny generic ORM creation; callers must use the verified source-message method."""
        raise AccessError(_("Chat intent receipts must be recorded from a verified Odoo source message."))

    def write(self, values):
        raise AccessError(_("Chat intent receipts are immutable after creation."))

    def unlink(self):
        raise AccessError(_("Chat intent receipts are retained for audit and cannot be deleted."))

    @api.model
    def record_intent_from_source_message(
        self,
        intake_id: int,
        source_message_id: int,
        intent_kind: str,
        attachment_ids: list[int] | None = None,
    ) -> dict[str, object]:
        """Record a non-executing intent after resolving all authority on the server.

        The caller may supply only record locators and a closed-vocabulary intent kind.
        Odoo resolves the current actor, active company, native message, target access,
        message-thread binding, attachment evidence, and canonical read snapshot.
        """
        self.check_access_rights("create")
        if self.env.user.share:
            raise AccessError(_("Only internal Odoo users may record Mack chat intents."))
        if len(self.env.companies) != 1:
            raise ValidationError(
                _(
                    "Mack chat intent receipts require a single-company Odoo context until canonical intake "
                    "company scope is defined."
                )
            )
        if intent_kind not in _ALLOWED_INTENT_KINDS:
            raise ValidationError(_("Intent kind is invalid."))

        resolved_intake_id = _required_positive_int(intake_id, label="Canonical intake")
        resolved_message_id = _required_positive_int(source_message_id, label="Source message")
        requested_attachment_ids = _validated_attachment_ids(attachment_ids)

        intake = self.env["plasticos.intake"].browse(resolved_intake_id).exists()
        if not intake:
            raise ValidationError(_("Canonical intake does not exist."))
        intake.check_access_rights("read")
        intake.check_access_rule("read")
        intake.check_access_rights("write")
        intake.check_access_rule("write")

        message = self.env["mail.message"].browse(resolved_message_id).exists()
        if not message:
            raise ValidationError(_("Source message does not exist."))
        message.check_access_rights("read")
        message.check_access_rule("read")
        if message.model != "plasticos.intake" or message.res_id != intake.id:
            raise ValidationError(_("Source message is not part of the canonical intake thread."))
        if message.message_type != "comment":
            raise ValidationError(_("Only native Odoo chatter comments may record a Mack chat intent."))
        if message.author_id != self.env.user.partner_id:
            raise AccessError(_("Only the authenticated author's native Odoo message may record an intent."))

        message_body = message.body or ""
        if not message_body.strip():
            raise ValidationError(_("Source message body is required."))
        if len(message_body.encode("utf-8")) > _MAX_MESSAGE_BODY_BYTES:
            raise ValidationError(_("Source message body exceeds the maximum allowed size."))

        attachments_by_id = {attachment.id: attachment for attachment in message.attachment_ids}
        attachment_refs: list[dict[str, object]] = []
        for attachment_id in requested_attachment_ids:
            attachment = attachments_by_id.get(attachment_id)
            if not attachment:
                raise ValidationError(_("Attachment is not linked to the verified source message."))
            attachment.check_access_rights("read")
            attachment.check_access_rule("read")
            attachment_refs.append(
                {
                    "attachment_id": attachment.id,
                    "checksum": attachment.checksum or None,
                }
            )

        idempotency_key = f"mack-chat-intent:v1:{self.env.company.id}:{message.id}"
        existing = self.search(
            [
                ("company_id", "=", self.env.company.id),
                ("source_message_id", "=", message.id),
            ],
            limit=1,
        )
        values = {
            "company_id": self.env.company.id,
            "actor_user_id": self.env.user.id,
            "actor_partner_id": self.env.user.partner_id.id,
            "intake_id": intake.id,
            "source_message_id": message.id,
            "source_message_date": message.date,
            "source_message_body_sha256": _sha256_text(message_body),
            "attachment_refs": attachment_refs,
            "intent_kind": intent_kind,
            "canonical_write_date": intake.write_date,
            "idempotency_key": idempotency_key,
            "state": _RECEIPT_STATE,
        }
        if existing:
            existing._assert_idempotent_replay(values)
            return existing._receipt_response()

        values["name"] = self.env["ir.sequence"].next_by_code("plasticos.mack.chat.intent.receipt") or "New"
        receipt = super().create([values])
        return receipt._receipt_response()

    def _assert_idempotent_replay(self, values: dict[str, object]) -> None:
        """Return an existing receipt only when all server-resolved material matches."""
        self.ensure_one()
        comparable = {
            "company_id": self.company_id.id,
            "actor_user_id": self.actor_user_id.id,
            "actor_partner_id": self.actor_partner_id.id,
            "intake_id": self.intake_id.id,
            "source_message_id": self.source_message_id.id,
            "source_message_date": self.source_message_date,
            "source_message_body_sha256": self.source_message_body_sha256,
            "attachment_refs": self.attachment_refs,
            "intent_kind": self.intent_kind,
            "canonical_write_date": self.canonical_write_date,
            "idempotency_key": self.idempotency_key,
            "state": self.state,
        }
        for field_name, existing_value in comparable.items():
            if values.get(field_name) != existing_value:
                raise ValidationError(
                    _("Source message is already bound to different chat intent material (%s).") % field_name
                )

    def _receipt_response(self) -> dict[str, object]:
        """Return only the bounded receipt locator for authenticated RPC callers."""
        self.ensure_one()
        return {
            "receipt_id": self.id,
            "receipt_ref": self.name,
            "state": self.state,
            "source_message_id": self.source_message_id.id,
        }
