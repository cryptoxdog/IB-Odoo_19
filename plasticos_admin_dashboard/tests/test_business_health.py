"""Admin Business Health & Bottleneck Intelligence (TASK-031, AC-031 / A20, F-005).

* Every declared Admin KPI equals the aggregate of the records its drill opens (DEC-007).
* Ratios drill to their denominator set; unavailable renders "n/a", never 0.
* The stage funnel partitions open delivered work and drills to the exact transactions.
* Open exceptions drill by owner role (as the router recorded it) and by assignee.
"""

from odoo import Command, fields
from odoo.addons.plasticos_admin_dashboard.models.admin_dashboard import (
    AGG_COUNT,
    AGG_SUM,
    KPI_AGGREGATES,
    KPI_DECLARATIONS,
    RATIO_KPIS,
)
from odoo.tests import TransactionCase, tagged

_BYPASS = {"bypass_state_guard": True}
_FUNNEL = ("funnel_transaction", "funnel_shipping", "funnel_documents", "funnel_invoicing", "funnel_payment")


@tagged("post_install", "-at_install")
class TestBusinessHealth(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Kpi = cls.env["plasticos.admin.kpi"]
        cls.kpi = cls.Kpi._get_or_create()
        cls.buyer = cls.env["res.partner"].create({"name": "Health Buyer", "customer_rank": 1})

    def _tx(self, state, **vals):
        order = self.env["sale.order"].create({"partner_id": self.buyer.id, "company_id": self.env.company.id})
        tx = self.env["plasticos.transaction"].create({"user_id": self.env.user.id, "sale_order_id": order.id})
        tx.with_context(**_BYPASS).write({"state": state})
        if vals:
            tx.write(vals)
        return tx

    def _read(self, name):
        self.kpi.invalidate_recordset()
        return self.kpi[name]

    def _drill_records(self, kpi_name):
        action = self.kpi.with_context(kpi=kpi_name).action_open_kpi()
        return self.env[action["res_model"]].search(action["domain"])

    def _expected(self, kpi_name, records):
        aggregate = KPI_AGGREGATES.get(kpi_name, (AGG_COUNT,))
        if aggregate[0] == AGG_COUNT:
            return len(records)
        if aggregate[0] == AGG_SUM:
            return sum(records.mapped(aggregate[1]))
        now = fields.Datetime.now()
        return round(sum((now - r[aggregate[1]]).total_seconds() / 86400 for r in records) / len(records), 1)

    def test_every_declared_kpi_equals_its_drill(self):
        for kpi_name, (_title, model_name, _builder) in KPI_DECLARATIONS.items():
            with self.subTest(kpi=kpi_name):
                available_flag = f"{kpi_name}_available"
                if available_flag in self.kpi._fields and not self._read(available_flag):
                    self.assertEqual(self._read(kpi_name), 0)
                    continue
                action = self.kpi.with_context(kpi=kpi_name).action_open_kpi()
                self.assertEqual(action["res_model"], model_name)
                records = self.env[model_name].search(action["domain"])
                self.assertAlmostEqual(self._read(kpi_name), self._expected(kpi_name, records), places=1)

    def test_ratios_drill_to_their_denominator_and_are_unavailable_on_empty(self):
        for ratio, (numerator, denominators) in RATIO_KPIS.items():
            with self.subTest(ratio=ratio):
                drilled = self._drill_records(ratio)
                expected = self.env[drilled._name]
                for name in denominators:
                    expected |= self._drill_records(name)
                self.assertEqual(drilled, expected)
                denominator = sum(self._read(name) for name in denominators)
                self.assertEqual(self._read(f"{ratio}_available"), bool(denominator))
                if denominator:
                    self.assertAlmostEqual(
                        self._read(ratio), round(self._read(numerator) / denominator * 100, 1), places=1
                    )
                else:
                    self.assertEqual(self._read(ratio), 0)

    def test_linda_intervention_rate_is_unavailable_not_zero(self):
        self.assertFalse(self._read("linda_intervention_rate_available"))

    def test_every_availability_flag_renders_na_in_the_form(self):
        arch = self.Kpi.get_views([(False, "form")])["views"]["form"]["arch"]
        for name in self.kpi._fields:
            if name.endswith("_available"):
                with self.subTest(flag=name):
                    self.assertIn(f'invisible="{name}"', arch)

    def test_unknown_kpi_is_refused(self):
        with self.assertRaises(Exception):
            self.kpi.with_context(kpi="no_such_kpi").action_open_kpi()

    def test_funnel_stages_partition_and_drill_to_the_exact_transactions(self):
        invoice = self.env["account.move"].create({"move_type": "out_invoice", "partner_id": self.buyer.id})
        cases = {
            "funnel_transaction": self._tx("active"),
            "funnel_shipping": self._tx("in_transit"),
            "funnel_documents": self._tx("delivered", compliance_status="missing"),
            "funnel_invoicing": self._tx("delivered", customer_invoice_id=invoice.id),
        }
        cases["funnel_invoicing"].write({"compliance_status": "compliant"})
        drilled = {stage: self._drill_records(stage) for stage in _FUNNEL}
        for stage, tx in cases.items():
            with self.subTest(stage=stage):
                self.assertIn(tx, drilled[stage])
                for other in _FUNNEL:
                    if other != stage:
                        self.assertNotIn(tx, drilled[other])
                self.assertEqual(self._read(stage), len(drilled[stage]))

    def test_exceptions_drill_by_owner_role_and_assignee(self):
        tx = self._tx("delivered", compliance_status="missing")
        activity_type = self.env.ref("plasticos_documents.activity_type_missing_documents")
        activity = self.env["mail.activity"].create(
            {
                "activity_type_id": activity_type.id,
                "res_model_id": self.env["ir.model"]._get_id("plasticos.transaction"),
                "res_id": tx.id,
                "user_id": self.env.user.id,
                "summary": "Missing documents",
                "note": "Missing BOL. Routed to operations: transaction-level exception.",
            }
        )
        self.assertIn(activity, self._drill_records("exceptions_operations_open"))
        self.assertNotIn(activity, self._drill_records("exceptions_logistics_open"))
        self.assertEqual(
            self._read("exceptions_operations_open"), len(self._drill_records("exceptions_operations_open"))
        )

        by_owner = self.kpi.action_open_exceptions_by_owner()
        rows = self.env[by_owner["res_model"]].search(by_owner["domain"])
        self.assertIn(activity, rows)
        self.assertEqual(by_owner["context"]["group_by"][0], "user_id")
        self.assertEqual((activity.res_model, activity.res_id, activity.user_id), (tx._name, tx.id, self.env.user))

    def test_admin_without_linda_access_sees_unavailable(self):
        admin_group = self.env.ref("plasticos_security_base.group_system_admin")
        user = self.env["res.users"].create(
            {
                "name": "Health Admin",
                "login": "health.admin@example.com",
                "group_ids": [Command.set([self.env.ref("base.group_user").id, admin_group.id])],
            }
        )
        kpi = self.kpi.with_user(user)
        if self.env["plasticos.linda.approval"].with_user(user).has_access("read"):
            self.assertTrue(kpi.linda_held_mtd_available)
        else:
            self.assertFalse(kpi.linda_held_mtd_available)
            self.assertEqual(kpi.linda_held_mtd, 0)
