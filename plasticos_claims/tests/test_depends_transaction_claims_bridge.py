"""Transaction ↔ claims bridge: @api.depends recomputation contract.

Architecture note (2026-08 reconciliation): this suite previously bound to a
standalone join model ``plasticos.transaction.claim`` with ``claim_pct_of_revenue``
and ``residual_margin`` computed fields. No such model exists — the bridge lives on
``plasticos.transaction`` itself (``plasticos_claims/models/transaction_claims.py``
and ``transaction_claims_bridge.py``, both ``_inherit = "plasticos.transaction"``).

The current canonical contract this suite pins:
  - ``claim_ids``            One2many plasticos.claim (inverse transaction_id)
  - ``claim_count``          stored compute over claim_ids
  - ``has_quality_claim``    stored compute — unresolved buyer_claim/inspection
  - ``freight_chargebacks`` / ``lightweight_penalties`` are manual transaction
    amounts. Resolving or archiving a claim must not write them. A resolved
    claim is not a booked credit (operator decision 2026-10-25).
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestTransactionClaimsBridgeDepends(PlasticosTestCase):
    """Computed claim links recompute from claims. Manual recovery amounts do not."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Transaction = cls.env["plasticos.transaction"]
        cls.Claim = cls.env["plasticos.claim"]

        cls.supplier = cls._create_partner("Bridge Supplier", supplier_rank=1)
        cls.buyer = cls._create_partner("Bridge Buyer", customer_rank=1)
        cls.tx = cls.Transaction.create(
            {
                "supplier_id": cls.supplier.id,
                "buyer_id": cls.buyer.id,
                "revenue_total": 1000.0,
            }
        )

    def _create_claim(self, case_type="buyer_claim", **kw):
        vals = {
            "transaction_id": self.tx.id,
            "case_type": case_type,
            "claimed_amount": 200.0,
        }
        vals.update(kw)
        return self.Claim.create(vals)

    def test_claim_ids_and_count_track_new_claims(self):
        """claim_ids/claim_count recompute when a claim is linked."""
        before = self.tx.claim_count
        claim = self._create_claim()
        self.assertIn(claim, self.tx.claim_ids)
        self.assertEqual(self.tx.claim_count, before + 1)

    def test_has_quality_claim_set_and_cleared_by_state(self):
        """Unresolved buyer_claim raises the flag; resolving it clears the flag."""
        claim = self._create_claim(case_type="buyer_claim")
        self.assertTrue(self.tx.has_quality_claim)

        claim.write({"recovery_amount": 50.0, "resolution_note": "Settled"})
        claim.action_resolve()
        self.assertEqual(claim.state, "resolved")
        self.assertFalse(self.tx.has_quality_claim)

    def test_freight_chargeback_resolve_preserves_manual_amount(self):
        """Resolving and archiving a freight claim leaves the manual transaction amount.

        Replaces test_freight_chargeback_recovery_flows_to_transaction.
        """
        self.tx.freight_chargebacks = 40.0
        claim = self._create_claim(case_type="freight_chargeback")
        claim.write({"recovery_amount": 125.0, "resolution_note": "Carrier credit"})
        claim.action_resolve()
        self.assertEqual(claim.state, "resolved")
        self.assertAlmostEqual(claim.recovery_amount, 125.0)
        self.assertAlmostEqual(self.tx.freight_chargebacks, 40.0)
        claim.action_archive()
        self.assertEqual(claim.state, "archived")
        self.assertAlmostEqual(self.tx.freight_chargebacks, 40.0)

    def test_lightweight_penalty_resolve_preserves_manual_amount(self):
        """Resolving and archiving a lightweight claim leaves the manual transaction amount.

        Replaces test_lightweight_penalty_recovery_flows_to_transaction.
        """
        self.tx.lightweight_penalties = 40.0
        claim = self._create_claim(case_type="lightweight_penalty")
        claim.write({"recovery_amount": 75.0, "resolution_note": "Underweight credit"})
        claim.action_resolve()
        self.assertEqual(claim.state, "resolved")
        self.assertAlmostEqual(claim.recovery_amount, 75.0)
        self.assertAlmostEqual(self.tx.lightweight_penalties, 40.0)
        claim.action_archive()
        self.assertEqual(claim.state, "archived")
        self.assertAlmostEqual(self.tx.lightweight_penalties, 40.0)

    def test_unresolved_claim_does_not_change_manual_recovery(self):
        """An unresolved claim does not write the manual freight amount.

        Replaces test_unresolved_claim_contributes_no_recovery.
        """
        self.tx.freight_chargebacks = 40.0
        self._create_claim(case_type="freight_chargeback", recovery_amount=500.0)
        self.assertAlmostEqual(self.tx.freight_chargebacks, 40.0)
