"""Preserve native verification columns that disagree with plasticos.document.

Runs before the ORM stops reading the stored native decision columns. It copies
them into a snapshot and marks review. It does not update plasticos.document
and it does not turn a disagreement into an approval. A second run changes nothing.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("SELECT to_regclass('public.documents_document'), to_regclass('public.plasticos_document')")
    native_table, legacy_table = cr.fetchone()
    if not native_table or not legacy_table:
        return
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = 'documents_document'
           AND column_name = 'verified'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        ALTER TABLE documents_document
            ADD COLUMN IF NOT EXISTS verification_conflict_snapshot text,
            ADD COLUMN IF NOT EXISTS verification_review_required boolean DEFAULT false,
            ADD COLUMN IF NOT EXISTS verification_snapshot_captured boolean DEFAULT false
        """
    )
    cr.execute(
        """
        UPDATE documents_document AS native
           SET verification_conflict_snapshot = src.snapshot,
               verification_review_required = src.review,
               verification_snapshot_captured = true
          FROM (
                SELECT doc.id,
                       json_build_object(
                           'verified', doc.verified,
                           'verified_by', doc.verified_by,
                           'verified_at', doc.verified_at,
                           'override', doc.override,
                           'override_reason', doc.override_reason
                       )::text AS snapshot,
                       CASE
                           WHEN doc.plasticos_doc_id IS NULL AND (doc.verified OR doc.override) THEN true
                           WHEN legacy.id IS NULL AND (doc.verified OR doc.override) THEN true
                           WHEN doc.verified IS DISTINCT FROM legacy.verified
                             OR doc.override IS DISTINCT FROM legacy.override
                             OR doc.verified_by IS DISTINCT FROM legacy.verified_by
                             OR doc.verified_at IS DISTINCT FROM legacy.verified_at
                             OR doc.override_reason IS DISTINCT FROM legacy.override_reason
                           THEN true
                           ELSE false
                       END AS review
                  FROM documents_document AS doc
                  LEFT JOIN plasticos_document AS legacy
                    ON legacy.id = doc.plasticos_doc_id
                 WHERE COALESCE(doc.verification_snapshot_captured, false) = false
               ) AS src
         WHERE native.id = src.id
        """
    )
    _logger.info("Captured %s native verification snapshots without writing business decisions.", cr.rowcount)
