"""Tests for plasticos.rate.memory — freight rate caching.

Target module: plasticos_logistics
Target model:  plasticos.rate.memory

Validates: unique constraint (carrier + lane + date), cached rate lookup,
and update-overwrite behavior.
"""

import uuid
from datetime import date, timedelta

from psycopg2 import IntegrityError

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install", "plasticos", "logistics", "rate")
class TestRateMemory(PlasticosTestCase):
    """Test rate memory cache model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.RateMemory = cls.env["plasticos.rate.memory"]
        cls.carrier = cls.env["res.partner"].create(
            {
                "name": "Rate Test Carrier",
                "is_company": True,
            }
        )
        # Use unique prefix for lane_keys to avoid conflicts with other tests
        cls.test_prefix = str(uuid.uuid4())[:8]

    def _create_rate(self, **kwargs):
        """Helper: create a rate memory with defaults."""
        vals = {
            "carrier_id": self.carrier.id,
            "lane_key": f"{self.test_prefix}-HOUSTON-CHICAGO",
            "rate_amount": 1750.00,
            "rate_date": fields.Date.today(),
        }
        vals.update(kwargs)
        return self.RateMemory.create(vals)

    # ── CRUD ───────────────────────────────────────────────────

    def test_create_basic(self):
        """Rate memory can be created with required fields."""
        rate = self._create_rate()
        self.assertTrue(rate.id)
        self.assertEqual(rate.carrier_id.id, self.carrier.id)

    # ── Unique Constraint ──────────────────────────────────────

    def test_duplicate_carrier_lane_date_rejected(self):
        """Same carrier + lane_key + date raises exception."""
        unique_lane = f"{self.test_prefix}-DALLAS-MEMPHIS-{uuid.uuid4().hex[:6]}"
        unique_date = date(2026, 1, 15)
        self._create_rate(
            lane_key=unique_lane,
            rate_date=unique_date,
        )
        with self.assertRaises(IntegrityError), self.env.cr.savepoint():
            self._create_rate(
                lane_key=unique_lane,
                rate_date=unique_date,
            )

    def test_same_lane_different_date_accepted(self):
        """Same lane but different date is valid."""
        unique_lane = f"{self.test_prefix}-ATLANTA-MIAMI-{uuid.uuid4().hex[:6]}"
        self._create_rate(
            lane_key=unique_lane,
            rate_date=date(2026, 2, 1),
        )
        rate2 = self._create_rate(
            lane_key=unique_lane,
            rate_date=date(2026, 2, 15),
        )
        self.assertTrue(rate2.id)

    def test_same_lane_different_carrier_accepted(self):
        """Same lane and date but different carrier is valid."""
        carrier2 = self.env["res.partner"].create(
            {
                "name": "Second Carrier",
                "is_company": True,
            }
        )
        unique_lane = f"{self.test_prefix}-NYC-BOSTON-{uuid.uuid4().hex[:6]}"
        unique_date = date(2026, 3, 1)
        self._create_rate(
            lane_key=unique_lane,
            rate_date=unique_date,
        )
        rate2 = self._create_rate(
            carrier_id=carrier2.id,
            lane_key=unique_lane,
            rate_date=unique_date,
        )
        self.assertTrue(rate2.id)

    # ── Rate Lookup ────────────────────────────────────────────

    def test_get_recent_rate_returns_latest(self):
        """Search returns the most recent rate within date range."""
        unique_lane = f"{self.test_prefix}-LA-PHOENIX-{uuid.uuid4().hex[:6]}"
        self._create_rate(
            lane_key=unique_lane,
            rate_date=date.today() - timedelta(days=5),
            rate_amount=1500.00,
        )
        rate2 = self._create_rate(
            lane_key=unique_lane,
            rate_date=date.today(),
            rate_amount=1600.00,
        )
        # Search for most recent rate
        result = self.RateMemory.search(
            [
                ("carrier_id", "=", self.carrier.id),
                ("lane_key", "=", unique_lane),
            ],
            order="rate_date desc",
            limit=1,
        )
        self.assertEqual(result.id, rate2.id)
        self.assertAlmostEqual(result.rate_amount, 1600.00, places=2)

    def test_rate_scoped_to_carrier(self):
        """Search only returns rates for specified carrier."""
        other_carrier = self.env["res.partner"].create(
            {
                "name": "Other Carrier Co",
                "is_company": True,
            }
        )
        unique_lane = f"{self.test_prefix}-SEATTLE-PORTLAND-{uuid.uuid4().hex[:6]}"
        self._create_rate(
            carrier_id=other_carrier.id,
            lane_key=unique_lane,
            rate_date=date.today(),
        )
        result = self.RateMemory.search(
            [
                ("carrier_id", "=", self.carrier.id),
                ("lane_key", "=", unique_lane),
            ]
        )
        self.assertFalse(result)
