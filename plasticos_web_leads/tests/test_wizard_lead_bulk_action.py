"""
Tests for plasticos.web.lead.bulk.action.wizard

Covers: default_get, computed stats, force_hot, retry_triage,
        mark_skipped, validation guards.
"""

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestLeadBulkActionWizard(PlasticosTestCase):
    """Test suite for the Web Lead Bulk Action Wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env["plasticos.web.lead.bulk.action.wizard"]
        cls.Lead = cls.env["plasticos.web.lead"]

    def _create_lead(self, decision="cold", state="received", **kw):
        """Helper to create a web lead."""
        vals = {
            "lead_id": f"WL-{self.Lead.search_count([])+1:04d}",
            "decision": decision,
            "state": state,
            "company_name": "Test Co",
            "email": "test@example.com",
        }
        vals.update(kw)
        return self.Lead.create(vals)

    # ── default_get / stats ──────────────────────────────────────────────────

    def test_default_get_populates_leads(self):
        """Wizard pre-fills lead_ids from active_ids context."""
        lead = self._create_lead()
        wiz = self.Wizard.with_context(active_ids=[lead.id]).create({"action_type": "force_hot"})
        self.assertEqual(wiz.lead_count, 1)

    def test_stats_computed(self):
        """Hot/cold/error counts reflect actual leads."""
        hot = self._create_lead(decision="hot")
        cold = self._create_lead(decision="cold")
        err = self._create_lead(decision="cold", state="error")
        wiz = self.Wizard.with_context(active_ids=[hot.id, cold.id, err.id]).create({"action_type": "force_hot"})
        self.assertEqual(wiz.hot_count, 1)
        self.assertEqual(wiz.cold_count, 2)  # cold + error (decision=cold)
        self.assertEqual(wiz.error_count, 1)

    # ── Validation ───────────────────────────────────────────────────────────

    def test_no_leads_raises(self):
        """Executing with no leads raises UserError."""
        wiz = self.Wizard.create({"action_type": "force_hot"})
        with self.assertRaises(UserError):
            wiz.action_execute()

    def test_force_hot_no_cold_raises(self):
        """Force hot with no COLD leads raises UserError."""
        hot = self._create_lead(decision="hot", state="intake_created")
        wiz = self.Wizard.with_context(active_ids=[hot.id]).create({"action_type": "force_hot"})
        with self.assertRaises(UserError):
            wiz.action_execute()

    def test_retry_triage_no_eligible_raises(self):
        """Retry triage with no error/skipped/received leads raises."""
        lead = self._create_lead(state="intake_created")
        wiz = self.Wizard.with_context(active_ids=[lead.id]).create({"action_type": "retry_triage"})
        with self.assertRaises(UserError):
            wiz.action_execute()

    # ── Successful actions ───────────────────────────────────────────────────

    def test_mark_skipped_success(self):
        """mark_skipped sets state=skipped, decision=cold."""
        lead = self._create_lead(state="received")
        wiz = self.Wizard.with_context(active_ids=[lead.id]).create(
            {"action_type": "mark_skipped", "notes": "Not relevant"}
        )
        result = wiz.action_execute()
        self.assertEqual(lead.state, "skipped")
        self.assertEqual(lead.decision, "cold")
        self.assertEqual(result["type"], "ir.actions.client")

    def test_mark_skipped_excludes_intake_created(self):
        """Leads in intake_created state are not eligible for skip."""
        lead = self._create_lead(state="intake_created")
        other = self._create_lead(state="received")
        wiz = self.Wizard.with_context(active_ids=[lead.id, other.id]).create({"action_type": "mark_skipped"})
        wiz.action_execute()
        self.assertNotEqual(lead.state, "skipped")
        self.assertEqual(other.state, "skipped")
