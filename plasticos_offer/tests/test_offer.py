from datetime import timedelta

from psycopg.errors import IntegrityError

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestPlasticosOffer(PlasticosTestCase):
    """Test suite for plasticos.offer"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Offer = cls.env["plasticos.offer"]
        cls.Partner = cls.env["res.partner"]
        cls.Intake = cls.env["plasticos.intake"]

        # Create test partners
        cls.supplier = cls.Partner.create({"name": "Test Supplier", "is_company": True, "supplier_rank": 1})
        cls.buyer = cls.Partner.create({"name": "Test Buyer", "is_company": True, "customer_rank": 1})

        # Create test intake
        cls.intake = cls.Intake.create(
            {
                "partner_id": cls.supplier.id,
                "quantity_lbs": 40000,
            }
        )

    def _create_offer(self, **kwargs):
        """Helper to create plasticos.offer with defaults"""
        vals = {
            "intake_id": self.intake.id,
            "supplier_id": self.supplier.id,
            "buyer_id": self.buyer.id,
            "price_per_lb": 0.25,
            "quantity_lbs": 40000,
            "valid_until": fields.Date.today() + timedelta(days=30),
        }
        vals.update(kwargs)
        return self.Offer.create(vals)

    # ========================================================================
    # CREATION TESTS
    # ========================================================================

    def test_create_basic(self):
        """Test basic record creation"""
        record = self._create_offer()
        self.assertTrue(record.exists())
        self.assertEqual(record.intake_id, self.intake)
        self.assertEqual(record.supplier_id, self.supplier)
        self.assertEqual(record.buyer_id, self.buyer)
        self.assertEqual(record.state, "draft")

    def test_create_with_match_result(self):
        """Test creation with match_result_id"""
        if "plasticos.match.result" in self.env:
            match = self.env["plasticos.match.result"].create(
                {
                    "intake_id": self.intake.id,
                    "buyer_partner_id": self.buyer.id,
                    "score": 0.85,
                }
            )
            offer = self._create_offer(match_result_id=match.id)
            self.assertEqual(offer.match_result_id, match)

    # ========================================================================
    # ACTION TESTS
    # ========================================================================

    def test_action_send_sets_sent(self):
        """Test action_send moves draft → sent"""
        offer = self._create_offer(state="draft")
        offer.action_send()
        self.assertEqual(offer.state, "sent")

    def test_action_mark_responded_sets_responded(self):
        """Test action_mark_responded moves sent → responded"""
        offer = self._create_offer(state="sent")
        offer.action_mark_responded()
        self.assertEqual(offer.state, "responded")

    def test_action_accept_sets_accepted(self):
        """Test action_accept moves responded → accepted"""
        offer = self._create_offer(state="responded")
        offer.action_accept()
        self.assertEqual(offer.state, "accepted")

    def test_action_reject_sets_rejected(self):
        """Test action_reject moves responded → rejected"""
        offer = self._create_offer(state="responded")
        offer.action_reject()
        self.assertEqual(offer.state, "rejected")

    def test_action_cancel_sets_cancelled(self):
        """Test action_cancel moves to cancelled"""
        offer = self._create_offer(state="draft")
        offer.action_cancel()
        self.assertEqual(offer.state, "cancelled")

    def test_action_reset_to_draft(self):
        """Test action_reset_to_draft moves cancelled → draft"""
        offer = self._create_offer(state="cancelled")
        offer.action_reset_to_draft()
        self.assertEqual(offer.state, "draft")

    def test_action_view_intake_returns_action(self):
        """Test action_view_intake returns window action"""
        offer = self._create_offer()
        result = offer.action_view_intake()
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "plasticos.intake")

    def test_action_view_supplier_returns_action(self):
        """Test action_view_supplier returns window action"""
        offer = self._create_offer()
        result = offer.action_view_supplier()
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "res.partner")

    def test_action_view_buyer_returns_action(self):
        """Test action_view_buyer returns window action"""
        offer = self._create_offer()
        result = offer.action_view_buyer()
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "res.partner")

    # ========================================================================
    # COMPUTED FIELD TESTS
    # ========================================================================

    def test_total_value_computed(self):
        """Test total_value = price_per_lb * quantity_lbs"""
        offer = self._create_offer(price_per_lb=0.50, quantity_lbs=10000)
        self.assertEqual(offer.total_value, 5000.0)

    def test_days_until_expiry_positive(self):
        """Test days_until_expiry is positive for future date"""
        offer = self._create_offer(valid_until=fields.Date.today() + timedelta(days=10))
        self.assertGreaterEqual(offer.days_until_expiry, 9)

    # ========================================================================
    # CONSTRAINT TESTS
    # ========================================================================

    def test_constraint_intake_id_required(self):
        """Test intake_id is required"""
        with self.assertRaises((ValidationError, IntegrityError)):
            with self.env.cr.savepoint():
                self.Offer.create(
                    {
                        "supplier_id": self.supplier.id,
                        "buyer_id": self.buyer.id,
                        "price_per_lb": 0.25,
                    }
                )

    def test_constraint_supplier_id_required(self):
        """Test supplier_id is required"""
        with self.assertRaises((ValidationError, IntegrityError)):
            with self.env.cr.savepoint():
                self.Offer.create(
                    {
                        "intake_id": self.intake.id,
                        "buyer_id": self.buyer.id,
                        "price_per_lb": 0.25,
                    }
                )

    def test_constraint_buyer_id_required(self):
        """Test buyer_id is required"""
        with self.assertRaises((ValidationError, IntegrityError)):
            with self.env.cr.savepoint():
                self.Offer.create(
                    {
                        "intake_id": self.intake.id,
                        "supplier_id": self.supplier.id,
                        "price_per_lb": 0.25,
                    }
                )

    def test_constraint_negative_price_raises(self):
        """Test negative price_per_lb raises error"""
        raised = False
        try:
            self._create_offer(price_per_lb=-1.0)
        except (ValidationError, UserError):
            raised = True
        self.assertTrue(raised, "Expected exception was not raised")
