"""Extend Odoo Enterprise ``documents.document`` with plastics-specific fields.

This module adds relational links to the Plasticos domain models so that
every native document can be associated with a polymer type, load, transaction,
or intake record.  The native ``documents.document`` model already provides
``attachment_id``, ``folder_id``, ``tag_ids``, ``res_model``, ``res_id``,
``partner_id``, and ``owner_id`` — we do **not** duplicate any of those.

Fields prefixed with ``x_`` follow the Odoo convention for extension fields
to avoid future collisions with upstream Enterprise changes.
"""

import json
import logging

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

NATIVE_DECISION_FIELDS = frozenset(
    {
        "verified",
        "verified_by",
        "verified_at",
        "override",
        "override_reason",
        "verification_review_required",
        "verification_conflict_snapshot",
        "verification_snapshot_captured",
    }
)
NATIVE_HISTORY_KEY = "plasticos_native_verification_history_grant"
PROJECTION_FIELDS = ("verified", "verified_by", "verified_at", "override", "override_reason")


class NativeHistoryGrant:
    """In-process capability for the historical snapshot only. RPC JSON cannot carry it."""

    __slots__ = ("uid",)

    def __init__(self, uid):
        self.uid = uid


class DocumentNative(models.Model):
    """Plastics-specific extension of the native Enterprise document."""

    _inherit = "documents.document"

    # ── Plastics Domain Links ────────────────────────────────
    polymer_id = fields.Many2one(
        "plasticos.polymer",
        string="Polymer Type",
        index=True,
        tracking=True,
        help="Primary polymer type referenced in this document.",
        ondelete="restrict",
    )
    load_id = fields.Many2one(
        "plasticos.load",
        string="Load",
        index=True,
        tracking=True,
        help="Load this document is associated with (BOL, scale ticket).",
        ondelete="cascade",
    )
    transaction_id = fields.Many2one(
        "plasticos.transaction",
        string="Transaction",
        index=True,
        tracking=True,
        help="Transaction this document belongs to.",
        ondelete="cascade",
    )
    intake_id = fields.Many2one(
        "plasticos.intake",
        string="Intake",
        index=True,
        tracking=True,
        help="Intake record this document originated from.",
        ondelete="cascade",
    )

    # ── Classification ───────────────────────────────────────
    doc_type = fields.Selection(
        [
            ("bol", "Bill of Lading"),
            ("invoice", "Invoice / Vendor Bill"),
            ("scale_ticket", "Scale Ticket"),
            ("loading_pic", "Loading Pic"),
            ("customer_order", "Customer Order (CO)"),
            ("certification", "Certification"),
            ("permit", "Permit"),
            ("lab_report", "Lab / Test Report"),
            ("photo", "Photo / Image"),
            ("contract", "Contract"),
            ("correspondence", "Correspondence"),
            ("other", "Other"),
        ],
        string="Document Type",
        index=True,
        tracking=True,
        help="Plastics-specific document classification.",
    )

    # ── Verification projection (domain owner is plasticos.document) ──
    verified = fields.Boolean(
        string="Verified",
        compute="_compute_business_verification",
        search="_search_verified",
    )
    verified_by = fields.Many2one(
        "res.users",
        string="Verified By",
        compute="_compute_business_verification",
        search="_search_verified_by",
        ondelete="set null",
    )
    verified_at = fields.Datetime(
        string="Verified At",
        compute="_compute_business_verification",
    )
    override = fields.Boolean(
        string="Override",
        compute="_compute_business_verification",
        search="_search_override",
    )
    override_reason = fields.Text(
        string="Override Reason",
        compute="_compute_business_verification",
    )
    override_reason_draft = fields.Text(
        string="Override Reason",
        help="Reason typed before the override command. It is not the recorded decision.",
    )
    verification_review_required = fields.Boolean(
        string="Verification Review Required",
        default=False,
        help="Historical native and business verification disagree. Neither side is overwritten.",
    )
    verification_conflict_snapshot = fields.Text(
        string="Historical Native Verification",
        help="JSON snapshot of the native verification columns before this projection.",
    )
    verification_snapshot_captured = fields.Boolean(
        string="Verification Snapshot Captured",
        default=False,
    )

    # ── Sync Reference ───────────────────────────────────────
    plasticos_doc_id = fields.Many2one(
        "plasticos.document",
        string="Plasticos Document",
        readonly=True,
        help="Navigation to one business row. It is not the only association and it is not verification.",
        ondelete="restrict",
    )
    association_subject_model = fields.Selection(
        [
            ("plasticos.transaction", "Transaction"),
            ("plasticos.load", "Load"),
            ("purchase.order", "Purchase Order"),
            ("sale.order", "Sales Order"),
            ("stock.picking", "Transfer"),
        ],
        string="Subject",
    )
    association_subject_id = fields.Integer(string="Subject Record")
    association_source_reference = fields.Char(string="Source Reference")
    association_covered_quantity = fields.Float(string="Covered Quantity")

    # ── Actions ──────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._refuse_direct_decision_write(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._refuse_direct_decision_write(vals)
        return super().write(vals)

    def _refuse_direct_decision_write(self, vals):
        touched = NATIVE_DECISION_FIELDS.intersection(vals)
        if not touched:
            return
        history = touched <= {
            "verification_review_required",
            "verification_conflict_snapshot",
            "verification_snapshot_captured",
        }
        grant = self.env.context.get(NATIVE_HISTORY_KEY)
        if history and isinstance(grant, NativeHistoryGrant) and grant.uid == self.env.uid:
            return
        raise AccessError("Business verification cannot be written directly.")

    def _history_write(self, vals):
        grant = NativeHistoryGrant(self.env.uid)
        return self.with_context(**{NATIVE_HISTORY_KEY: grant}).write(vals)

    def _excluded_evidence_models(self):
        from odoo.addons.plasticos_documents.models.document import EXCLUDED_EVIDENCE_MODELS

        return EXCLUDED_EVIDENCE_MODELS

    def _domain_docs_for_attachment(self):
        attachments = self.mapped("attachment_id")
        if not attachments:
            return {}
        found = self.env["plasticos.document"].search([("attachment_id", "in", attachments.ids)])
        grouped = {}
        for doc in found:
            grouped.setdefault(doc.attachment_id.id, self.env["plasticos.document"])
            grouped[doc.attachment_id.id] |= doc
        return grouped

    def verification_binding(self):
        """exact, unlinked, ambiguous, unresolved, or conflict. Does not write."""
        self.ensure_one()
        if self.verification_review_required:
            return "conflict"
        if self.shortcut_document_id or self.type != "binary" or not self.attachment_id:
            return "unresolved"
        linked = self._domain_docs_for_attachment().get(self.attachment_id.id, self.env["plasticos.document"])
        if not self.plasticos_doc_id:
            return "ambiguous" if linked else "unlinked"
        if len(linked) != 1 or linked != self.plasticos_doc_id:
            return "ambiguous"
        legacy = self.plasticos_doc_id
        if legacy.attachment_id != self.attachment_id or legacy.res_model in self._excluded_evidence_models():
            return "unresolved"
        if not legacy.res_id or legacy.association_state != "accepted":
            return "unresolved"
        return "exact"

    def _exact_domain_document(self):
        self.ensure_one()
        if self.verification_binding() != "exact":
            return self.env["plasticos.document"]
        return self.plasticos_doc_id

    @api.depends(
        "plasticos_doc_id",
        "plasticos_doc_id.verified",
        "plasticos_doc_id.verified_by",
        "plasticos_doc_id.verified_at",
        "plasticos_doc_id.override",
        "plasticos_doc_id.override_reason",
        "plasticos_doc_id.attachment_id",
        "plasticos_doc_id.res_model",
        "plasticos_doc_id.res_id",
        "plasticos_doc_id.association_state",
        "attachment_id",
        "verification_review_required",
        "shortcut_document_id",
        "type",
    )
    def _compute_business_verification(self):
        grouped = self._domain_docs_for_attachment()
        excluded = self._excluded_evidence_models()
        empty = self.env["plasticos.document"]
        for rec in self:
            linked = grouped.get(rec.attachment_id.id, empty) if rec.attachment_id else empty
            legacy = rec.plasticos_doc_id
            exact = (
                not rec.verification_review_required
                and not rec.shortcut_document_id
                and rec.type == "binary"
                and legacy
                and rec.attachment_id
                and len(linked) == 1
                and linked == legacy
                and legacy.attachment_id == rec.attachment_id
                and legacy.res_model not in excluded
                and legacy.res_id
                and legacy.association_state == "accepted"
            )
            if exact:
                rec.verified = bool(legacy.verified)
                rec.verified_by = legacy.verified_by
                rec.verified_at = legacy.verified_at
                rec.override = bool(legacy.override)
                rec.override_reason = legacy.override_reason or False
            else:
                rec.verified = False
                rec.verified_by = False
                rec.verified_at = False
                rec.override = False
                rec.override_reason = False

    def _search_projected_boolean(self, fname, operator, value):
        if operator not in ("=", "!=") or not isinstance(value, bool):
            return [("id", "in", [])]
        want = value if operator == "=" else not value
        candidates = self.search([("type", "=", "binary")])
        ids = [rec.id for rec in candidates if bool(rec[fname]) is want]
        return [("id", "in", ids)]

    def _search_verified(self, operator, value):
        return self._search_projected_boolean("verified", operator, value)

    def _search_override(self, operator, value):
        return self._search_projected_boolean("override", operator, value)

    def _search_verified_by(self, operator, value):
        if operator not in ("=", "in", "!="):
            return [("id", "in", [])]
        candidates = self.search([("type", "=", "binary")])
        if operator == "in":
            wanted = set(value or [])
            ids = [rec.id for rec in candidates if rec.verified_by.id in wanted]
        elif operator == "!=":
            ids = [rec.id for rec in candidates if rec.verified_by.id != value]
        else:
            ids = [rec.id for rec in candidates if rec.verified_by.id == value]
        return [("id", "in", ids)]

    def _require_exact_domain(self):
        legacy = self.env["plasticos.document"]
        for rec in self:
            found = rec._exact_domain_document()
            if not found:
                raise UserError("UNRESOLVED: this file has no single authoritative evidence association.")
            legacy |= found
        return legacy

    def action_verify(self):
        """Delegate verification to plasticos.document. Does not author a native decision."""
        if not self.env.user.has_group("plasticos_documents.group_documents_user"):
            raise AccessError("Not authorized to verify documents.")
        legacy = self._require_exact_domain()
        legacy.action_verify()
        self.invalidate_recordset(list(PROJECTION_FIELDS))
        _logger.info("Native verify delegated for documents %s", self.ids)
        return True

    def action_override(self, reason=None):
        """Delegate override to plasticos.document. Reason is taken at decision time."""
        if not self.env.user.has_group("plasticos_documents.group_documents_manager"):
            raise AccessError("Not authorized to override.")
        if len(self) != 1 and reason is None:
            raise UserError("Override reason is required at decision time.")
        text = reason if isinstance(reason, str) else (self.override_reason_draft or "")
        legacy = self._require_exact_domain()
        legacy.action_override(reason=text.strip())
        drafts = self.filtered("override_reason_draft")
        if drafts:
            drafts.write({"override_reason_draft": False})
        self.invalidate_recordset(list(PROJECTION_FIELDS))
        return True

    def action_associate_exact(self, res_model, res_id, source_reference, covered_quantity=0.0):
        """Delegate an exact association. Does not verify and does not copy the original."""
        self.ensure_one()
        shell = self.env["plasticos.document.sync"].sync_native_to_legacy(self)
        if not shell:
            raise UserError("UNRESOLVED: the original file is missing.")
        row = shell.action_associate(res_model, res_id, source_reference, covered_quantity)
        self.invalidate_recordset(list(PROJECTION_FIELDS))
        return row

    def action_associate_from_form(self):
        self.ensure_one()
        return self.action_associate_exact(
            self.association_subject_model,
            self.association_subject_id,
            self.association_source_reference or "",
            self.association_covered_quantity,
        )

    def preserve_historical_native_verification(self, snapshot):
        """Record a historical native decision without copying it onto the business document.

        A second call is a no-op. The business ``verified`` fields are not written.
        """
        self.ensure_one()
        if not self.env.user.has_group("plasticos_documents.group_documents_manager"):
            raise AccessError("Not authorized to record a verification conflict.")
        if self.verification_snapshot_captured:
            return False
        if not isinstance(snapshot, dict):
            raise UserError("UNRESOLVED: historical verification snapshot is missing.")
        legacy = self.plasticos_doc_id
        conflict = _snapshot_conflicts(snapshot, legacy)
        payload = json.dumps(snapshot, sort_keys=True, default=str)
        self._history_write(
            {
                "verification_conflict_snapshot": payload,
                "verification_review_required": conflict,
                "verification_snapshot_captured": True,
            }
        )
        return True

    @api.model
    def _auto_link_partner(self, document):
        """Partner recency is not an exact evidence association.

        Phase A does not guess a transaction or load and does not verify the file.
        """
        if not document.partner_id:
            return
        if document.transaction_id or document.load_id:
            return
        _logger.info(
            "Document %s stays unlinked: partner %s is not an exact evidence association.",
            document.id,
            document.partner_id.id,
        )


def _snapshot_value(snapshot, key):
    value = snapshot.get(key)
    if value in ("", None, False):
        return False
    return value


def _snapshot_conflicts(snapshot, legacy):
    if not isinstance(snapshot, dict):
        return False
    native_verified = bool(_snapshot_value(snapshot, "verified"))
    native_override = bool(_snapshot_value(snapshot, "override"))
    if not legacy:
        return native_verified or native_override
    pairs = (
        ("verified", bool(legacy.verified)),
        ("override", bool(legacy.override)),
        ("verified_by", legacy.verified_by.id or False),
        ("verified_at", legacy.verified_at or False),
        ("override_reason", legacy.override_reason or False),
    )
    for key, current in pairs:
        historical = _snapshot_value(snapshot, key)
        if key in ("verified", "override"):
            historical = bool(historical)
        if historical != current:
            return True
    return False
