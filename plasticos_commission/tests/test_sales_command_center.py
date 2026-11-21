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
        Tx = cls.env["plasticos.transaction"]
        cls.own = Tx.create([{"user_id": cls.rep_a.id} for _index in range(3)])
        cls.own[0].write({"supplier_confirmation_received": fields.Datetime.now()})
        cls.foreign = Tx.create([{"user_id": cls.rep_b.id} for _index in range(2)])
        for tx in cls.own | cls.foreign:
            if tx.state in ("draft", "closed", "cancelled"):
                tx.write({"state": "active"})
        if "crm.lead" in cls.env:
            Lead = cls.env["crm.lead"]
            Lead.create({"name": "A opp", "type": "opportunity", "user_id": cls.rep_a.id})
            Lead.create({"name": "B opp", "type": "opportunity", "user_id": cls.rep_b.id})
        cls.env.flush_all()

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
