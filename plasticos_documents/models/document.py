import logging

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

# Identity that is not an exact business evidence scope. Partner recency and a
# native document pointing at itself are not verification targets.
EXCLUDED_EVIDENCE_MODELS = frozenset({"res.partner", "documents.document"})

ALLOWED_SUBJECT_SELECTION = [
    ("plasticos.transaction", "Transaction"),
    ("plasticos.load", "Load"),
    ("purchase.order", "Purchase Order"),
    ("sale.order", "Sales Order"),
    ("stock.picking", "Transfer"),
]
ALLOWED_SUBJECTS = frozenset(item[0] for item in ALLOWED_SUBJECT_SELECTION)
ASSOCIATION_GRANT_KEY = "plasticos_document_association_grant"

# Obligation of a business row. Every row that existed before operation scope
# is legacy: invoice, close, transaction display and claims read legacy rows only.
LEGACY_OBLIGATION = "legacy"
# Operation-scope dimensions. They identify which obligation and which business
# operation revision this row proves. They never change once the row is accepted.
SCOPE_FIELDS = frozenset(
    {
        "obligation_kind",
        "operation_revision_key",
        "coverage_key",
        "quantity_known",
        "evidence_uom_id",
    }
)
ASSOCIATION_PROVENANCE = frozenset(
    {
        "associated_by",
        "associated_at",
        "source_reference",
        "source_revision",
        "subject_company_id",
        "association_review_required",
        "covered_quantity",
        "operation_revision_key",
        "coverage_key",
        "quantity_known",
        "evidence_uom_id",
    }
)
ASSOCIATION_IDENTITY = frozenset({"res_model", "res_id", "transaction_id", "load_id"})

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


class AssociationGrant:
    """In-process capability for an exact association. RPC JSON cannot carry it."""

    __slots__ = ("uid",)

    def __init__(self, uid):
        self.uid = uid


class VerificationGrant:
    """In-process write capability. RPC context is JSON and cannot carry this instance."""

    __slots__ = ("uid", "fields")

    def __init__(self, uid, fields):
        self.uid = uid
        self.fields = frozenset(fields)


class LifecycleGrant:
    """In-process capability for supersession. RPC context cannot carry this instance."""

    __slots__ = ("uid",)

    def __init__(self, uid):
        self.uid = uid


LIFECYCLE_GRANT_KEY = "plasticos_document_lifecycle_grant"
# Category, revision, and eligibility accepted with a verification decision.
# A plain write must not retarget or revive that decision.
ELIGIBILITY_FIELDS = frozenset(
    {
        "tag_id",
        "doc_category",
        "attachment_id",
        "res_model",
        "res_id",
        "transaction_id",
        "load_id",
        "active",
        "expiry_date",
        "is_current",
        "superseded_by",
        "version",
    }
)


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
    override_reason = fields.Text(string="Override Reason")
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
        string="Draft Override Reason",
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
        help="Stored calendar flag. Eligibility uses the live date, not this column.",
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

    association_state = fields.Selection(
        [("pending", "Pending"), ("accepted", "Accepted"), ("review", "Review")],
        string="Association",
        default="pending",
        required=True,
        index=True,
        readonly=True,
        help="Accepted only by the exact association command. Pending and review are not evidence.",
    )
    associated_by = fields.Many2one(
        "res.users",
        string="Associated By",
        readonly=True,
        ondelete="restrict",
    )
    associated_at = fields.Datetime(string="Associated At", readonly=True)
    source_reference = fields.Char(
        string="Source Reference",
        readonly=True,
        help="Attributable request, message, or on-screen selection recorded with the association.",
    )
    source_revision = fields.Char(
        string="Source Revision",
        readonly=True,
        help="Attachment checksum at the time the association was accepted.",
    )
    covered_quantity = fields.Float(
        string="Covered Quantity",
        readonly=True,
        help="Quantity this evidence row covers. It does not cover sibling loads or the rest of a shipment.",
    )
    subject_company_id = fields.Many2one(
        "res.company",
        string="Subject Company",
        readonly=True,
        ondelete="restrict",
    )
    candidate_partner_id = fields.Many2one(
        "res.partner",
        string="Candidate Partner",
        ondelete="set null",
        help="Navigation hint only. It is not an accepted association.",
    )
    pending_reason = fields.Text(string="Pending Reason", readonly=True)
    association_review_required = fields.Boolean(string="Association Review", readonly=True)
    association_subject_model = fields.Selection(
        ALLOWED_SUBJECT_SELECTION,
        string="Subject",
    )
    association_subject_id = fields.Integer(string="Subject Record")
    association_source_reference = fields.Char(string="Source Reference Draft")
    association_covered_quantity = fields.Float(string="Covered Quantity Draft")

    # ── Operation scope (one row per original, subject, obligation and revision) ──
    obligation_kind = fields.Char(
        string="Obligation",
        required=True,
        default=LEGACY_OBLIGATION,
        readonly=True,
        index=True,
        help=(
            "Which obligation this row proves. 'legacy' is the invoice, close and transaction evidence. "
            "Any other value is an operation obligation declared by its owner."
        ),
    )
    operation_revision_key = fields.Char(
        string="Operation Revision",
        readonly=True,
        index=True,
        help=(
            "The business operation revision this row proves, for example one booking revision. "
            "It is not the attachment checksum (Source Revision)."
        ),
    )
    coverage_key = fields.Char(
        string="Coverage",
        readonly=True,
        help="Normalized documentary coverage inside the operation, for example one container or one photo set.",
    )
    quantity_known = fields.Boolean(
        string="Quantity Known",
        readonly=True,
        default=False,
        help="True only when the source states the covered quantity and its unit. Unknown is never inferred.",
    )
    evidence_uom_id = fields.Many2one(
        "uom.uom",
        string="Evidence Unit",
        readonly=True,
        ondelete="restrict",
        help="Unit of the covered quantity. Required when the quantity is known.",
    )
    association_obligation_kind = fields.Char(string="Obligation Draft")
    association_operation_revision_key = fields.Char(string="Operation Revision Draft")
    association_coverage_key = fields.Char(string="Coverage Draft")
    association_quantity_known = fields.Boolean(string="Quantity Known Draft")
    association_evidence_uom_id = fields.Many2one(
        "uom.uom",
        string="Evidence Unit Draft",
        ondelete="set null",
    )

    _legacy_rows_carry_no_operation_scope = models.Constraint(
        "CHECK(obligation_kind <> 'legacy' OR (operation_revision_key IS NULL AND coverage_key IS NULL "
        "AND quantity_known IS NOT TRUE AND evidence_uom_id IS NULL))",
        "A legacy evidence row carries no operation scope.",
    )
    _accepted_operation_scope_is_complete = models.Constraint(
        "CHECK(obligation_kind = 'legacy' OR association_state <> 'accepted' OR "
        "(operation_revision_key IS NOT NULL AND coverage_key IS NOT NULL AND subject_company_id IS NOT NULL))",
        "Accepted operation evidence needs its operation revision, coverage and subject company.",
    )
    _known_quantity_has_unit = models.Constraint(
        "CHECK(quantity_known IS NOT TRUE OR evidence_uom_id IS NOT NULL)",
        "A known evidence quantity needs its unit.",
    )
    # NOT NULL keys on accepted operation rows close the NULL replay gap.
    _unique_accepted_operation_scope = models.UniqueIndex(
        "(attachment_id, res_model, res_id, source_revision, obligation_kind, operation_revision_key, coverage_key) "
        "WHERE association_state = 'accepted' AND obligation_kind <> 'legacy'"
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

    def _evidence_today(self):
        """Server calendar date. RPC context, caller timezone, and headers are not a clock."""
        return fields.Date.today()

    def _expiry_elapsed(self):
        self.ensure_one()
        return bool(self.expiry_date and self.expiry_date < self._evidence_today())

    def _elapsed_expiry_domain(self):
        """Live expiry domain. Do not route this through stored is_expired.

        The midnight recompute searches the stored column to repair drift.
        A custom is_expired search hides those rows and the repair never runs.
        """
        today = self._evidence_today()
        return [("expiry_date", "!=", False), ("expiry_date", "<", today)]

    @api.depends("expiry_date")
    def _compute_is_expired(self):
        today = self._evidence_today()
        for rec in self:
            rec.is_expired = bool(rec.expiry_date and rec.expiry_date < today)

    def _refuse_direct_decision_write(self, vals):
        touched = DECISION_FIELDS.intersection(vals)
        if not touched:
            return
        grant = self.env.context.get(VERIFICATION_GRANT_KEY)
        if not isinstance(grant, VerificationGrant) or grant.uid != self.env.uid or not touched <= grant.fields:
            raise AccessError("Business verification cannot be written directly.")

    def _association_vals_need_grant(self, vals):
        """Accepted evidence cannot be retargeted or stripped by a plain write.

        A pending row may still store a subject pointer. That pointer is not
        evidence until the association command sets the accepted state.
        """
        if vals.get("association_state") == "accepted":
            return True
        if any(vals.get(name) for name in ASSOCIATION_PROVENANCE):
            return True
        if "obligation_kind" in vals and (vals["obligation_kind"] or LEGACY_OBLIGATION) != LEGACY_OBLIGATION:
            return True
        accepted = any(rec.association_state == "accepted" for rec in self)
        if not accepted:
            return False
        if "association_state" in vals or ASSOCIATION_PROVENANCE.intersection(vals):
            return True
        if "obligation_kind" in vals:
            return True
        return bool(ASSOCIATION_IDENTITY.intersection(vals))

    @staticmethod
    def _scope_value(record, name):
        value = record[name]
        if isinstance(value, models.BaseModel):
            return value.id or False
        if isinstance(value, bool):
            return value
        return value or False

    def _scope_input_normalizers(self):
        return {
            "evidence_uom_id": self._m2o_id,
            "quantity_known": bool,
            "obligation_kind": lambda value: value or LEGACY_OBLIGATION,
        }

    @api.model
    def _legacy_obligation_domain(self):
        """Domain of the legacy obligation: invoice, close, transaction, claims, scale ticket."""
        return [("obligation_kind", "=", LEGACY_OBLIGATION)]

    @api.model
    def _operation_obligation_domain(self):
        return [("obligation_kind", "!=", LEGACY_OBLIGATION)]

    def _is_legacy_obligation(self):
        self.ensure_one()
        return (self.obligation_kind or LEGACY_OBLIGATION) == LEGACY_OBLIGATION

    def _refuse_accepted_scope_rewrite(self, vals):
        """Accepted operation scope is immutable, whatever grant the caller holds."""
        touched = SCOPE_FIELDS.intersection(vals)
        if not touched:
            return
        for rec in self:
            if rec.association_state != "accepted":
                continue
            for name in touched:
                normalize = self._scope_input_normalizers().get(name, lambda value: value or False)
                new = normalize(vals[name])
                if new != self._scope_value(rec, name):
                    raise AccessError("Accepted evidence scope cannot be rewritten.")

    def _refuse_direct_association_write(self, vals):
        if not self._association_vals_need_grant(vals):
            return
        grant = self.env.context.get(ASSOCIATION_GRANT_KEY)
        if not isinstance(grant, AssociationGrant) or grant.uid != self.env.uid:
            raise AccessError("Exact evidence association cannot be written directly.")

    @staticmethod
    def _m2o_id(value):
        if not value:
            return False
        return value.id if hasattr(value, "id") else int(value)

    def _eligibility_write_revives(self, rec, vals):
        """True when a plain write would reclassify or revive an accepted decision."""
        if not (rec.verified or rec.override):
            return False
        if "tag_id" in vals and self._m2o_id(vals["tag_id"]) != rec.tag_id.id:
            return True
        if "doc_category" in vals and (vals["doc_category"] or False) != (rec.doc_category or False):
            return True
        if "attachment_id" in vals and self._m2o_id(vals["attachment_id"]) != rec.attachment_id.id:
            return True
        if "version" in vals and vals["version"] != rec.version:
            return True
        if "active" in vals and vals["active"] and not rec.active:
            return True
        if "is_current" in vals and vals["is_current"] and not rec.is_current:
            return True
        if "superseded_by" in vals and not self._m2o_id(vals["superseded_by"]) and rec.superseded_by:
            return True
        if "expiry_date" in vals:
            new_value = vals["expiry_date"]
            if not new_value:
                return bool(rec.expiry_date)
            if rec.expiry_date and fields.Date.to_date(new_value) > rec.expiry_date:
                return True
        return False

    def _refuse_verified_eligibility_write(self, vals):
        watched = {
            "tag_id",
            "doc_category",
            "attachment_id",
            "version",
            "active",
            "is_current",
            "superseded_by",
            "expiry_date",
        }
        if not watched.intersection(vals):
            return
        for rec in self:
            if self._eligibility_write_revives(rec, vals):
                raise AccessError("Verified evidence category and eligibility cannot be rewritten directly.")

    def _refuse_direct_eligibility_write(self, vals):
        """A recorded decision stays bound to the category and eligibility it accepted.

        Fail-closed edits stay open: archive, supersede, and an earlier expiry.
        Clearing or extending expiry, restoring current, and retagging do not.
        """
        if not ELIGIBILITY_FIELDS.intersection(vals):
            return
        grant = self.env.context.get(LIFECYCLE_GRANT_KEY)
        if isinstance(grant, LifecycleGrant) and grant.uid == self.env.uid:
            return
        for rec in self:
            if self._eligibility_write_revives(rec, vals):
                raise AccessError("Verified evidence category and eligibility cannot be written directly.")

    def _decision_write(self, vals):
        grant = VerificationGrant(self.env.uid, DECISION_FIELDS)
        return self.with_context(**{VERIFICATION_GRANT_KEY: grant}).write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._refuse_direct_decision_write(vals)
            self._refuse_direct_association_write(vals)
        records = super().create(vals_list)
        records._invalidate_native_projection()
        self._trigger_transaction_recompute(records)
        return records

    def write(self, vals):
        self._refuse_direct_decision_write(vals)
        self._refuse_direct_association_write(vals)
        self._refuse_accepted_scope_rewrite(vals)
        self._refuse_verified_eligibility_write(vals)
        self._refuse_direct_eligibility_write(vals)
        # Old subjects lose this evidence when it moves or changes scope.
        previous = self.env["plasticos.transaction"]
        if ASSOCIATION_IDENTITY.intersection(vals) or SCOPE_FIELDS.intersection(vals):
            previous = self._get_related_transactions(self)
        result = super().write(vals)
        # Recompute if any compliance-affecting field changed
        compliance_fields = {
            "tag_id",
            "active",
            "transaction_id",
            "load_id",
            "res_model",
            "res_id",
            "verified",
            "override",
            "is_current",
            "expiry_date",
            "association_state",
            "source_revision",
            "evidence_digest",
            "superseded_by",
            *SCOPE_FIELDS,
        }
        if compliance_fields.intersection(vals.keys()):
            self._invalidate_native_projection()
            self._trigger_transaction_recompute(self, previous=previous)
        return result

    def _refuse_evidence_unlink(self):
        """Accepted or decided evidence is deleted only by a Documents Manager.

        BRS-POS-03-R004 and BRS-POS-03-R005: the recorded decision and its
        exact association are the audit trail. Superuser code paths (module
        uninstall, data repair) are server-side only and stay open.
        """
        if self.env.su or self.env.user.has_group(OVERRIDE_GROUP):
            return
        for rec in self:
            if rec.association_state == "accepted" or rec.verified or rec.override:
                raise AccessError(
                    "Accepted, verified, or overridden evidence can be deleted only by a Documents Manager."
                )

    def unlink(self):
        self._refuse_evidence_unlink()
        decided = self.filtered(
            lambda rec: (
                rec.association_state == "accepted"
                and not rec._is_legacy_obligation()
                and (rec.verified or rec.override)
            )
        )
        if decided:
            raise UserError(
                "Decided operation evidence cannot be deleted: its decision, actor and revision are history. "
                "Record a correction with action_supersede instead."
            )
        # Capture transactions before delete
        transactions = self._get_related_transactions(self)
        attachments = self.attachment_id
        result = super().unlink()
        self._invalidate_native_attachments(attachments)
        # Trigger recompute after delete (both flags AND compliance)
        if transactions:
            projected = transactions.sudo()  # sudo: compliance flags; internal users keep document read access
            projected._compute_missing_doc_flags()
            if hasattr(projected, "_compute_compliance"):
                projected._compute_compliance()
        return result

    def _invalidate_native_projection(self):
        """Native Documents overrides this. Base has no Enterprise projection."""
        return

    def _invalidate_native_attachments(self, attachments):
        """Native Documents overrides this after unlink."""
        return

    def _trigger_transaction_recompute(self, records, previous=None):
        """Trigger recomputation of doc-related fields on related transactions.

        R2 fix: Ensures real-time updates when documents are created/modified.
        Issue 3 fix: Also recomputes compliance_status.
        ``previous`` names the transactions the rows pointed at before a write,
        so the old subject drops evidence that moved away from it.
        """
        transactions = self._get_related_transactions(records)
        if previous:
            transactions |= previous.exists()
        if transactions:
            projected = transactions.sudo()  # sudo: compliance flags; internal users keep document read access
            projected._compute_missing_doc_flags()
            # Issue 3 fix: compliance_status depends on documents too
            if hasattr(projected, "_compute_compliance"):
                projected._compute_compliance()

    def _association_conflict_reason(self):
        """A stored transaction pointer must agree with the accepted load's parent."""
        self.ensure_one()
        if self.load_id and self.transaction_id and self.load_id.transaction_id != self.transaction_id:
            return "The stored transaction does not match the load's transaction."
        if self.res_model == "plasticos.load" and self.load_id and self.res_id and self.res_id != self.load_id.id:
            return "The accepted load does not match the stored load."
        if self.res_model == "plasticos.load" and self.res_id and self.transaction_id:
            load = self.env["plasticos.load"].browse(self.res_id).exists()
            if load and load.transaction_id != self.transaction_id:
                return "The load parent does not match the stored transaction."
        if (
            self.res_model == "plasticos.transaction"
            and self.transaction_id
            and self.res_id
            and self.res_id != self.transaction_id.id
        ):
            return "The accepted transaction does not match the stored transaction."
        return False

    def _route_association_conflict(self):
        """Keep the original and ask for review. Do not rewrite the pointers."""
        self.ensure_one()
        reason = self._association_conflict_reason()
        if not reason:
            return
        marker = "Conflicting association withheld from evidence."
        if any(marker in (message.body or "") for message in self.message_ids):
            return
        note_target = self.sudo()  # sudo: system review note; a read-only user reaches this via recompute
        note_target.message_post(
            body=f"{marker} {reason}",
            message_type="notification",
            subtype_xmlid="mail.mt_note",
        )

    def _get_related_transactions(self, records):
        """Find transactions related to documents whose pointers agree.

        A conflicting load and transaction pointer invalidates neither side.
        """
        tx_model = self.env["plasticos.transaction"]
        tx_ids = set()
        sale_order_ids = [record.res_id for record in records if record.res_model == "sale.order"]
        by_sale_order = {}
        if sale_order_ids:
            found = tx_model.search([("sale_order_id", "in", sale_order_ids)])
            for order, group in found.grouped("sale_order_id").items():
                by_sale_order[order.id] = group

        for record in records:
            if record._association_conflict_reason():
                record._route_association_conflict()
                continue
            if record.transaction_id:
                tx_ids.add(record.transaction_id.id)

            if record.res_model == "plasticos.transaction":
                tx_ids.add(record.res_id)
            elif record.res_model == "plasticos.load":
                load = self.env["plasticos.load"].browse(record.res_id).exists()
                if load.transaction_id:
                    tx_ids.add(load.transaction_id.id)
            elif record.res_model == "sale.order":
                txs = by_sale_order.get(record.res_id, tx_model) if record.res_id else tx_model
                if len(txs) == 1:
                    tx_ids.add(txs.id)

            if record.load_id.transaction_id:
                tx_ids.add(record.load_id.transaction_id.id)

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
        attachment = self.attachment_id.sudo()  # sudo: checksum only; verifier or override check already ran
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
        if not self.active or not self.is_current or self.superseded_by or self._expiry_elapsed():
            raise UserError("UNRESOLVED: expired, inactive, or superseded evidence cannot be accepted.")
        if self.association_state != "accepted":
            raise UserError("UNRESOLVED: the evidence is not an accepted exact association.")
        if self.source_revision and attachment.checksum != self.source_revision:
            raise UserError("UNRESOLVED: the approved original was replaced. A new version is required.")

    def _currently_eligible(self):
        """Current compliance use of a historical decision. Does not erase the decision."""
        self.ensure_one()
        if self._association_conflict_reason():
            return False
        if not (self.verified or self.override):
            return False
        if not self.active or not self.is_current or self.superseded_by or self._expiry_elapsed():
            return False
        attachment = self.attachment_id.sudo()  # sudo: checksum of the attachment already linked to this document
        if not self.evidence_digest or not attachment or attachment.checksum != self.evidence_digest:
            return False
        if self.evidence_attachment_id and self.evidence_attachment_id != attachment:
            return False
        if not self.res_model or self.res_model in EXCLUDED_EVIDENCE_MODELS or not self.res_id:
            return False
        if self.association_state != "accepted":
            return False
        if self.source_revision and attachment.checksum != self.source_revision:
            return False
        return True

    def _association_write(self, vals):
        grant = AssociationGrant(self.env.uid)
        return self.with_context(**{ASSOCIATION_GRANT_KEY: grant}).write(vals)

    def _subject_parties(self, target):
        parties = self.env["res.partner"]
        for fname in ("partner_id", "supplier_id", "buyer_id", "carrier_id"):
            if fname in target._fields and target[fname]:
                parties |= target[fname]
        return parties

    def _lock_original(self, attachment):
        """One lock per original so two subjects cannot both fill the same shell."""
        self.env.cr.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s))",
            [f"plasticos.document.original:{attachment.id}"],
        )

    def _lock_association(self, attachment, res_model, res_id, digest):
        self.env.cr.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s))",
            [f"plasticos.document.associate:{attachment.id}:{res_model}:{res_id}:{digest}"],
        )

    def _original_file_company(self, attachment):
        """Company recorded on the native original. Native Documents supplies it."""
        return self.env["res.company"]

    def _subject_company_candidates(self, target):
        """Legal company sources of a subject. Reads identity only; grants nothing.

        Returns ``(companies, requires_company)``.
        """
        owned = target.sudo()  # sudo: legal-company identity only; actor company_ids still gate acceptance
        companies = self.env["res.company"]
        requires_company = False
        if target._name == "plasticos.transaction":
            if owned.sale_order_id:
                requires_company = True
                if owned.sale_order_id.company_id:
                    companies |= owned.sale_order_id.company_id
            if owned.purchase_order_ids:
                requires_company = True
                companies |= owned.purchase_order_ids.mapped("company_id")
        elif target._name == "plasticos.load":
            # No sale order means no legal company. Do not invent env.company.
            if owned.sale_order_id or owned.company_id:
                requires_company = True
                if owned.company_id:
                    companies |= owned.company_id
        elif "company_id" in target._fields:
            requires_company = True
            if owned.company_id:
                companies |= owned.company_id
        return companies, requires_company

    def _resolved_subject_company(self, target):
        """Unique legal company of a visible subject. Does not invent env.company.

        Returns ``(company, error)``. ``company`` is empty when the subject has
        no commercial company source. ``error`` is a UserError message fragment.
        """
        if self.env.su:
            return self.env["res.company"], "exact association cannot be authorized through sudo"
        companies, requires_company = self._subject_company_candidates(target)
        if len(companies) > 1:
            return self.env["res.company"], "the subject companies conflict"
        if requires_company and not companies:
            return self.env["res.company"], "the subject company is not established"
        company = companies[:1]
        if company and company not in self.env.user.company_ids:
            return self.env["res.company"], "the subject belongs to another company"
        return company, False

    # ── Operation-scope extension hooks ────────────────────────────

    @api.model
    def _scoped_obligation_kinds(self):
        """Operation obligations an owner has declared. Core Documents declares none.

        A downstream owner (for example Export) adds its kinds by ordinary
        ``_inherit``. An undeclared kind is refused at association and is
        ``not_available`` in the verdict; it is never vacuously satisfied.
        """
        return frozenset()

    @api.model
    def _release_obligations(self, operation_kind):
        """Obligations whose stale evidence withholds this physical operation.

        Default: every declared obligation, for every operation kind. The owner
        of an obligation (for example Export) narrows this by ``_inherit``;
        Documents does not invent an obligation-to-operation mapping.
        """
        return self._scoped_obligation_kinds()

    @api.model
    def _scoped_subject_models(self):
        """Subjects that may carry operation evidence: the native subjects and Logistics J1.

        A model name is not an authority grant; target, company and original
        checks still run. Downstream owners extend this by ``_inherit``.
        """
        return ALLOWED_SUBJECTS | {"plasticos.iso.journey"}

    def _normalized_operation_scope(
        self, obligation_kind, operation_revision_key, coverage_key, quantity_known, covered_quantity, evidence_uom_id
    ):
        """Validate explicit operation dimensions. Nothing is inferred from old numbers or checksums."""
        if obligation_kind not in self._scoped_obligation_kinds():
            raise UserError("UNRESOLVED: that obligation is not a declared evidence obligation.")
        revision = (operation_revision_key or "").strip()
        if not revision:
            raise UserError("UNRESOLVED: operation evidence needs its exact operation revision.")
        coverage = " ".join((coverage_key or "").split()).lower() or "whole"
        uom = self.env["uom.uom"].browse(self._m2o_id(evidence_uom_id)).exists() if evidence_uom_id else False
        if quantity_known:
            if not uom:
                raise UserError("UNRESOLVED: a known evidence quantity needs its unit.")
            if not covered_quantity or covered_quantity <= 0:
                raise UserError("UNRESOLVED: a known evidence quantity must be positive.")
        elif covered_quantity:
            raise UserError("UNRESOLVED: an unknown quantity cannot carry a covered quantity.")
        return {
            "obligation_kind": obligation_kind,
            "operation_revision_key": revision,
            "coverage_key": coverage,
            "quantity_known": bool(quantity_known),
            "evidence_uom_id": uom.id if quantity_known and uom else False,
            "covered_quantity": covered_quantity if quantity_known else 0.0,
        }

    def action_associate(self, res_model, res_id, source_reference, covered_quantity=0.0):
        """Accept one exact subject for this original. Does not verify it.

        This is the legacy obligation: invoice, close and transaction evidence.
        """
        return self._associate_scope(
            res_model,
            res_id,
            source_reference,
            obligation_kind=LEGACY_OBLIGATION,
            covered_quantity=covered_quantity,
        )

    def _associate_scope(
        self,
        res_model,
        res_id,
        source_reference,
        *,
        obligation_kind=LEGACY_OBLIGATION,
        operation_revision_key=False,
        coverage_key=False,
        quantity_known=False,
        covered_quantity=0.0,
        evidence_uom_id=False,
    ):
        """Accept one exact subject and obligation scope for this original. Does not verify it.

        The acting user is checked here. A context flag cannot authorize it.
        Replaying the same scope returns the accepted row; a contradictory
        payload for the same scope is refused.
        """
        self.ensure_one()
        self._require_verifier()
        legacy = (obligation_kind or LEGACY_OBLIGATION) == LEGACY_OBLIGATION
        reference = (source_reference or "").strip()
        if not reference:
            raise UserError("UNRESOLVED: an attributable source reference is required.")
        if legacy:
            scope = {"covered_quantity": covered_quantity or 0.0}
            allowed = ALLOWED_SUBJECTS
        else:
            scope = self._normalized_operation_scope(
                obligation_kind,
                operation_revision_key,
                coverage_key,
                quantity_known,
                covered_quantity,
                evidence_uom_id,
            )
            allowed = self._scoped_subject_models()
        if res_model not in allowed or res_model not in self.env or not res_id:
            raise UserError("UNRESOLVED: that record is not an exact evidence subject.")
        attachment = self.attachment_id.sudo()  # sudo: checksum only; the verifier check already ran
        if (
            not attachment
            or not attachment.exists()
            or attachment.type != "binary"
            or not attachment.checksum
            or not attachment.file_size
        ):
            raise UserError("UNRESOLVED: the original file is missing.")
        target = self.env[res_model].browse(int(res_id)).exists()
        if not target:
            raise UserError("UNRESOLVED: the evidence target record is missing.")
        company, company_error = self._resolved_subject_company(target)
        if company_error:
            raise UserError(f"UNRESOLVED: {company_error}.")
        if not legacy and not company:
            raise UserError("UNRESOLVED: operation evidence needs the subject's company.")
        if self.candidate_partner_id and self.candidate_partner_id not in self._subject_parties(target):
            raise UserError("UNRESOLVED: the subject party does not match the stated counterparty.")
        partner_company = self.candidate_partner_id.company_id if self.candidate_partner_id else False
        if partner_company and company and partner_company != company:
            raise UserError("UNRESOLVED: the stated counterparty belongs to another company.")
        original_company = self._original_file_company(attachment)
        if company and original_company and original_company != company:
            raise UserError("UNRESOLVED: the original file belongs to another company.")
        digest = attachment.checksum
        subject_id = int(res_id)
        self._lock_original(attachment)
        lock_digest = digest
        if not legacy:
            lock_digest = (
                f"{digest}:{scope['obligation_kind']}:{scope['operation_revision_key']}:{scope['coverage_key']}"
            )
        self._lock_association(attachment, res_model, subject_id, lock_digest)
        self.invalidate_recordset()
        domain = [
            ("attachment_id", "=", attachment.id),
            ("res_model", "=", res_model),
            ("res_id", "=", subject_id),
            ("source_revision", "=", digest),
            ("association_state", "=", "accepted"),
            ("obligation_kind", "=", LEGACY_OBLIGATION if legacy else scope["obligation_kind"]),
        ]
        if not legacy:
            domain += [
                ("operation_revision_key", "=", scope["operation_revision_key"]),
                ("coverage_key", "=", scope["coverage_key"]),
            ]
        existing = self.search(domain, limit=1)
        if existing:
            if not legacy and (
                bool(existing.quantity_known) != scope["quantity_known"]
                or (existing.evidence_uom_id.id or False) != scope["evidence_uom_id"]
                or existing.covered_quantity != scope["covered_quantity"]
            ):
                raise UserError("UNRESOLVED: this evidence scope was already accepted with a different quantity.")
            return existing
        vals = {
            "res_model": res_model,
            "res_id": subject_id,
            "association_state": "accepted",
            "associated_by": self.env.uid,
            "associated_at": fields.Datetime.now(),
            "source_reference": reference,
            "source_revision": digest,
            "subject_company_id": company.id if company else False,
            "pending_reason": False,
            "transaction_id": target.id if res_model == "plasticos.transaction" else False,
            "load_id": target.id if res_model == "plasticos.load" else False,
            **scope,
        }
        placeholder = (
            self.association_state == "pending"
            and self.res_model in EXCLUDED_EVIDENCE_MODELS
            and not self.verified
            and not self.override
        )
        if placeholder:
            self._association_write(vals)
            return self
        grant = AssociationGrant(self.env.uid)
        return self.with_context(**{ASSOCIATION_GRANT_KEY: grant}).create(
            [
                {
                    "name": self.name,
                    "tag_id": self.tag_id.id,
                    "attachment_id": attachment.id,
                    "candidate_partner_id": self.candidate_partner_id.id,
                    "doc_category": self.doc_category,
                    **vals,
                }
            ]
        )

    def action_associate_from_form(self):
        """Form command. Draft fields are not the association until this runs."""
        self.ensure_one()
        kind = (self.association_obligation_kind or "").strip()
        if kind and kind != LEGACY_OBLIGATION:
            return self._associate_scope(
                self.association_subject_model,
                self.association_subject_id,
                self.association_source_reference or "",
                obligation_kind=kind,
                operation_revision_key=self.association_operation_revision_key,
                coverage_key=self.association_coverage_key,
                quantity_known=self.association_quantity_known,
                covered_quantity=self.association_covered_quantity,
                evidence_uom_id=self.association_evidence_uom_id.id,
            )
        row = self.action_associate(
            self.association_subject_model,
            self.association_subject_id,
            self.association_source_reference or "",
            self.association_covered_quantity,
        )
        return row

    @api.model
    def get_scoped_evidence_verdict(self, company_id, subject_kind, subject_id, obligation_kind, source_revision_key):
        """Frozen Documents command: is this exact operation obligation currently proven?

        Delegates to the compliance service. Returns ``applied`` with the proving
        row, ``blocked`` (missing or not yet verified), ``stale`` (only expired,
        superseded, replaced or other-revision evidence), ``ambiguous``
        (conflicting originals for one coverage) or ``not_available`` (unknown
        obligation, subject or company). It writes nothing.
        """
        return self.env["plasticos.compliance.service"].scoped_evidence_verdict(
            company_id, subject_kind, subject_id, obligation_kind, source_revision_key
        )

    def action_verify(self):
        """Record one verification decision for this evidence scope."""
        self._require_verifier()
        now = fields.Datetime.now()
        for rec in self:
            if rec.verified:
                digest = (
                    rec.attachment_id.sudo().checksum  # sudo: checksum after the verifier check
                    if rec.attachment_id
                    else False
                )
                if rec.evidence_digest and digest != rec.evidence_digest:
                    raise UserError("UNRESOLVED: the approved original was replaced. A new version is required.")
                continue
            rec._require_exact_current_scope()
            rec._decision_write(
                {
                    "verified": True,
                    "verified_by": self.env.uid,
                    "verified_at": now,
                    "evidence_digest": rec.attachment_id.sudo().checksum,  # sudo: checksum after the verifier check
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
                vals["evidence_digest"] = rec.attachment_id.sudo().checksum  # sudo: checksum after the override check
                vals["evidence_attachment_id"] = rec.attachment_id.id
            rec._decision_write(vals)
            if rec.override_reason_draft:
                rec.write({"override_reason_draft": False})
        return True

    def action_supersede(self, new_doc_id):
        """Suspend current eligibility. The historical decision actor and time stay."""
        self._require_verifier()
        grant = LifecycleGrant(self.env.uid)
        for rec in self:
            rec.with_context(**{LIFECYCLE_GRANT_KEY: grant}).write({"is_current": False, "superseded_by": new_doc_id})
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
                    *self._elapsed_expiry_domain(),
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


class IrAttachmentEvidenceRevision(models.Model):
    """A replaced original does not keep the previous version's current eligibility."""

    _inherit = "ir.attachment"

    def write(self, vals):
        result = super().write(vals)
        if not {"datas", "raw"}.intersection(vals):
            return result
        documents = self.env["plasticos.document"].search([("attachment_id", "in", self.ids)])
        replaced = documents.filtered(_replaced_accepted_evidence)
        if replaced:
            flagged = replaced.sudo()  # sudo: fail-closed review flag; actor may hold only document read
            flagged._association_write({"association_review_required": True})
        if documents:
            documents._invalidate_native_projection()
            documents._trigger_transaction_recompute(documents)
        return result


def _replaced_accepted_evidence(row):
    if row.association_state != "accepted" or not row.source_revision or not row.attachment_id:
        return False
    return row.attachment_id.checksum != row.source_revision
