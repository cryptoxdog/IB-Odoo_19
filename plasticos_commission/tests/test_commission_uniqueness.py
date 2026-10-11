"""One active commission rule per sales representative."""

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCommissionUniqueness(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rep = cls.env["res.users"].create({"name": "Commission Rep", "login": "commission-rep-batch"})
        cls.other = cls.env["res.users"].create({"name": "Other Rep", "login": "commission-rep-other"})

    def _rule(self, rep, active=True):
        return self.env["plasticos.commission.rule"].create({"sales_rep_id": rep.id, "active": active})

    def test_second_active_rule_is_rejected(self):
        self._rule(self.rep)
        with self.assertRaises(ValidationError):
            self._rule(self.rep)

    def test_same_batch_duplicate_rep_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.env["plasticos.commission.rule"].create([{"sales_rep_id": self.rep.id}, {"sales_rep_id": self.rep.id}])

    def test_inactive_rule_for_the_same_rep_is_legal(self):
        self._rule(self.rep)
        inactive = self._rule(self.rep, active=False)
        self.assertFalse(inactive.active)

    def test_activating_a_second_rule_is_rejected(self):
        self._rule(self.rep)
        inactive = self._rule(self.rep, active=False)
        with self.assertRaises(ValidationError):
            inactive.active = True

    def test_reassigning_onto_an_active_rep_is_rejected(self):
        self._rule(self.rep)
        other_rule = self._rule(self.other)
        with self.assertRaises(ValidationError):
            other_rule.sales_rep_id = self.rep

    def test_distinct_reps_are_accepted(self):
        self._rule(self.rep)
        self._rule(self.other)
        self.assertEqual(
            self.env["plasticos.commission.rule"].search_count(
                [("sales_rep_id", "in", (self.rep | self.other).ids), ("active", "=", True)]
            ),
            2,
        )

    def test_database_index_rejects_a_second_active_row(self):
        self._rule(self.rep)
        with self.assertRaises(Exception), self.env.cr.savepoint():
            self.env.cr.execute(
                """
                INSERT INTO plasticos_commission_rule
                    (name, sales_rep_id, calculation_type, percentage, active)
                VALUES (%s, %s, 'percentage', 0.05, TRUE)
                """,
                ("SQL bypass", self.rep.id),
            )
