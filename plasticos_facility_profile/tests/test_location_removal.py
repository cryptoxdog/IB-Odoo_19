"""Trash on a company location deletes an unused site and archives one still in use."""

import uuid

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLocationRemoval(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        suffix = uuid.uuid4().hex[:8]
        partner = cls.env["res.partner"]
        cls.parent = partner.create({"name": f"Removal Parent {suffix}", "is_company": True})
        cls.location = partner.create(
            {"name": f"Removal Site {suffix}", "is_company": True, "parent_id": cls.parent.id}
        )
        rep_group = cls.env.ref("plasticos_security_base.group_sales_rep")
        cls.rep = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": f"Removal Rep {suffix}",
                    "login": f"location_removal_rep_{suffix}",
                    "group_ids": [Command.set([rep_group.id])],
                }
            )
        )

    def test_unreferenced_location_is_deleted(self):
        location_id = self.location.id
        self.location.action_remove_location()
        self.assertFalse(self.env["res.partner"].browse(location_id).exists())
        self.assertNotIn(location_id, self.parent.location_child_ids.ids)

    def test_location_with_a_person_is_archived(self):
        self.env["res.partner"].create({"name": "Removal Person", "is_company": False, "parent_id": self.location.id})
        self.location.action_remove_location()
        kept = self.env["res.partner"].with_context(active_test=False).browse(self.location.id)
        self.assertTrue(kept.exists())
        self.assertFalse(kept.active)
        self.assertEqual(kept.entity_status, "inactive")
        self.assertNotIn(self.location.id, self.parent.location_child_ids.ids)

    def test_location_on_a_sale_order_is_archived(self):
        self.env["sale.order"].create({"partner_id": self.location.id})
        self.location.action_remove_location()
        kept = self.env["res.partner"].with_context(active_test=False).browse(self.location.id)
        self.assertTrue(kept.exists())
        self.assertFalse(kept.active)
        self.assertEqual(kept.entity_status, "inactive")
        self.assertNotIn(self.location.id, self.parent.location_child_ids.ids)

    def test_parent_company_cannot_be_removed(self):
        with self.assertRaises(UserError):
            self.parent.action_remove_location()
        self.assertTrue(self.parent.exists())

    def test_user_who_cannot_read_the_company_cannot_remove_its_location(self):
        self.parent.write({"is_private": True})
        with self.assertRaises(AccessError):
            self.location.with_user(self.rep).action_remove_location()
        self.assertTrue(self.location.active)
