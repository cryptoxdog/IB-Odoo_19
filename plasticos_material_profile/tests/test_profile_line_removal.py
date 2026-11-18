"""Trash on a material profile deletes an unused line and archives an approved one."""

import uuid

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestProfileLineRemoval(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        suffix = uuid.uuid4().hex[:8].upper()
        cls.company = cls.env["res.partner"].create({"name": f"Profile Parent {suffix}", "is_company": True})
        cls.polymer = cls.env["plasticos.polymer"].create(
            {"name": f"Removal Polymer {suffix}", "code": f"rmp-{suffix.lower()}"}
        )
        cls.form = cls.env["plasticos.material.form"].create(
            {"name": f"Removal Form {suffix}", "code": f"rmf-{suffix.lower()}"}
        )

    def _profile(self, partner):
        return self.env["plasticos.material.profile"].create(
            {"partner_id": partner.id, "polymer_id": self.polymer.id, "form_id": self.form.id}
        )

    def test_unreferenced_profile_is_deleted(self):
        profile = self._profile(self.company)
        profile_id = profile.id
        profile.action_remove_profile()
        self.assertFalse(self.env["plasticos.material.profile"].browse(profile_id).exists())
        self.assertNotIn(profile_id, self.company.material_profile_ids.ids)

    def test_parent_company_can_hold_a_profile_without_a_child(self):
        profile = self._profile(self.company)
        self.assertFalse(self.company.child_ids)
        self.assertEqual(profile.partner_id, self.company)
        self.assertIn(profile, self.company.material_profile_ids)
