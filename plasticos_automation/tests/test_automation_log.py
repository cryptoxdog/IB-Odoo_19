"""Comprehensive tests for plasticos.automation.log model.

Tests cover:
    - CRUD operations with all required fields
    - Field constraints (required fields)
    - Selection field validation
    - Record ordering
    - Search and filtering
"""


from psycopg2 import IntegrityError

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestPlasticosAutomationLog(PlasticosTestCase):
    """Test suite for plasticos.automation.log"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.AutomationLog = cls.env["plasticos.automation.log"]
        cls.partner = cls.env["res.partner"].create({"name": "Test Partner"})

    def _create_log(self, **kwargs):
        """Helper to create plasticos.automation.log with defaults."""
        vals = {
            "name": "Test Automation Log",
            "model_name": "res.partner",
            "res_id": self.partner.id,
            "action_type": "approval_flag",
        }
        vals.update(kwargs)
        return self.AutomationLog.create(vals)

    # ═══════════════════════════════════════════════════════════════════
    # CREATION TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_create_basic(self):
        """Test basic record creation with all required fields."""
        record = self._create_log()
        self.assertTrue(record.exists(), "Record should be created")
        self.assertEqual(record.name, "Test Automation Log")
        self.assertEqual(record.model_name, "res.partner")
        self.assertEqual(record.res_id, self.partner.id)
        self.assertEqual(record.action_type, "approval_flag")

    def test_create_with_note(self):
        """Test creation with optional note field."""
        record = self._create_log(note="This is a test note for the automation log")
        self.assertEqual(record.note, "This is a test note for the automation log")

    def test_create_all_action_types(self):
        """Test creation with each valid action_type."""
        action_types = [
            ("approval_flag", "Approval Flag"),
            ("invoice_reminder", "Invoice Reminder"),
            ("contract_alert", "Contract Renewal Alert"),
            ("stock_alert", "Stock Reorder Alert"),
        ]
        for action_type, label in action_types:
            record = self._create_log(
                name=f"Test {label}",
                action_type=action_type,
            )
            self.assertEqual(record.action_type, action_type, f"action_type should be {action_type}")

    # ═══════════════════════════════════════════════════════════════════
    # CONSTRAINT TESTS - Required Fields
    # ═══════════════════════════════════════════════════════════════════

    def test_constraint_name_required(self):
        """Test that name field is required."""
        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.AutomationLog.create(
                    {
                        "model_name": "res.partner",
                        "res_id": self.partner.id,
                        "action_type": "approval_flag",
                    }
                )

    def test_constraint_model_name_required(self):
        """Test that model_name field is required."""
        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.AutomationLog.create(
                    {
                        "name": "Test Log",
                        "res_id": self.partner.id,
                        "action_type": "approval_flag",
                    }
                )

    def test_constraint_res_id_required(self):
        """Test that res_id field is required."""
        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.AutomationLog.create(
                    {
                        "name": "Test Log",
                        "model_name": "res.partner",
                        "action_type": "approval_flag",
                    }
                )

    def test_constraint_action_type_required(self):
        """Test that action_type field is required."""
        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.AutomationLog.create(
                    {
                        "name": "Test Log",
                        "model_name": "res.partner",
                        "res_id": self.partner.id,
                    }
                )

    def test_constraint_invalid_action_type(self):
        """Test that invalid action_type raises error."""
        raised = False
        try:
            self.AutomationLog.create(
                {
                    "name": "Test Log",
                    "model_name": "res.partner",
                    "res_id": self.partner.id,
                    "action_type": "invalid_type",
                }
            )
        except (ValidationError, ValueError):
            raised = True
        self.assertTrue(raised, "Expected exception was not raised")

    # ═══════════════════════════════════════════════════════════════════
    # ORDERING TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_default_order_by_create_date_desc(self):
        """Test that records are ordered by create_date descending."""
        log1 = self._create_log(name="First Log")
        log2 = self._create_log(name="Second Log")
        log3 = self._create_log(name="Third Log")

        logs = self.AutomationLog.search([("id", "in", [log1.id, log2.id, log3.id])])
        self.assertEqual(logs[0].id, log3.id, "Most recent should be first")

    # ═══════════════════════════════════════════════════════════════════
    # SEARCH AND FILTER TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_search_by_action_type(self):
        """Test searching logs by action_type."""
        self._create_log(name="Approval 1", action_type="approval_flag")
        self._create_log(name="Approval 2", action_type="approval_flag")
        self._create_log(name="Invoice", action_type="invoice_reminder")

        approval_logs = self.AutomationLog.search([("action_type", "=", "approval_flag")])
        self.assertGreaterEqual(len(approval_logs), 2)

    def test_search_by_model_name(self):
        """Test searching logs by model_name."""
        self._create_log(name="Partner Log", model_name="res.partner")

        partner_logs = self.AutomationLog.search([("model_name", "=", "res.partner")])
        self.assertGreaterEqual(len(partner_logs), 1)

    def test_search_by_res_id(self):
        """Test searching logs by res_id."""
        self._create_log(name="Specific Record Log", res_id=self.partner.id)

        logs = self.AutomationLog.search([("res_id", "=", self.partner.id)])
        self.assertGreaterEqual(len(logs), 1)

    # ═══════════════════════════════════════════════════════════════════
    # UPDATE TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_update_note(self):
        """Test updating the note field."""
        record = self._create_log()
        record.note = "Updated note content"
        self.assertEqual(record.note, "Updated note content")

    def test_update_action_type(self):
        """Test updating the action_type field."""
        record = self._create_log(action_type="approval_flag")
        record.action_type = "invoice_reminder"
        self.assertEqual(record.action_type, "invoice_reminder")

    # ═══════════════════════════════════════════════════════════════════
    # DELETE TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_delete_log(self):
        """Test that logs can be deleted."""
        record = self._create_log()
        record_id = record.id
        record.unlink()
        self.assertFalse(self.AutomationLog.search([("id", "=", record_id)]), "Record should be deleted")
