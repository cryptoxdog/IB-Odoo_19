import uuid

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


def _unique_code(prefix="TEST"):
    """Generate a unique code for testing."""
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


@tagged("post_install", "-at_install")
class TestMaterialProfileOnchange(TransactionCase):
    """Covers @api.onchange helpers on material profile."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Profile = cls.env["plasticos.material.profile"]
        cls.partner = cls.env["res.partner"].create({"name": "Facility B"})
        cls.polymer = cls.env["plasticos.polymer"].create({"name": "PP", "code": _unique_code("PP")})
        cls.form = cls.env["plasticos.material.form"].create({"name": "Regrind", "code": _unique_code("REGR")})

    def test_onchange_partner_sets_partner_display(self):
        profile = self.Profile.new({"partner_id": self.partner.id})
        if hasattr(profile, "_onchange_partner_id"):
            profile._onchange_partner_id()
        if hasattr(profile, "partner_display"):
            self.assertIn("Facility", profile.partner_display or "")

    def test_onchange_registry_fields_updates_display_name(self):
        profile = self.Profile.new(
            {
                "partner_id": self.partner.id,
                "polymer_id": self.polymer.id,
                "form_id": self.form.id,
            }
        )
        if hasattr(profile, "_onchange_registry_fields"):
            profile._onchange_registry_fields()
        # We only assert it is populated and sane, not exact format
        self.assertTrue(profile.display_name)
        self.assertIn("PP", profile.display_name)
        self.assertIn("Regrind", profile.display_name)
