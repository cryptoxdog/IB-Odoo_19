"""Tests for intake normalizer — validation engine and packet assembly.

Target module: plasticos_intake_normalizer
Target model:  plasticos.intake (via _inherit)
Config:        plasticos.normalizer.config
"""

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestIntakeNormalizer(TransactionCase):
    """Test intake normalization: validation, packet assembly, batch cron."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Intake = cls.env["plasticos.intake"]
        cls.NormConfig = cls.env["plasticos.normalizer.config"]

        # Ensure normalizer config singleton
        cls.norm_config = cls.NormConfig.get_config()

        # Master data
        cls.Polymer = cls.env["plasticos.polymer"]
        cls.Form = cls.env["plasticos.material.form"]
        cls.Color = cls.env["plasticos.material.color"]

        cls.polymer_pp = cls.Polymer.search([("code", "=", "PP")], limit=1)
        if not cls.polymer_pp:
            cls.polymer_pp = cls.Polymer.create({"name": "PP", "code": "PP"})

        cls.form_regrind = cls.Form.search([("code", "=", "REGRIND")], limit=1)
        if not cls.form_regrind:
            cls.form_regrind = cls.Form.create({"name": "Regrind", "code": "REGRIND"})

        cls.color_natural = cls.Color.search([("code", "=", "NATURAL")], limit=1)
        if not cls.color_natural:
            cls.color_natural = cls.Color.create({"name": "Natural", "code": "NATURAL"})

        cls.partner = cls.env["res.partner"].create({"name": "Normalizer Test Supplier"})

    def _create_valid_intake(self, **overrides):
        """Create a fully valid intake ready for normalization."""
        vals = {
            "name": "INT-NORM-TEST",
            "partner_id": self.partner.id,
            "polymer_id": self.polymer_pp.id,
            "form_id": self.form_regrind.id,
            "color_id": self.color_natural.id,
            "quantity_per_load_lbs": 40000.0,
            "loads_per_month": 4,
        }
        vals.update(overrides)
        return self.Intake.create(vals)

    # ── Validation: required fields ──────────────────────────

    def test_normalize_missing_polymer_fails(self):
        """Normalization fails when polymer_id is missing."""
        intake = self._create_valid_intake(polymer_id=False)
        with self.assertRaises(UserError):
            intake.action_normalize()
        self.assertEqual(intake.match_status, "error")

    def test_normalize_missing_form_fails(self):
        """Normalization fails when form_id is missing."""
        intake = self._create_valid_intake(form_id=False)
        with self.assertRaises(UserError):
            intake.action_normalize()
        self.assertEqual(intake.match_status, "error")

    def test_normalize_zero_quantity_fails(self):
        """Normalization fails when quantity_per_load_lbs is 0."""
        intake = self._create_valid_intake(quantity_per_load_lbs=0)
        with self.assertRaises(UserError):
            intake.action_normalize()

    def test_normalize_missing_partner_fails(self):
        """Normalization fails when partner_id is missing and required."""
        self.norm_config.require_partner = True
        intake = self._create_valid_intake(partner_id=False)
        with self.assertRaises(UserError):
            intake.action_normalize()

    # ── Successful normalization ─────────────────────────────

    def test_normalize_success(self):
        """Fully valid intake normalizes successfully."""
        intake = self._create_valid_intake()
        intake.action_normalize()
        self.assertTrue(intake.normalized)
        self.assertEqual(intake.match_status, "normalized")
        self.assertTrue(intake.last_packet_id)
        self.assertTrue(intake.last_packet_id.startswith("PKT-"))
        self.assertEqual(intake.last_packet_version, "1.0.0")

    def test_normalize_sets_packet_payload(self):
        """Successful normalization writes a JSON packet payload."""
        intake = self._create_valid_intake()
        intake.action_normalize()
        self.assertIsNotNone(intake.last_packet_payload)
        payload = intake.last_packet_payload
        self.assertIn("schema_version", payload)
        self.assertIn("quality", payload)
        self.assertIn("frequency", payload)

    def test_normalize_clears_previous_errors(self):
        """Successful normalization clears any previous errors."""
        intake = self._create_valid_intake(polymer_id=False)
        try:
            intake.action_normalize()
        except UserError:
            pass
        self.assertTrue(intake.normalization_errors)
        # Fix and re-normalize
        intake.polymer_id = self.polymer_pp.id
        intake.action_normalize()
        self.assertFalse(intake.normalization_errors)
        self.assertTrue(intake.normalized)

    # ── Warnings (non-blocking) ──────────────────────────────

    def test_normalize_warns_missing_color(self):
        """Missing color generates a warning but normalization succeeds."""
        intake = self._create_valid_intake(color_id=False)
        intake.action_normalize()
        self.assertTrue(intake.normalized)
        warnings = intake.normalization_warnings or []
        warning_fields = [w["field"] for w in warnings]
        self.assertIn("color_id", warning_fields)

    def test_normalize_warns_missing_geo(self):
        """Missing coordinates generates a geo warning."""
        intake = self._create_valid_intake()
        intake.action_normalize()
        self.assertTrue(intake.normalized)
        warnings = intake.normalization_warnings or []
        warning_fields = [w["field"] for w in warnings]
        self.assertIn("geo", warning_fields)

    # ── Batch cron ───────────────────────────────────────────

    def test_batch_cron_normalizes_pending(self):
        """Batch cron normalizes pending intakes."""
        intake = self._create_valid_intake()
        self.assertEqual(intake.match_status, "pending")
        self.Intake.cron_batch_normalize()
        intake.invalidate_recordset()
        self.assertTrue(intake.normalized)
        self.assertEqual(intake.match_status, "normalized")

    def test_batch_cron_skips_already_normalized(self):
        """Batch cron skips intakes already normalized."""
        intake = self._create_valid_intake()
        intake.action_normalize()
        packet_id_before = intake.last_packet_id
        self.Intake.cron_batch_normalize()
        intake.invalidate_recordset()
        self.assertEqual(intake.last_packet_id, packet_id_before)

    def test_batch_cron_handles_errors_per_record(self):
        """Batch cron marks errored records without crashing the batch."""
        good_intake = self._create_valid_intake(name="INT-GOOD")
        bad_intake = self._create_valid_intake(name="INT-BAD", polymer_id=False)
        self.Intake.cron_batch_normalize()
        good_intake.invalidate_recordset()
        bad_intake.invalidate_recordset()
        self.assertTrue(good_intake.normalized)
        self.assertFalse(bad_intake.normalized)
        self.assertEqual(bad_intake.match_status, "error")
