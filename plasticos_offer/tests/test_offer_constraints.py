"""
Test offer SQL constraints.

- price > 0
- quantity > 0
"""

try:
    from psycopg.errors import IntegrityError
except ImportError:
    from psycopg2 import IntegrityError

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestOfferConstraints(PlasticosTestCase):
    """Test plasticos.offer constraints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Buyer",
                "is_company": True,
                "customer_rank": 1,
            }
        )

    def _create_offer(self, **kwargs):
        """Helper to create an offer with defaults."""
        vals = {
            "buyer_id": self.partner.id,
            "price_per_lb": 0.25,
            "quantity_lbs": 40000,
        }
        vals.update(kwargs)
        return self.env["plasticos.offer"].create(vals)

    # ═══════════════════════════════════════════════════════════
    # Price Constraint Tests
    # ═══════════════════════════════════════════════════════════

    def test_price_must_be_positive(self):
        """Price per lb must be > 0 (SQL constraint)."""
        with self.assertRaises((ValidationError, IntegrityError)):
            with self.env.cr.savepoint():
                self._create_offer(price_per_lb=0)

    def test_price_cannot_be_negative(self):
        """Price per lb cannot be negative."""
        with self.assertRaises((ValidationError, IntegrityError)):
            with self.env.cr.savepoint():
                self._create_offer(price_per_lb=-0.10)

    def test_valid_price_accepted(self):
        """Valid positive price should be accepted."""
        offer = self._create_offer(price_per_lb=0.50)
        self.assertEqual(offer.price_per_lb, 0.50)

    # ═══════════════════════════════════════════════════════════
    # Quantity Constraint Tests
    # ═══════════════════════════════════════════════════════════

    def test_quantity_must_be_positive(self):
        """Quantity lbs must be > 0 (SQL constraint)."""
        with self.assertRaises((ValidationError, IntegrityError)):
            with self.env.cr.savepoint():
                self._create_offer(quantity_lbs=0)

    def test_quantity_cannot_be_negative(self):
        """Quantity lbs cannot be negative."""
        with self.assertRaises((ValidationError, IntegrityError)):
            with self.env.cr.savepoint():
                self._create_offer(quantity_lbs=-1000)

    def test_valid_quantity_accepted(self):
        """Valid positive quantity should be accepted."""
        offer = self._create_offer(quantity_lbs=50000)
        self.assertEqual(offer.quantity_lbs, 50000)

    # ═══════════════════════════════════════════════════════════
    # Computed Field Tests
    # ═══════════════════════════════════════════════════════════

    def test_total_value_computed(self):
        """Total value should be price * quantity."""
        offer = self._create_offer(price_per_lb=0.25, quantity_lbs=40000)
        self.assertEqual(offer.total_value, 10000.0)

    def test_days_until_expiry_computed(self):
        """Days until expiry should be computed from expiry_date."""
        from datetime import date, timedelta

        expiry = date.today() + timedelta(days=30)
        offer = self._create_offer(expiry_date=expiry)

        # Should be approximately 30 days
        self.assertGreaterEqual(offer.days_until_expiry, 29)
        self.assertLessEqual(offer.days_until_expiry, 30)
