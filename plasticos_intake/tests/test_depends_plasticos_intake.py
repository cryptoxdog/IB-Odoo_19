from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestIntakeDepends(TransactionCase):
    """Intake @api.depends computations."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Intake = cls.env["plasticos.intake"]
        cls.Line = cls.env["plasticos.intake.match.line"]
        cls.partner = cls.env["res.partner"].create({"name": "Intake Partner"})

    def _intake(self, **vals):
        base = {
            "partner_id": self.partner.id,
            "quantity_per_load_lbs": 1000.0,
            "loads_per_month": 2,
        }
        base.update(vals)
        return self.Intake.create(base)

    def test_best_match_score(self):
        intake = self._intake()
        l1 = self.Line.create({"intake_id": intake.id, "match_score": 60})
        l2 = self.Line.create({"intake_id": intake.id, "match_score": 90})
        intake.invalidate_recordset()
        self.assertEqual(intake.best_match_score, 90)

    def test_match_counts(self):
        intake = self._intake()
        self.Line.create({"intake_id": intake.id, "match_score": 60, "is_selected": True})
        self.Line.create({"intake_id": intake.id, "match_score": 40, "is_selected": False})
        intake.invalidate_recordset()
        self.assertEqual(intake.match_count, 2)
        self.assertEqual(intake.selected_count, 1)

    def test_total_monthly_quantity(self):
        intake = self._intake(quantity_per_load_lbs=2000.0, loads_per_month=3)
        self.assertEqual(intake.total_monthly_quantity_lbs, 6000.0)

    def test_name_and_company_display(self):
        intake = self._intake()
        self.assertTrue(intake.name)
        self.assertTrue(intake.company_display)
