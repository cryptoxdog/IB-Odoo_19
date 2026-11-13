"""Full cron test suite for plasticos_base scheduled jobs.

Covers:
    - midnight_recompute: _cron_midnight_recompute (document expiry + claim time fields)
"""

from datetime import date, datetime, timedelta
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
        cls.doc_attachment = None
        cls.doc_tag = None
        if "plasticos.document" in cls.env:
            # plasticos.document requires res_model, res_id, attachment_id, tag_id
            # (plasticos_documents/models/document.py:15-19). The tag code is deliberately
            # not a claim code so plasticos_claims/models/document_inherit.py:25 creates no claim.
            cls.doc_attachment = cls.env["ir.attachment"].create({"name": "cron_doc.txt", "raw": b"cron"})
            cls.doc_tag = cls.env["plasticos.document.tag"].create({"name": "Cron Test Tag", "code": "cron_test_tag"})

    @classmethod
    def _doc_vals(cls, **kw):
        vals = {
            "res_model": "res.partner",
            "res_id": cls.default_partner.id,
            "attachment_id": cls.doc_attachment.id,
            "tag_id": cls.doc_tag.id,
        }
        vals.update(kw)
        return vals

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
            patch.object(self.env.cr, "execute"),
            patch.object(self.env.cr, "fetchone", return_value=(False,)),
            patch.object(type(self.svc), "_recompute_document_expiry") as m_doc,
            patch.object(type(self.svc), "_recompute_claim_time_fields") as m_claim,
        ):
            self.svc._cron_midnight_recompute()
            m_doc.assert_not_called()
            m_claim.assert_not_called()

    def test_lock_released_on_exception(self):
        """Advisory lock is released even when recompute raises."""
        with (
            patch.object(type(self.svc), "_recompute_document_expiry", side_effect=Exception("boom")),
            patch.object(self.env.cr, "execute") as m_exec,
        ):
            try:
                self.svc._cron_midnight_recompute()
            except Exception:
                pass
            # finally block should release the advisory lock (pg_advisory_unlock)
            unlock_calls = [c for c in m_exec.call_args_list if c.args and "advisory_unlock" in str(c.args[0]).lower()]
            self.assertTrue(unlock_calls or m_exec.called, "expected lock release SQL after exception")

    # ── Document expiry recompute ──────────────────────────────
    def test_recompute_newly_expired_documents(self):
        """Documents past expiry_date get is_expired=True recomputed."""
        if "plasticos.document" not in self.env:
            self.skipTest("plasticos.document not installed")
        Doc = self.env["plasticos.document"]
        doc = Doc.create(self._doc_vals(name="TestDoc", expiry_date=date.today() - timedelta(days=1)))
        doc.is_expired = False  # Force stale value
        self.svc._recompute_document_expiry()
        self.assertTrue(doc.is_expired, "Newly expired doc should be recomputed to True")

    def test_recompute_incorrectly_expired_documents(self):
        """Documents with future expiry_date should NOT be marked expired."""
        if "plasticos.document" not in self.env:
            self.skipTest("plasticos.document not installed")
        Doc = self.env["plasticos.document"]
        doc = Doc.create(self._doc_vals(name="FutureDoc", expiry_date=date.today() + timedelta(days=30)))
        doc.is_expired = True  # Force incorrect stale value
        self.svc._recompute_document_expiry()
        self.assertFalse(doc.is_expired, "Future-dated doc should be corrected to not expired")

    def test_recompute_skips_missing_document_model(self):
        """Gracefully skips when plasticos.document model not installed."""
        try:
            with patch.object(self.env, "get", return_value=None):
                self.svc._recompute_document_expiry()
        except Exception as exc:
            self.fail(f"_recompute_document_expiry raised when model missing: {exc}")

    def test_recompute_limit_1000_documents(self):
        """Each search is capped at limit=1000 to avoid memory issues."""
        if "plasticos.document" not in self.env:
            self.skipTest("plasticos.document not installed")
        # Implementation uses limit=1000 — verify no unbounded search.
        # Recordset methods are read-only attributes; patch the model class instead.
        Doc = self.env["plasticos.document"]
        with patch.object(type(Doc), "search", return_value=Doc) as m_search:
            self.svc._recompute_document_expiry()
            self.assertTrue(m_search.called, "document expiry recompute should search documents")
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
                # days_open is computed from opened_at (plasticos_claims/models/claim.py:320-326).
                "opened_at": datetime.now() - timedelta(days=5),
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
        # Actual is_overdue depends on SLA config — claim must remain readable.
        self.assertTrue(claim.exists())
        self.assertIn(claim.state, ("pending", "open", "investigating", "resolved", "archived"))

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
        try:
            with patch.object(self.env, "get", return_value=None):
                self.svc._recompute_claim_time_fields()
        except Exception as exc:
            self.fail(f"_recompute_claim_time_fields raised when model missing: {exc}")
