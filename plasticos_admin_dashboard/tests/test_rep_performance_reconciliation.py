"""Rep-performance measures reconcile with their source rows (AC-011, F-002).

Fixture: one rep with 2 closed deals (10k, 20k), 3 open deals (5k each) and
2 intakes with 2 offers each. Before the rewrite the joined rows multiplied
money by the join cardinality (360k closed, 120k pipeline) and deals_open
counted users (1).
"""

from datetime import timedelta

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged

_BYPASS = {"bypass_state_guard": True}


@tagged("post_install", "-at_install")
class TestRepPerformanceReconciliation(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.transaction", "plasticos.intake", "plasticos.offer")
        cls.rep = cls.env["res.users"].create({"name": "Reconciliation Rep", "login": "reconciliation.rep@example.com"})
        cls.supplier = cls._create_partner("Reconciliation Supplier", supplier_rank=1)
        cls.buyer = cls._create_partner("Reconciliation Buyer", customer_rank=1)
        Tx = cls.env["plasticos.transaction"].with_context(**_BYPASS)
        for state, revenue in [("closed", 10000.0), ("closed", 20000.0)] + [("active", 5000.0)] * 3:
            tx = Tx.create({"user_id": cls.rep.id})
            tx.write({"state": state})
            vals = {"revenue_total": revenue}
            if state == "closed":
                # DEC-002: a closed deal's period is its commission_earned_date.
                vals["commission_earned_date"] = fields.Date.context_today(tx)
            tx.write(vals)
        for _intake in range(2):
            intake = cls._create_intake(
                partner=cls.supplier,
                polymer=cls.default_polymer,
                form=cls.default_form,
                assigned_user_id=cls.rep.id,
            )
            for _offer in range(2):
                cls.env["plasticos.offer"].create(
                    {
                        "intake_id": intake.id,
                        "supplier_id": cls.supplier.id,
                        "buyer_id": cls.buyer.id,
                        "price_per_lb": 0.25,
                        "quantity_lbs": 40000,
                        "valid_until": fields.Date.today() + timedelta(days=30),
                    }
                )
        cls.env.flush_all()
        cls.env["plasticos.rep.performance"].init()

    def _row(self, period):
        rows = self.env["plasticos.rep.performance"].search(
            [("salesperson_id", "=", self.rep.id), ("period", "=", period)]
        )
        self.assertEqual(len(rows), 1)
        return rows

    def test_measures_are_not_multiplied_by_join_cardinality(self):
        for period in ("MTD", "YTD"):
            with self.subTest(period=period):
                row = self._row(period)
                self.assertEqual(row.deals_closed, 2)
                self.assertAlmostEqual(row.revenue_closed, 30000.0, places=2)
                self.assertEqual(row.deals_open, 3)
                self.assertAlmostEqual(row.pipeline_val, 15000.0, places=2)
                self.assertEqual(row.intakes_created, 2)

    def test_open_pipeline_is_the_same_snapshot_in_every_period(self):
        values = {
            (row.deals_open, row.pipeline_val)
            for row in self.env["plasticos.rep.performance"].search([("salesperson_id", "=", self.rep.id)])
        }
        self.assertEqual(values, {(3, 15000.0)})

    def test_historical_erp_closed_deal_is_excluded(self):
        historical = self.env["plasticos.transaction"].with_context(**_BYPASS).create({"user_id": self.rep.id})
        historical.write({"state": "closed"})
        historical.write(
            {
                "revenue_total": 99000.0,
                "legacy_erp_history": True,
                "commission_earned_date": fields.Date.context_today(historical),
            }
        )
        self.env.flush_all()
        self.assertAlmostEqual(self._row("YTD").revenue_closed, 30000.0, places=2)
