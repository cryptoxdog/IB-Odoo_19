from psycopg.errors import IntegrityError

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestPlasticosClaim(PlasticosTestCase):
    """Test suite for plasticos.claim"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Claim = cls.env["plasticos.claim"]
        cls.Transaction = cls.env["plasticos.transaction"]
        # Create a transaction for claims to reference
        cls.tx = cls.Transaction.create({"name": "TX-CLAIM-TEST"})

    def _create_claim(self, **kwargs):
        """Helper to create plasticos.claim with defaults"""
        vals = {
            "transaction_id": self.tx.id,
            "case_type": "buyer_claim",
            "severity": "medium",
            "state": "pending",
        }
        vals.update(kwargs)
        return self.Claim.create(vals)

    # ========================================================================
    # CREATION TESTS
    # ========================================================================

    def test_create_basic(self):
        """Test basic record creation"""
        record = self._create_claim()
        self.assertTrue(record.exists())
        self.assertEqual(record.transaction_id, self.tx)
        self.assertEqual(record.case_type, "buyer_claim")
        self.assertEqual(record.severity, "medium")
        self.assertEqual(record.state, "pending")

    def test_create_with_all_case_types(self):
        """Test creation with each valid case_type."""
        case_types = ["buyer_claim", "inspection", "freight_chargeback", "lightweight_penalty", "other"]
        for case_type in case_types:
            record = self._create_claim(case_type=case_type)
            self.assertEqual(record.case_type, case_type)

    # ========================================================================
    # ACTION TESTS
    # ========================================================================

    def test_action_start_executes_successfully(self):
        """Test action_start moves pending → in_progress"""
        record = self._create_claim(state="pending")
        record.action_start()
        self.assertEqual(record.state, "in_progress")

    def test_action_escalate_executes_successfully(self):
        """Test action_escalate moves to escalated"""
        record = self._create_claim(state="in_progress")
        record.action_escalate()
        self.assertEqual(record.state, "escalated")

    def test_action_resolve_requires_note(self):
        """Test action_resolve requires resolution_note"""
        record = self._create_claim(state="in_progress")
        raised = False
        try:
            record.action_resolve()
        except (UserError, ValidationError):
            raised = True
        self.assertTrue(raised, "Expected exception was not raised")

    def test_action_resolve_with_note(self):
        """Test action_resolve with resolution_note succeeds"""
        record = self._create_claim(state="in_progress")
        record.resolution_note = "Issue resolved via credit"
        record.action_resolve()
        self.assertEqual(record.state, "resolved")

    def test_action_archive_from_resolved(self):
        """Test action_archive moves resolved → archived"""
        record = self._create_claim(state="resolved")
        record.resolution_note = "Archived"
        record.action_archive()
        self.assertEqual(record.state, "archived")

    def test_action_reopen_from_resolved(self):
        """Test action_reopen moves resolved → in_progress"""
        record = self._create_claim(state="resolved")
        record.action_reopen()
        self.assertEqual(record.state, "in_progress")

    def test_action_view_transaction_returns_action(self):
        """Test action_view_transaction returns window action"""
        record = self._create_claim()
        result = record.action_view_transaction()
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "plasticos.transaction")

    # ========================================================================
    # CONSTRAINT TESTS
    # ========================================================================

    def test_constraint_transaction_id_required(self):
        """Test transaction_id is required"""
        with self.assertRaises((ValidationError, IntegrityError)):
            with self.env.cr.savepoint():
                self.Claim.create(
                    {
                        "case_type": "buyer_claim",
                        "severity": "medium",
                    }
                )

    def test_constraint_invalid_case_type(self):
        """Test invalid case_type raises error"""
        raised = False
        try:
            self._create_claim(case_type="invalid_type")
        except (ValidationError, ValueError):
            raised = True
        self.assertTrue(raised, "Expected exception was not raised")

    def test_constraint_invalid_severity(self):
        """Test invalid severity raises error"""
        raised = False
        try:
            self._create_claim(severity="invalid")
        except (ValidationError, ValueError):
            raised = True
        self.assertTrue(raised, "Expected exception was not raised")
