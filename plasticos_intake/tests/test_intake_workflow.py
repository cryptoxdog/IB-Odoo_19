"""Unit tests for plasticos.intake workflow.

Tests cover:
- Record creation and computed name
- Status workflow transitions (draft → matched → offer_sent → processing → won/lost/expired)
- Status guard enforcement (invalid transitions raise UserError)
- Constraint validation (quantity, loads_per_month)
- Computed fields (has_residue, match_count, best_match_score, company_display)
- Reset to draft behavior
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestIntakeWorkflow(PlasticosTestCase):
    """Test intake status transitions and computed fields."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.polymer_hdpe = cls.env["plasticos.polymer"].create(
            {
                "name": "HDPE",
                "code": "hdpe_test_intake",
                "full_name": "High-Density Polyethylene",
                "category": "commodity",
            }
        )
        cls.form_bales = cls.env["plasticos.material.form"].create(
            {
                "name": "Bales",
                "code": "bales_test_intake",
            }
        )
        cls.color_natural = cls.env["plasticos.material.color"].create(
            {
                "name": "Natural",
                "code": "natural_test_intake",
            }
        )
        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "Test Intake Supplier Co",
                "is_company": True,
                "supplier_rank": 1,
            }
        )
        cls.buyer = cls.env["res.partner"].create(
            {
                "name": "Test Intake Buyer Co",
                "is_company": True,
                "customer_rank": 1,
            }
        )
        cls.intake = cls.env["plasticos.intake"].create(
            {
                "partner_id": cls.supplier.id,
                "polymer_id": cls.polymer_hdpe.id,
                "form_id": cls.form_bales.id,
                "color_id": cls.color_natural.id,
                "quantity_per_load_lbs": 40000,
                "loads_per_month": 2,
            }
        )

    # ── Creation & Computed Name ────────────────────────────────

    def test_intake_created_in_draft(self):
        """New intakes default to draft status."""
        self.assertEqual(self.intake.status, "draft")

    def test_computed_name_includes_partner_and_polymer(self):
        """Auto-name includes company name and polymer."""
        self.assertIn("Test Intake Supplier Co", self.intake.name)
        self.assertIn("HDPE", self.intake.name)

    def test_computed_name_pending_company(self):
        """Auto-name shows [PENDING] for web lead intakes."""
        pending = self.env["plasticos.intake"].create(
            {
                "pending_company_name": "Acme Recyclers",
                "polymer_id": self.polymer_hdpe.id,
                "quantity_per_load_lbs": 20000,
            }
        )
        self.assertIn("[PENDING]", pending.name)
        self.assertIn("Acme Recyclers", pending.name)

    def test_company_display_partner(self):
        """company_display shows partner name when set."""
        self.assertEqual(self.intake.company_display, "Test Intake Supplier Co")

    def test_company_display_pending(self):
        """company_display shows pending name with indicator when no partner."""
        pending = self.env["plasticos.intake"].create(
            {
                "pending_company_name": "Pending Corp",
                "quantity_per_load_lbs": 10000,
            }
        )
        self.assertIn("Pending Corp", pending.company_display)

    # ── Status Workflow — Happy Path ────────────────────────────

    def test_draft_to_offer_sent_blocked(self):
        """Cannot jump from draft to offer_sent (must be matched first)."""
        with self.assertRaises(UserError):
            self.intake.action_send_offer()

    def test_matched_to_offer_sent(self):
        """matched → offer_sent via action_send_offer."""
        self.intake.status = "matched"
        self.intake.action_send_offer()
        self.assertEqual(self.intake.status, "offer_sent")

    def test_offer_sent_to_processing(self):
        """offer_sent → processing via action_mark_processing."""
        self.intake.status = "offer_sent"
        self.intake.action_mark_processing()
        self.assertEqual(self.intake.status, "processing")

    def test_processing_to_won(self):
        """processing → won via action_mark_won."""
        self.intake.status = "processing"
        self.intake.action_mark_won()
        self.assertEqual(self.intake.status, "won")

    def test_offer_sent_to_won(self):
        """offer_sent → won (skip processing)."""
        self.intake.status = "offer_sent"
        self.intake.action_mark_won()
        self.assertEqual(self.intake.status, "won")

    def test_any_to_lost(self):
        """Any status → lost via action_mark_lost (no guard)."""
        self.intake.status = "matched"
        self.intake.action_mark_lost()
        self.assertEqual(self.intake.status, "lost")

    def test_any_to_expired(self):
        """Any status → expired via action_mark_expired (no guard)."""
        self.intake.status = "draft"
        self.intake.action_mark_expired()
        self.assertEqual(self.intake.status, "expired")

    # ── Status Guards — Blocked Transitions ─────────────────────

    def test_send_offer_from_draft_blocked(self):
        """action_send_offer requires matched status."""
        self.intake.status = "draft"
        with self.assertRaises(UserError):
            self.intake.action_send_offer()

    def test_mark_processing_from_draft_blocked(self):
        """action_mark_processing requires offer_sent status."""
        self.intake.status = "draft"
        with self.assertRaises(UserError):
            self.intake.action_mark_processing()

    def test_mark_won_from_draft_blocked(self):
        """action_mark_won requires offer_sent or processing."""
        self.intake.status = "draft"
        with self.assertRaises(UserError):
            self.intake.action_mark_won()

    # ── Reset to Draft ──────────────────────────────────────────

    def test_reset_to_draft_clears_matches(self):
        """Reset to draft clears match lines and resets status."""
        self.env["plasticos.intake.match"].create(
            {
                "intake_id": self.intake.id,
                "buyer_id": self.buyer.id,
                "match_score": 85.0,
            }
        )
        self.intake.status = "matched"
        self.intake.action_reset_to_draft()
        self.assertEqual(self.intake.status, "draft")
        self.assertEqual(len(self.intake.match_line_ids), 0)

    def test_reset_from_won_blocked(self):
        """Cannot reset a Won intake."""
        self.intake.status = "won"
        with self.assertRaises(UserError):
            self.intake.action_reset_to_draft()

    # ── Constraints ─────────────────────────────────────────────

    def test_zero_quantity_raises(self):
        """quantity_per_load_lbs must be positive."""
        with self.assertRaises(ValidationError):
            self.env["plasticos.intake"].create(
                {
                    "partner_id": self.supplier.id,
                    "polymer_id": self.polymer_hdpe.id,
                    "quantity_per_load_lbs": 0,
                }
            )

    def test_negative_loads_raises(self):
        """loads_per_month cannot be negative."""
        with self.assertRaises(ValidationError):
            self.env["plasticos.intake"].create(
                {
                    "partner_id": self.supplier.id,
                    "polymer_id": self.polymer_hdpe.id,
                    "quantity_per_load_lbs": 40000,
                    "loads_per_month": -1,
                }
            )

    # ── Computed Fields ─────────────────────────────────────────

    def test_has_residue_true_when_contamination(self):
        """has_residue auto-computed from contamination_pct > 0."""
        self.intake.contamination_pct = 2.5
        self.assertTrue(self.intake.has_residue)

    def test_has_residue_false_when_clean(self):
        """has_residue is False when contamination_pct is 0."""
        self.intake.contamination_pct = 0
        self.assertFalse(self.intake.has_residue)

    def test_match_count_computed(self):
        """match_count reflects number of match lines."""
        self.env["plasticos.intake.match"].create(
            {
                "intake_id": self.intake.id,
                "buyer_id": self.buyer.id,
                "match_score": 90.0,
            }
        )
        self.intake.invalidate_recordset()
        self.assertEqual(self.intake.match_count, 1)

    def test_best_match_score(self):
        """best_match_score picks highest score."""
        buyer2 = self.env["res.partner"].create(
            {
                "name": "Buyer 2",
                "is_company": True,
                "customer_rank": 1,
            }
        )
        self.env["plasticos.intake.match"].create(
            {
                "intake_id": self.intake.id,
                "buyer_id": self.buyer.id,
                "match_score": 75.0,
            }
        )
        self.env["plasticos.intake.match"].create(
            {
                "intake_id": self.intake.id,
                "buyer_id": buyer2.id,
                "match_score": 92.0,
            }
        )
        self.intake.invalidate_recordset()
        self.assertAlmostEqual(self.intake.best_match_score, 92.0, places=1)

    def test_selected_count(self):
        """selected_count only counts selected match lines."""
        self.env["plasticos.intake.match"].create(
            {
                "intake_id": self.intake.id,
                "buyer_id": self.buyer.id,
                "match_score": 80.0,
                "selected": True,
            }
        )
        buyer2 = self.env["res.partner"].create(
            {
                "name": "Buyer 3",
                "is_company": True,
                "customer_rank": 1,
            }
        )
        self.env["plasticos.intake.match"].create(
            {
                "intake_id": self.intake.id,
                "buyer_id": buyer2.id,
                "match_score": 70.0,
                "selected": False,
            }
        )
        self.intake.invalidate_recordset()
        self.assertEqual(self.intake.selected_count, 1)
