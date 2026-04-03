from unittest.mock import patch
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestIntakeMatchingFlow(TransactionCase):

    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create({
            "name": "Test Supplier Co", "is_company": True, "supplier_rank": 1,
        })
        self.buyer = self.env["res.partner"].create({
            "name": "Test Buyer Co", "is_company": True, "customer_rank": 1,
        })
        self.intake = self.env["plasticos.intake"].create({
            "partner_id": self.partner.id,
            "quantity_lbs": 10000.0,
            "asking_price": 0.45,
        })

    def _mock_results(self, typical_price=0.35):
        return [{
            "buyer_id": self.buyer.id,
            "total_score": 0.82,
            "gates_passed": 10,
            "gates_total": 12,
            "gates_failed": ["lead_time", "certification"],
            "typical_price": typical_price,
        }]

    def test_todo1_action_match_creates_match_lines(self):
        """TODO #1: action_match_to_buyers() must create match_line_ids."""
        with patch.object(
            type(self.env["plasticos.buyer.matcher"]),
            "find_matches_for_supplier",
            return_value=self._mock_results(),
        ):
            self.intake.action_match_to_buyers()
        self.assertEqual(len(self.intake.match_line_ids), 1)

    def test_todo1_status_transitions_to_matched(self):
        with patch.object(
            type(self.env["plasticos.buyer.matcher"]),
            "find_matches_for_supplier",
            return_value=self._mock_results(),
        ):
            self.intake.action_match_to_buyers()
        self.assertEqual(self.intake.status, "matched")

    def test_todo1_idempotent_clears_stale_lines(self):
        """TODO #1: Re-running match must clear old lines first."""
        with patch.object(
            type(self.env["plasticos.buyer.matcher"]),
            "find_matches_for_supplier",
            return_value=self._mock_results(),
        ):
            self.intake.action_match_to_buyers()
            self.intake.action_match_to_buyers()
        self.assertEqual(len(self.intake.match_line_ids), 1)

    def test_todo2_typical_price_populated(self):
        """TODO #2: typical_price must come from match result, not be 0.0."""
        with patch.object(
            type(self.env["plasticos.buyer.matcher"]),
            "find_matches_for_supplier",
            return_value=self._mock_results(typical_price=0.38),
        ):
            self.intake.action_match_to_buyers()
        line = self.intake.match_line_ids[0]
        self.assertAlmostEqual(line.typical_price, 0.38, places=4)

    def test_todo3_send_offers_raises_if_none_selected(self):
        """TODO #3: action_send_offers() must raise if no lines selected."""
        with patch.object(
            type(self.env["plasticos.buyer.matcher"]),
            "find_matches_for_supplier",
            return_value=self._mock_results(),
        ):
            self.intake.action_match_to_buyers()
        with self.assertRaises(UserError):
            self.intake.action_send_offers()

    def test_todo3_send_offers_creates_offer_record(self):
        """TODO #3: action_send_offers() must create a plasticos.offer."""
        with patch.object(
            type(self.env["plasticos.buyer.matcher"]),
            "find_matches_for_supplier",
            return_value=self._mock_results(),
        ):
            self.intake.action_match_to_buyers()
        self.intake.match_line_ids[0].selected = True
        self.intake.action_send_offers()
        self.assertEqual(self.intake.status, "offer_sent")
        self.assertEqual(self.intake.offer_count, 1)

    def test_todo3_send_offers_idempotent(self):
        """TODO #3: Re-running send_offers must not duplicate offers."""
        with patch.object(
            type(self.env["plasticos.buyer.matcher"]),
            "find_matches_for_supplier",
            return_value=self._mock_results(),
        ):
            self.intake.action_match_to_buyers()
        self.intake.match_line_ids[0].selected = True
        self.intake.action_send_offers()
        with self.assertRaises(UserError):
            self.intake.action_send_offers()  # all lines already have offer_id

    def test_todo4_offer_count_computed(self):
        """TODO #4: offer_count must reflect created offers."""
        with patch.object(
            type(self.env["plasticos.buyer.matcher"]),
            "find_matches_for_supplier",
            return_value=self._mock_results(),
        ):
            self.intake.action_match_to_buyers()
        self.intake.match_line_ids[0].selected = True
        self.intake.action_send_offers()
        self.assertEqual(self.intake.offer_count, 1)

    def test_todo4_action_view_offers_returns_window_action(self):
        """TODO #4: action_view_offers() must return an act_window."""
        with patch.object(
            type(self.env["plasticos.buyer.matcher"]),
            "find_matches_for_supplier",
            return_value=self._mock_results(),
        ):
            self.intake.action_match_to_buyers()
        self.intake.match_line_ids[0].selected = True
        self.intake.action_send_offers()
        result = self.intake.action_view_offers()
        self.assertEqual(result.get("type"), "ir.actions.act_window")
        self.assertEqual(result.get("res_model"), "plasticos.offer")
