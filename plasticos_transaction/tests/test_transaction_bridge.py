"""Comprehensive tests for plasticos_transaction bridge models.

Tests cover:
    - transaction_bridge.py: intake_id field and action_view_intake
    - Proper field relationships
    - Navigation action returns
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestTransactionBridge(PlasticosTestCase):
    """Tests for plasticos.transaction bridge to intake."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "plasticos.transaction" not in cls.env:
            raise cls.skipTest("plasticos.transaction not installed")
        if "plasticos.intake" not in cls.env:
            raise cls.skipTest("plasticos.intake not installed")

        cls.Transaction = cls.env["plasticos.transaction"]
        cls.Intake = cls.env["plasticos.intake"]
        cls.Partner = cls.env["res.partner"]

        cls.partner = cls.Partner.create(
            {
                "name": "Test Supplier",
                "is_company": True,
            }
        )

        if "plasticos.polymer" in cls.env:
            cls.polymer = cls.env["plasticos.polymer"].create(
                {
                    "name": "HDPE",
                    "code": "HDPE",
                }
            )
        else:
            cls.polymer = None

        if "plasticos.material.form" in cls.env:
            cls.form = cls.env["plasticos.material.form"].create(
                {
                    "name": "Pellet",
                    "code": "pellet",
                }
            )
        else:
            cls.form = None

    def _create_intake(self, **kwargs):
        """Helper to create intake with defaults."""
        vals = {
            "partner_id": self.partner_rec.id,
        }
        if self.polymer:
            vals["polymer_id"] = self.polymer.id
        if self.form:
            vals["form_id"] = self.form.id
        vals.update(kwargs)
        return self.Intake.create(vals)

    def _create_transaction(self, **kwargs):
        """Helper to create transaction with defaults."""
        vals = {
            "partner_id": self.partner_rec.id,
        }
        vals.update(kwargs)
        return self.Transaction.create(vals)

    # ═══════════════════════════════════════════════════════════════════
    # INTAKE_ID FIELD TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_intake_id_field_exists(self):
        """Test that intake_id field exists on transaction."""
        self.assertIn("intake_id", self.Transaction._fields, "Transaction should have intake_id field")

    def test_transaction_with_intake(self):
        """Test creating transaction with linked intake."""
        intake = self._create_intake()
        transaction = self._create_transaction(intake_id=intake.id)

        self.assertEqual(transaction.intake_id.id, intake.id, "Transaction should be linked to intake")

    def test_transaction_without_intake(self):
        """Test creating transaction without intake (optional field)."""
        transaction = self._create_transaction()
        self.assertFalse(transaction.intake_id, "Transaction can exist without intake")

    def test_intake_ondelete_set_null(self):
        """Test that deleting intake sets transaction.intake_id to null."""
        intake = self._create_intake()
        transaction = self._create_transaction(intake_id=intake.id)

        intake.unlink()
        transaction.invalidate_recordset()

        self.assertFalse(transaction.intake_id, "intake_id should be null after intake deletion")

    # ═══════════════════════════════════════════════════════════════════
    # ACTION_VIEW_INTAKE TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_action_view_intake_with_intake(self):
        """Test action_view_intake returns proper action dict."""
        intake = self._create_intake()
        transaction = self._create_transaction(intake_id=intake.id)

        action = transaction.action_view_intake()

        self.assertIsNotNone(action, "Action should be returned")
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "plasticos.intake")
        self.assertEqual(action["view_mode"], "form")
        self.assertEqual(action["res_id"], intake.id)

    def test_action_view_intake_without_intake(self):
        """Test action_view_intake returns None when no intake."""
        transaction = self._create_transaction()
        action = transaction.action_view_intake()
        self.assertIsNone(action, "Action should be None when no intake")

    def test_action_view_intake_name_includes_intake_name(self):
        """Test action name includes intake name."""
        intake = self._create_intake()
        transaction = self._create_transaction(intake_id=intake.id)

        action = transaction.action_view_intake()

        self.assertIn(intake.name, action["name"], "Action name should include intake name")

    # ═══════════════════════════════════════════════════════════════════
    # TRACKING TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_intake_id_tracking(self):
        """Test that intake_id field has tracking enabled."""
        field = self.Transaction._fields.get("intake_id")
        self.assertTrue(getattr(field, "tracking", False), "intake_id should have tracking enabled")

    # ═══════════════════════════════════════════════════════════════════
    # INDEX TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_intake_id_indexed(self):
        """Test that intake_id field is indexed for performance."""
        field = self.Transaction._fields.get("intake_id")
        self.assertTrue(getattr(field, "index", False), "intake_id should be indexed")

    # ═══════════════════════════════════════════════════════════════════
    # MULTIPLE TRANSACTIONS PER INTAKE
    # ═══════════════════════════════════════════════════════════════════

    def test_multiple_transactions_same_intake(self):
        """Test multiple transactions can link to same intake."""
        intake = self._create_intake()
        tx1 = self._create_transaction(intake_id=intake.id)
        tx2 = self._create_transaction(intake_id=intake.id)
        tx3 = self._create_transaction(intake_id=intake.id)

        self.assertEqual(tx1.intake_id.id, intake.id)
        self.assertEqual(tx2.intake_id.id, intake.id)
        self.assertEqual(tx3.intake_id.id, intake.id)
