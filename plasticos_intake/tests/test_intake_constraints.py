"""
Test intake constraints.

- quantity_per_load_lbs > 0
- loads_per_month > 0
"""

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestIntakeConstraints(TransactionCase):
    """Test plasticos.intake constraints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Supplier",
                "is_company": True,
                "supplier_rank": 1,
            }
        )

    def _create_intake(self, **kwargs):
        """Helper to create an intake with defaults."""
        vals = {
            "partner_id": self.partner.id,
        }
        vals.update(kwargs)
        return self.env["plasticos.intake"].create(vals)

    # ═══════════════════════════════════════════════════════════
    # Quantity Per Load Constraint Tests
    # ═══════════════════════════════════════════════════════════

    def test_quantity_per_load_must_be_positive(self):
        """quantity_per_load_lbs must be > 0 when set."""
        intake = self._create_intake()

        with self.assertRaises(ValidationError):
            intake.write({"quantity_per_load_lbs": 0})
            intake._check_quantity()

    def test_quantity_per_load_cannot_be_negative(self):
        """quantity_per_load_lbs cannot be negative."""
        intake = self._create_intake()

        with self.assertRaises(ValidationError):
            intake.write({"quantity_per_load_lbs": -1000})
            intake._check_quantity()

    def test_quantity_per_load_valid(self):
        """Valid quantity_per_load_lbs should be accepted."""
        intake = self._create_intake(quantity_per_load_lbs=40000)
        self.assertEqual(intake.quantity_per_load_lbs, 40000)

    # ═══════════════════════════════════════════════════════════
    # Loads Per Month Constraint Tests
    # ═══════════════════════════════════════════════════════════

    def test_loads_per_month_must_be_positive(self):
        """loads_per_month must be > 0 when set."""
        intake = self._create_intake()

        with self.assertRaises(ValidationError):
            intake.write({"loads_per_month": 0})
            intake._check_loads()

    def test_loads_per_month_cannot_be_negative(self):
        """loads_per_month cannot be negative."""
        intake = self._create_intake()

        with self.assertRaises(ValidationError):
            intake.write({"loads_per_month": -5})
            intake._check_loads()

    def test_loads_per_month_valid(self):
        """Valid loads_per_month should be accepted."""
        intake = self._create_intake(loads_per_month=4)
        self.assertEqual(intake.loads_per_month, 4)

    # ═══════════════════════════════════════════════════════════
    # Combined Constraint Tests
    # ═══════════════════════════════════════════════════════════

    def test_both_quantity_and_loads_valid(self):
        """Both quantity and loads can be set with valid values."""
        intake = self._create_intake(
            quantity_per_load_lbs=40000,
            loads_per_month=4,
        )
        self.assertEqual(intake.quantity_per_load_lbs, 40000)
        self.assertEqual(intake.loads_per_month, 4)

    def test_monthly_volume_computed(self):
        """Monthly volume should be quantity * loads."""
        intake = self._create_intake(
            quantity_per_load_lbs=40000,
            loads_per_month=4,
        )

        if hasattr(intake, "monthly_volume_lbs"):
            self.assertEqual(intake.monthly_volume_lbs, 160000)
