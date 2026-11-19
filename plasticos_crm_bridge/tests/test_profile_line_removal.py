"""An approved lot archives the material profile instead of deleting it."""

import uuid

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestApprovedProfileRemoval(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        suffix = uuid.uuid4().hex[:8].upper()
        # No f-string braces in these create dicts: tests/test_odoo_test_setup_validity.py
        # captures the dict with a brace-bounded regex and must see "parent_id".
        cls.group = cls.env["res.partner"].create({"name": "Approved Profile Group " + suffix, "is_company": True})
        cls.company = cls.env["res.partner"].create(
            {"name": "Approved Profile Site " + suffix, "is_company": True, "parent_id": cls.group.id}
        )
        cls.polymer = cls.env["plasticos.polymer"].create(
            {"name": f"Approved Removal Polymer {suffix}", "code": f"arp-{suffix.lower()}"}
        )
        cls.form = cls.env["plasticos.material.form"].create(
            {"name": f"Approved Removal Form {suffix}", "code": f"arf-{suffix.lower()}"}
        )

    def test_approved_profile_is_archived(self):
        profile = self.env["plasticos.material.profile"].create(
            {"partner_id": self.company.id, "polymer_id": self.polymer.id, "form_id": self.form.id}
        )
        opportunity = self.env["crm.lead"].create(
            {"name": "Profile removal opportunity", "type": "opportunity", "partner_id": self.company.id}
        )
        approval = self.env["plasticos.opportunity.approval"].mint(
            opportunity,
            source="manual",
            partner=self.company,
            material_profile=profile,
        )
        profile.action_remove_profile()
        kept = self.env["plasticos.material.profile"].with_context(active_test=False).browse(profile.id)
        self.assertTrue(kept.exists())
        self.assertFalse(kept.active)
        self.assertNotIn(profile.id, self.company.material_profile_ids.ids)
        self.assertTrue(approval.exists())
        self.assertEqual(approval.with_context(active_test=False).material_profile_id, kept)
