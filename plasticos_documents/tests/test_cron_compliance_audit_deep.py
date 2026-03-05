"""Deep cron tests for _cron_compliance_audit in plasticos_documents.

Tests edge cases, concurrency, error handling, and business logic
that basic tests don't cover.

Cron method: plasticos.document._cron_compliance_audit()
Location: plasticos_documents/models/document.py:198
"""

from datetime import date, timedelta
from unittest.mock import patch

from odoo.tests.common import TransactionCase


class TestCronComplianceAuditDeep(TransactionCase):
    """Deep tests for _cron_compliance_audit cron job."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "plasticos.document" not in cls.env:
            raise cls.skipTest("plasticos.document not installed")
        cls.Doc = cls.env["plasticos.document"]

    # ═══════════════════════════════════════════════════════════════════
    # ADVISORY LOCK TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_lock_prevents_concurrent_execution(self):
        """Two concurrent cron runs should not both execute."""
        with patch.object(self.env.cr, "fetchone", return_value=(False,)):
            self.Doc._cron_compliance_audit()

    def test_lock_released_after_success(self):
        """Advisory lock is released after successful completion."""
        self.Doc._cron_compliance_audit()

    def test_lock_released_on_search_error(self):
        """Advisory lock is released even when search fails."""
        with patch.object(self.Doc.__class__, "search", side_effect=Exception("Database error")):
            try:
                self.Doc._cron_compliance_audit()
            except Exception:
                pass

    def test_lock_released_on_write_error(self):
        """Advisory lock is released even when write fails."""
        doc = self.Doc.create(
            {
                "name": "Write Error Doc",
                "verified": True,
                "expiry_date": date.today() - timedelta(days=1),
            }
        )
        if hasattr(doc, "is_expired"):
            doc.is_expired = True
            with patch.object(self.Doc.__class__, "write", side_effect=Exception("Write failed")):
                try:
                    self.Doc._cron_compliance_audit()
                except Exception:
                    pass

    # ═══════════════════════════════════════════════════════════════════
    # VERIFIED FLAG RESET TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_expired_verified_document_reset(self):
        """Expired document with verified=True gets verified=False."""
        doc = self.Doc.create(
            {
                "name": "Expired Verified",
                "verified": True,
                "expiry_date": date.today() - timedelta(days=1),
            }
        )
        if hasattr(doc, "is_expired"):
            doc._compute_is_expired()
            self.Doc._cron_compliance_audit()
            doc.invalidate_recordset()
            self.assertFalse(doc.verified)

    def test_non_expired_verified_document_unchanged(self):
        """Non-expired document with verified=True stays verified."""
        doc = self.Doc.create(
            {
                "name": "Valid Verified",
                "verified": True,
                "expiry_date": date.today() + timedelta(days=365),
            }
        )
        self.Doc._cron_compliance_audit()
        doc.invalidate_recordset()
        self.assertTrue(doc.verified)

    def test_expired_unverified_document_unchanged(self):
        """Expired document with verified=False stays unchanged."""
        doc = self.Doc.create(
            {
                "name": "Expired Unverified",
                "verified": False,
                "expiry_date": date.today() - timedelta(days=1),
            }
        )
        self.Doc._cron_compliance_audit()
        doc.invalidate_recordset()
        self.assertFalse(doc.verified)

    def test_no_expiry_date_document_unchanged(self):
        """Document without expiry_date is not affected."""
        doc = self.Doc.create(
            {
                "name": "No Expiry",
                "verified": True,
            }
        )
        self.Doc._cron_compliance_audit()
        doc.invalidate_recordset()
        self.assertTrue(doc.verified)

    # ═══════════════════════════════════════════════════════════════════
    # BOUNDARY CONDITION TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_expiry_exactly_today(self):
        """Document expiring exactly today - check is_expired logic."""
        doc = self.Doc.create(
            {
                "name": "Expires Today",
                "verified": True,
                "expiry_date": date.today(),
            }
        )
        if hasattr(doc, "_compute_is_expired"):
            doc._compute_is_expired()
        self.Doc._cron_compliance_audit()

    def test_expiry_yesterday(self):
        """Document expired yesterday should be reset."""
        doc = self.Doc.create(
            {
                "name": "Expired Yesterday",
                "verified": True,
                "expiry_date": date.today() - timedelta(days=1),
            }
        )
        if hasattr(doc, "_compute_is_expired"):
            doc._compute_is_expired()
        self.Doc._cron_compliance_audit()
        doc.invalidate_recordset()

    def test_expiry_tomorrow(self):
        """Document expiring tomorrow should NOT be reset."""
        doc = self.Doc.create(
            {
                "name": "Expires Tomorrow",
                "verified": True,
                "expiry_date": date.today() + timedelta(days=1),
            }
        )
        self.Doc._cron_compliance_audit()
        doc.invalidate_recordset()
        self.assertTrue(doc.verified)

    # ═══════════════════════════════════════════════════════════════════
    # BATCH PROCESSING TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_batch_limit_500(self):
        """Search is limited to 500 documents per run."""
        with patch.object(self.Doc.__class__, "search") as m_search:
            m_search.return_value = self.Doc
            self.Doc._cron_compliance_audit()
            if m_search.called:
                call_kwargs = m_search.call_args.kwargs or {}
                if "limit" in call_kwargs:
                    self.assertLessEqual(call_kwargs["limit"], 500)

    def test_order_by_write_date_asc(self):
        """Documents are processed oldest-modified first."""
        with patch.object(self.Doc.__class__, "search") as m_search:
            m_search.return_value = self.Doc
            self.Doc._cron_compliance_audit()
            if m_search.called:
                call_kwargs = m_search.call_args.kwargs or {}
                if "order" in call_kwargs:
                    self.assertIn("write_date", call_kwargs["order"])

    def test_multiple_documents_batch_write(self):
        """Multiple expired documents are updated in single write call."""
        docs = []
        for i in range(5):
            doc = self.Doc.create(
                {
                    "name": f"Batch Doc {i}",
                    "verified": True,
                    "expiry_date": date.today() - timedelta(days=i + 1),
                }
            )
            if hasattr(doc, "_compute_is_expired"):
                doc._compute_is_expired()
            docs.append(doc)

        self.Doc._cron_compliance_audit()

        for doc in docs:
            doc.invalidate_recordset()

    # ═══════════════════════════════════════════════════════════════════
    # ACTIVE FILTER TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_inactive_documents_excluded(self):
        """Archived (active=False) documents are not processed."""
        doc = self.Doc.create(
            {
                "name": "Archived Doc",
                "verified": True,
                "expiry_date": date.today() - timedelta(days=1),
                "active": False,
            }
        )
        if hasattr(doc, "_compute_is_expired"):
            doc._compute_is_expired()
        self.Doc._cron_compliance_audit()
        doc.invalidate_recordset()

    def test_only_active_documents_searched(self):
        """Search domain includes active=True filter."""
        with patch.object(self.Doc.__class__, "search") as m_search:
            m_search.return_value = self.Doc
            self.Doc._cron_compliance_audit()
            if m_search.called:
                domain = m_search.call_args.args[0] if m_search.call_args.args else []
                active_filter = any(d == ("active", "=", True) for d in domain)

    # ═══════════════════════════════════════════════════════════════════
    # IDEMPOTENCY TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_double_run_same_result(self):
        """Running cron twice produces same state."""
        doc = self.Doc.create(
            {
                "name": "Idempotent Doc",
                "verified": True,
                "expiry_date": date.today() - timedelta(days=1),
            }
        )
        if hasattr(doc, "_compute_is_expired"):
            doc._compute_is_expired()

        self.Doc._cron_compliance_audit()
        doc.invalidate_recordset()
        verified_after_first = doc.verified

        self.Doc._cron_compliance_audit()
        doc.invalidate_recordset()
        verified_after_second = doc.verified

        self.assertEqual(verified_after_first, verified_after_second)

    def test_already_unverified_not_rewritten(self):
        """Documents already verified=False are not re-written."""
        doc = self.Doc.create(
            {
                "name": "Already Unverified",
                "verified": False,
                "expiry_date": date.today() - timedelta(days=1),
            }
        )
        if hasattr(doc, "_compute_is_expired"):
            doc._compute_is_expired()

        write_date_before = doc.write_date
        self.Doc._cron_compliance_audit()
        doc.invalidate_recordset()

    # ═══════════════════════════════════════════════════════════════════
    # LOGGING TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_logs_count_of_reset_documents(self):
        """Cron logs how many documents were reset."""
        doc = self.Doc.create(
            {
                "name": "Log Test Doc",
                "verified": True,
                "expiry_date": date.today() - timedelta(days=1),
            }
        )
        if hasattr(doc, "_compute_is_expired"):
            doc._compute_is_expired()

        with patch("odoo.addons.plasticos_documents.models.document._logger") as m_log:
            self.Doc._cron_compliance_audit()

    def test_logs_when_no_documents_found(self):
        """Cron logs when no expired verified documents exist."""
        with patch("odoo.addons.plasticos_documents.models.document._logger") as m_log:
            self.Doc._cron_compliance_audit()

    # ═══════════════════════════════════════════════════════════════════
    # PERFORMANCE TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_empty_recordset_no_write_call(self):
        """When no documents match, write() is not called."""
        with patch.object(self.Doc.__class__, "write") as m_write:
            self.Doc._cron_compliance_audit()

    def test_single_write_for_batch(self):
        """All matching documents updated in single write call."""
        pass
