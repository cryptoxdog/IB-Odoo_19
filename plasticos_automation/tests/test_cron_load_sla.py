"""Tests for load SLA cron — escalation engine in plasticos_automation.

Target module: plasticos_automation
Target model:  plasticos.load (via _inherit)
Cron:          cron_load_sla_check
"""

from datetime import timedelta

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestCronLoadSla(PlasticosTestCase):
    """Test Load SLA breach detection and escalation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Load = cls.env["plasticos.load"]
        cls.AutoLog = cls.env["plasticos.automation.log"]
        cls.partner = cls.env["res.partner"].create({"name": "Test Carrier"})

    def _create_load(self, state="awaiting_ready", hours_ago=0):
        """Helper: create a load stuck in a state for N hours."""
        load = self.Load.create(
            {
                "name": f"LOAD-TEST-{state}",
                "state": state,
                "carrier_id": self.partner.id,
            }
        )
        if hours_ago:
            past = fields.Datetime.now() - timedelta(hours=hours_ago)
            load.entered_state_at = past
        return load

    # ── SLA Breach Detection ─────────────────────────────────

    def test_no_breach_within_sla(self):
        """Load within SLA window should not be flagged."""
        load = self._create_load("awaiting_ready", hours_ago=10)
        self.Load.cron_load_sla_check()
        load.invalidate_recordset()
        self.assertFalse(load.sla_breached)

    def test_breach_after_sla_exceeded(self):
        """Load exceeding SLA hours should get sla_breached = True."""
        load = self._create_load("awaiting_ready", hours_ago=60)
        self.Load.cron_load_sla_check()
        load.invalidate_recordset()
        self.assertTrue(load.sla_breached)

    def test_warning_escalation_level(self):
        """Load just past SLA should escalate to 'warning'."""
        load = self._create_load("awaiting_ready", hours_ago=60)
        self.Load.cron_load_sla_check()
        load.invalidate_recordset()
        self.assertEqual(load.escalation_level, "warning")

    def test_critical_escalation_level(self):
        """Load past 2x SLA should escalate to 'critical'."""
        load = self._create_load("awaiting_ready", hours_ago=120)
        self.Load.cron_load_sla_check()
        load.invalidate_recordset()
        self.assertEqual(load.escalation_level, "critical")

    def test_no_entered_state_at_skipped(self):
        """Loads without entered_state_at are skipped gracefully."""
        load = self._create_load("awaiting_ready", hours_ago=0)
        load.entered_state_at = False
        self.Load.cron_load_sla_check()
        load.invalidate_recordset()
        self.assertFalse(load.sla_breached)

    def test_escalation_resets_when_within_sla(self):
        """If load is fixed (back within SLA), escalation_level resets to 'none'."""
        load = self._create_load("awaiting_ready", hours_ago=60)
        self.Load.cron_load_sla_check()
        load.invalidate_recordset()
        self.assertEqual(load.escalation_level, "warning")
        load.entered_state_at = fields.Datetime.now()
        self.Load.cron_load_sla_check()
        load.invalidate_recordset()
        self.assertEqual(load.escalation_level, "none")

    def test_chatter_message_posted_on_breach(self):
        """SLA breach should post a chatter message."""
        load = self._create_load("awaiting_ready", hours_ago=60)
        msg_count_before = len(load.message_ids)
        self.Load.cron_load_sla_check()
        load.invalidate_recordset()
        self.assertGreater(len(load.message_ids), msg_count_before)

    def test_dispatched_sla_72h(self):
        """Dispatched state has 72h SLA — test breach at 80h."""
        load = self._create_load("dispatched", hours_ago=80)
        self.Load.cron_load_sla_check()
        load.invalidate_recordset()
        self.assertTrue(load.sla_breached)
        self.assertEqual(load.escalation_level, "warning")
