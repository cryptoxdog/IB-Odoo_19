"""Tests for Transaction Bulk Update Wizard.

Tests the bulk status update wizard for transactions.
Aligned with plasticos_transaction/wizards/transaction_bulk_update_wizard.py.

States: active, pending_supplier, supplier_ready, in_progress,
        in_transit, delivered, invoiced, cancelled, closed
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests.common import tagged


@tagged("post_install", "-at_install")
class TestTransactionBulkUpdateWizard(PlasticosTestCase):
    """Test plasticos.tx.bulk.wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tx1 = cls.env["plasticos.transaction"].create(
            {
                "state": "active",
            }
        )
        cls.tx2 = cls.env["plasticos.transaction"].create(
            {
                "state": "active",
            }
        )

    def setUp(self):
        super().setUp()
        # Reset transaction states before each test
        self.tx1.write({"state": "active"})
        self.tx2.write({"state": "active"})

    # ------------------------------------------------------------------
    # Context loading
    # ------------------------------------------------------------------
    def test_default_get_loads_transactions(self):
        """Wizard should populate transaction_ids from active_ids."""
        wiz = (
            self.env["plasticos.tx.bulk.wizard"]
            .with_context(
                active_ids=[self.tx1.id, self.tx2.id],
            )
            .create(
                {
                    "new_state": "in_progress",
                    "reason": "Batch update",
                }
            )
        )
        self.assertEqual(wiz.transaction_count, 2)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def test_no_transactions_raises(self):
        """Executing without transactions should raise UserError."""
        wiz = self.env["plasticos.tx.bulk.wizard"].create(
            {
                "new_state": "in_progress",
                "reason": "Empty",
            }
        )
        with self.assertRaises(UserError):
            wiz.action_update_status()

    def test_closed_transaction_cannot_change(self):
        """Closed transactions should block status changes."""
        self.tx1.state = "closed"
        wiz = (
            self.env["plasticos.tx.bulk.wizard"]
            .with_context(
                active_ids=[self.tx1.id],
            )
            .create(
                {
                    "new_state": "active",
                    "reason": "Reopen attempt",
                }
            )
        )
        with self.assertRaises(UserError):
            wiz.action_update_status()

    def test_cancelled_can_only_go_draft(self):
        """Cancelled transactions should only accept draft as new state."""
        self.tx1.state = "cancelled"
        wiz = (
            self.env["plasticos.tx.bulk.wizard"]
            .with_context(
                active_ids=[self.tx1.id],
            )
            .create(
                {
                    "new_state": "active",
                    "reason": "Invalid transition",
                }
            )
        )
        with self.assertRaises(UserError):
            wiz.action_update_status()

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def test_bulk_update_changes_state(self):
        """Bulk update should change state on all selected transactions."""
        wiz = (
            self.env["plasticos.tx.bulk.wizard"]
            .with_context(
                active_ids=[self.tx1.id, self.tx2.id],
            )
            .create(
                {
                    "new_state": "in_progress",
                    "reason": "Moving to in_progress",
                }
            )
        )
        result = wiz.action_update_status()
        self.tx1.invalidate_recordset(["state"])
        self.tx2.invalidate_recordset(["state"])
        self.assertEqual(self.tx1.state, "in_progress")
        self.assertEqual(self.tx2.state, "in_progress")
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "display_notification")

    def test_bulk_update_logs_chatter(self):
        """Bulk update should post chatter messages."""
        wiz = (
            self.env["plasticos.tx.bulk.wizard"]
            .with_context(
                active_ids=[self.tx1.id],
            )
            .create(
                {
                    "new_state": "in_transit",
                    "reason": "Shipping started",
                }
            )
        )
        wiz.action_update_status()
        messages = self.tx1.message_ids.filtered(lambda m: "Bulk Update" in (m.body or ""))
        self.assertTrue(messages)
