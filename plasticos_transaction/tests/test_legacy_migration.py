"""Deterministic migration test suite for legacy staging → transaction."""

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.exceptions import UserError


class TestLegacyMigration(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.Transaction = cls.env["plasticos.transaction"]
        cls.Staging = cls.env["plastos.legacy.staging"]
        cls.MigrationService = cls.env["plastos.legacy.migration.service"]

        # Deterministic partner
        cls.customer = cls.env["res.partner"].create(
            {
                "name": "TEST CUSTOMER",
                "company_type": "company",
                "is_company": True,
                "customer_rank": 1,
            }
        )

        # Deterministic product
        cls.product = cls.env["product.product"].create(
            {
                "name": "TEST PRODUCT",
                "default_code": "TEST001",
                "type": "consu",
            }
        )

    # ---------------------------------------------------
    # 1. Basic Migration Success
    # ---------------------------------------------------

    def test_01_basic_migration_creates_transaction(self):
        self.Staging.create(
            {
                "legacy_external_id": "LEG-001",
                "customer_name": "TEST CUSTOMER",
                "product_code": "TEST001",
                "quantity": 10,
                "sell_amount": 1000,
                "buy_amount": 700,
                "freight_cost": 50,
                "commission_amount": 25,
            }
        )

        result = self.MigrationService.migrate_batch()

        self.assertEqual(result["created"], 1)
        self.assertEqual(result["errors"], 0)

        tx = self.Transaction.search([("legacy_external_id", "=", "LEG-001")], limit=1)

        self.assertTrue(tx)
        self.assertEqual(tx.revenue_total, 1000)
        self.assertEqual(tx.cost_total, 750)
        self.assertEqual(tx.state, "closed")

    # ---------------------------------------------------
    # 2. Idempotency Replay Test
    # ---------------------------------------------------

    def test_02_idempotent_replay(self):
        self.Staging.create(
            {
                "legacy_external_id": "LEG-REPLAY",
                "customer_name": "TEST CUSTOMER",
                "product_code": "TEST001",
                "quantity": 5,
                "sell_amount": 500,
                "buy_amount": 300,
            }
        )

        # First run
        self.MigrationService.migrate_batch()

        # Second run (should not duplicate)
        result = self.MigrationService.migrate_batch()

        self.assertEqual(result["created"], 0)

        count = self.Transaction.search_count([("legacy_external_id", "=", "LEG-REPLAY")])

        self.assertEqual(count, 1)

    # ---------------------------------------------------
    # 3. Dry Run Mode
    # ---------------------------------------------------

    def test_03_dry_run_creates_nothing(self):
        self.Staging.create(
            {
                "legacy_external_id": "LEG-DRY",
                "customer_name": "TEST CUSTOMER",
                "product_code": "TEST001",
                "quantity": 3,
                "sell_amount": 300,
                "buy_amount": 200,
            }
        )

        result = self.MigrationService.migrate_batch(dry_run=True)

        self.assertEqual(result["created"], 1)

        tx = self.Transaction.search([("legacy_external_id", "=", "LEG-DRY")])

        self.assertFalse(tx)

    # ---------------------------------------------------
    # 4. Missing Partner Failure
    # ---------------------------------------------------

    def test_04_missing_partner_error(self):
        self.Staging.create(
            {
                "legacy_external_id": "LEG-ERR",
                "customer_name": "UNKNOWN CUSTOMER",
                "product_code": "TEST001",
                "quantity": 1,
                "sell_amount": 100,
            }
        )

        result = self.MigrationService.migrate_batch()

        self.assertEqual(result["errors"], 1)

        tx = self.Transaction.search([("legacy_external_id", "=", "LEG-ERR")])

        self.assertFalse(tx)

    # ---------------------------------------------------
    # 5. Margin Integrity Validation
    # ---------------------------------------------------

    def test_05_margin_computation_integrity(self):
        self.Staging.create(
            {
                "legacy_external_id": "LEG-MARGIN",
                "customer_name": "TEST CUSTOMER",
                "product_code": "TEST001",
                "quantity": 1,
                "sell_amount": 1000,
                "buy_amount": 600,
                "freight_cost": 100,
            }
        )

        self.MigrationService.migrate_batch()

        tx = self.Transaction.search([("legacy_external_id", "=", "LEG-MARGIN")], limit=1)

        expected_cost = 700
        expected_margin = 300

        self.assertEqual(tx.cost_total, expected_cost)
        self.assertEqual(tx.revenue_total - tx.cost_total, expected_margin)

    # ---------------------------------------------------
    # 6. Closed Transaction Write Guard
    # ---------------------------------------------------

    def test_06_closed_transaction_immutable(self):
        self.Staging.create(
            {
                "legacy_external_id": "LEG-IMM",
                "customer_name": "TEST CUSTOMER",
                "product_code": "TEST001",
                "quantity": 1,
                "sell_amount": 200,
                "buy_amount": 100,
            }
        )

        self.MigrationService.migrate_batch()

        tx = self.Transaction.search([("legacy_external_id", "=", "LEG-IMM")], limit=1)

        with self.assertRaises(UserError):
            tx.write({"revenue_total": 9999})
