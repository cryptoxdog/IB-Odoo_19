"""DEC-007 KPI-drill parity for the Admin urgency rail (AC-010).

Each urgency KPI is declared once (model, domain). These tests assert that the
displayed value equals search_count(drill domain) on the drill's res_model, that
the drill opens the source model (not a projection missing the fields), and that
the Admin menu opens the stored KPI record.
"""

from odoo.addons.plasticos_admin_dashboard.models.admin_dashboard import URGENCY_KPIS
from odoo.tests import TransactionCase, tagged

_BYPASS = {"bypass_state_guard": True}


@tagged("post_install", "-at_install")
class TestUrgencyDrillParity(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Kpi = cls.env["plasticos.admin.kpi"]
        cls.Tx = cls.env["plasticos.transaction"]
        cls.kpi = cls.Kpi._get_or_create()
        cls.buyer = cls.env["res.partner"].create({"name": "Parity Buyer", "customer_rank": 1})

    def _tx(self, state=None, **vals):
        tx = self.Tx.create({"user_id": self.env.user.id})
        if state:
            tx.with_context(**_BYPASS).write({"state": state})
        if vals:
            tx.with_context(**_BYPASS).write(vals)
        return tx

    def _value(self, kpi_name):
        self.kpi.invalidate_recordset()
        return self.kpi[kpi_name]

    def _drilled(self, kpi_name):
        action = self.Kpi._urgency_drill(kpi_name)
        return self.env[action["res_model"]].search(action["domain"])

    def _assert_parity(self, kpi_name):
        action = self.Kpi._urgency_drill(kpi_name)
        self.assertEqual(action["res_model"], URGENCY_KPIS[kpi_name][1])
        count = self.env[action["res_model"]].search_count(action["domain"])
        self.assertEqual(self._value(kpi_name), count, f"{kpi_name}: KPI value differs from its drill count")

    def test_every_urgency_kpi_matches_its_drill(self):
        self.assertEqual(len(URGENCY_KPIS), 8)
        for kpi_name in URGENCY_KPIS:
            with self.subTest(kpi=kpi_name):
                self._assert_parity(kpi_name)

    def test_drill_buttons_return_the_declared_drill(self):
        buttons = {
            "action_open_negative_margin": "tx_negative_margin",
            "action_open_delivered_uninvoiced": "tx_delivered_uninvoiced",
            "action_open_missing_docs": "tx_missing_docs",
            "action_open_supplier_not_ready": "tx_sup_not_ready",
            "action_open_stalled_followup": "tx_stalled_followup",
            "action_open_expiring_offers": "offer_expiring_soon",
            "action_open_lead_errors": "lead_error_open",
            "action_open_commission_unlocked": "commission_unlocked",
        }
        for method, kpi_name in buttons.items():
            with self.subTest(button=method):
                self.assertEqual(getattr(self.kpi, method)(), self.Kpi._urgency_drill(kpi_name))

    def test_transaction_fixtures_are_counted_and_drilled(self):
        cases = [
            ("tx_negative_margin", self._tx("active", gross_margin=-50.0), self._tx("active", gross_margin=50.0)),
            ("tx_sup_not_ready", self._tx("supplier_not_ready"), self._tx("supplier_ready")),
            ("tx_missing_docs", self._tx("active", compliance_status="missing"), self._tx("draft")),
            ("tx_delivered_uninvoiced", self._tx("delivered"), self._tx("in_transit")),
            (
                "tx_stalled_followup",
                self._tx("pending_supplier", supplier_confirmation_followup_count=3),
                self._tx("pending_supplier", supplier_confirmation_followup_count=2),
            ),
        ]
        for kpi_name, counted, excluded in cases:
            with self.subTest(kpi=kpi_name):
                drilled = self._drilled(kpi_name)
                self.assertIn(counted, drilled)
                self.assertNotIn(excluded, drilled)
                self._assert_parity(kpi_name)

    def test_commission_unlocked_excludes_historical_sale_import(self):
        live = self._tx("closed", commission_locked=False)
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        historical = self.Tx.create({"user_id": self.env.user.id, "sale_order_id": order.id})
        historical.with_context(**_BYPASS).write({"state": "closed"})
        self.env["ir.model.data"].create(
            {
                "module": "plasticos_transaction",
                "name": f"legacy_erp_so_parity_{order.id}",
                "model": "sale.order",
                "res_id": order.id,
            }
        )
        drilled = self._drilled("commission_unlocked")
        self.assertIn(live, drilled)
        self.assertNotIn(historical, drilled)
        self._assert_parity("commission_unlocked")

    def test_menu_opens_the_stored_kpi_record(self):
        server_action = self.env.ref("plasticos_admin_dashboard.action_server_open_admin_dashboard")
        menu = self.env.ref("plasticos_admin_dashboard.menu_plasticos_admin_dashboard")
        self.assertEqual(menu.action, server_action)
        action = server_action.run()
        self.assertEqual(action["res_model"], "plasticos.admin.kpi")
        self.assertEqual(action["res_id"], self.kpi.id)
        self.assertTrue(self.Kpi.browse(action["res_id"]).exists())

    def test_sales_dashboard_default_filter_is_defined(self):
        context = self.kpi.action_open_sales_dashboard()["context"]
        filters = [key.removeprefix("search_default_") for key in context if key.startswith("search_default_")]
        arch = self.env["plasticos.sales.dashboard"].get_views([(False, "search")])["views"]["search"]["arch"]
        for name in filters:
            with self.subTest(filter=name):
                self.assertIn(f'name="{name}"', arch)
