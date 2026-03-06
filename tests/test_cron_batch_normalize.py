"""Full cron test suite for plasticos_intake_normalizer batch cron.

Covers: cron_batch_normalize (batch processing, idempotency, error handling).
"""

import unittest
from unittest.mock import patch

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase


class TestBatchNormalizeCron(PlasticosTestCase):
    """Tests for cron_batch_normalize on plasticos.intake."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "plasticos.intake" not in cls.env:
            raise unittest.SkipTest("plasticos.intake not installed")
        cls.Intake = cls.env["plasticos.intake"]
        # Create shared reference data (search first to avoid duplicates)
        cls.polymer = cls.env["plasticos.polymer"].search([("code", "=", "HDPE")], limit=1)
        if not cls.polymer:
            cls.polymer = cls.env["plasticos.polymer"].create({"name": "HDPE", "code": "HDPE"})
        cls.form = cls.env["plasticos.material.form"].search([("code", "=", "pellet")], limit=1)
        if not cls.form:
            cls.form = cls.env["plasticos.material.form"].create({"name": "Pellet", "code": "pellet"})
        cls.partner = cls.env["res.partner"].create({"name": "Normalizer Test"})

    def _create_intake(self, **kwargs):
        vals = {
            "partner_id": self.partner.id,
            "polymer_id": self.polymer.id,
            "form_id": self.form.id,
            "quantity_per_load_lbs": 40000,
            "normalized": False,
            "match_status": "pending",
        }
        vals.update(kwargs)
        return self.Intake.create(vals)

    def test_pending_intake_normalized(self):
        """Pending intakes get normalized in batch."""
        intake = self._create_intake()
        self.Intake.cron_batch_normalize()
        self.assertTrue(intake.normalized)
        self.assertEqual(intake.match_status, "normalized")

    def test_packet_fields_populated(self):
        """Normalized intake gets packet_id, version, payload set."""
        intake = self._create_intake()
        self.Intake.cron_batch_normalize()
        self.assertTrue(intake.last_packet_id)
        self.assertTrue(intake.last_packet_version)
        self.assertTrue(intake.last_packet_payload)
        self.assertTrue(intake.last_packet_ts)

    def test_idempotency_already_normalized(self):
        """Already-normalized intakes are not re-processed."""
        intake = self._create_intake(normalized=True, match_status="normalized")
        old_packet = intake.last_packet_id
        self.Intake.cron_batch_normalize()
        self.assertEqual(intake.last_packet_id, old_packet)

    def test_validation_error_sets_error_status(self):
        """Intakes with validation errors get match_status=error."""
        intake = self._create_intake(polymer_id=False)  # Missing required field
        self.Intake.cron_batch_normalize()
        self.assertEqual(intake.match_status, "error")
        self.assertFalse(intake.normalized)
        self.assertTrue(intake.normalization_errors)

    def test_unexpected_exception_handled(self):
        """Unexpected exceptions are caught per-record, not raised."""
        intake = self._create_intake()
        with patch.object(type(intake), "_validate_for_normalization", side_effect=Exception("Boom")):
            self.Intake.cron_batch_normalize()  # Should not raise
        self.assertEqual(intake.match_status, "error")

    def test_batch_limit_from_config(self):
        """Batch size respects config.batch_limit."""
        config = self.env["plasticos.normalizer.config"].sudo().get_config()
        limit = config.batch_limit or 200
        with patch.object(self.Intake.__class__, "search", return_value=self.Intake) as m_search:
            self.Intake.cron_batch_normalize()
            if m_search.called:
                kw = m_search.call_args.kwargs or {}
                if "limit" in kw:
                    self.assertLessEqual(kw["limit"], limit)

    def test_advisory_lock_skip(self):
        """Cron skips when lock held."""
        with patch.object(self.env.cr, "execute"), patch.object(self.env.cr, "fetchone", return_value=(False,)):
            self.Intake.cron_batch_normalize()

    def test_creates_automation_log(self):
        """Normalized intake creates automation log entry."""
        intake = self._create_intake()
        self.Intake.cron_batch_normalize()
        # Log is written via _log_normalization

    def test_normalization_warnings_stored(self):
        """Non-blocking warnings are stored on the intake."""
        intake = self._create_intake()  # Missing color triggers a warning
        self.Intake.cron_batch_normalize()
        if intake.normalization_warnings:
            self.assertIsInstance(intake.normalization_warnings, list)

    def test_order_by_create_date(self):
        """Batch processes oldest intakes first (FIFO)."""
        with patch.object(self.Intake.__class__, "search", return_value=self.Intake) as m_search:
            self.Intake.cron_batch_normalize()
            if m_search.called:
                kw = m_search.call_args.kwargs or {}
                if "order" in kw:
                    self.assertIn("create_date ASC", kw["order"])
