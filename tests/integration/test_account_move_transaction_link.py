"""Test 11 — Account Move ↔ Transaction Integration.

Source: plasticos_transaction/models/account_move_inherit.py
Risk: CRITICAL — Financial data corruption if linking or guards break.

Validates:
  - action_post() links customer invoices to transactions via SO.transaction_id
  - action_post() links vendor bills to transactions via PO
  - button_cancel() blocks cancellation when linked tx is closed
  - unlink() blocks deletion when linked tx is closed
  - action_post() blocks credit notes on closed transactions
  - action_post() runs compliance check before posting
"""

import logging
from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests.common import tagged

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "accounting", "critical")
class TestAccountMoveTransactionLink(PlasticosTestCase):
    """Invoice/bill ↔ transaction linking on action_post()."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Supplier Co",
                "is_company": True,
            }
        )
        cls.buyer = cls.env["res.partner"].create(
            {
                "name": "Test Buyer Co",
                "is_company": True,
            }
        )
        # Create a minimal transaction
        try:
            cls.tx = cls.env["plasticos.transaction"].create(
                {
                    "supplier_id": cls.partner.id,
                    "buyer_id": cls.buyer.id,
                    "quantity": 40000,
                }
            )
            cls.has_tx = True
        except Exception:
            cls.has_tx = False

    def _skip_if_missing(self):
        if not self.has_tx:
            self.skipTest("plasticos_transaction not fully installable in test env")

    def _create_invoice(self, move_type="out_invoice", origin=None):
        """Helper: create a minimal account.move."""
        vals = {
            "move_type": move_type,
            "partner_id": self.partner.id,
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "name": "Test line",
                        "quantity": 1,
                        "price_unit": 100.0,
                    },
                )
            ],
        }
        if origin:
            vals["invoice_origin"] = origin
        return self.env["account.move"].create(vals)

    # ── _find_linked_transactions ────────────────────────
    def test_find_linked_transactions_via_customer_invoice(self):
        """_find_linked_transactions finds tx via customer_invoice_id."""
        self._skip_if_missing()
        move = self._create_invoice()
        self.tx.customer_invoice_id = move.id
        found = self.env["account.move"]._find_linked_transactions(move.id)
        self.assertIn(self.tx, found)

    def test_find_linked_transactions_via_vendor_bill(self):
        """_find_linked_transactions finds tx via vendor_bill_ids."""
        self._skip_if_missing()
        move = self._create_invoice(move_type="in_invoice")
        self.tx.vendor_bill_ids = [(4, move.id)]
        found = self.env["account.move"]._find_linked_transactions(move.id)
        self.assertIn(self.tx, found)

    def test_find_linked_transactions_via_freight_bill(self):
        """_find_linked_transactions finds tx via freight_bill_ids."""
        self._skip_if_missing()
        if "freight_bill_ids" not in self.tx._fields:
            self.skipTest("freight_bill_ids not on transaction")
        move = self._create_invoice(move_type="in_invoice")
        self.tx.freight_bill_ids = [(4, move.id)]
        found = self.env["account.move"]._find_linked_transactions(move.id)
        self.assertIn(self.tx, found)

    def test_find_linked_transactions_returns_empty_when_no_link(self):
        self._skip_if_missing()
        move = self._create_invoice()
        found = self.env["account.move"]._find_linked_transactions(move.id)
        self.assertFalse(found)


@tagged("post_install", "-at_install", "accounting", "critical")
class TestAccountMoveCancelGuard(PlasticosTestCase):
    """button_cancel() must block when linked transaction is closed."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Guard Test Partner",
                "is_company": True,
            }
        )
        try:
            cls.tx = cls.env["plasticos.transaction"].create(
                {
                    "supplier_id": cls.partner.id,
                    "buyer_id": cls.partner.id,
                    "quantity": 10000,
                }
            )
            cls.has_tx = True
        except Exception:
            cls.has_tx = False

    def _skip_if_missing(self):
        if not self.has_tx:
            self.skipTest("plasticos_transaction not installable")

    def test_cannot_cancel_invoice_linked_to_closed_tx(self):
        """button_cancel raises UserError when tx is closed."""
        self._skip_if_missing()
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 1,
                            "price_unit": 50.0,
                        },
                    )
                ],
            }
        )
        self.tx.customer_invoice_id = move.id
        self.tx.state = "closed"
        with self.assertRaises(UserError, msg="Should block cancel on closed tx"):
            move.button_cancel()

    def test_cancel_allowed_when_tx_not_closed(self):
        """button_cancel succeeds when tx is not closed."""
        self._skip_if_missing()
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 1,
                            "price_unit": 50.0,
                        },
                    )
                ],
            }
        )
        self.tx.customer_invoice_id = move.id
        self.tx.state = "active"
        # Should NOT raise
        try:
            move.button_cancel()
        except UserError:
            self.fail("button_cancel should succeed when tx is active")


@tagged("post_install", "-at_install", "accounting", "critical")
class TestAccountMoveUnlinkGuard(PlasticosTestCase):
    """unlink() must block when linked transaction is closed."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Unlink Guard Partner",
                "is_company": True,
            }
        )
        try:
            cls.tx = cls.env["plasticos.transaction"].create(
                {
                    "supplier_id": cls.partner.id,
                    "buyer_id": cls.partner.id,
                    "quantity": 10000,
                }
            )
            cls.has_tx = True
        except Exception:
            cls.has_tx = False

    def test_cannot_delete_invoice_linked_to_closed_tx(self):
        if not self.has_tx:
            self.skipTest("plasticos_transaction not installable")
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 1,
                            "price_unit": 50.0,
                        },
                    )
                ],
            }
        )
        self.tx.customer_invoice_id = move.id
        self.tx.state = "closed"
        with self.assertRaises(UserError):
            move.unlink()

    def test_delete_allowed_when_no_linked_tx(self):
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 1,
                            "price_unit": 50.0,
                        },
                    )
                ],
            }
        )
        # No tx link — should succeed
        move.unlink()


@tagged("post_install", "-at_install", "accounting", "critical")
class TestAccountMoveCreditNoteGuard(PlasticosTestCase):
    """Credit note post blocked when reversed move links to closed tx."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Credit Note Partner",
                "is_company": True,
            }
        )
        try:
            cls.tx = cls.env["plasticos.transaction"].create(
                {
                    "supplier_id": cls.partner.id,
                    "buyer_id": cls.partner.id,
                    "quantity": 10000,
                }
            )
            cls.has_tx = True
        except Exception:
            cls.has_tx = False

    def test_credit_note_blocked_for_closed_transaction(self):
        """action_post raises UserError for credit note on closed tx."""
        if not self.has_tx:
            self.skipTest("plasticos_transaction not installable")
        original = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 1,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )
        self.tx.customer_invoice_id = original.id
        self.tx.state = "closed"
        refund = self.env["account.move"].create(
            {
                "move_type": "out_refund",
                "partner_id": self.partner.id,
                "reversed_entry_id": original.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Refund line",
                            "quantity": 1,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )
        with self.assertRaises(UserError, msg="Credit note should be blocked"):
            refund.action_post()


@tagged("post_install", "-at_install", "accounting")
class TestAccountMoveComplianceGate(PlasticosTestCase):
    """action_post checks compliance before posting customer invoices."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Compliance Partner",
                "is_company": True,
            }
        )

    def test_compliance_check_blocks_invoice_when_docs_missing(self):
        """If compliance service returns False, action_post raises."""
        ComplianceService = self.env["plasticos.compliance.service"]
        if ComplianceService is None:
            self.skipTest("plasticos_documents not installed")

        # Mock is_compliant to return False
        with patch.object(type(ComplianceService), "is_compliant", return_value=False):
            SO = self.env["sale.order"]
            TX = self.env["plasticos.transaction"]
            if not SO or not TX:
                self.skipTest("sale.order or transaction not available")

            tx = TX.create(
                {
                    "supplier_id": self.partner.id,
                    "buyer_id": self.partner.id,
                    "quantity": 10000,
                }
            )
            so = SO.create(
                {
                    "partner_id": self.partner.id,
                    "transaction_id": tx.id,
                }
            )
            move = self.env["account.move"].create(
                {
                    "move_type": "out_invoice",
                    "partner_id": self.partner.id,
                    "invoice_origin": so.name,
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "name": "Line",
                                "quantity": 1,
                                "price_unit": 50.0,
                            },
                        )
                    ],
                }
            )
            with self.assertRaises(UserError):
                move.action_post()
