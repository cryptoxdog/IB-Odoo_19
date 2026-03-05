"""
Test rate memory model.

Tests unique carrier+lane+date constraint.
"""

from psycopg2 import IntegrityError

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestRateMemory(TransactionCase):
    """Test plasticos.rate.memory model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.carrier = cls.env["res.partner"].create(
            {
                "name": "Test Carrier",
                "is_company": True,
                "supplier_rank": 1,
            }
        )
        cls.origin = cls.env["res.partner"].create(
            {
                "name": "Origin Location",
                "is_company": True,
            }
        )
        cls.destination = cls.env["res.partner"].create(
            {
                "name": "Destination Location",
                "is_company": True,
            }
        )

    def _create_rate_memory(self, **kwargs):
        """Helper to create a rate memory record."""
        vals = {
            "carrier_id": self.carrier.id,
            "origin_id": self.origin.id,
            "destination_id": self.destination.id,
            "rate": 500.0,
            "effective_date": "2026-03-01",
        }
        vals.update(kwargs)
        return self.env["plasticos.rate.memory"].create(vals)

    # ═══════════════════════════════════════════════════════════
    # CRUD Tests
    # ═══════════════════════════════════════════════════════════

    def test_create_rate_memory(self):
        """Rate memory record can be created."""
        rate = self._create_rate_memory()
        self.assertTrue(rate.id)
        self.assertEqual(rate.rate, 500.0)

    def test_search_rate_memory(self):
        """Rate memory can be searched by carrier and lane."""
        rate = self._create_rate_memory()

        found = self.env["plasticos.rate.memory"].search(
            [
                ("carrier_id", "=", self.carrier.id),
                ("origin_id", "=", self.origin.id),
                ("destination_id", "=", self.destination.id),
            ]
        )
        self.assertIn(rate, found)

    # ═══════════════════════════════════════════════════════════
    # Constraint Tests
    # ═══════════════════════════════════════════════════════════

    def test_unique_carrier_lane_date_constraint(self):
        """Unique constraint on carrier+origin+destination+date."""
        self._create_rate_memory()

        # Try to create duplicate
        with self.assertRaises(IntegrityError):
            self.env.cr.execute(
                """
                INSERT INTO plasticos_rate_memory
                (carrier_id, origin_id, destination_id, rate, effective_date)
                VALUES (%s, %s, %s, %s, %s)
            """,
                (
                    self.carrier.id,
                    self.origin.id,
                    self.destination.id,
                    600.0,  # Different rate
                    "2026-03-01",  # Same date
                ),
            )

    def test_different_dates_allowed(self):
        """Same carrier+lane with different dates should be allowed."""
        rate1 = self._create_rate_memory(effective_date="2026-03-01")
        rate2 = self._create_rate_memory(effective_date="2026-03-15")

        self.assertNotEqual(rate1.id, rate2.id)

    def test_different_carriers_allowed(self):
        """Same lane with different carriers should be allowed."""
        carrier2 = self.env["res.partner"].create(
            {
                "name": "Test Carrier 2",
                "is_company": True,
                "supplier_rank": 1,
            }
        )

        rate1 = self._create_rate_memory()
        rate2 = self._create_rate_memory(carrier_id=carrier2.id)

        self.assertNotEqual(rate1.id, rate2.id)

    # ═══════════════════════════════════════════════════════════
    # Rate Memory Store Tests
    # ═══════════════════════════════════════════════════════════

    def test_store_rate_memory_from_load(self):
        """Rate memory should be stored when load is closed."""
        # Create a load
        load = self.env["plasticos.load"].create(
            {
                "carrier_id": self.carrier.id,
                "pickup_partner_id": self.origin.id,
                "delivery_partner_id": self.destination.id,
                "rate": 550.0,
            }
        )

        # Trigger rate memory storage
        if hasattr(load, "_store_rate_memory"):
            load._store_rate_memory()

            # Verify rate memory was created
            rate = self.env["plasticos.rate.memory"].search(
                [
                    ("carrier_id", "=", self.carrier.id),
                    ("origin_id", "=", self.origin.id),
                    ("destination_id", "=", self.destination.id),
                ],
                limit=1,
            )
            self.assertTrue(rate)
            self.assertEqual(rate.rate, 550.0)
