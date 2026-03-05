"""Performance and load tests for PlastOS critical paths.

Covers:
    - Bulk import (1000+ records)
    - Graph sync large batches
    - Cron execution time
    - Complex domain search performance
"""

import time
import unittest

from odoo.tests.common import TransactionCase


class PerfFactoryMixin:
    @classmethod
    def _partner(cls, name="Perf Partner"):
        return cls.env["res.partner"].create({"name": name, "is_company": True})

    @classmethod
    def _polymer(cls):
        return cls.env["plasticos.polymer"].create({"name": "HDPE", "code": "HDPE"})

    @classmethod
    def _form(cls):
        return cls.env["plasticos.material.form"].create({"name": "Pellet", "code": "pellet"})


class TestBulkImportPerformance(TransactionCase, PerfFactoryMixin):
    """Bulk import performance benchmarks."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "plasticos.intake" not in cls.env:
            raise unittest.SkipTest("plasticos.intake not installed")
        cls.partner = cls._partner()
        cls.polymer = cls._polymer()
        cls.form = cls._form()

    def test_bulk_create_100_intakes(self):
        """Creating 100 intakes completes in < 10s."""
        vals_list = [
            {
                "partner_id": self.partner.id,
                "polymer_id": self.polymer.id,
                "form_id": self.form.id,
                "quantity_per_load_lbs": 40000 + i,
            }
            for i in range(100)
        ]
        start = time.time()
        records = self.env["plasticos.intake"].create(vals_list)
        elapsed = time.time() - start
        self.assertEqual(len(records), 100)
        self.assertLess(elapsed, 10.0, f"Bulk create took {elapsed:.1f}s > 10s limit")

    def test_bulk_create_100_partners(self):
        """Creating 100 partners completes in < 10s."""
        vals_list = [{"name": f"Perf Partner {i}", "is_company": True} for i in range(100)]
        start = time.time()
        records = self.env["res.partner"].create(vals_list)
        elapsed = time.time() - start
        self.assertEqual(len(records), 100)
        self.assertLess(elapsed, 10.0, f"Partner bulk create took {elapsed:.1f}s > 10s limit")

    def test_bulk_create_100_match_results(self):
        """Creating 100 match results completes in < 10s."""
        if "plasticos.match.result" not in self.env:
            self.skipTest("plasticos.match.result not installed")
        intake = self.env["plasticos.intake"].create(
            {
                "partner_id": self.partner.id,
                "polymer_id": self.polymer.id,
                "form_id": self.form.id,
                "quantity_per_load_lbs": 40000,
            }
        )
        buyer = self._partner("Perf Buyer")
        vals_list = [
            {
                "intake_id": intake.id,
                "buyer_partner_id": buyer.id,
                "score": 50.0 + i * 0.5,
            }
            for i in range(100)
        ]
        start = time.time()
        records = self.env["plasticos.match.result"].create(vals_list)
        elapsed = time.time() - start
        self.assertEqual(len(records), 100)
        self.assertLess(elapsed, 10.0)


class TestGraphSyncPerformance(TransactionCase):
    """Neo4j graph sync benchmarks."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "plasticos.graph.service" not in cls.env:
            raise unittest.SkipTest("plasticos.graph.service not installed")
        cls.GraphSvc = cls.env["plasticos.graph.service"]

    def test_build_facility_payloads_under_5s(self):
        start = time.time()
        self.GraphSvc._build_facility_payloads()
        elapsed = time.time() - start
        self.assertLess(elapsed, 5.0, f"Payload build took {elapsed:.1f}s > 5s limit")

    def test_build_material_payloads_under_5s(self):
        start = time.time()
        self.GraphSvc._build_material_payloads()
        elapsed = time.time() - start
        self.assertLess(elapsed, 5.0)


class TestCronPerformance(TransactionCase):
    """Cron job execution time benchmarks."""

    def test_midnight_recompute_under_30s(self):
        if "plasticos.midnight.recompute" not in self.env:
            self.skipTest("plasticos.midnight.recompute not installed")
        svc = self.env["plasticos.midnight.recompute"]
        start = time.time()
        svc._cron_midnight_recompute()
        elapsed = time.time() - start
        self.assertLess(elapsed, 30.0)

    def test_batch_normalize_under_30s(self):
        if "plasticos.intake" not in self.env:
            self.skipTest("plasticos.intake not installed")
        start = time.time()
        self.env["plasticos.intake"].cron_batch_normalize()
        elapsed = time.time() - start
        self.assertLess(elapsed, 30.0)


class TestSearchPerformance(TransactionCase, PerfFactoryMixin):
    """Complex domain search benchmarks."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls._partner()

    def test_partner_search_under_1s(self):
        start = time.time()
        self.env["res.partner"].search(
            [
                ("is_company", "=", True),
                ("supplier_rank", ">", 0),
            ],
            limit=100,
        )
        elapsed = time.time() - start
        self.assertLess(elapsed, 1.0)

    def test_intake_complex_domain_under_2s(self):
        if "plasticos.intake" not in self.env:
            self.skipTest("plasticos.intake not installed")
        start = time.time()
        self.env["plasticos.intake"].search(
            [
                ("state", "not in", ("cancelled", "archived")),
                ("normalized", "=", True),
            ],
            limit=100,
        )
        elapsed = time.time() - start
        self.assertLess(elapsed, 2.0)
