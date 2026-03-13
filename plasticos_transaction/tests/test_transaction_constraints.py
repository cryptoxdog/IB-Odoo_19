"""
Test transaction SQL and Python constraints.

- unique name SQL constraint
- commission_override_pct range (0.0-1.0)
"""

try:
    from psycopg.errors import IntegrityError
except ImportError:
    from psycopg2 import IntegrityError

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestTransactionConstraints(PlasticosTestCase):
    """Test plasticos.transaction constraints."""

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

    def test_unique_name_constraint(self):
        """Transaction name must be unique (SQL constraint)."""
        tx1 = self._create_transaction()
        tx1_name = tx1.name

        # Try to create another with the same name
        with self.assertRaises(IntegrityError):
            self.env.cr.execute(
                """
                INSERT INTO plasticos_transaction (name, supplier_id, buyer_id, state)
                VALUES (%s, %s, %s, 'draft')
            """,
                (tx1_name, self.partner.id, self.buyer.id),
            )

    def test_commission_override_pct_valid_range(self):
        """commission_override_pct must be between 0.0 and 1.0."""
        tx = self._create_transaction()

        # Valid values should work
        tx.commission_override_pct = 0.0
        tx.commission_override_pct = 0.15
        tx.commission_override_pct = 1.0

        # Invalid values should raise ValidationError
        with self.assertRaises(ValidationError):
            tx.commission_override_pct = -0.1
            tx._check_override_pct_range()

        with self.assertRaises(ValidationError):
            tx.commission_override_pct = 1.5
            tx._check_override_pct_range()

    def test_commission_override_pct_zero_is_valid(self):
        """Zero commission override should be valid (uses rule instead)."""
        tx = self._create_transaction()
        tx.commission_override_pct = 0.0
        # Should not raise
        tx._check_override_pct_range()

    def test_vendor_bill_cannot_be_linked_twice(self):
        """Vendor bill cannot be linked to multiple transactions."""
        tx1 = self._create_transaction()
        tx2 = self._create_transaction()

        # Create a vendor bill
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
            }
        )

        # Link to first transaction
        tx1.write({"vendor_bill_ids": [(4, bill.id)]})

        # Try to link to second transaction
        from odoo.exceptions import UserError

        with self.assertRaises(UserError):
            tx2.write({"vendor_bill_ids": [(4, bill.id)]})
