"""
Test transaction CRUD operations.

- create with partner sync
- write guards
- unlink protection on posted
"""

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestTransactionCRUD(PlasticosTestCase):
    """Test plasticos.transaction CRUD operations."""

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
        cls.buyer = cls.env["res.partner"].create(
            {
                "name": "Test Buyer",
                "is_company": True,
                "customer_rank": 1,
            }
        )

    def _create_transaction(self, **kwargs):
        """Helper to create a transaction with defaults."""
        vals = {
            "supplier_id": self.partner.id,
            "buyer_id": self.buyer.id,
        }
        vals.update(kwargs)
        return self.env["plasticos.transaction"].create(vals)

    # ═══════════════════════════════════════════════════════════
    # Create Tests
    # ═══════════════════════════════════════════════════════════

    def test_create_generates_sequence_name(self):
        """New transaction should get auto-generated name from sequence."""
        tx = self._create_transaction(name="New")
        self.assertNotEqual(tx.name, "New")
        self.assertTrue(tx.name)

    def test_create_with_explicit_name(self):
        """Transaction can be created with explicit name."""
        tx = self._create_transaction(name="TX-CUSTOM-001")
        self.assertEqual(tx.name, "TX-CUSTOM-001")

    def test_create_sets_default_state(self):
        """New transaction should be in draft state."""
        tx = self._create_transaction()
        self.assertEqual(tx.state, "draft")

    def test_create_sets_default_user(self):
        """New transaction should default to current user as salesperson."""
        tx = self._create_transaction()
        self.assertEqual(tx.user_id, self.env.user)

    # ═══════════════════════════════════════════════════════════
    # Write Guards Tests
    # ═══════════════════════════════════════════════════════════

    def test_write_name_blocked(self):
        """Transaction name cannot be changed after creation."""
        tx = self._create_transaction()
        with self.assertRaises(UserError):
            tx.write({"name": "CHANGED"})

    def test_write_state_blocked_direct(self):
        """Direct state change should be blocked (use action methods)."""
        tx = self._create_transaction()
        with self.assertRaises(UserError):
            tx.write({"state": "closed"})

    def test_write_customer_invoice_cannot_reassign(self):
        """Customer invoice cannot be reassigned once set."""
        tx = self._create_transaction()

        invoice1 = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.buyer.id,
            }
        )
        invoice2 = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.buyer.id,
            }
        )

        tx.customer_invoice_id = invoice1.id

        with self.assertRaises(UserError):
            tx.write({"customer_invoice_id": invoice2.id})

    def test_write_commission_rule_blocked_when_locked(self):
        """Commission rule cannot be modified after lock."""
        tx = self._create_transaction()
        tx.commission_locked = True

        with self.assertRaises(UserError):
            tx.write({"commission_rule_id": False})

    # ═══════════════════════════════════════════════════════════
    # Unlink Protection Tests
    # ═══════════════════════════════════════════════════════════

    def test_unlink_draft_allowed(self):
        """Draft transaction without accounting links can be deleted."""
        tx = self._create_transaction()
        tx_id = tx.id
        tx.unlink()
        self.assertFalse(self.env["plasticos.transaction"].browse(tx_id).exists())

    def test_unlink_with_invoice_blocked(self):
        """Cannot delete transaction with customer invoice."""
        tx = self._create_transaction()

        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.buyer.id,
            }
        )
        tx.customer_invoice_id = invoice.id

        with self.assertRaises(UserError):
            tx.unlink()

    def test_unlink_with_vendor_bills_blocked(self):
        """Cannot delete transaction with vendor bills."""
        tx = self._create_transaction()

        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
            }
        )
        tx.write({"vendor_bill_ids": [(4, bill.id)]})

        with self.assertRaises(UserError):
            tx.unlink()

    def test_unlink_closed_blocked(self):
        """Cannot delete closed transaction."""
        tx = self._create_transaction()
        tx.action_activate()

        # Manually set to closed for testing
        tx.with_context(skip_state_check=True).write(
            {
                "state": "closed",
                "commission_locked": True,
            }
        )

        with self.assertRaises(UserError):
            tx.unlink()
