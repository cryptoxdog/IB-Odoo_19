import logging

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

# Identity that is not an exact business evidence scope. Partner recency and a
# native document pointing at itself are not verification targets.
EXCLUDED_EVIDENCE_MODELS = frozenset({"res.partner", "documents.document"})

DECISION_FIELDS = frozenset(
    {
        "verified",
        "verified_by",
        "verified_at",
        "override",
        "override_reason",
        "override_by",
        "override_at",
        "evidence_digest",
        "evidence_attachment_id",
    }
)

VERIFICATION_GRANT_KEY = "plasticos_document_verification_grant"
VERIFIER_GROUP = "plasticos_documents.group_documents_user"
OVERRIDE_GROUP = "plasticos_documents.group_documents_manager"


class VerificationGrant:
    """In-process write capability. RPC context is JSON and cannot carry this instance."""

    __slots__ = ("uid", "fields")

    def __init__(self, uid, fields):
        self.uid = uid
        self.fields = frozenset(fields)


class PlasticosDocument(models.Model):
    _name = "plasticos.document"
    _description = "Plasticos Document"
    _inherit = ["mail.thread"]

    name = fields.Char(required=True)
    res_model = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)

    attachment_id = fields.Many2one("ir.attachment", required=True, ondelete="restrict")
    tag_id = fields.Many2one("plasticos.document.tag", required=True, ondelete="restrict")

    verified = fields.Boolean(default=False)
    verified_by = fields.Many2one("res.users", ondelete="restrict")
    verified_at = fields.Datetime()

    override = fields.Boolean(default=False)
    override_reason = fields.Text()
    override_by = fields.Many2one(
        "res.users",
        string="Override By",
        ondelete="restrict",
        help="Manager who recorded the override. Set only by the override command.",
    )
    override_at = fields.Datetime(
        string="Override At",
        help="When the override was recorded. Set only by the override command.",
    )
    override_reason_draft = fields.Text(
        string="Override Reason",
        help="Reason typed before the override command. It is not the recorded decision.",
    )
    evidence_digest = fields.Char(
        string="Evidence Digest",
        help="Attachment checksum accepted by the verification or override command.",
    )
    evidence_attachment_id = fields.Many2one(
        "ir.attachment",
        string="Evidence Attachment",
        ondelete="restrict",
        help="Attachment accepted by the verification or override command.",
    )

    active = fields.Boolean(default=True)

    # ── Expiry Tracking ────────────────────────────────────────────
    expiry_date = fields.Date(
        string="Expiry Date",
        help="Date after which this document is no longer valid.",
    )
    is_expired = fields.Boolean(
        string="Expired",
        compute="_compute_is_expired",
        store=True,
        help="Computed flag indicating whether the document has expired.",
    )

    # ── Versioning ─────────────────────────────────────────────────
    version = fields.Integer(
        string="Version",
        default=1,
        help="Document version number. Incremented on re-upload.",
    )
    superseded_by = fields.Many2one(
        "plasticos.document",
        string="Superseded By",
        help="Reference to the newer version of this document.",
        ondelete="restrict",
    )
    is_current = fields.Boolean(
        string="Current Version",
        default=True,
        help="Whether this is the current (latest) version of the document.",
    )

    # ── Transaction Link ───────────────────────────────────────────
    transaction_id = fields.Many2one(
        "plasticos.transaction",
        string="Transaction",
        index=True,
        help="Link this document to a specific transaction.",
        ondelete="cascade",
    )
    load_id = fields.Many2one(
        "plasticos.load",
        string="Load",
        index=True,
        ondelete="set null",
        help="Load this document is attached to (BOL, weight ticket, etc.).",
    )

    # ── Document Category ──────────────────────────────────────────
    doc_category = fields.Selection(
        [
            ("supplier", "Supplier Document"),
            ("carrier", "Carrier Document"),
            ("buyer", "Buyer Document"),
            ("internal", "Internal Document"),
        ],
        string="Document Category",
        help="Classification of the document by party responsible.",
    )

    @api.depends("expiry_date")
    def _compute_is_expired(self):
        today = fields.Date.today()
        for rec in self:
            if rec.expiry_date:
                rec.is_expired = rec.expiry_date < today
            else:
                rec.is_expired = False

    def _refuse_direct_decision_write(self, vals):
        touched = DECISION_FIELDS.intersection(vals)
        if not touched:
            return
        grant = self.env.context.get(VERIFICATION_GRANT_KEY)
        if not isinstance(grant, VerificationGrant) or grant.uid != self.env.uid or not touched <= grant.fields:
            raise AccessError("Business verification cannot be written directly.")

    def _decision_write(self, vals):
        grant = VerificationGrant(self.env.uid, DECISION_FIELDS)
        return self.with_context(**{VERIFICATION_GRANT_KEY: grant}).write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._refuse_direct_decision_write(vals)
        records = super().create(vals_list)
        records._invalidate_native_projection()
        self._trigger_transaction_recompute(records)
        return records

    def write(self, vals):
        self._refuse_direct_decision_write(vals)
        result = super().write(vals)
        # Recompute if any compliance-affecting field changed
        compliance_fields = {"tag_id", "active", "transaction_id", "verified", "override", "is_current", "expiry_date"}
        if compliance_fields.intersection(vals.keys()):
            self._invalidate_native_projection()
            self._trigger_transaction_recompute(self)
        return result

    def unlink(self):
        # Capture transactions before delete
        transactions = self._get_related_transactions(self)
        attachments = self.attachment_id
        result = super().unlink()
        if "documents.document" in self.env and attachments:
            native = self.env["documents.document"].search([("attachment_id", "in", attachments.ids)])
            native.invalidate_recordset(["verified", "verified_by", "verified_at", "override", "override_reason"])
        # Trigger recompute after delete (both flags AND compliance)
        if transactions:
            transactions._compute_missing_doc_flags()
            if hasattr(transactions, "_compute_compliance"):
                transactions._compute_compliance()
        return result

    def _invalidate_native_projection(self):
        """Drop cached native projections. Does not write a verification decision."""
        if "documents.document" not in self.env:
            return
        attachments = self.mapped("attachment_id")
        if not attachments:
            return
        native = self.env["documents.document"].search([("attachment_id", "in", attachments.ids)])
        native.invalidate_recordset(["verified", "verified_by", "verified_at", "override", "override_reason"])

    def _trigger_transaction_recompute(self, records):
        """Trigger recomputation of doc-related fields on related transactions.

        R2 fix: Ensures real-time updates when documents are created/modified.
        Issue 3 fix: Also recomputes compliance_status.
        """
        transactions = self._get_related_transactions(records)
        if transactions:
            transactions._compute_missing_doc_flags()
            # Issue 3 fix: compliance_status depends on documents too
            if hasattr(transactions, "_compute_compliance"):
                transactions._compute_compliance()

    def _get_related_transactions(self, records):
        """Find all transactions related to the given document records.

        Handles both direct link (transaction_id) and polymorphic link (res_model/res_id).
        """
        tx_model = self.env["plasticos.transaction"]
        tx_ids = set()

        for record in records:
            # Direct link
            if record.transaction_id:
                tx_ids.add(record.transaction_id.id)

            # Polymorphic link: document on transaction directly
            if record.res_model == "plasticos.transaction":
                tx_ids.add(record.res_id)

            # Polymorphic link: document on load -> find transaction
            elif record.res_model == "plasticos.load":
                tx = tx_model.search([("load_id", "=", record.res_id)], limit=1)
                if tx:
                    tx_ids.add(tx.id)

            # Polymorphic link: document on sale order -> find transaction
            elif record.res_model == "sale.order":
                tx = tx_model.search([("sale_order_id", "=", record.res_id)], limit=1)
                if tx:
                    tx_ids.add(tx.id)

        return tx_model.browse(list(tx_ids)) if tx_ids else tx_model

    def _require_verifier(self):
        if not self.env.user.has_group(VERIFIER_GROUP):
            raise AccessError("Not authorized to verify documents.")

    def _require_override_manager(self):
        if not self.env.user.has_group(OVERRIDE_GROUP):
            raise AccessError("Not authorized to override.")

    def _require_exact_current_scope(self):
        """Refuse a decision whose file or business target is not exact and current."""
        self.ensure_one()
        # The command already checked the actor. ir.attachment rules hide an
        # original with no res_id from anyone but its author; the checksum read
        # is the evidence identity, not a second verification writer.
        attachment = self.attachment_id.sudo()  # checksum only; actor already passed the command check
        if (
            not attachment
            or not attachment.exists()
            or attachment.type != "binary"
            or not attachment.checksum
            or not attachment.file_size
        ):
            raise UserError("UNRESOLVED: the original file is missing.")
        if not self.res_model or not self.res_id or self.res_model in EXCLUDED_EVIDENCE_MODELS:
            raise UserError("UNRESOLVED: the evidence is not bound to an exact business record.")
        if self.res_model not in self.env:
            raise UserError("UNRESOLVED: the evidence target model is missing.")
        target = self.env[self.res_model].browse(self.res_id).exists()
        if not target:
            raise UserError("UNRESOLVED: the evidence target record is missing.")
        if not self.active or not self.is_current or self.superseded_by or self.is_expired:
            raise UserError("UNRESOLVED: expired, inactive, or superseded evidence cannot be accepted.")

    def _currently_eligible(self):
        """Current compliance use of a historical decision. Does not erase the decision."""
        self.ensure_one()
        if not (self.verified or self.override):
            return False
        if not self.active or not self.is_current or self.superseded_by or self.is_expired:
            return False
        attachment = self.attachment_id.sudo()  # checksum only; actor already passed the command check
        if not self.evidence_digest or not attachment or attachment.checksum != self.evidence_digest:
            return False
        if self.evidence_attachment_id and self.evidence_attachment_id != attachment:
            return False
        if not self.res_model or self.res_model in EXCLUDED_EVIDENCE_MODELS or not self.res_id:
            return False
        return True

    def action_verify(self):
        """Record one verification decision for this evidence scope."""
        self._require_verifier()
        now = fields.Datetime.now()
        for rec in self:
            if rec.verified:
                digest = rec.attachment_id.sudo().checksum if rec.attachment_id else False  # same identity read
                if rec.evidence_digest and digest != rec.evidence_digest:
                    raise UserError("UNRESOLVED: the approved original was replaced. A new version is required.")
                continue
            rec._require_exact_current_scope()
            rec._decision_write(
                {
                    "verified": True,
                    "verified_by": self.env.uid,
                    "verified_at": now,
                    "evidence_digest": rec.attachment_id.sudo().checksum,  # same identity read
                    "evidence_attachment_id": rec.attachment_id.id,
                }
            )
        return True

    def action_override(self, reason=None):
        """Record a manager override. The reason is fixed at decision time."""
        self._require_override_manager()
        text = reason if isinstance(reason, str) else ""
        if reason is None and len(self) == 1:
            text = self.override_reason_draft or ""
        text = text.strip()
        if not text:
            raise UserError("Override reason is required at decision time.")
        now = fields.Datetime.now()
        for rec in self:
            if rec.override:
                if (rec.override_reason or "").strip() != text:
                    raise UserError("Override reason cannot be changed after the decision.")
                continue
            rec._require_exact_current_scope()
            vals = {
                "override": True,
                "override_reason": text,
                "override_by": self.env.uid,
                "override_at": now,
            }
            if not rec.evidence_digest:
                vals["evidence_digest"] = rec.attachment_id.sudo().checksum  # same identity read
                vals["evidence_attachment_id"] = rec.attachment_id.id
            rec._decision_write(vals)
            if rec.override_reason_draft:
                rec.write({"override_reason_draft": False})
        return True

    def action_supersede(self, new_doc_id):
        """Mark this document as superseded by a newer version."""
        for rec in self:
            rec.is_current = False
            rec.superseded_by = new_doc_id
            _logger.info(
                "Document %s (v%d) superseded by document %s",
                rec.name,
                rec.version,
                new_doc_id,
            )

    @api.model
    def _cron_compliance_audit(self):
        """Report expired historical approvals. Does not erase them.

        Called by the scheduled action ``cron_document_compliance_check``.
        Expiry removes current eligibility inside the compliance service.
        The original ``verified`` decision and its actor/time stay in place.
        """
        self.env.cr.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s))", ["plasticos_documents.cron_document_compliance_check"]
        )
        locked = self.env.cr.fetchone()[0]
        if not locked:
            _logger.info("Skipping compliance audit cron: lock is already held.")
            return

        try:
            expired = self.search(
                [
                    ("verified", "=", True),
                    ("is_expired", "=", True),
                    ("active", "=", True),
                ],
                order="write_date ASC, id ASC",
                limit=500,
            )
            _logger.info(
                "Compliance audit: %s historically verified documents are expired and "
                "excluded from current eligibility.",
                len(expired),
            )
        finally:
            self.env.cr.execute(
                "SELECT pg_advisory_unlock(hashtext(%s))", ["plasticos_documents.cron_document_compliance_check"]
            )
