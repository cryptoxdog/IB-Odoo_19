"""Trash on a facility profile line deletes it, unless the partner has a live sale order."""

import uuid

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFacilityProfileRemoval(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        suffix = uuid.uuid4().hex[:8].upper()
        parent = cls.env["res.partner"].create({"name": f"Removal Parent {suffix}", "is_company": True})
        cls.plant = cls.env["res.partner"].create(
            {"name": f"Removal Plant {suffix}", "is_company": True, "parent_id": parent.id}
        )

    def test_unused_profile_is_deleted(self):
        profile = self.env["plasticos.facility.profile"].create({"partner_id": self.plant.id})
        profile_id = profile.id
        self.assertTrue(profile.action_remove_profile())
        self.assertFalse(self.env["plasticos.facility.profile"].browse(profile_id).exists())
        self.assertNotIn(profile_id, self.plant.facility_profile_ids.ids)

    def test_profile_with_live_sale_order_is_kept(self):
        profile = self.env["plasticos.facility.profile"].create({"partner_id": self.plant.id})
        self.env["sale.order"].create({"partner_id": self.plant.id})
        with self.assertRaises(ValidationError):
            profile.action_remove_profile()
        self.assertTrue(profile.exists())
