"""Tests for Load Bulk Update Wizard."""

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestLoadBulkUpdateWizard(TransactionCase):
    """Test plasticos.load.bulk.update.wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.load1 = cls.env["plasticos.load"].create(
            {
                "name": "LD-BU-001",
                "state": "draft",
            }
        )
        cls.load2 = cls.env["plasticos.load"].create(
            {
                "name": "LD-BU-002",
                "state": "awaiting_ready",
            }
        )

    # ------------------------------------------------------------------
    # Context
    # ------------------------------------------------------------------
    def test_default_get_loads_active_ids(self):
        """Wizard should populate load_ids from context."""
        wiz = (
            self.env["plasticos.load.bulk.update.wizard"]
            .with_context(
                active_ids=[self.load1.id, self.load2.id],
            )
            .create(
                {
                    "new_state": "scheduled",
                    "reason": "Batch schedule",
                }
            )
        )
        self.assertEqual(wiz.load_count, 2)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def test_no_loads_raises(self):
        """Executing with no loads should raise UserError."""
        wiz = self.env["plasticos.load.bulk.update.wizard"].create(
            {
                "new_state": "scheduled",
                "reason": "Empty",
            }
        )
        with self.assertRaises(UserError):
            wiz.action_update_status()

    def test_closed_load_cannot_change_except_exception(self):
        """Closed loads should only allow exception state."""
        self.load1.state = "closed"
        wiz = (
            self.env["plasticos.load.bulk.update.wizard"]
            .with_context(
                active_ids=[self.load1.id],
            )
            .create(
                {
                    "new_state": "draft",
                    "reason": "Revert attempt",
                }
            )
        )
        with self.assertRaises(UserError):
            wiz.action_update_status()

    def test_dispatched_cannot_revert_to_draft(self):
        """Dispatched loads should not revert to early states."""
        self.load1.state = "dispatched"
        wiz = (
            self.env["plasticos.load.bulk.update.wizard"]
            .with_context(
                active_ids=[self.load1.id],
            )
            .create(
                {
                    "new_state": "draft",
                    "reason": "Invalid revert",
                }
            )
        )
        with self.assertRaises(UserError):
            wiz.action_update_status()

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def test_bulk_update_changes_state(self):
        """Bulk update should change state on selected loads."""
        wiz = (
            self.env["plasticos.load.bulk.update.wizard"]
            .with_context(
                active_ids=[self.load1.id, self.load2.id],
            )
            .create(
                {
                    "new_state": "scheduled",
                    "reason": "Schedule all",
                }
            )
        )
        result = wiz.action_update_status()
        self.load1.invalidate_recordset(["state"])
        self.load2.invalidate_recordset(["state"])
        self.assertEqual(self.load1.state, "scheduled")
        self.assertEqual(self.load2.state, "scheduled")
        self.assertEqual(result["tag"], "display_notification")

    def test_bulk_update_logs_chatter(self):
        """Status change should post chatter audit trail."""
        wiz = (
            self.env["plasticos.load.bulk.update.wizard"]
            .with_context(
                active_ids=[self.load1.id],
            )
            .create(
                {
                    "new_state": "ready_confirmed",
                    "reason": "Ready check passed",
                }
            )
        )
        wiz.action_update_status()
        messages = self.load1.message_ids.filtered(lambda m: "Bulk Update" in (m.body or ""))
        self.assertTrue(messages)
