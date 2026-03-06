"""
Tests for plasticos.partner.import.wizard

Covers: default field values, import mode selection, dry_run guard,
        file upload validation, action_close, action_view_partners.
"""

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestPartnerImportWizard(PlasticosTestCase):
    """Test suite for the Partner Import Wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env["plasticos.partner.import.wizard"]

    # ── Defaults ─────────────────────────────────────────────────────────────

    def test_defaults(self):
        """Wizard defaults: use_default_files=True, mode=full, state=draft."""
        wiz = self.Wizard.create({})
        self.assertTrue(wiz.use_default_files)
        self.assertEqual(wiz.import_mode, "full")
        self.assertEqual(wiz.state, "draft")
        self.assertFalse(wiz.dry_run)

    # ── Validation guards ────────────────────────────────────────────────────

    def test_corporate_upload_required(self):
        """Full import without corporate CSV upload raises UserError."""
        wiz = self.Wizard.create(
            {
                "use_default_files": False,
                "import_mode": "full",
            }
        )
        with self.assertRaises(UserError):
            wiz.action_import()

    def test_facility_upload_required(self):
        """Facility-only import without facility CSV raises UserError."""
        wiz = self.Wizard.create(
            {
                "use_default_files": False,
                "import_mode": "facility_only",
            }
        )
        with self.assertRaises(UserError):
            wiz.action_import()

    def test_corporate_only_skips_facility_validation(self):
        """Corporate-only mode does not require facility CSV."""
        wiz = self.Wizard.create(
            {
                "use_default_files": False,
                "import_mode": "corporate_only",
            }
        )
        # Should raise for missing corporate file, not facility
        with self.assertRaises(UserError) as ctx:
            wiz.action_import()
        self.assertIn("Corporate", str(ctx.exception))

    # ── Navigation actions ───────────────────────────────────────────────────

    def test_action_close(self):
        """action_close returns window close action."""
        wiz = self.Wizard.create({})
        result = wiz.action_close()
        self.assertEqual(result["type"], "ir.actions.act_window_close")

    def test_action_view_partners(self):
        """action_view_partners opens the partner list view."""
        wiz = self.Wizard.create({})
        result = wiz.action_view_partners()
        self.assertEqual(result["res_model"], "res.partner")
        self.assertEqual(result["view_mode"], "list,form")
