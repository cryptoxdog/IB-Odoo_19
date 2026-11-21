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
# A classified original with a file gets its pending business row when one of these is written.
SHELL_TRIGGER_FIELDS = frozenset({"doc_type", "attachment_id", "datas", "raw"})
PROJECTION_FIELDS = ("verified", "verified_by", "verified_at", "override", "override_reason")

# DEC-015 / DEC-014 (TASK-070): a native type tag (xmlid in this module) and the doc_type it
# names. Review-signal tags (Needs Review, To Split, Evidence Gap, Duplicate Candidate,
# Includes Supporting Evidence) and Verified name no doc_type and are not in this map.
TYPE_TAG_DOC_TYPES = {
    "tag_bol": "bol",
    "tag_vendor_bill": "invoice",
    "tag_scale_ticket": "scale_ticket",
    "tag_loading_pic": "loading_pic",
    "tag_customer_order": "customer_order",
    "tag_contract": "contract",
    "tag_certification": "certification",
    "tag_permit": "permit",
    "tag_lab_report": "lab_report",
    "tag_photo": "photo",
    "tag_correspondence": "correspondence",
    "tag_purchase_order": "purchase_order",
    "tag_packing_list": "packing_list",
    "tag_receiving_report": "receiving_report",
    "tag_certified_scale_ticket": "certified_scale_ticket",
    "tag_delivery_order_confirmation": "delivery_order",
    "tag_delivery_receipt": "delivery_receipt",
    "tag_carrier_certification": "carrier_certification",
    "tag_customer_invoice": "customer_invoice",
    "tag_financial_document": "financial_document",
    "tag_carrier_invoice": "carrier_invoice",
    "tag_credit_note": "credit_note",
    "tag_debit_note": "debit_note",
    "tag_statement": "statement",
    "tag_payment_confirmation": "payment_confirmation",
    "tag_order_confirmation": "order_confirmation",
    "tag_material_certification": "material_certification",
    "tag_technical_specification": "technical_specification",
    "tag_unloading_pic": "unloading_pic",
    "tag_delivery_photo": "delivery_photo",
    "tag_damage_photo": "damage_photo",
}
MODULE = "plasticos_documents_native"
NEEDS_REVIEW_TAG = f"{MODULE}.tag_needs_review"
VERIFIED_TAG = f"{MODULE}.tag_verified"
DOC_TYPE_SOURCE_TAG = "tag"
DOC_TYPE_SOURCE_HUMAN = "human"
# A write made by the bridge itself: its doc_type stays tag-derived and it does not re-bridge.
BRIDGE_CONTEXT_KEY = "plasticos_classification_bridge"
VERIFIED_TAG_GRANT_KEY = "plasticos_verified_tag_grant"


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
            # DEC-014 OPT-A (TASK-069): the types the v2.0 Auto-Sort prompts name.
            ("purchase_order", "Purchase Order"),
            ("packing_list", "Packing List"),
            ("receiving_report", "Receiving Report"),
            ("certified_scale_ticket", "Certified Scale Ticket (CST)"),
            ("delivery_order", "Delivery Order Confirmation"),
            ("delivery_receipt", "Delivery Receipt"),
            ("carrier_certification", "Carrier Certification"),
            ("customer_invoice", "Customer Invoice"),
            ("financial_document", "Financial Document"),
            ("carrier_invoice", "Carrier Invoice"),
            ("credit_note", "Credit Note"),
            ("debit_note", "Debit Note"),
            ("statement", "Statement"),
            ("payment_confirmation", "Payment Confirmation"),
            ("order_confirmation", "Order Confirmation"),
            ("material_certification", "Material Certification"),
            ("technical_specification", "Technical Specification"),
            ("unloading_pic", "Unloading Pic"),
            ("delivery_photo", "Delivery Photo"),
            ("damage_photo", "Damage Photo"),
            ("other", "Other"),
        ],
        string="Document Type",
        index=True,
        tracking=True,
        help="Plastics-specific document classification.",
    )
    doc_type_source = fields.Selection(
        [(DOC_TYPE_SOURCE_TAG, "Type tag"), (DOC_TYPE_SOURCE_HUMAN, "Human")],
        string="Document Type Source",
        tracking=True,
        readonly=True,
        copy=False,
        help="Where the document type came from. A human-set type is never replaced by a tag (DEC-015).",
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
        string="Draft Override Reason",
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
        index=True,
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
            self._prepare_classification_vals(vals)
        records = super().create(vals_list)
        records._hold_classified_originals()
        tagged_records = records.filtered(lambda rec: rec.tag_ids)
        if tagged_records and not self.env.context.get(BRIDGE_CONTEXT_KEY):
            tagged_records._bridge_classification_tags()
        return records

    def write(self, vals):
        self._refuse_direct_decision_write(vals)
        vals = self._prepare_classification_vals(dict(vals))
        result = super().write(vals)
        if SHELL_TRIGGER_FIELDS.intersection(vals):
            self._hold_classified_originals()
        if "tag_ids" in vals and not self.env.context.get(BRIDGE_CONTEXT_KEY):
            self._bridge_classification_tags()
        return result

    # ── Classification bridge (DEC-015, TASK-070) ───────────────
    def _prepare_classification_vals(self, vals):
        """Stamp who set ``doc_type`` and drop Verified from a tag write outside verification."""
        if "doc_type" in vals and not self.env.context.get(BRIDGE_CONTEXT_KEY):
            vals["doc_type_source"] = DOC_TYPE_SOURCE_HUMAN if vals["doc_type"] else False
        if "tag_ids" in vals and not self.env.context.get(VERIFIED_TAG_GRANT_KEY):
            verified = self.env.ref(VERIFIED_TAG, raise_if_not_found=False)
            if verified:
                vals["tag_ids"] = self._without_tag(vals["tag_ids"], verified.id)
        return vals

    @staticmethod
    def _without_tag(value, tag_id):
        """The x2many write value with ``tag_id`` never added. Removals are kept."""
        if isinstance(value, models.BaseModel):
            return [(6, 0, [rid for rid in value.ids if rid != tag_id])]
        cleaned = []
        for command in value or ():
            if not isinstance(command, (list, tuple)) or not command:
                cleaned.append(command)
                continue
            code = command[0]
            if code == 4 and command[1] == tag_id:
                _logger.info("Dropped the Verified tag from a write outside verification")
                continue
            if code == 6:
                ids = [rid for rid in (command[2] or ()) if rid != tag_id]
                if len(ids) != len(command[2] or ()):
                    _logger.info("Dropped the Verified tag from a write outside verification")
                cleaned.append((6, 0, ids))
                continue
            cleaned.append(command)
        return cleaned

    def _type_tag_doc_types(self):
        """``{documents.tag id: doc_type}`` for the native type tags that exist in this database."""
        found = {}
        for xmlid, doc_type in TYPE_TAG_DOC_TYPES.items():
            tag = self.env.ref(f"{MODULE}.{xmlid}", raise_if_not_found=False)
            if tag:
                found[tag.id] = doc_type
        return found

    def _bridge_classification_tags(self):
        """Derive ``doc_type`` from type tags as Auto-Sort leaves them, then route the review signals.

        Exactly one type tag sets its ``doc_type`` (source "tag"), which reaches the pending
        business shell through ``SHELL_TRIGGER_FIELDS``. Two or more type tags set nothing and add
        Needs Review. A human-set ``doc_type`` is never replaced.
        """
        type_tags = self._type_tag_doc_types()
        needs_review = self.env.ref(NEEDS_REVIEW_TAG, raise_if_not_found=False)
        bridge = self.with_context(**{BRIDGE_CONTEXT_KEY: True})
        for rec in bridge:
            if rec.type != "binary" or rec.shortcut_document_id:
                continue
            if rec.doc_type and rec.doc_type_source != DOC_TYPE_SOURCE_TAG:
                continue
            doc_types = {type_tags[tag.id] for tag in rec.tag_ids if tag.id in type_tags}
            if len(doc_types) == 1:
                doc_type = doc_types.pop()
                if rec.doc_type != doc_type:
                    rec.write({"doc_type": doc_type, "doc_type_source": DOC_TYPE_SOURCE_TAG})
            elif len(doc_types) > 1 and needs_review and needs_review not in rec.tag_ids:
                rec.write({"tag_ids": [(4, needs_review.id)]})
        bridge._route_review_signals()

    def _route_review_signals(self):
        """One DEC-019 activity per review signal through the TASK-060 router; idempotent."""
        service = self.env["plasticos.document.sync"]
        for rec in self:
            if rec.type != "binary" or not rec.attachment_id or rec.shortcut_document_id:
                continue
            # A failed routing must not lose the tag write; the error is logged with its trace.
            try:
                with self.env.cr.savepoint():
                    if rec.plasticos_doc_id:
                        service.sync_native_to_legacy(rec)
                    else:
                        service._schedule_review_signals(rec)
            except Exception:
                _logger.exception("Could not route the review signals of native document %s", rec.id)

    def action_open_classification_correction(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Correct Classification",
            "res_model": "plasticos.document.classification.correction",
            "view_mode": "form",
            "target": "new",
            "context": {"default_document_id": self.id, "default_folder_id": self.folder_id.id},
        }

    def _hold_classified_originals(self):
        """Give a classified original its pending business row as it arrives.

        Runs when a type is set and the file exists. It creates or finds the
        pending row and the manager review activity. It does not associate,
        accept or verify anything, and a repeat is a no-op.
        """
        service = self.env["plasticos.document.sync"]
        for rec in self:
            if not rec.doc_type or not rec.attachment_id or rec.shortcut_document_id or rec.type != "binary":
                continue
            if rec.plasticos_doc_id:
                continue
            # A failed hold must not lose the upload. The savepoint undoes the
            # partial row, the error is logged with its trace, and the operator
            # backfill (batch_sync_unlinked) picks the original up again.
            try:
                with self.env.cr.savepoint():
                    service.sync_native_to_legacy(rec)
            except Exception:
                _logger.exception("Could not hold classified native document %s as a pending business row", rec.id)

    def _message_post_after_hook(self, message, msg_vals):
        result = super()._message_post_after_hook(message, msg_vals)
        if message.message_type == "email":
            # The email arrives after the original is created: read its references now.
            service = self.env["plasticos.document.sync"]
            for rec in self.filtered(lambda doc: doc.doc_type and doc.attachment_id and doc.type == "binary"):
                try:
                    with self.env.cr.savepoint():
                        service.sync_native_to_legacy(rec)
                except Exception:
                    _logger.exception("Could not read email references for native document %s", rec.id)
        return result

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
        "plasticos_doc_id.obligation_kind",
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
                # A sole operation-scoped row is not global native verification.
                and legacy._is_legacy_obligation()
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

    def _exact_projected_rows(self, predicate):
        """Accepted legacy domain rows that are the only row on their original.

        Siblings of every obligation are counted, so an original with a legacy
        row and an operation row stays ambiguous at the native Boolean.
        """
        document = self.env["plasticos.document"]
        excluded = list(self._excluded_evidence_models())
        matched = document.search(
            [
                *predicate,
                ("association_state", "=", "accepted"),
                *document._legacy_obligation_domain(),
                ("res_id", "!=", 0),
                ("res_model", "not in", excluded),
            ]
        )
        if not matched:
            return document.browse()
        siblings = document.search([("attachment_id", "in", matched.attachment_id.ids)])
        counts = {}
        for row in siblings:
            counts[row.attachment_id.id] = counts.get(row.attachment_id.id, 0) + 1
        return matched.filtered(lambda row: counts.get(row.attachment_id.id) == 1)

    def _exact_pair_domain(self, rows):
        """Indexed native domain: one business row and the same original."""
        linked = rows.filtered("attachment_id")
        if not linked:
            return fields.Domain(False)
        return fields.Domain.OR(
            fields.Domain("plasticos_doc_id", "=", row.id) & fields.Domain("attachment_id", "=", row.attachment_id.id)
            for row in linked
        )

    def _positive_projection_domain(self, rows):
        return (
            fields.Domain("type", "=", "binary")
            & fields.Domain("verification_review_required", "=", False)
            & fields.Domain("shortcut_document_id", "=", False)
            & self._exact_pair_domain(rows)
        )

    def _negative_projection_domain(self, rows):
        """Every native record whose computed verification is not this exact set.

        URL and shortcut rows compute verified False. A binary-only negative
        domain hides them from verified=False and verified_by=False searches.
        """
        return ~self._positive_projection_domain(rows)

    def _search_projected_boolean(self, fname, operator, value):
        if operator == "in":
            wanted = list(value or [])
            domains = []
            if True in wanted:
                domains.append(self._positive_projection_domain(self._exact_projected_rows([(fname, "=", True)])))
            if False in wanted:
                domains.append(self._negative_projection_domain(self._exact_projected_rows([(fname, "=", True)])))
            if not domains:
                return [("id", "in", [])]
            if len(domains) == 1:
                return domains[0]
            return fields.Domain.OR(domains)
        # Odoo rewrites "=" into "in" before the search method. Refuse other forms
        # so the framework calls this method again with "=" or "!=".
        if operator not in ("=", "!="):
            raise NotImplementedError
        if not isinstance(value, bool):
            return [("id", "in", [])]
        want = value if operator == "=" else not value
        rows = self._exact_projected_rows([(fname, "=", True)])
        if want:
            return self._positive_projection_domain(rows)
        return self._negative_projection_domain(rows)

    def _search_verified(self, operator, value):
        return self._search_projected_boolean("verified", operator, value)

    def _search_override(self, operator, value):
        return self._search_projected_boolean("override", operator, value)

    def _search_verified_by(self, operator, value):
        if operator not in ("=", "in", "!="):
            raise NotImplementedError
        if operator == "in":
            wanted = list(value or [])
            users = [item for item in wanted if item]
            matched = (
                self._positive_projection_domain(self._exact_projected_rows([("verified_by", "in", users)]))
                if users
                else fields.Domain(False)
            )
            if any(not item for item in wanted):
                assigned = self._exact_projected_rows([("verified_by", "!=", False)])
                return matched | self._negative_projection_domain(assigned)
            return matched
        if operator == "!=":
            if not value:
                return self._positive_projection_domain(self._exact_projected_rows([("verified_by", "!=", False)]))
            return self._negative_projection_domain(self._exact_projected_rows([("verified_by", "=", value)]))
        if not value:
            return self._negative_projection_domain(self._exact_projected_rows([("verified_by", "!=", False)]))
        return self._positive_projection_domain(self._exact_projected_rows([("verified_by", "=", value)]))

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


_BOOLEAN_SNAPSHOT_KEYS = frozenset({"verified", "override"})


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
        if key in _BOOLEAN_SNAPSHOT_KEYS:
            historical = bool(historical)
        if historical != current:
            return True
    return False


class PlasticosDocumentNativeBridge(models.Model):
    """Enterprise document lookups live on the addon that depends on documents."""

    _inherit = "plasticos.document"

    def _invalidate_native_projection(self):
        attachments = self.mapped("attachment_id")
        self._invalidate_native_attachments(attachments)

    def _invalidate_native_attachments(self, attachments):
        if not attachments:
            return
        native = self.env["documents.document"].search([("attachment_id", "in", attachments.ids)])
        native.invalidate_recordset(["verified", "verified_by", "verified_at", "override", "override_reason"])

    def _original_file_company(self, attachment):
        if not attachment:
            return self.env["res.company"]
        natives = (
            self.env["documents.document"]
            .sudo()  # sudo: original company identity only; not an acceptance grant
            .search([("attachment_id", "=", attachment.id), ("shortcut_document_id", "=", False)])
        )
        companies = natives.mapped("company_id")
        if len(companies) > 1:
            raise UserError("UNRESOLVED: the original file companies conflict.")
        return companies[:1]
