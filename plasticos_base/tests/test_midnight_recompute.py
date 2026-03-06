from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPlasticosMidnightRecompute(TransactionCase):
    """Test suite for plasticos.midnight.recompute (AbstractModel service)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.MidnightService = cls.env["plasticos.midnight.recompute"]

    # ========================================================================
    # SERVICE TESTS (AbstractModel — no record creation)
    # ========================================================================

    def test_cron_runs_without_error(self):
        """Cron method executes without raising."""
        self.MidnightService._cron_midnight_recompute()

    def test_advisory_lock_skip(self):
        """Cron skips when advisory lock is held."""
        with patch.object(self.env.cr, "execute"), patch.object(self.env.cr, "fetchone", return_value=(False,)):
            self.MidnightService._cron_midnight_recompute()

    def test_document_recompute_called_if_model_exists(self):
        """_recompute_document_expiry is called if plasticos.document exists."""
        with (
            patch.object(self.MidnightService, "_recompute_document_expiry") as mock_doc,
            patch.object(self.MidnightService, "_recompute_claim_time_fields") as mock_claim,
        ):
            self.MidnightService._cron_midnight_recompute()
            mock_doc.assert_called_once()
            mock_claim.assert_called_once()

    def test_missing_document_model_skipped(self):
        """_recompute_document_expiry handles missing model gracefully."""
        with patch.object(self.env, "get", return_value=None):
            self.MidnightService._recompute_document_expiry()

    def test_missing_claim_model_skipped(self):
        """_recompute_claim_time_fields handles missing model gracefully."""
        with patch.object(self.env, "get", return_value=None):
            self.MidnightService._recompute_claim_time_fields()
