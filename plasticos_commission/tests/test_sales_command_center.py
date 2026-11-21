"""TASK-033 / DEC-007: each Sales command-center KPI reconciles with its drill.

The value and the drill come from one declaration. For the logged-in rep the
drill domain's count (or sum) equals the KPI value, and no KPI counts another
rep's records. An uninstalled or unreadable source is unavailable, never 0.
"""

from __future__ import annotations

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSalesCommandCenter(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        rep_group = cls.env.ref("plasticos_security_base.group_sales_rep")
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.rep_a = Users.create(
            {"name": "KPI Rep A", "login": "t033_kpi_rep_a", "group_ids": [Command.set([rep_group.id])]}
        )
        cls.rep_b = Users.create(
            {"name": "KPI Rep B", "login": "t033_kpi_rep_b", "group_ids": [Command.set([rep_group.id])]}
        )
        cls.company = cls.env.company
        cls.buyer = cls.env["res.partner"].create({"name": "KPI Buyer", "customer_rank": 1})
        cls.own = cls._deals(cls.rep_a, 3)
        cls.own[0].write({"supplier_confirmation_received": fields.Datetime.now()})
        cls.foreign = cls._deals(cls.rep_b, 2)
        if "crm.lead" in cls.env:
            Lead = cls.env["crm.lead"]
            Lead.create({"name": "A opp", "type": "opportunity", "user_id": cls.rep_a.id})
            Lead.create({"name": "B opp", "type": "opportunity", "user_id": cls.rep_b.id})
        cls.env.flush_all()

    @classmethod
    def _deals(cls, user, count, company=None):
        Tx = cls.env["plasticos.transaction"]
        deals = Tx
        for _index in range(count):
            order = cls.env["sale.order"].create(
                {"partner_id": cls.buyer.id, "company_id": (company or cls.company).id}
            )
            deals |= Tx.create({"user_id": user.id, "sale_order_id": order.id})
        deals.write({"state": "active"})
        return deals

    def _kpis(self, user):
        return {kpi["key"]: kpi for kpi in self.env["plasticos.sales.dashboard"].with_user(user).get_sales_kpis()}

    def _drill_value(self, user, kpi):
        action = self.env["plasticos.sales.dashboard"].with_user(user).action_open_sales_kpi(kpi["key"])
        self.assertEqual(action["res_model"], kpi["model"])
        self.assertEqual(action["domain"], kpi["domain"])
        records = self.env[action["res_model"]].with_user(user).search(action["domain"])
        if kpi["aggregate"] == "count":
            return records, len(records)
        field_name = kpi["aggregate"].split(":", 1)[1]
        return records, sum(records.mapped(field_name))

    def test_every_available_kpi_reconciles_with_its_drill(self):
        for kpi in self._kpis(self.rep_a).values():
            with self.subTest(kpi=kpi["key"]):
                if not kpi["available"]:
                    self.assertIsNone(kpi["value"])
                    with self.assertRaises(UserError):
                        self.env["plasticos.sales.dashboard"].with_user(self.rep_a).action_open_sales_kpi(kpi["key"])
                    continue
                records, value = self._drill_value(self.rep_a, kpi)
                self.assertAlmostEqual(value, kpi["value"])
                if "user_id" in records._fields:
                    self.assertLessEqual(records.mapped("user_id"), self.rep_a)

    def test_kpis_exclude_another_reps_records(self):
        kpis = self._kpis(self.rep_a)
        self.assertEqual(kpis["active_deals"]["value"], len(self.own))
        self.assertEqual(kpis["pending_confirmations"]["value"], 2)
        rows = self.env["plasticos.sales.dashboard"].search([("transaction_id", "in", self.own.ids)])
        self.assertAlmostEqual(kpis["margin"]["value"], sum(rows.mapped("gross_margin")))
        self.assertAlmostEqual(kpis["expected_commission"]["value"], sum(rows.mapped("commission_amount")))
        self.assertEqual(self._kpis(self.rep_b)["active_deals"]["value"], len(self.foreign))

    def test_uninstalled_source_is_unavailable_not_zero(self):
        dashboard = self.env["plasticos.sales.dashboard"].with_user(self.rep_a)
        declaration = dict(dashboard._sales_kpi_declarations()["active_deals"], model="no.such.model")
        self.assertFalse(dashboard._sales_kpi_available(declaration))
        missing_field = dict(
            dashboard._sales_kpi_declarations()["missing_customer_documents"],
            domain=[("no_such_field", "=", True)],
        )
        self.assertFalse(dashboard._sales_kpi_available(missing_field))

    def test_unknown_kpi_is_refused(self):
        with self.assertRaises(UserError):
            self.env["plasticos.sales.dashboard"].with_user(self.rep_a).action_open_sales_kpi("nope")

    def test_deal_without_sale_order_is_not_counted(self):
        before = self._kpis(self.rep_a)["active_deals"]["value"]
        orphan = self.env["plasticos.transaction"].create({"user_id": self.rep_a.id})
        orphan.write({"state": "active"})
        self.env.flush_all()
        self.assertEqual(self._kpis(self.rep_a)["active_deals"]["value"], before)

    def test_kpis_are_scoped_to_the_active_companies(self):
        other = self.env["res.company"].create({"name": "KPI Other Co"})
        self.rep_a.write({"company_ids": [Command.link(other.id)]})
        self._deals(self.rep_a, 2, company=other)
        self.env.flush_all()
        dashboard = self.env["plasticos.sales.dashboard"].with_user(self.rep_a)
        only_main = dashboard.with_context(allowed_company_ids=[self.company.id]).get_sales_kpis()
        both = dashboard.with_context(allowed_company_ids=[self.company.id, other.id]).get_sales_kpis()
        value = {kpi["key"]: kpi["value"] for kpi in only_main}
        value_both = {kpi["key"]: kpi["value"] for kpi in both}
        self.assertEqual(value["active_deals"], len(self.own))
        self.assertEqual(value_both["active_deals"], len(self.own) + 2)
        self.assertEqual(value_both["pending_confirmations"], value["pending_confirmations"] + 2)

    def test_tiles_show_the_kpi_values_and_open_the_drills(self):
        tiles = self.env["plasticos.sales.command.center"].with_user(self.rep_a).browse(1)
        for kpi in self._kpis(self.rep_a).values():
            with self.subTest(kpi=kpi["key"]):
                self.assertEqual(tiles[f"{kpi['key']}_available"], kpi["available"])
                if kpi["available"]:
                    self.assertAlmostEqual(tiles[f"{kpi['key']}_value"], kpi["value"])
                    action = tiles.with_context(kpi_key=kpi["key"]).action_open_kpi()
                    self.assertEqual(action["domain"], kpi["domain"])
