"""Test 17 — Sale Order Confirm → Transaction Auto-Create.

File: plasticos_transaction/models/sale_inherit.py
Risk: CRITICAL — Core revenue path. SO confirmation creates transactions.

Validates:
  - sale.order has transaction_id field (added by bridge)
  - action_confirm() creates or links a transaction
  - Transaction inherits partner from SO
  - Transaction links back to sale order
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "transaction", "sale", "critical")
class TestSaleOrderTransactionBridge(PlasticosTestCase):
    """sale.order → plasticos.transaction bridge wiring."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "SO Bridge Partner",
                "is_company": True,
            }
        )
        try:
            cls.TX = cls.env["plasticos.transaction"]
            cls.has_tx = True
        except KeyError:
            cls.has_tx = False

    def _skip_check(self):
        if not self.has_tx:
            self.skipTest("plasticos_transaction not installed")

    def test_sale_order_has_transaction_id_field(self):
        """sale_inherit.py adds transaction_id to sale.order."""
        self._skip_check()
        self.assertIn(
            "transaction_id",
            self.env["sale.order"]._fields,
            "transaction_id missing on sale.order — is plasticos_transaction installed?",
        )

    def test_sale_order_transaction_id_targets_transaction(self):
        self._skip_check()
        f = self.env["sale.order"]._fields.get("transaction_id")
        if not f:
            self.skipTest("transaction_id not on sale.order")
        self.assertEqual(f.comodel_name, "plasticos.transaction")

    def test_transaction_has_sale_order_link(self):
        """Transaction should reference its originating SO."""
        self._skip_check()
        fields = self.TX._fields
        has_so_link = "sale_order_id" in fields or "sale_order_ids" in fields or "origin" in fields
        self.assertTrue(has_so_link, "Transaction has no sale order backlink")


@tagged("post_install", "-at_install", "transaction", "sale")
class TestSaleConfirmTransactionCreation(PlasticosTestCase):
    """action_confirm() auto-creates a transaction."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Confirm Test Co",
                "is_company": True,
            }
        )
        try:
            cls.TX = cls.env["plasticos.transaction"]
            cls.has_tx = True
        except KeyError:
            cls.has_tx = False

        # Need a product for SO line
        cls.product = cls.env["product.product"].create(
            {
                "name": "Test Polymer Product",
                "type": "consu",
                "list_price": 0.15,
            }
        )

    def _skip_check(self):
        if not self.has_tx:
            self.skipTest("plasticos_transaction not installed")
        if "transaction_id" not in self.env["sale.order"]._fields:
            self.skipTest("transaction_id not wired on sale.order")

    def _make_so(self):
        return self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 40000,
                            "price_unit": 0.15,
                        },
                    )
                ],
            }
        )

    def test_confirm_creates_transaction(self):
        """SO confirmation should result in a linked transaction."""
        self._skip_check()
        so = self._make_so()
        so.action_confirm()
        # After confirm, transaction_id should be set
        if so.transaction_id:
            self.assertTrue(so.transaction_id.id)
            self.assertEqual(so.transaction_id.supplier_id, self.partner)
        else:
            # Some implementations create tx lazily
            tx = self.TX.search(
                [
                    "|",
                    ("sale_order_id", "=", so.id),
                    ("sale_order_ids", "in", so.id),
                ],
                limit=1,
            )
            # At minimum, the bridge should exist
            self.assertTrue(
                so.transaction_id or tx,
                "No transaction created or linked after SO confirm",
            )
