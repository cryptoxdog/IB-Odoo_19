"""Contacts and web-lead view modes, plus activity after intake creation."""

from __future__ import annotations

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "plasticos", "screen_views")
class TestScreenViews(TransactionCase):
    def test_contacts_offer_map_and_hierarchy(self):
        action = self.env.ref("contacts.action_contacts")
        modes = action.view_mode.split(",")
        self.assertIn("map", modes)
        self.assertIn("hierarchy", modes)
        map_arch = self.env.ref("contacts_enterprise.res_partner_view_map").arch
        hierarchy_arch = self.env.ref("plasticos_screen_views.view_res_partner_hierarchy").arch
        self.assertIn('res_partner="id"', map_arch)
        self.assertIn('child_field="child_ids"', hierarchy_arch)

    def test_web_leads_open_on_the_list_and_name_the_analysis_fields(self):
        action = self.env.ref("plasticos_web_leads.action_web_lead")
        modes = action.view_mode.split(",")
        self.assertEqual(modes[0], "list")
        self.assertEqual(action.mobile_view_mode, "list")
        for mode in ("calendar", "pivot", "graph", "map", "activity"):
            self.assertIn(mode, modes)
        self.assertEqual(len(modes), len(set(modes)))
        self.assertNotIn(" ", action.view_mode)
        calendar_arch = self.env.ref("plasticos_screen_views.view_web_lead_calendar").arch
        pivot_arch = self.env.ref("plasticos_screen_views.view_web_lead_pivot").arch
        graph_arch = self.env.ref("plasticos_screen_views.view_web_lead_graph").arch
        self.assertIn('date_start="submitted_at"', calendar_arch)
        for arch in (pivot_arch, graph_arch):
            for field_name in ("decision", "state", "lead_source_id", "estimated_lbs_per_load"):
                self.assertIn(f'name="{field_name}"', arch)

    def test_intake_created_lead_accepts_an_activity_and_rejects_a_company_rename(self):
        lead = self.env["plasticos.web.lead"].create(
            {
                "lead_id": "SV-INTAKE-1",
                "company_name": "Screen View Co",
                "submitted_at": "2026-09-21 12:00:00",
            }
        )
        lead.write({"state": "intake_created"})
        lead.activity_schedule(summary="Follow up", note="Call the seller")
        self.assertTrue(lead.activity_ids)
        lead.write({"activity_summary": "Follow up again"})
        self.assertEqual(lead.activity_summary, "Follow up again")
        with self.assertRaises(UserError):
            lead.write({"company_name": "Renamed"})
