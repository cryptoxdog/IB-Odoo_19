"""Tests for Partner Bulk Update Wizard.

Tests the bulk update wizard for partners.
Aligned with plasticos_partner_import/wizards/partner_bulk_update_wizard.py.

Actions: assign_salesperson, assign_category, set_company_type, assign_payment_terms
"""

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests.common import tagged


@tagged("post_install", "-at_install")
class TestPartnerBulkUpdateWizard(PlasticosTestCase):
    """Test plasticos.partner.bulk.update.wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner1 = cls.env["res.partner"].create(
            {
                "name": "Partner Alpha",
                "is_company": True,
            }
        )
        cls.partner2 = cls.env["res.partner"].create(
            {
                "name": "Partner Beta",
                "is_company": False,
            }
        )
        cls.salesperson = cls.env["res.users"].create(
            {
                "name": "Test Salesperson",
                "login": "test_salesperson_bulk",
            }
        )
        cls.tag1 = cls.env["res.partner.category"].create({"name": "Recycler"})
        cls.tag2 = cls.env["res.partner.category"].create({"name": "Supplier"})

    def setUp(self):
        super().setUp()
        # Reset partner fields before each test
        self.partner1.write({"user_id": False, "category_id": [(5, 0, 0)]})
        self.partner2.write({"user_id": False, "category_id": [(5, 0, 0)], "is_company": False})

    # ------------------------------------------------------------------
    # Context / defaults
    # ------------------------------------------------------------------
    def test_default_get_loads_partners(self):
        """Wizard should load partner_ids from active_ids."""
        wiz = (
            self.env["plasticos.partner.bulk.update.wizard"]
            .with_context(
                active_ids=[self.partner1.id, self.partner2.id],
            )
            .create(
                {
                    "action_type": "assign_salesperson",
                    "user_id": self.salesperson.id,
                    "reason": "Test",
                }
            )
        )
        self.assertEqual(wiz.partner_count, 2)
        self.assertEqual(wiz.company_count, 1)
        self.assertEqual(wiz.contact_count, 1)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def test_no_partners_raises(self):
        """Executing with empty partner_ids should raise UserError."""
        wiz = self.env["plasticos.partner.bulk.update.wizard"].create(
            {
                "action_type": "assign_salesperson",
                "user_id": self.salesperson.id,
                "reason": "Empty",
            }
        )
        with self.assertRaises(UserError):
            wiz.action_execute()

    def test_assign_salesperson_requires_user(self):
        """assign_salesperson without user_id should raise."""
        wiz = (
            self.env["plasticos.partner.bulk.update.wizard"]
            .with_context(
                active_ids=[self.partner1.id],
            )
            .create(
                {
                    "action_type": "assign_salesperson",
                    "reason": "No user",
                }
            )
        )
        with self.assertRaises(UserError):
            wiz.action_execute()

    def test_assign_category_requires_tags(self):
        """assign_category without category_ids should raise."""
        wiz = (
            self.env["plasticos.partner.bulk.update.wizard"]
            .with_context(
                active_ids=[self.partner1.id],
            )
            .create(
                {
                    "action_type": "assign_category",
                    "reason": "No tags",
                }
            )
        )
        with self.assertRaises(UserError):
            wiz.action_execute()

    def test_set_company_type_requires_type(self):
        """set_company_type without company_type should raise."""
        wiz = (
            self.env["plasticos.partner.bulk.update.wizard"]
            .with_context(
                active_ids=[self.partner1.id],
            )
            .create(
                {
                    "action_type": "set_company_type",
                    "reason": "No type",
                }
            )
        )
        with self.assertRaises(UserError):
            wiz.action_execute()

    def test_assign_payment_terms_requires_at_least_one(self):
        """assign_payment_terms without any terms should raise."""
        wiz = (
            self.env["plasticos.partner.bulk.update.wizard"]
            .with_context(
                active_ids=[self.partner1.id],
            )
            .create(
                {
                    "action_type": "assign_payment_terms",
                    "reason": "No terms",
                }
            )
        )
        with self.assertRaises(UserError):
            wiz.action_execute()

    # ------------------------------------------------------------------
    # Execution happy paths
    # ------------------------------------------------------------------
    def test_assign_salesperson_success(self):
        """Bulk assign salesperson should update partner user_id."""
        wiz = (
            self.env["plasticos.partner.bulk.update.wizard"]
            .with_context(
                active_ids=[self.partner1.id, self.partner2.id],
            )
            .create(
                {
                    "action_type": "assign_salesperson",
                    "user_id": self.salesperson.id,
                    "reason": "New rep",
                }
            )
        )
        result = wiz.action_execute()
        self.assertEqual(self.partner1.user_id, self.salesperson)
        self.assertEqual(self.partner2.user_id, self.salesperson)
        self.assertEqual(result["type"], "ir.actions.client")

    def test_assign_category_add_mode(self):
        """Add mode should append tags, not replace."""
        self.partner1.category_id = self.tag1
        wiz = (
            self.env["plasticos.partner.bulk.update.wizard"]
            .with_context(
                active_ids=[self.partner1.id],
            )
            .create(
                {
                    "action_type": "assign_category",
                    "category_ids": [(6, 0, [self.tag2.id])],
                    "category_mode": "add",
                    "reason": "Add tag",
                }
            )
        )
        wiz.action_execute()
        self.assertIn(self.tag1, self.partner1.category_id)
        self.assertIn(self.tag2, self.partner1.category_id)

    def test_assign_category_replace_mode(self):
        """Replace mode should overwrite all existing tags."""
        self.partner1.category_id = self.tag1
        wiz = (
            self.env["plasticos.partner.bulk.update.wizard"]
            .with_context(
                active_ids=[self.partner1.id],
            )
            .create(
                {
                    "action_type": "assign_category",
                    "category_ids": [(6, 0, [self.tag2.id])],
                    "category_mode": "replace",
                    "reason": "Replace tags",
                }
            )
        )
        wiz.action_execute()
        self.assertNotIn(self.tag1, self.partner1.category_id)
        self.assertIn(self.tag2, self.partner1.category_id)

    def test_set_company_type_to_company(self):
        """set_company_type=company should set is_company=True."""
        wiz = (
            self.env["plasticos.partner.bulk.update.wizard"]
            .with_context(
                active_ids=[self.partner2.id],
            )
            .create(
                {
                    "action_type": "set_company_type",
                    "company_type": "company",
                    "reason": "Upgrade to company",
                }
            )
        )
        wiz.action_execute()
        self.assertTrue(self.partner2.is_company)
