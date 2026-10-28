"""Bidirectional sync between native ``documents.document`` and legacy
``plasticos.document``.

When a native document gets plastics-specific fields populated (polymer,
load, transaction, doc_type), this service ensures a corresponding
``plasticos.document`` record exists for backward compatibility with the
compliance service and existing document rules.

The sync is **one-way primary**: native → legacy.  The legacy record is
a mirror that the compliance engine can query without knowing about the
Enterprise module.
"""

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class DocumentSyncService(models.AbstractModel):
    """Service that synchronises native Enterprise documents with the legacy
    ``plasticos.document`` model used by the compliance engine."""

    _name = "plasticos.document.sync"
    _description = "Native ↔ Legacy Document Sync Service"

    # ── Tag Mapping ──────────────────────────────────────────
    # Maps doc_type selection values to plasticos.document.tag codes.
    # Aligned with plasticos_documents/data/document_tags_data.xml
    DOC_TYPE_TAG_MAP = {
        "bol": "BOL",
        "invoice": "INV",
        "scale_ticket": "SCALE",
        "loading_pic": "PHOTO",
        "customer_order": "CO",
        "contract": "CONTRACT",
        "certification": "CERT",
        "permit": "PERMIT",
        "lab_report": "LAB",
        "photo": "PHOTO",
        "correspondence": "CORR",
        "other": "OTHER",
    }

    @api.model
    def sync_native_to_legacy(self, native_doc):
        """Create or update a ``plasticos.document`` record from a native
        ``documents.document`` record.

        Parameters
        ----------
        native_doc : recordset
            A single ``documents.document`` record with plastics fields.

        Returns
        -------
        recordset
            The created or updated ``plasticos.document`` record.
        """
        PlasticosDoc = self.env["plasticos.document"]

        # Skip if no attachment (empty/url-only documents)
        if not native_doc.attachment_id:
            return PlasticosDoc

        # Already linked? Do not retarget that pointer or erase other evidence rows.
        if native_doc.plasticos_doc_id:
            legacy = self._update_legacy(native_doc)
        else:
            legacy = self._create_pending_shell(native_doc)
        if legacy and legacy.association_state != "accepted":
            self._schedule_review_once(native_doc)
        return legacy

    @api.model
    def _create_pending_shell(self, native_doc):
        """Unassigned classification. Native navigation is not copied as evidence."""
        PlasticosDoc = self.env["plasticos.document"]
        PlasticosTag = self.env["plasticos.document.tag"]
        tag_code = self.DOC_TYPE_TAG_MAP.get(native_doc.doc_type, "OTHER")
        tag = PlasticosTag.search([("code", "=", tag_code)], limit=1)
        if not tag:
            tag = PlasticosTag.search([("code", "=", "OTHER")], limit=1)
        if not tag:
            _logger.warning(
                "No plasticos.document.tag found for code '%s'; skipping sync for document %s",
                tag_code,
                native_doc.id,
            )
            return PlasticosDoc
        existing = PlasticosDoc.search(
            [
                ("attachment_id", "=", native_doc.attachment_id.id),
                ("res_model", "=", "documents.document"),
                ("res_id", "=", native_doc.id),
                ("association_state", "=", "pending"),
            ],
            limit=1,
        )
        if existing:
            native_doc.write({"plasticos_doc_id": existing.id})
            return existing
        legacy_doc = PlasticosDoc.create(
            {
                "name": native_doc.name or "Untitled",
                "res_model": "documents.document",
                "res_id": native_doc.id,
                "attachment_id": native_doc.attachment_id.id,
                "tag_id": tag.id,
                "association_state": "pending",
                "candidate_partner_id": native_doc.partner_id.id,
                "pending_reason": self._navigation_reason(native_doc),
            }
        )
        native_doc.write({"plasticos_doc_id": legacy_doc.id})
        _logger.info(
            "Held native document %s as unverified pending plasticos.document %s",
            native_doc.id,
            legacy_doc.id,
        )
        return legacy_doc

    @api.model
    def _navigation_reason(self, native_doc):
        if native_doc.transaction_id and native_doc.load_id:
            return "Native transaction and load were not accepted; they disagree as evidence."
        if native_doc.transaction_id or native_doc.load_id or native_doc.intake_id or native_doc.partner_id:
            return "Native navigation was not accepted as evidence."
        return "Original is unassigned."

    @api.model
    def _schedule_review_once(self, native_doc):
        """At most one internal activity. No recipient is invented when the file has no owner."""
        if not native_doc.owner_id:
            return
        summary = "Document association needs review"
        activity = self.env["mail.activity"]
        if activity.search_count(
            [
                ("res_model", "=", "documents.document"),
                ("res_id", "=", native_doc.id),
                ("summary", "=", summary),
            ]
        ):
            return
        activity.with_context(mail_activity_quick_update=True).create(
            {
                "res_model_id": self.env["ir.model"]._get_id("documents.document"),
                "res_id": native_doc.id,
                "activity_type_id": self.env.ref("mail.mail_activity_data_todo").id,
                "summary": summary,
                "note": native_doc.plasticos_doc_id.pending_reason or self._navigation_reason(native_doc),
                "user_id": native_doc.owner_id.id,
                "date_deadline": fields.Date.context_today(native_doc),
            }
        )

    @api.model
    def _update_legacy(self, native_doc):
        """Return the linked business document without writing verification.

        Repeated sync is idempotent. A native flag, tag change, or auto-sort
        cannot accept evidence or revive a stale approval.
        """
        legacy = native_doc.plasticos_doc_id
        if not legacy:
            return self.env["plasticos.document"]
        return legacy

    @api.model
    def _resolve_business_link(self, native_doc):
        """Native attributes are not an accepted association.

        Transaction, load, intake, and partner stay navigation. The pending
        shell points at the native original itself.
        """
        return "documents.document", native_doc.id

    @api.model
    def batch_sync_unlinked(self):
        """Cron-callable method: find all native documents with plastics
        fields populated but no legacy link, and sync them.

        This catches documents that were classified by AI auto-sort but
        not yet synced (e.g., if the create hook was bypassed).
        """
        NativeDoc = self.env["documents.document"]
        domain = [
            ("plasticos_doc_id", "=", False),
            ("doc_type", "!=", False),
            ("attachment_id", "!=", False),
        ]
        last_id = 0
        seen = 0
        synced = 0
        while True:
            batch = NativeDoc.search(
                [*domain, ("id", ">", last_id)],
                order="id ASC",
                limit=200,
            )
            if not batch:
                break
            last_id = batch[-1].id
            seen += len(batch)
            for doc in batch:
                # A savepoint per document: a failure rolls back only that
                # document's partial work (e.g. a legacy row created before
                # the link is written), so it stays unlinked for a later run
                # without a duplicate, and later documents still sync.
                try:
                    with self.env.cr.savepoint():
                        legacy = self.sync_native_to_legacy(doc)
                except Exception:
                    _logger.exception(
                        "Failed to sync native document %s to legacy",
                        doc.id,
                    )
                    continue
                # An empty result (no matching tag) links nothing.
                if legacy:
                    synced += 1
        _logger.info(
            "Batch sync complete: %d of %d documents synced",
            synced,
            seen,
        )
        return synced
