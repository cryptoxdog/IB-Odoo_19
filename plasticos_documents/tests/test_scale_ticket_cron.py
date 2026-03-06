"""Integration tests for scale ticket cron job.

Tests cover:
- Reminder fires once after 2 business days (48h) from delivery
- Escalation fires once after 7 business days from pickup
- No duplicate notifications
- Transactions with scale tickets are skipped
"""

from datetime import datetime, timedelta

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestScaleTicketCron(PlasticosTestCase):
    """Integration tests for cron_check_scale_tickets()."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Transaction = cls.env["plasticos.transaction"]
        cls.Load = cls.env["plasticos.load"]
        cls.Document = cls.env["plasticos.document"]
        cls.DocumentTag = cls.env["plasticos.document.tag"]

        # Get or create SCALE tag
        cls.scale_tag = cls.DocumentTag.search([("code", "=", "SCALE")], limit=1)
        if not cls.scale_tag:
            cls.scale_tag = cls.DocumentTag.create(
                {
                    "name": "Scale Ticket",
                    "code": "SCALE",
                }
            )

        # Create a carrier partner
        cls.carrier = cls.env["res.partner"].create(
            {
                "name": "Test Carrier",
                "is_company": True,
            }
        )

    def _create_load_with_dates(self, pickup_days_ago, delivery_days_ago):
        """Helper to create a load with specific pickup/delivery dates."""
        now = datetime.now()
        load = self.Load.create(
            {
                "name": f"LOAD-{now.timestamp()}",
                "carrier_id": self.carrier.id,
                "dispatched_at": now - timedelta(days=pickup_days_ago),
                "delivered_at": now - timedelta(days=delivery_days_ago),
                "state": "closed",
            }
        )
        return load

    def _create_transaction_with_load(self, load, state="delivered"):
        """Helper to create a transaction linked to a load."""
        tx = self.Transaction.create(
            {
                "name": f"TX-{datetime.now().timestamp()}",
                "load_id": load.id,
                "state": state,
            }
        )
        return tx

    # ══════════════════════════════════════════════════════════════
    # Reminder Tests (2 BD after delivery)
    # ══════════════════════════════════════════════════════════════

    def test_reminder_sent_after_2_business_days(self):
        """Reminder is sent when delivery was 2+ business days ago."""
        load = self._create_load_with_dates(pickup_days_ago=10, delivery_days_ago=3)
        tx = self._create_transaction_with_load(load)

        # Verify initial state
        self.assertFalse(tx.x_scale_ticket_reminder_sent)

        # Run cron
        self.Transaction.cron_check_scale_tickets()

        # Refresh and check
        tx.invalidate_recordset()
        self.assertTrue(tx.x_scale_ticket_reminder_sent)

    def test_reminder_not_sent_before_2_business_days(self):
        """Reminder is NOT sent when delivery was <2 business days ago."""
        load = self._create_load_with_dates(pickup_days_ago=2, delivery_days_ago=1)
        tx = self._create_transaction_with_load(load)

        # Run cron
        self.Transaction.cron_check_scale_tickets()

        # Refresh and check
        tx.invalidate_recordset()
        self.assertFalse(tx.x_scale_ticket_reminder_sent)

    def test_reminder_not_duplicated(self):
        """Reminder is only sent once, not on every cron run."""
        load = self._create_load_with_dates(pickup_days_ago=10, delivery_days_ago=3)
        tx = self._create_transaction_with_load(load)

        # Count messages before
        msg_count_before = len(tx.message_ids)

        # Run cron twice
        self.Transaction.cron_check_scale_tickets()
        tx.invalidate_recordset()
        msg_count_after_first = len(tx.message_ids)

        self.Transaction.cron_check_scale_tickets()
        tx.invalidate_recordset()
        msg_count_after_second = len(tx.message_ids)

        # Should have added exactly one message, not two
        self.assertEqual(msg_count_after_first - msg_count_before, 1)
        self.assertEqual(msg_count_after_second, msg_count_after_first)

    # ══════════════════════════════════════════════════════════════
    # Escalation Tests (7 BD from pickup)
    # ══════════════════════════════════════════════════════════════

    def test_escalation_triggered_after_7_business_days(self):
        """Escalation is triggered when pickup was 7+ business days ago."""
        load = self._create_load_with_dates(pickup_days_ago=10, delivery_days_ago=8)
        tx = self._create_transaction_with_load(load)

        # Verify initial state
        self.assertFalse(tx.x_scale_ticket_escalated)

        # Run cron
        self.Transaction.cron_check_scale_tickets()

        # Refresh and check
        tx.invalidate_recordset()
        self.assertTrue(tx.x_scale_ticket_escalated)

    def test_escalation_not_triggered_before_7_business_days(self):
        """Escalation is NOT triggered when pickup was <7 business days ago."""
        load = self._create_load_with_dates(pickup_days_ago=5, delivery_days_ago=3)
        tx = self._create_transaction_with_load(load)

        # Run cron
        self.Transaction.cron_check_scale_tickets()

        # Refresh and check
        tx.invalidate_recordset()
        self.assertFalse(tx.x_scale_ticket_escalated)

    def test_escalation_not_duplicated(self):
        """Escalation is only triggered once, not on every cron run."""
        load = self._create_load_with_dates(pickup_days_ago=10, delivery_days_ago=8)
        tx = self._create_transaction_with_load(load)

        # Count activities before
        activity_count_before = self.env["mail.activity"].search_count(
            [
                ("res_model", "=", "plasticos.transaction"),
                ("res_id", "=", tx.id),
            ]
        )

        # Run cron twice
        self.Transaction.cron_check_scale_tickets()
        tx.invalidate_recordset()

        self.Transaction.cron_check_scale_tickets()
        tx.invalidate_recordset()

        # Count activities after
        activity_count_after = self.env["mail.activity"].search_count(
            [
                ("res_model", "=", "plasticos.transaction"),
                ("res_id", "=", tx.id),
            ]
        )

        # Should have added at most one activity
        self.assertLessEqual(activity_count_after - activity_count_before, 1)

    # ══════════════════════════════════════════════════════════════
    # Skip Tests (scale ticket exists)
    # ══════════════════════════════════════════════════════════════

    def test_skipped_when_scale_ticket_exists(self):
        """Transaction is skipped when scale ticket document exists."""
        load = self._create_load_with_dates(pickup_days_ago=10, delivery_days_ago=8)
        tx = self._create_transaction_with_load(load)

        # Create a scale ticket document
        self.Document.create(
            {
                "name": "Scale Ticket Test",
                "tag_id": self.scale_tag.id,
                "transaction_id": tx.id,
            }
        )

        # Run cron
        self.Transaction.cron_check_scale_tickets()

        # Refresh and check - should NOT have triggered anything
        tx.invalidate_recordset()
        self.assertFalse(tx.x_scale_ticket_reminder_sent)
        self.assertFalse(tx.x_scale_ticket_escalated)

    # ══════════════════════════════════════════════════════════════
    # State Filter Tests
    # ══════════════════════════════════════════════════════════════

    def test_only_delivered_closed_invoiced_states(self):
        """Only transactions in delivered/closed/invoiced states are checked."""
        load = self._create_load_with_dates(pickup_days_ago=10, delivery_days_ago=8)

        # Create transaction in draft state
        tx = self.Transaction.create(
            {
                "name": f"TX-DRAFT-{datetime.now().timestamp()}",
                "load_id": load.id,
                "state": "draft",
            }
        )

        # Run cron
        self.Transaction.cron_check_scale_tickets()

        # Refresh and check - should NOT have triggered anything
        tx.invalidate_recordset()
        self.assertFalse(tx.x_scale_ticket_reminder_sent)
        self.assertFalse(tx.x_scale_ticket_escalated)

    def test_invoiced_state_included(self):
        """Transactions in 'invoiced' state are also checked."""
        load = self._create_load_with_dates(pickup_days_ago=10, delivery_days_ago=8)
        tx = self._create_transaction_with_load(load, state="invoiced")

        # Run cron
        self.Transaction.cron_check_scale_tickets()

        # Refresh and check
        tx.invalidate_recordset()
        self.assertTrue(tx.x_scale_ticket_escalated)


@tagged("post_install", "-at_install")
class TestBusinessDayCalculation(PlasticosTestCase):
    """Test the business day calculation helper."""

    def test_count_business_days_excludes_weekends(self):
        """Business day count excludes Saturday and Sunday."""
        from datetime import date

        Transaction = self.env["plasticos.transaction"]

        # Monday to Friday = 4 business days
        monday = date(2026, 3, 2)  # Monday
        friday = date(2026, 3, 6)  # Friday
        self.assertEqual(Transaction._count_business_days(monday, friday), 4)

        # Friday to Monday = 1 business day (Friday only)
        friday = date(2026, 3, 6)  # Friday
        monday = date(2026, 3, 9)  # Monday
        self.assertEqual(Transaction._count_business_days(friday, monday), 1)

    def test_count_business_days_handles_none(self):
        """Returns 0 when dates are None."""
        Transaction = self.env["plasticos.transaction"]
        self.assertEqual(Transaction._count_business_days(None, None), 0)
