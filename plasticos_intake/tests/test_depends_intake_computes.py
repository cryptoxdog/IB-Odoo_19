from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestIntakeComputesDepends(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Intake = cls.env["plasticos.intake"]
        cls.partner = cls.env["res.partner"].create({"name": "Compute Co"})

    def _intake(self, **vals):
        base = {
            "partner_id": self.partner.id,
            "quantity_per_load_lbs": 1000.0,
            "loads_per_month": 2,
        }
        base.update(vals)
        return self.Intake.create(base)

    def test_match_score_computed_from_lines(self):
        intake = self._intake()
        line = self.env["plasticos.intake.match.line"].create(
            {
                "intake_id": intake.id,
                "match_score": 80,
            }
        )
        intake.invalidate_recordset()
        self.assertEqual(intake.best_match_score, 80)
        line.write({"match_score": 90})
        intake.invalidate_recordset()
        self.assertEqual(intake.best_match_score, 90)

    def test_monthly_quantity_computed(self):
        intake = self._intake()
        self.assertGreater(intake.total_monthly_quantity_lbs, 0.0)
