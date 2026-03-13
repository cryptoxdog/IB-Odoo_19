"""
Test claim constraints.

- unique name SQL constraint
- resolution_note required on resolve
"""

from psycopg.errors import IntegrityError

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestClaimConstraints(PlasticosTestCase):
    """Test plasticos.claim constraints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier = cls.env["res.partner"].create({"name": "Constraint Test Supplier", "is_company": True})
        cls.buyer = cls.env["res.partner"].create({"name": "Constraint Test Buyer", "is_company": True})
        cls.tx = cls.env["plasticos.transaction"].create({"supplier_id": cls.supplier.id, "buyer_id": cls.buyer.id})

    def _create_claim(self, **kwargs):
        """Helper to create a claim with defaults."""
        vals = {
            "transaction_id": self.tx.id,
            "case_type": "buyer_claim",
            "severity": "medium",
        }
        vals.update(kwargs)
        return self.env["plasticos.claim"].create(vals)

    # ═══════════════════════════════════════════════════════════
    # Unique Name Constraint Tests
    # ═══════════════════════════════════════════════════════════

    def test_unique_name_constraint(self):
        """Claim name must be unique (SQL constraint)."""
        claim1 = self._create_claim()
        claim1_name = claim1.name

        # Try to create another with the same name
        with self.assertRaises(IntegrityError):
            self.env.cr.execute(
                """
                INSERT INTO plasticos_claim (name, transaction_id, case_type, severity, state)
                VALUES (%s, %s, %s, %s, %s)
            """,
                (claim1_name, self.tx.id, "buyer_claim", "medium", "pending"),
            )

    def test_name_auto_generated(self):
        """Claim name should be auto-generated from sequence."""
        claim = self._create_claim(name="New")
        self.assertNotEqual(claim.name, "New")
        self.assertTrue(claim.name)

    # ═══════════════════════════════════════════════════════════
    # Resolution Note Constraint Tests
    # ═══════════════════════════════════════════════════════════

    def test_resolution_note_required_on_resolve(self):
        """resolution_note is required when resolving a claim."""
        claim = self._create_claim()
        claim.action_start()

        # Try to resolve without resolution_note
        with self.assertRaises(UserError):
            claim.action_resolve()

    def test_resolution_note_not_required_on_other_states(self):
        """resolution_note is not required for other state transitions."""
        claim = self._create_claim()

        # Should not raise
        claim.action_start()
        self.assertEqual(claim.state, "in_progress")

        # Escalate without resolution_note
        claim.action_escalate()
        self.assertEqual(claim.state, "escalated")

    def test_resolution_note_can_be_empty_string_initially(self):
        """resolution_note can be empty when claim is created."""
        claim = self._create_claim(resolution_note="")
        self.assertEqual(claim.resolution_note, "")

    def test_resolution_note_preserved_after_resolve(self):
        """resolution_note should be preserved after resolution."""
        claim = self._create_claim()
        claim.action_start()
        claim.write({"resolution_note": "Replaced defective material."})
        claim.action_resolve()

        self.assertEqual(claim.resolution_note, "Replaced defective material.")
        self.assertEqual(claim.state, "resolved")
