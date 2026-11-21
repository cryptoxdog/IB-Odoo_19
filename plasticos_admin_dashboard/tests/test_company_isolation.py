"""Admin KPI company isolation (AC-013, DEC-005(c), DEC-008, POS-INV-05).

Two companies with their own transactions: each company's KPI record counts
only its own transactions (company derived from the sale order), a user of
company A cannot read company B's KPI record, and a company has exactly one
KPI record.
"""

from psycopg2 import IntegrityError

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

_BYPASS = {"bypass_state_guard": True}


@tagged("post_install", "-at_install")
class TestAdminKpiCompanyIsolation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Kpi = cls.env["plasticos.admin.kpi"]
        cls.company_a = cls.env.company
        cls.company_b = cls.env["res.company"].create({"name": "Admin KPI Company B"})
        cls.buyer = cls.env["res.partner"].create({"name": "Isolation Buyer", "customer_rank": 1})
        cls.kpi_a = cls.Kpi._get_or_create(cls.company_a)
        cls.kpi_b = cls.Kpi._get_or_create(cls.company_b)
        internal = cls.env.ref("base.group_user")
        admin = cls.env.ref("plasticos_security_base.group_system_admin")
        cls.user_a = cls.env["res.users"].create(
            {
                "name": "Company A Admin",
                "login": "kpi.company.a.admin@example.com",
                "company_id": cls.company_a.id,
                "company_ids": [Command.set([cls.company_a.id])],
                "group_ids": [Command.set([internal.id, admin.id])],
            }
        )

    def _tx(self, company, state="supplier_not_ready"):
        order = self.env["sale.order"].create({"partner_id": self.buyer.id, "company_id": company.id})
        tx = self.env["plasticos.transaction"].create({"user_id": self.env.user.id, "sale_order_id": order.id})
        tx.with_context(**_BYPASS).write({"state": state})
        return tx

    def _value(self, kpi, name):
        kpi.invalidate_recordset()
        return kpi[name]

    def test_each_company_counts_only_its_own_transactions(self):
        open_a, open_b = self._value(self.kpi_a, "tx_open"), self._value(self.kpi_b, "tx_open")
        tx_a = self._tx(self.company_a)
        tx_b = self._tx(self.company_b)
        self.env.flush_all()
        self.assertEqual(self._value(self.kpi_a, "tx_open"), open_a + 1)
        self.assertEqual(self._value(self.kpi_b, "tx_open"), open_b + 1)

        drill_a = self.env["plasticos.transaction"].search(self.kpi_a._kpi_drill("tx_sup_not_ready")["domain"])
        drill_b = self.env["plasticos.transaction"].search(self.kpi_b._kpi_drill("tx_sup_not_ready")["domain"])
        self.assertIn(tx_a, drill_a)
        self.assertNotIn(tx_b, drill_a)
        self.assertIn(tx_b, drill_b)
        self.assertNotIn(tx_a, drill_b)
        self.assertEqual(self._value(self.kpi_a, "tx_sup_not_ready"), len(drill_a))
        self.assertEqual(self._value(self.kpi_b, "tx_sup_not_ready"), len(drill_b))

    def test_transaction_without_sale_order_counts_for_no_company(self):
        before = (self._value(self.kpi_a, "tx_open"), self._value(self.kpi_b, "tx_open"))
        orphan = self.env["plasticos.transaction"].create({"user_id": self.env.user.id})
        orphan.with_context(**_BYPASS).write({"state": "active"})
        self.env.flush_all()
        self.assertEqual((self._value(self.kpi_a, "tx_open"), self._value(self.kpi_b, "tx_open")), before)

    def test_company_a_user_cannot_read_company_b_record(self):
        Kpi_a = self.Kpi.with_user(self.user_a)
        self.assertEqual(Kpi_a.search([]), self.kpi_a.with_user(self.user_a))
        with self.assertRaises(AccessError):
            self.kpi_b.with_user(self.user_a).read(["last_refresh"])

    def test_open_admin_dashboard_opens_the_current_company_record(self):
        action = self.Kpi.with_company(self.company_b).action_open_admin_dashboard()
        self.assertEqual(action["res_id"], self.kpi_b.id)

    def test_one_record_per_company(self):
        self.assertEqual(self.Kpi._get_or_create(self.company_a), self.kpi_a)
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.cr.savepoint():
            self.Kpi.create({"company_id": self.company_a.id})
            self.env.flush_all()
