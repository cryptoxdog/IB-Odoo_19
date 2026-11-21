"""Closed-deal periods use the business date, not write_date (AC-012, DEC-002, N-001).

A closed deal earned last year and edited today stays in last year: it is not
counted in this month's or this year's closed-deal figures, in the KPI record
or in the rep view. Transaction-based KPIs say they are operational closed-deal
figures with their source date, never accounting revenue.
"""

from datetime import date

from odoo import fields
from odoo.tests import TransactionCase, tagged

_BYPASS = {"bypass_state_guard": True}

_TRANSACTION_PERIOD_FIELDS = (
    "tx_closed_mtd",
    "revenue_mtd",
    "revenue_ytd",
    "gm_mtd",
    "gm_ytd",
    "gm_pct_mtd",
    "gm_pct_ytd",
    "net_margin_mtd",
    "net_margin_ytd",
    "commission_mtd",
    "commission_ytd",
)
_REP_PERIOD_FIELDS = ("deals_closed", "revenue_closed", "gm_closed", "net_margin", "commission")


@tagged("post_install", "-at_install")
class TestClosedDealPeriod(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.kpi = cls.env["plasticos.admin.kpi"]._get_or_create()
        cls.buyer = cls.env["res.partner"].create({"name": "Period Buyer", "customer_rank": 1})
        cls.rep = cls.env["res.users"].create({"name": "Period Rep", "login": "period.rep@example.com"})

    def _closed(self, revenue, earned_on):
        order = self.env["sale.order"].create({"partner_id": self.buyer.id, "company_id": self.env.company.id})
        tx = self.env["plasticos.transaction"].create({"user_id": self.rep.id, "sale_order_id": order.id})
        tx.with_context(**_BYPASS).write({"state": "closed"})
        tx.write({"revenue_total": revenue, "commission_earned_date": earned_on})
        return tx

    def _kpi(self, name):
        self.kpi.invalidate_recordset()
        return self.kpi[name]

    def test_editing_an_old_closed_deal_keeps_it_in_its_period(self):
        before = {name: self._kpi(name) for name in ("tx_closed_mtd", "revenue_mtd", "revenue_ytd")}
        today = fields.Date.context_today(self.kpi)
        self._closed(1000.0, today)
        old = self._closed(5000.0, date(today.year - 1, 6, 1))
        old.write({"supplier_not_ready_reason": "edited today"})
        self.env.flush_all()

        self.assertEqual(self._kpi("tx_closed_mtd"), before["tx_closed_mtd"] + 1)
        self.assertAlmostEqual(self._kpi("revenue_mtd"), before["revenue_mtd"] + 1000.0, places=2)
        self.assertAlmostEqual(self._kpi("revenue_ytd"), before["revenue_ytd"] + 1000.0, places=2)

        self.env["plasticos.rep.performance"].init()
        ytd = self.env["plasticos.rep.performance"].search(
            [("salesperson_id", "=", self.rep.id), ("period", "=", "YTD")]
        )
        self.assertEqual(ytd.deals_closed, 1)
        self.assertAlmostEqual(ytd.revenue_closed, 1000.0, places=2)

    def test_transaction_figures_name_their_source_date_and_are_not_accounting_revenue(self):
        for model_name, names in (
            ("plasticos.admin.kpi", _TRANSACTION_PERIOD_FIELDS),
            ("plasticos.rep.performance", _REP_PERIOD_FIELDS),
        ):
            model_fields = self.env[model_name]._fields
            for name in names:
                with self.subTest(field=f"{model_name}.{name}"):
                    help_text = model_fields[name].help or ""
                    self.assertIn("commission_earned_date", help_text)
                    self.assertIn("Not accounting-recognized revenue", help_text)
                    self.assertNotEqual(model_fields[name].string.strip().lower(), "revenue")
