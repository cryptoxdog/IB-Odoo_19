"""Tests for Transaction Bulk Assign Wizard."""

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.exceptions import UserError


class TestTransactionBulkAssignWizard(PlasticosTestCase):
    """Test plasticos.transaction.bulk.assign.wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_supplier = cls.env["res.partner"].create(
            {
                "name": "Test Supplier Co",
                "is_company": True,
            }
        )
        cls.partner_buyer = cls.env["res.partner"].create(
            {
                "name": "Test Buyer Co",
                "is_company": True,
            }
        )
        cls.tx1 = cls.env["plasticos.transaction"].create({"name": "TX-BA-001"})
        cls.tx2 = cls.env["plasticos.transaction"].create({"name": "TX-BA-002"})

    # ------------------------------------------------------------------
    # default_get / context loading
    # ------------------------------------------------------------------
    def test_default_get_loads_active_ids(self):
        """Wizard should load transactions from active_ids context."""
        wiz = (
            self.env["plasticos.transaction.bulk.assign.wizard"]
            .with_context(
                active_ids=[self.tx1.id, self.tx2.id],
            )
            .create(
                {
                    "action_type": "assign_supplier",
                    "supplier_id": self.partner_supplier.id,
                    "reason": "Batch assignment",
                }
            )
        )
        self.assertEqual(wiz.transaction_count, 2)
        self.assertEqual(set(wiz.transaction_ids.ids), {self.tx1.id, self.tx2.id})

    def test_default_get_empty_context(self):
        """Wizard with no active_ids should have zero transactions."""
        wiz = self.env["plasticos.transaction.bulk.assign.wizard"].create(
            {
                "action_type": "assign_supplier",
                "supplier_id": self.partner_supplier.id,
                "reason": "Empty batch",
            }
        )
        self.assertEqual(wiz.transaction_count, 0)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def test_execute_no_transactions_raises(self):
        """Executing without transactions should raise UserError."""
        wiz = self.env["plasticos.transaction.bulk.assign.wizard"].create(
            {
                "action_type": "assign_supplier",
                "supplier_id": self.partner_supplier.id,
                "reason": "No txs",
            }
        )
        with self.assertRaises(UserError):
            wiz.action_execute()

    def test_assign_supplier_requires_supplier_id(self):
        """assign_supplier action without supplier_id should raise."""
        wiz = (
            self.env["plasticos.transaction.bulk.assign.wizard"]
            .with_context(
                active_ids=[self.tx1.id],
            )
            .create(
                {
                    "action_type": "assign_supplier",
                    "reason": "Missing supplier",
                }
            )
        )
        with self.assertRaises(UserError):
            wiz.action_execute()

    def test_assign_buyer_requires_buyer_id(self):
        """assign_buyer action without buyer_id should raise."""
        wiz = (
            self.env["plasticos.transaction.bulk.assign.wizard"]
            .with_context(
                active_ids=[self.tx1.id],
            )
            .create(
                {
                    "action_type": "assign_buyer",
                    "reason": "Missing buyer",
                }
            )
        )
        with self.assertRaises(UserError):
            wiz.action_execute()

    # ------------------------------------------------------------------
    # Bulk execution - happy paths
    # ------------------------------------------------------------------
    def test_assign_supplier_success(self):
        """Bulk assign supplier should update all selected transactions."""
        wiz = (
            self.env["plasticos.transaction.bulk.assign.wizard"]
            .with_context(
                active_ids=[self.tx1.id, self.tx2.id],
            )
            .create(
                {
                    "action_type": "assign_supplier",
                    "supplier_id": self.partner_supplier.id,
                    "reason": "New supplier assignment",
                }
            )
        )
        result = wiz.action_execute()
        self.assertTrue(result)  # returns notification / close action
        self.assertEqual(self.tx1.supplier_id, self.partner_supplier)
        self.assertEqual(self.tx2.supplier_id, self.partner_supplier)

    def test_assign_buyer_success(self):
        """Bulk assign buyer should update all selected transactions."""
        wiz = (
            self.env["plasticos.transaction.bulk.assign.wizard"]
            .with_context(
                active_ids=[self.tx1.id, self.tx2.id],
            )
            .create(
                {
                    "action_type": "assign_buyer",
                    "buyer_id": self.partner_buyer.id,
                    "reason": "New buyer assignment",
                }
            )
        )
        result = wiz.action_execute()
        self.assertTrue(result)
        self.assertEqual(self.tx1.buyer_id, self.partner_buyer)
        self.assertEqual(self.tx2.buyer_id, self.partner_buyer)

    def test_assign_both_success(self):
        """assign_both should set both supplier and buyer."""
        wiz = (
            self.env["plasticos.transaction.bulk.assign.wizard"]
            .with_context(
                active_ids=[self.tx1.id],
            )
            .create(
                {
                    "action_type": "assign_both",
                    "supplier_id": self.partner_supplier.id,
                    "buyer_id": self.partner_buyer.id,
                    "reason": "Full assignment",
                }
            )
        )
        wiz.action_execute()
        self.assertEqual(self.tx1.supplier_id, self.partner_supplier)
        self.assertEqual(self.tx1.buyer_id, self.partner_buyer)

    # ------------------------------------------------------------------
    # Computed fields
    # ------------------------------------------------------------------
    def test_transaction_count_computed(self):
        """transaction_count should match len(transaction_ids)."""
        wiz = (
            self.env["plasticos.transaction.bulk.assign.wizard"]
            .with_context(
                active_ids=[self.tx1.id],
            )
            .create(
                {
                    "action_type": "assign_supplier",
                    "supplier_id": self.partner_supplier.id,
                    "reason": "Count check",
                }
            )
        )
        self.assertEqual(wiz.transaction_count, 1)
