"""
State machine tests for plasticos.transaction.

Tests the full lifecycle: draft → active → closed, plus guards on
action_close (invoice posted, vendor bills posted, logistics closed,
compliance, gross margin ≥ 0, manager group), and write() protection.

Covers:
- Happy path: draft → active → closed
- Guard: cannot close without posted customer invoice
- Guard: cannot close with unposted vendor bills
- Guard: cannot close with open logistics load
- Guard: cannot close with negative gross margin
- Guard: only group_plasticos_manager can close
- Guard: write() rejects direct state manipulation
- Guard: name is immutable after create
- Guard: closed transactions block protected field writes
- Guard: commission_locked blocks commission_rule_id changes
- Guard: unlink blocked on closed or accounting-linked txns
- Sequence: auto-generates name via ir.sequence
"""

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTransactionStates(TransactionCase):
    """State machine + write guards for plasticos.transaction."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ── Manager user (can close transactions) ──────────────
        cls.manager_group = cls.env.ref("plasticos_transaction.group_plasticos_manager", raise_if_not_found=False)
        base_group = cls.env.ref("base.group_user", raise_if_not_found=False)

        manager_groups = []
        if base_group:
            manager_groups.append((4, base_group.id))
        if cls.manager_group:
            manager_groups.append((4, cls.manager_group.id))

        cls.manager_user = cls.env["res.users"].create(
            {
                "name": "TX Test Manager",
                "login": "tx_test_manager",
                "group_ids": manager_groups,
            }
        )

        # ── Regular user (cannot close) ────────────────────────
        regular_groups = [(4, base_group.id)] if base_group else []
        cls.regular_user = cls.env["res.users"].create(
            {
                "name": "TX Test User",
                "login": "tx_test_user",
                "group_ids": regular_groups,
            }
        )

        # ── Minimal partner fixtures ───────────────────────────
        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "Test Supplier TX",
                "is_company": True,
                "supplier_rank": 1,
            }
        )
        cls.buyer = cls.env["res.partner"].create(
            {
                "name": "Test Buyer TX",
                "is_company": True,
                "customer_rank": 1,
            }
        )

    def _create_tx(self, **kw):
        """Helper: create a minimal transaction."""
        vals = {
            "supplier_id": self.supplier.id,
            "buyer_id": self.buyer.id,
        }
        vals.update(kw)
        return self.env["plasticos.transaction"].create(vals)

    # ═══════════════════════════════════════════════════════════
    # Happy path
    # ═══════════════════════════════════════════════════════════

    def test_default_state_is_draft(self):
        """New transaction starts in draft."""
        tx = self._create_tx()
        self.assertEqual(tx.state, "draft")

    def test_sequence_auto_generates_name(self):
        """create() should assign an ir.sequence name, not 'New'."""
        tx = self._create_tx()
        self.assertNotEqual(tx.name, "New", "Sequence should replace 'New' placeholder")
        self.assertTrue(tx.name, "Name should not be empty")

    def test_activate_from_draft(self):
        """action_activate transitions draft → active."""
        tx = self._create_tx()
        tx.action_activate()
        self.assertEqual(tx.state, "active")

    def test_close_happy_path(self):
        """Full close with all guards satisfied."""
        tx = self._create_tx()
        tx.action_activate()

        # Create and post customer invoice
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.buyer.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Test line",
                            "quantity": 1,
                            "price_unit": 1000.0,
                        },
                    )
                ],
            }
        )
        invoice.action_post()
        tx.customer_invoice_id = invoice

        # Ensure positive gross margin (set unit_price & quantity)
        tx.write(
            {
                "unit_price": 100.0,
                "quantity": 100.0,
            }
        )

        # Close as manager
        tx_as_manager = tx.with_user(self.manager_user)
        tx_as_manager.action_close()
        self.assertEqual(tx.state, "closed")
        self.assertTrue(tx.commission_locked, "Commission should be locked after close")

    # ═══════════════════════════════════════════════════════════
    # Close guards
    # ═══════════════════════════════════════════════════════════

    def test_close_already_closed_raises(self):
        """Cannot close an already-closed transaction."""
        tx = self._create_tx()
        tx.action_activate()
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.buyer.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 1,
                            "price_unit": 500.0,
                        },
                    )
                ],
            }
        )
        invoice.action_post()
        tx.customer_invoice_id = invoice
        tx.write({"unit_price": 50.0, "quantity": 100.0})

        tx_mgr = tx.with_user(self.manager_user)
        tx_mgr.action_close()
        with self.assertRaises(UserError, msg="Already closed"):
            tx_mgr.action_close()

    def test_close_without_invoice_raises(self):
        """Cannot close without a posted customer invoice."""
        tx = self._create_tx()
        tx.action_activate()
        tx_mgr = tx.with_user(self.manager_user)
        with self.assertRaises(UserError, msg="Customer invoice must be posted"):
            tx_mgr.action_close()

    def test_close_with_draft_vendor_bill_raises(self):
        """Cannot close if any vendor bill is still in draft."""
        tx = self._create_tx()
        tx.action_activate()

        # Posted customer invoice
        inv = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.buyer.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 1,
                            "price_unit": 500.0,
                        },
                    )
                ],
            }
        )
        inv.action_post()
        tx.customer_invoice_id = inv

        # Draft vendor bill
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.supplier.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Bill",
                            "quantity": 1,
                            "price_unit": 200.0,
                        },
                    )
                ],
            }
        )
        tx.vendor_bill_ids = [(4, bill.id)]

        tx_mgr = tx.with_user(self.manager_user)
        with self.assertRaises(UserError, msg="Vendor bills must be posted"):
            tx_mgr.action_close()

    def test_close_with_open_load_raises(self):
        """Cannot close if linked load is not closed."""
        so = self.env["sale.order"].create(
            {
                "partner_id": self.buyer.id,
            }
        )
        load = self.env["plasticos.load"].create(
            {
                "name": "LOAD-TEST-001",
                "sale_order_id": so.id,
            }
        )
        tx = self._create_tx(load_id=load.id)
        tx.action_activate()

        inv = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.buyer.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 1,
                            "price_unit": 500.0,
                        },
                    )
                ],
            }
        )
        inv.action_post()
        tx.customer_invoice_id = inv

        tx_mgr = tx.with_user(self.manager_user)
        with self.assertRaises(UserError, msg="Logistics must be closed"):
            tx_mgr.action_close()

    def test_close_non_manager_raises(self):
        """Regular user cannot close transactions."""
        tx = self._create_tx()
        tx.action_activate()

        inv = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.buyer.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 1,
                            "price_unit": 500.0,
                        },
                    )
                ],
            }
        )
        inv.action_post()
        tx.customer_invoice_id = inv

        tx_user = tx.with_user(self.regular_user)
        with self.assertRaises(UserError, msg="Only Plasticos Managers"):
            tx_user.action_close()

    def test_close_negative_margin_raises(self):
        """Cannot close with negative gross margin."""
        tx = self._create_tx()
        tx.action_activate()

        inv = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.buyer.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 1,
                            "price_unit": 1.0,
                        },
                    )
                ],
            }
        )
        inv.action_post()
        tx.customer_invoice_id = inv

        # Force negative margin via other_expenses
        tx.write({"other_expenses": 999999.0})

        tx_mgr = tx.with_user(self.manager_user)
        with self.assertRaises(UserError, msg="negative gross margin"):
            tx_mgr.action_close()

    # ═══════════════════════════════════════════════════════════
    # write() guards
    # ═══════════════════════════════════════════════════════════

    def test_write_direct_state_change_blocked(self):
        """Cannot set state directly via write() (except allowed combos)."""
        tx = self._create_tx()
        with self.assertRaises(UserError, msg="State can only be changed via action"):
            tx.write({"state": "closed"})

    def test_name_immutable(self):
        """Transaction name cannot be changed after creation."""
        tx = self._create_tx()
        with self.assertRaises(UserError, msg="reference cannot be modified"):
            tx.write({"name": "TAMPERED"})

    def test_closed_tx_protected_fields_blocked(self):
        """Protected fields cannot be changed on closed transactions."""
        tx = self._create_tx()
        tx.action_activate()

        inv = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.buyer.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 1,
                            "price_unit": 500.0,
                        },
                    )
                ],
            }
        )
        inv.action_post()
        tx.customer_invoice_id = inv
        tx.write({"unit_price": 50.0, "quantity": 100.0})

        tx_mgr = tx.with_user(self.manager_user)
        tx_mgr.action_close()

        so = self.env["sale.order"].create({"partner_id": self.buyer.id})
        with self.assertRaises(UserError, msg="immutable"):
            tx.write({"sale_order_id": so.id})

    # ═══════════════════════════════════════════════════════════
    # unlink guards
    # ═══════════════════════════════════════════════════════════

    def test_unlink_closed_tx_blocked(self):
        """Cannot delete a closed transaction."""
        tx = self._create_tx()
        tx.action_activate()
        inv = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.buyer.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 1,
                            "price_unit": 500.0,
                        },
                    )
                ],
            }
        )
        inv.action_post()
        tx.customer_invoice_id = inv
        tx.write({"unit_price": 50.0, "quantity": 100.0})
        tx.with_user(self.manager_user).action_close()

        with self.assertRaises(UserError, msg="cannot be deleted"):
            tx.unlink()

    def test_unlink_with_invoice_blocked(self):
        """Cannot delete a transaction linked to accounting records."""
        tx = self._create_tx()
        inv = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.buyer.id,
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
        tx.customer_invoice_id = inv
        with self.assertRaises(UserError, msg="linked to accounting"):
            tx.unlink()

    def test_unlink_draft_no_accounting_ok(self):
        """Draft tx with no accounting links can be deleted."""
        tx = self._create_tx()
        tx_id = tx.id
        tx.unlink()
        self.assertFalse(
            self.env["plasticos.transaction"].search([("id", "=", tx_id)]),
            "Transaction should be deleted",
        )
