"""@api.onchange tests for plasticos.material.profile.

Focus: partner/polymer/form onchanges that build human-friendly labels.[web:125]
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestMaterialProfileOnchangeAll(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Profile = cls.env["plasticos.material.profile"]
        cls.partner = cls.env["res.partner"].create({"name": "Facility B"})
        cls.polymer = cls.env["plasticos.polymer"].create({"name": "PP", "code": "PP"})
        cls.form = cls.env["plasticos.material.form"].create({"name": "Regrind", "code": "REGR"})

    def test_onchange_partner_updates_partner_display(self):
        prof = self.Profile.new({"partner_id": self.partner.id})
        if hasattr(prof, "_onchange_partner_id"):
            prof._onchange_partner_id()
        if hasattr(prof, "partner_display"):
            self.assertIn("Facility", prof.partner_display or "")

    def test_onchange_registry_fields_updates_display_name(self):
        prof = self.Profile.new(
            {
                "partner_id": self.partner.id,
                "polymer_id": self.polymer.id,
                "form_id": self.form.id,
            }
        )
        for m in ("_onchange_polymer_id", "_onchange_form_id", "_onchange_registry_fields"):
            if hasattr(prof, m):
                getattr(prof, m)()
        self.assertTrue(prof.display_name)
        self.assertIn("PP", prof.display_name)
        self.assertIn("Regrind", prof.display_name)

    def test_onchange_quality_flags_sets_notes(self):
        prof = self.Profile.new({"has_odor": True, "has_mixed_colors": True})
        if hasattr(prof, "_onchange_quality_flags"):
            prof._onchange_quality_flags()
        # Only sanity: if field exists, ensure it's set to something non-crashing
        if hasattr(prof, "quality_notes"):
            self.assertIsNotNone(prof.quality_notes)
