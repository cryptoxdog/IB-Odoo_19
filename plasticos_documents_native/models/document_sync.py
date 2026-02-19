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

from odoo import api, models

_logger = logging.getLogger(__name__)


class DocumentSyncService(models.AbstractModel):
    """Service that synchronises native Enterprise documents with the legacy
    ``plasticos.document`` model used by the compliance engine."""

    _name = "plasticos.document.sync"
    _description = "Native ↔ Legacy Document Sync Service"

    # ── Tag Mapping ──────────────────────────────────────────
    # Maps x_doc_type selection values to plasticos.document.tag codes.
    DOC_TYPE_TAG_MAP = {
        "bol": "BOL",
        "invoice": "INV",
        "scale_ticket": "SCALE",
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
        PlasticosTag = self.env["plasticos.document.tag"]

        # Skip if no attachment (empty/url-only documents)
        if not native_doc.attachment_id:
            return PlasticosDoc

        # Already linked?
        if native_doc.x_plasticos_doc_id:
            return self._update_legacy(native_doc)

        # Resolve the tag
        tag_code = self.DOC_TYPE_TAG_MAP.get(native_doc.x_doc_type, "OTHER")
        tag = PlasticosTag.search([("code", "=", tag_code)], limit=1)
        if not tag:
            tag = PlasticosTag.search([("code", "=", "OTHER")], limit=1)
        if not tag:
            _logger.warning(
                "No plasticos.document.tag found for code '%s'; "
                "skipping sync for document %s",
                tag_code,
                native_doc.id,
            )
            return PlasticosDoc

        # Determine res_model / res_id for the legacy record
        res_model, res_id = self._resolve_business_link(native_doc)

        vals = {
            "name": native_doc.name or "Untitled",
            "res_model": res_model,
            "res_id": res_id,
            "attachment_id": native_doc.attachment_id.id,
            "tag_id": tag.id,
            "verified": native_doc.x_verified,
            "verified_by": native_doc.x_verified_by.id if native_doc.x_verified_by else False,
            "verified_at": native_doc.x_verified_at,
            "override": native_doc.x_override,
            "override_reason": native_doc.x_override_reason,
        }

        legacy_doc = PlasticosDoc.create(vals)
        native_doc.write({"x_plasticos_doc_id": legacy_doc.id})

        _logger.info(
            "Synced native document %s → legacy plasticos.document %s",
            native_doc.id,
            legacy_doc.id,
        )
        return legacy_doc

    @api.model
    def _update_legacy(self, native_doc):
        """Push verification/override state changes to the linked legacy
        record."""
        legacy = native_doc.x_plasticos_doc_id
        if not legacy:
            return self.env["plasticos.document"]

        legacy.write({
            "verified": native_doc.x_verified,
            "verified_by": native_doc.x_verified_by.id if native_doc.x_verified_by else False,
            "verified_at": native_doc.x_verified_at,
            "override": native_doc.x_override,
            "override_reason": native_doc.x_override_reason,
        })
        return legacy

    @api.model
    def _resolve_business_link(self, native_doc):
        """Determine the best ``res_model`` / ``res_id`` pair for the legacy
        record based on the plastics domain links.

        Priority: transaction > load > intake > partner.
        """
        if native_doc.x_transaction_id:
            return "plasticos.transaction", native_doc.x_transaction_id.id
        if native_doc.x_load_id:
            return "plasticos.load", native_doc.x_load_id.id
        if native_doc.x_intake_id:
            return "plasticos.intake", native_doc.x_intake_id.id
        if native_doc.partner_id:
            return "res.partner", native_doc.partner_id.id
        return "documents.document", native_doc.id

    @api.model
    def batch_sync_unlinked(self):
        """Cron-callable method: find all native documents with plastics
        fields populated but no legacy link, and sync them.

        This catches documents that were classified by AI auto-sort but
        not yet synced (e.g., if the create hook was bypassed).
        """
        NativeDoc = self.env["documents.document"]
        unlinked = NativeDoc.search([
            ("x_plasticos_doc_id", "=", False),
            ("x_doc_type", "!=", False),
            ("attachment_id", "!=", False),
        ])
        count = 0
        for doc in unlinked:
            try:
                self.sync_native_to_legacy(doc)
                count += 1
            except Exception:
                _logger.exception(
                    "Failed to sync native document %s to legacy",
                    doc.id,
                )
        _logger.info(
            "Batch sync complete: %d of %d documents synced",
            count,
            len(unlinked),
        )
        return count
