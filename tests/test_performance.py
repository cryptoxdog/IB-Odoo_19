"""Performance and load tests for PlastOS critical paths.

Covers:
    - Bulk import (100+ records)
    - Cron execution time
    - Complex domain search performance

Performance thresholds are set conservatively to avoid flaky tests
while still catching major regressions. Actual production performance
should be significantly better than these thresholds.
"""

import time

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "plasticos", "performance", "bulk")
class TestBulkImportPerformance(PlasticosTestCase):
    """Bulk import performance benchmarks."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.intake")

    def test_bulk_create_100_intakes(self):
        """Creating 100 intakes completes in < 10s."""
        vals_list = [
            {
                "partner_id": self.default_partner.id,
                "polymer_id": self.default_polymer.id,
                "form_id": self.default_form.id,
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
                "partner_id": self.default_partner.id,
                "polymer_id": self.default_polymer.id,
                "form_id": self.default_form.id,
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


# TestGraphSyncPerformance benchmarked plasticos.graph.service payload builders.
# That model is in the mothball DISCARDABLE_CATALOG
# (scripts/migrations/mothball_local_intelligence.py): the local Neo4j helper was
# retired because CEG owns the graph. Odoo no longer builds graph payloads, so there
# is no in-repo work left to benchmark — Gate egress latency is measured on the Gate
# side, not here.


class TestCronPerformance(PlasticosTestCase):
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


class TestSearchPerformance(PlasticosTestCase):
    """Complex domain search benchmarks."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.default_partner = cls._partner()

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
