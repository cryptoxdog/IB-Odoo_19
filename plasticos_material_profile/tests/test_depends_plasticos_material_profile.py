from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestMaterialProfileDepends(TransactionCase):
    """Profile @api.depends fields."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Profile = cls.env["plasticos.material.profile"]
        cls.partner = cls.env["res.partner"].create({"name": "Facility C"})
        cls.polymer = cls.env["plasticos.polymer"].create({"name": "PET", "code": "PET"})
        cls.form = cls.env["plasticos.material.form"].create({"name": "Bottle", "code": "BOT"})

    def _profile(self, **vals):
        base = {
            "partner_id": self.partner.id,
            "polymer_id": self.polymer.id,
            "form_id": self.form.id,
        }
        base.update(vals)
        return self.Profile.create(base)

    def test_display_name(self):
        prof = self._profile()
        self.assertTrue(prof.display_name)
        self.assertIn("PET", prof.display_name)
        self.assertIn("Bottle", prof.display_name)

    def test_full_description(self):
        prof = self._profile()
        if hasattr(prof, "full_description"):
            self.assertIn("PET", prof.full_description)

    def test_partner_profile_count(self):
        p1 = self._profile()
        self.partner.invalidate_recordset()
        if hasattr(self.partner, "material_profile_count"):
            self.assertGreaterEqual(self.partner.material_profile_count, 1)
            self._profile(form_id=self.form.copy({"code": "BOT2"}).id)
            self.partner.invalidate_recordset()
            self.assertGreaterEqual(self.partner.material_profile_count, 2)
