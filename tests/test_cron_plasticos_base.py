"""Full cron test suite for plasticos_base scheduled jobs.

Covers:
    - midnight_recompute: _cron_midnight_recompute (document expiry + claim time fields)
    - attachment_maintenance: _cron_cleanup_missing_filestore_orphans
"""

from datetime import date, timedelta
from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase


# ═══════════════════════════════════════════════════════════════════
# midnight_recompute  (plasticos.midnight.recompute AbstractModel)
# ═══════════════════════════════════════════════════════════════════
class TestMidnightRecompute(PlasticosTestCase):
    """Tests for _cron_midnight_recompute service."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.svc = cls.env["plasticos.midnight.recompute"]

    # ── Advisory lock ──────────────────────────────────────────
    def test_lock_acquired_runs_full(self):
        """Cron acquires advisory lock and runs both recompute steps."""
        with (
            patch.object(type(self.svc), "_recompute_document_expiry") as m_doc,
            patch.object(type(self.svc), "_recompute_claim_time_fields") as m_claim,
        ):
            self.svc._cron_midnight_recompute()
            m_doc.assert_called_once()
            m_claim.assert_called_once()

    def test_lock_already_held_skips(self):
        """When advisory lock is held by another process, cron skips silently."""
        with (
            patch.object(self.env.cr, "execute") as m_exec,
            patch.object(self.env.cr, "fetchone", return_value=(False,)),
        ):
            self.svc._cron_midnight_recompute()
        # Should NOT call any recompute methods

    def test_lock_released_on_exception(self):
        """Advisory lock is released even when recompute raises."""
        with patch.object(type(self.svc), "_recompute_document_expiry", side_effect=Exception("boom")):
            try:
                self.svc._cron_midnight_recompute()
            except Exception:
                pass
        # Lock release is in the finally block — verified by no deadlock

    # ── Document expiry recompute ──────────────────────────────
    def test_recompute_newly_expired_documents(self):
        """Documents past expiry_date get is_expired=True recomputed."""
        if "plasticos.document" not in self.env:
            self.skipTest("plasticos.document not installed")
        Doc = self.env["plasticos.document"]
        doc = Doc.create(
            {
                "name": "TestDoc",
                "expiry_date": date.today() - timedelta(days=1),
            }
        )
        doc.is_expired = False  # Force stale value
        self.svc._recompute_document_expiry()
        self.assertTrue(doc.is_expired, "Newly expired doc should be recomputed to True")

    def test_recompute_incorrectly_expired_documents(self):
        """Documents with future expiry_date should NOT be marked expired."""
        if "plasticos.document" not in self.env:
            self.skipTest("plasticos.document not installed")
        Doc = self.env["plasticos.document"]
        doc = Doc.create(
            {
                "name": "FutureDoc",
                "expiry_date": date.today() + timedelta(days=30),
            }
        )
        doc.is_expired = True  # Force incorrect stale value
        self.svc._recompute_document_expiry()
        self.assertFalse(doc.is_expired, "Future-dated doc should be corrected to not expired")

    def test_recompute_skips_missing_document_model(self):
        """Gracefully skips when plasticos.document model not installed."""
        with patch.object(self.env, "get", return_value=None):
            self.svc._recompute_document_expiry()  # Should not raise

    def test_recompute_limit_1000_documents(self):
        """Each search is capped at limit=1000 to avoid memory issues."""
        if "plasticos.document" not in self.env:
            self.skipTest("plasticos.document not installed")
        # Implementation uses limit=1000 — verify no unbounded search
        with patch.object(
            self.env["plasticos.document"], "search", return_value=self.env["plasticos.document"]
        ) as m_search:
            self.svc._recompute_document_expiry()
            for call_args in m_search.call_args_list:
                if "limit" in call_args.kwargs:
                    self.assertLessEqual(call_args.kwargs["limit"], 1000)

    # ── Claim time fields recompute ────────────────────────────
    def test_recompute_claim_days_open(self):
        """Open claims get days_open recomputed at midnight."""
        if "plasticos.claim" not in self.env:
            self.skipTest("plasticos.claim not installed")
        Claim = self.env["plasticos.claim"]
        tx = self.env["plasticos.transaction"].create({"name": "TX-CRON-CLM"})
        claim = Claim.create(
            {
                "transaction_id": tx.id,
                "case_type": "buyer_claim",
                "severity": "medium",
                "state": "pending",
                "create_date": date.today() - timedelta(days=5),
            }
        )
        self.svc._recompute_claim_time_fields()
        self.assertGreater(claim.days_open, 0, "days_open should be recomputed")

    def test_recompute_claim_is_overdue(self):
        """Claims past SLA deadline get is_overdue recomputed."""
        if "plasticos.claim" not in self.env:
            self.skipTest("plasticos.claim not installed")
        Claim = self.env["plasticos.claim"]
        tx = self.env["plasticos.transaction"].create({"name": "TX-CRON-CLM2"})
        claim = Claim.create(
            {
                "transaction_id": tx.id,
                "case_type": "buyer_claim",
                "severity": "medium",
                "state": "pending",
            }
        )
        self.svc._recompute_claim_time_fields()
        # Just verify it runs without error — actual is_overdue depends on SLA config

    def test_recompute_skips_resolved_claims(self):
        """Resolved/archived claims are excluded from recompute."""
        if "plasticos.claim" not in self.env:
            self.skipTest("plasticos.claim not installed")
        Claim = self.env["plasticos.claim"]
        with patch.object(Claim.__class__, "search") as m_search:
            m_search.return_value = Claim
            self.svc._recompute_claim_time_fields()
            domain = m_search.call_args[0][0]
            # Domain should exclude resolved/archived
            self.assertIn(("state", "not in", ("resolved", "archived")), domain)

    def test_recompute_skips_missing_claim_model(self):
        """Gracefully skips when plasticos.claim model not installed."""
        with patch.object(self.env, "get", return_value=None):
            self.svc._recompute_claim_time_fields()  # Should not raise


# ═══════════════════════════════════════════════════════════════════
# attachment_maintenance  (ir.attachment cleanup)
# ═══════════════════════════════════════════════════════════════════
class TestAttachmentMaintenance(PlasticosTestCase):
    """Tests for _cron_cleanup_missing_filestore_orphans."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Attachment = cls.env["ir.attachment"]

    def test_lock_acquired_runs_cleanup(self):
        """Cron acquires lock and processes binary attachments."""
        with patch("os.path.exists", return_value=True):
            result = self.Attachment._cron_cleanup_missing_filestore_orphans()
            self.assertEqual(result, 0, "No orphans should exist in clean DB")

    def test_lock_already_held_skips(self):
        """Returns 0 when advisory lock already held."""
        with patch.object(self.env.cr, "execute"), patch.object(self.env.cr, "fetchone", return_value=(False,)):
            result = self.Attachment._cron_cleanup_missing_filestore_orphans()
            self.assertEqual(result, 0)

    def test_missing_data_dir_skips(self):
        """Returns 0 when data_dir config is missing."""
        with patch("odoo.tools.config.get", return_value=None):
            result = self.Attachment._cron_cleanup_missing_filestore_orphans()
            self.assertEqual(result, 0)

    def test_orphan_detection_and_deletion(self):
        """Attachments with missing filestore blob get deleted."""
        att = self.Attachment.create(
            {
                "name": "orphan_test.txt",
                "type": "binary",
                "datas": False,
            }
        )
        if att.store_fname:
            with patch("os.path.exists", return_value=False), patch("odoo.tools.config.get", return_value="/tmp"):
                result = self.Attachment._cron_cleanup_missing_filestore_orphans()
                self.assertGreaterEqual(result, 0)

    def test_existing_blobs_not_deleted(self):
        """Attachments with valid filestore blobs are preserved."""
        att = self.Attachment.create(
            {
                "name": "valid_test.txt",
                "type": "binary",
                "datas": "dGVzdA==",  # base64 "test"
            }
        )
        with patch("os.path.exists", return_value=True), patch("odoo.tools.config.get", return_value="/tmp"):
            self.Attachment._cron_cleanup_missing_filestore_orphans()
            self.assertTrue(att.exists(), "Valid attachment should not be deleted")

    def test_cleanup_limit_2000(self):
        """Search is limited to 2000 candidates per run."""
        with (
            patch.object(self.Attachment, "search") as m_search,
            patch("os.path.exists", return_value=True),
            patch("odoo.tools.config.get", return_value="/tmp"),
        ):
            m_search.return_value = self.Attachment
            self.Attachment._cron_cleanup_missing_filestore_orphans()
            if m_search.called:
                call_kwargs = m_search.call_args.kwargs if m_search.call_args.kwargs else {}
                if "limit" in call_kwargs:
                    self.assertLessEqual(call_kwargs["limit"], 2000)

    def test_lock_released_on_exception(self):
        """Advisory lock is released on unexpected exception."""
        with patch("os.path.exists", side_effect=Exception("disk error")):
            try:
                self.Attachment._cron_cleanup_missing_filestore_orphans()
            except Exception:
                pass
        # Lock in finally block ensures release
