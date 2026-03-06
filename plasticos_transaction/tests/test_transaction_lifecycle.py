"""Unit tests for plasticos.transaction lifecycle.

Tests cover:
- Record creation with auto-sequence
- State transitions (action_activate, action_close)
- Close guards: invoice posted, vendor bills posted, manager-only
- Commission engine: rule-based, locked state, override constraint
- Write guards: closed immutability, name immutability, bill uniqueness
- Unlink guards: cannot delete closed or linked transactions
- Financial computed fields (historical totals from lines)
- Transaction line margin and weight unit conversion
"""

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestTransactionLifecycle(PlasticosTestCase):
    """Test transaction state machine and close guards."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Transaction = cls.env["plasticos.transaction"]
        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "TX Test Supplier",
                "is_company": True,
                "supplier_rank": 1,
            }
        )
        cls.buyer = cls.env["res.partner"].create(
            {
                "name": "TX Test Buyer",
                "is_company": True,
                "customer_rank": 1,
            }
        )
        cls.tx = cls.Transaction.create(
            {
                "name": "TX-TEST-001",
                "supplier_id": cls.supplier.id,
                "buyer_id": cls.buyer.id,
            }
        )

    # ── Creation ────────────────────────────────────────────────

    def test_create_auto_sequence(self):
        """Transaction with name='New' gets auto-sequenced."""
        tx = self.Transaction.create({"name": "New"})
        self.assertNotEqual(tx.name, "New")

    def test_create_explicit_name_kept(self):
        """Transaction with explicit name keeps it."""
        self.assertEqual(self.tx.name, "TX-TEST-001")

    def test_default_state_draft(self):
        """New transactions start in draft."""
        self.assertEqual(self.tx.state, "draft")

    # ── Activate ────────────────────────────────────────────────

    def test_action_activate(self):
        """action_activate sets state to active."""
        self.tx.action_activate()
        self.assertEqual(self.tx.state, "active")

    # ── Close Guards ────────────────────────────────────────────

    def test_close_without_invoice_raises(self):
        """Cannot close without a posted customer invoice."""
        self.tx.action_activate()
        with self.assertRaises(UserError):
            self.tx.action_close()

    def test_close_already_closed_raises(self):
        """Cannot close a transaction that is already closed."""
        self.tx.write(
            {
                "commission_locked": True,
                "commission_locked_amount": 0.0,
                "state": "closed",
            }
        )
        with self.assertRaises(UserError):
            self.tx.action_close()

    def test_close_requires_manager_group(self):
        """Only users in group_plasticos_manager can close."""
        journal = self.env["account.journal"].search([("type", "=", "sale")], limit=1)
        if not journal:
            return
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.buyer.id,
                "journal_id": journal.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Test",
                            "quantity": 1,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )
        invoice.action_post()
        tx = self.Transaction.create(
            {
                "name": "TX-MGR-CHECK",
                "supplier_id": self.supplier.id,
                "buyer_id": self.buyer.id,
                "customer_invoice_id": invoice.id,
            }
        )
        tx.action_activate()
        manager_group = self.env.ref(
            "plasticos_transaction.group_plasticos_manager",
            raise_if_not_found=False,
        )
        if manager_group:
            manager_group.write({"users": [(3, self.env.user.id)]})
            with self.assertRaises(UserError):
                tx.action_close()

    # ── Write Guards ────────────────────────────────────────────

    def test_name_immutable(self):
        """Transaction reference cannot be modified."""
        with self.assertRaises(UserError):
            self.tx.write({"name": "CHANGED"})

    def test_closed_transaction_protected_fields(self):
        """Closed transactions block protected field writes."""
        tx = self.Transaction.create(
            {
                "name": "TX-CLOSE-GUARD",
                "supplier_id": self.supplier.id,
            }
        )
        tx.write(
            {
                "commission_locked": True,
                "commission_locked_amount": 0.0,
                "state": "closed",
            }
        )
        with self.assertRaises(UserError):
            tx.write({"sale_order_id": False})

    def test_vendor_bill_uniqueness(self):
        """Same vendor bill cannot be linked to two transactions."""
        purchase_journal = self.env["account.journal"].search(
            [("type", "=", "purchase")],
            limit=1,
        )
        if not purchase_journal:
            return
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.supplier.id,
                "journal_id": purchase_journal.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Shared Bill",
                            "quantity": 1,
                            "price_unit": 1000.0,
                        },
                    )
                ],
            }
        )
        tx1 = self.Transaction.create({"name": "TX-BILL-1"})
        tx1.write({"vendor_bill_ids": [(4, bill.id)]})
        tx2 = self.Transaction.create({"name": "TX-BILL-2"})
        with self.assertRaises(UserError):
            tx2.write({"vendor_bill_ids": [(4, bill.id)]})

    def test_freight_bill_uniqueness(self):
        """Same freight bill cannot be linked to two transactions."""
        purchase_journal = self.env["account.journal"].search(
            [("type", "=", "purchase")],
            limit=1,
        )
        if not purchase_journal:
            return
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.supplier.id,
                "journal_id": purchase_journal.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Shared Freight",
                            "quantity": 1,
                            "price_unit": 500.0,
                        },
                    )
                ],
            }
        )
        tx1 = self.Transaction.create({"name": "TX-FRT-1"})
        tx1.write({"freight_bill_ids": [(4, bill.id)]})
        tx2 = self.Transaction.create({"name": "TX-FRT-2"})
        with self.assertRaises(UserError):
            tx2.write({"freight_bill_ids": [(4, bill.id)]})

    def test_commission_locked_rule_change_blocked(self):
        """Cannot change commission_rule_id after lock."""
        rule = self.env["plasticos.commission.rule"].create(
            {
                "name": "Lock Test Rule",
                "sales_rep_id": self.env.user.id,
                "percentage": 0.15,
            }
        )
        tx = self.Transaction.create(
            {
                "name": "TX-LOCK-RULE",
                "commission_rule_id": rule.id,
            }
        )
        tx.write(
            {
                "commission_locked": True,
                "commission_locked_amount": 100.0,
                "state": "closed",
            }
        )
        with self.assertRaises(UserError):
            tx.write({"commission_rule_id": False})

    def test_direct_state_write_blocked(self):
        """Cannot set state directly via write() with arbitrary value."""
        with self.assertRaises(UserError):
            self.tx.write({"state": "invoiced"})

    # ── Unlink Guards ───────────────────────────────────────────

    def test_unlink_closed_raises(self):
        """Cannot delete closed transaction."""
        tx = self.Transaction.create({"name": "TX-DEL-CLOSED"})
        tx.write(
            {
                "commission_locked": True,
                "commission_locked_amount": 0.0,
                "state": "closed",
            }
        )
        with self.assertRaises(UserError):
            tx.unlink()

    def test_unlink_with_invoice_raises(self):
        """Cannot delete transaction linked to accounting records."""
        journal = self.env["account.journal"].search([("type", "=", "sale")], limit=1)
        if not journal:
            return
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.buyer.id,
                "journal_id": journal.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Test",
                            "quantity": 1,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )
        tx = self.Transaction.create(
            {
                "name": "TX-DEL-INV",
                "customer_invoice_id": invoice.id,
            }
        )
        with self.assertRaises(UserError):
            tx.unlink()


@tagged("post_install", "-at_install")
class TestTransactionCommission(PlasticosTestCase):
    """Test commission computation and locking."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Transaction = cls.env["plasticos.transaction"]
        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "Comm Supplier",
                "is_company": True,
                "supplier_rank": 1,
            }
        )
        cls.rule = cls.env["plasticos.commission.rule"].create(
            {
                "name": "Test Rep Rule",
                "sales_rep_id": cls.env.user.id,
                "percentage": 0.15,
            }
        )
        cls.tx = cls.Transaction.create(
            {
                "name": "TX-COMM-001",
                "supplier_id": cls.supplier.id,
                "commission_rule_id": cls.rule.id,
            }
        )

    def test_commission_zero_without_margin(self):
        """Commission is 0 when gross_margin is 0."""
        self.tx.invalidate_recordset()
        self.assertEqual(self.tx.commission_amount, 0.0)

    def test_commission_locked_uses_locked_amount(self):
        """When locked, commission uses commission_locked_amount."""
        self.tx.write(
            {
                "commission_locked": True,
                "commission_locked_amount": 500.0,
                "state": "closed",
            }
        )
        self.tx.invalidate_recordset()
        self.assertEqual(self.tx.commission_amount, 500.0)

    def test_commission_override_range_constraint(self):
        """Override must be 0.0-1.0."""
        manager_group = self.env.ref(
            "plasticos_transaction.group_plasticos_manager",
            raise_if_not_found=False,
        )
        if manager_group:
            manager_group.write({"users": [(4, self.env.user.id)]})
        with self.assertRaises(ValidationError):
            self.tx.commission_override_pct = 1.5

    def test_unique_active_commission_rule_per_rep(self):
        """Only one active commission rule per sales rep."""
        with self.assertRaises(ValidationError):
            self.env["plasticos.commission.rule"].create(
                {
                    "name": "Duplicate Rule",
                    "sales_rep_id": self.env.user.id,
                    "percentage": 0.10,
                }
            )

    def test_commission_rule_percentage_range(self):
        """Commission rule percentage must be 0.0-1.0."""
        with self.assertRaises(ValidationError):
            self.env["plasticos.commission.rule"].create(
                {
                    "name": "Bad Rule",
                    "sales_rep_id": self.env.user.id,
                    "percentage": 2.0,
                    "active": False,
                }
            )


@tagged("post_install", "-at_install")
class TestTransactionFinancials(PlasticosTestCase):
    """Test financial computed fields on transaction and lines."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Transaction = cls.env["plasticos.transaction"]
        cls.tx = cls.Transaction.create({"name": "TX-FIN-001"})

    def test_historical_totals_from_lines(self):
        """historical_sale/purchase_total and historical_margin from lines."""
        self.env["plasticos.transaction.line"].create(
            {
                "transaction_id": self.tx.id,
                "sale_amount": 5000.0,
                "purchase_amount": 3000.0,
            }
        )
        self.env["plasticos.transaction.line"].create(
            {
                "transaction_id": self.tx.id,
                "sale_amount": 2000.0,
                "purchase_amount": 1500.0,
            }
        )
        self.tx.invalidate_recordset()
        self.assertEqual(self.tx.historical_sale_total, 7000.0)
        self.assertEqual(self.tx.historical_purchase_total, 4500.0)
        self.assertEqual(self.tx.historical_margin, 2500.0)

    def test_line_count(self):
        """line_count reflects number of transaction lines."""
        self.env["plasticos.transaction.line"].create(
            {
                "transaction_id": self.tx.id,
                "sale_amount": 100.0,
                "purchase_amount": 50.0,
            }
        )
        self.tx.invalidate_recordset()
        self.assertEqual(self.tx.line_count, 1)

    def test_line_margin_computed(self):
        """Transaction line margin = sale_amount - purchase_amount."""
        line = self.env["plasticos.transaction.line"].create(
            {
                "transaction_id": self.tx.id,
                "sale_amount": 8000.0,
                "purchase_amount": 5000.0,
            }
        )
        self.assertEqual(line.margin, 3000.0)

    def test_line_weight_lbs_short_tons(self):
        """Short tons convert to lbs (x2000)."""
        line = self.env["plasticos.transaction.line"].create(
            {
                "transaction_id": self.tx.id,
                "sale_weight": 20.0,
                "weight_uom": "S",
                "sale_amount": 0,
                "purchase_amount": 0,
            }
        )
        self.assertEqual(line.sale_weight_lbs, 40000.0)

    def test_line_weight_lbs_pounds(self):
        """Pounds pass through unchanged."""
        line = self.env["plasticos.transaction.line"].create(
            {
                "transaction_id": self.tx.id,
                "sale_weight": 38000.0,
                "weight_uom": "L",
                "sale_amount": 0,
                "purchase_amount": 0,
            }
        )
        self.assertEqual(line.sale_weight_lbs, 38000.0)

    def test_line_weight_lbs_each(self):
        """Each UOM keeps weight as-is."""
        line = self.env["plasticos.transaction.line"].create(
            {
                "transaction_id": self.tx.id,
                "sale_weight": 500.0,
                "weight_uom": "E",
                "sale_amount": 0,
                "purchase_amount": 0,
            }
        )
        self.assertEqual(line.sale_weight_lbs, 500.0)
