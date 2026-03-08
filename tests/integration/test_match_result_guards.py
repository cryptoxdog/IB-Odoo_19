"""Test 12 — Match Result State Machine & Guard Tests.

Source: plasticos_matching/models/match_result.py
Risk: HIGH — Data integrity. Match results drive offer creation.

Validates:
  - action_accept() only from pending
  - action_reject() only from pending
  - accepted results capture reviewer + timestamp
  - rejected results capture reviewer + timestamp
  - state selection values are complete
  - SQL constraints (score range, uniqueness)
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "matching", "critical")
class TestMatchResultStateMachine(PlasticosTestCase):
    """State transitions on plasticos.match.result."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            cls.MatchResult = cls.env["plasticos.match.result"]
            cls.skip = False
        except KeyError:
            cls.skip = True
            return

        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "MR Test Supplier",
                "is_company": True,
            }
        )
        cls.buyer = cls.env["res.partner"].create(
            {
                "name": "MR Test Buyer",
                "is_company": True,
            }
        )

        # Create polymer and form for the intake
        Polymer = cls.env.get("plasticos.polymer")
        Form = cls.env.get("plasticos.material.form")
        polymer = Polymer.create({"name": "PP-Test"}) if Polymer else False
        form = Form.create({"name": "Regrind-Test"}) if Form else False

        cls.intake = cls.env["plasticos.intake"].create(
            {
                "partner_id": cls.supplier.id,
                "polymer_id": polymer.id if polymer else False,
                "form_id": form.id if form else False,
                "quantity_per_load_lbs": 40000,
            }
        )

    def _skip_check(self):
        if self.skip:
            self.skipTest("plasticos_matching not installed")

    def _make_match(self, **kw):
        vals = {
            "intake_id": self.intake.id,
            "buyer_partner_id": self.buyer.id,
            "score": 85.0,
            "confidence": 90.0,
            "run_id": "test-run-001",
        }
        vals.update(kw)
        return self.MatchResult.create(vals)

    # ── action_accept ────────────────────────────────────────
    def test_accept_from_pending_succeeds(self):
        self._skip_check()
        mr = self._make_match()
        self.assertEqual(mr.state, "pending")
        mr.action_accept()
        self.assertEqual(mr.state, "accepted")

    def test_accept_sets_reviewer_and_date(self):
        self._skip_check()
        mr = self._make_match()
        mr.action_accept()
        self.assertEqual(mr.reviewed_by.id, self.env.uid)
        self.assertTrue(mr.reviewed_date)

    def test_accept_from_accepted_raises(self):
        self._skip_check()
        mr = self._make_match()
        mr.action_accept()
        with self.assertRaises(UserError):
            mr.action_accept()

    def test_accept_from_rejected_raises(self):
        self._skip_check()
        mr = self._make_match()
        mr.action_reject()
        with self.assertRaises(UserError):
            mr.action_accept()

    def test_accept_from_expired_raises(self):
        self._skip_check()
        mr = self._make_match(state="expired")
        with self.assertRaises(UserError):
            mr.action_accept()

    # ── action_reject ────────────────────────────────────────
    def test_reject_from_pending_succeeds(self):
        self._skip_check()
        mr = self._make_match()
        mr.action_reject()
        self.assertEqual(mr.state, "rejected")

    def test_reject_sets_reviewer_and_date(self):
        self._skip_check()
        mr = self._make_match()
        mr.action_reject()
        self.assertEqual(mr.reviewed_by.id, self.env.uid)
        self.assertTrue(mr.reviewed_date)

    def test_reject_from_accepted_raises(self):
        self._skip_check()
        mr = self._make_match()
        mr.action_accept()
        with self.assertRaises(UserError):
            mr.action_reject()

    # ── State values ─────────────────────────────────────────
    def test_state_selection_values_complete(self):
        self._skip_check()
        f = self.MatchResult._fields["state"]
        values = [s[0] for s in f.selection]
        for expected in ("pending", "accepted", "rejected", "expired"):
            self.assertIn(expected, values, f"Missing match result state: {expected}")

    # ── Constraints ──────────────────────────────────────────
    def test_score_range_constraint_lower(self):
        """Score < 0 violates SQL constraint."""
        self._skip_check()
        with self.assertRaises((UserError, ValidationError)):
            self._make_match(score=-1.0)

    def test_score_range_constraint_upper(self):
        """Score > 100 violates SQL constraint."""
        self._skip_check()
        with self.assertRaises((UserError, ValidationError)):
            self._make_match(score=101.0)

    def test_confidence_range_constraint(self):
        self._skip_check()
        with self.assertRaises((UserError, ValidationError)):
            self._make_match(confidence=-5.0)

    def test_uniqueness_constraint(self):
        """Same intake + buyer + run_id should fail."""
        self._skip_check()
        self._make_match(run_id="dup-run")
        with self.assertRaises((UserError, ValidationError)):
            self._make_match(run_id="dup-run")

    # ── Display name ─────────────────────────────────────────
    def test_display_name_format(self):
        self._skip_check()
        mr = self._make_match()
        self.assertIn("→", mr.display_name)
        self.assertIn("85", mr.display_name)
