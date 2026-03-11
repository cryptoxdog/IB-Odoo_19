"""State machine tests for plasticos.match.result.

States: pending → accepted | rejected | expired

Source: plasticos_matching/models/match_result.py
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

# Odoo 19 may use psycopg3; handle both
try:
    from psycopg2 import IntegrityError
except ImportError:
    from psycopg import IntegrityError


@tagged("post_install", "-at_install")
class TestMatchResultStateMachine(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Result = cls.env["plasticos.match.result"]
        cls.supplier = cls.env["res.partner"].create({"name": "Match Supplier"})
        cls.buyer = cls.env["res.partner"].create({"name": "Match Buyer"})
        cls.intake = cls.env["plasticos.intake"].create(
            {
                "partner_id": cls.supplier.id,
                "quantity_per_load_lbs": 1000.0,
                "loads_per_month": 1,
            }
        )

    def _result(self, **kw):
        vals = {
            "intake_id": self.intake.id,
            "buyer_partner_id": self.buyer.id,
            "score": 85.0,
            "confidence": 90.0,
            "run_id": "RUN-001",
        }
        vals.update(kw)
        return self.Result.create(vals)

    # ── Initial state ────────────────────────────────────────
    def test_create_defaults_to_pending(self):
        result = self._result()
        self.assertEqual(result.state, "pending")

    def test_display_name_format(self):
        result = self._result()
        self.assertIn("→", result.display_name)
        self.assertIn("85%", result.display_name)

    # ── pending → accepted ───────────────────────────────────
    def test_accept_from_pending(self):
        result = self._result()
        result.action_accept()
        self.assertEqual(result.state, "accepted")
        self.assertTrue(result.reviewed_by)
        self.assertTrue(result.reviewed_date)

    def test_accept_from_non_pending_raises(self):
        result = self._result()
        result.action_accept()
        with self.assertRaises(UserError):
            result.action_accept()

    def test_accept_rejected_raises(self):
        result = self._result()
        result.action_reject()
        with self.assertRaises(UserError):
            result.action_accept()

    # ── pending → rejected ───────────────────────────────────
    def test_reject_from_pending(self):
        result = self._result()
        result.action_reject()
        self.assertEqual(result.state, "rejected")
        self.assertTrue(result.reviewed_by)
        self.assertTrue(result.reviewed_date)

    def test_reject_from_accepted_raises(self):
        result = self._result()
        result.action_accept()
        with self.assertRaises(UserError):
            result.action_reject()

    # ── Batch operations ─────────────────────────────────────
    def test_batch_accept(self):
        r1 = self._result(run_id="BATCH-1")
        r2 = self._result(run_id="BATCH-2")
        (r1 | r2).action_accept()
        self.assertEqual(r1.state, "accepted")
        self.assertEqual(r2.state, "accepted")

    def test_batch_reject(self):
        r1 = self._result(run_id="BATCH-3")
        r2 = self._result(run_id="BATCH-4")
        (r1 | r2).action_reject()
        self.assertEqual(r1.state, "rejected")
        self.assertEqual(r2.state, "rejected")

    # ── SQL constraints ──────────────────────────────────────
    def test_score_range_constraint(self):
        with self.assertRaises((ValidationError, UserError, IntegrityError)):
            with self.env.cr.savepoint():
                self._result(score=101.0)

    def test_confidence_range_constraint(self):
        with self.assertRaises((ValidationError, UserError, IntegrityError)):
            with self.env.cr.savepoint():
                self._result(confidence=-1.0)

    def test_unique_match_per_run(self):
        self._result(run_id="UNIQ-1")
        with self.assertRaises((ValidationError, UserError, IntegrityError)):
            with self.env.cr.savepoint():
                self._result(run_id="UNIQ-1")
