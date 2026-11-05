"""GMP-NC-B B-03: intake → partner sync writes run with the caller's own rights.

Editing an intake must not let a user write partner fields that the user cannot
write directly. Runs under ``odoo --test-enable --test-tags /plasticos_intake``.
"""

from __future__ import annotations

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestIntakePartnerSyncAccess(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        group_user = cls.env.ref("base.group_user")
        partner_manager = cls.env.ref("base.group_partner_manager")
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.internal_user = Users.create(
            {"name": "Intake Internal", "login": "nc_b_intake_internal", "group_ids": [Command.set([group_user.id])]}
        )
        cls.contact_editor = Users.create(
            {
                "name": "Intake Contact Editor",
                "login": "nc_b_intake_editor",
                "group_ids": [Command.set([group_user.id, partner_manager.id])],
            }
        )
        Partner = cls.env["res.partner"]
        cls.facility = Partner.create({"name": "NC-B Facility", "is_company": True})
        cls.contact_a = Partner.create({"name": "Contact A", "parent_id": cls.facility.id})
        cls.contact_b = Partner.create({"name": "Contact B", "parent_id": cls.facility.id})
        cls.facility.preferred_contact_id = cls.contact_a
        cls.source = cls.env["utm.source"].create({"name": "NC-B Source"})
        polymer = cls.env["plasticos.polymer"].create({"name": "NC-B Polymer", "code": "NCBPOLY"})
        form = cls.env["plasticos.material.form"].create({"name": "NC-B Form", "code": "ncbform"})
        cls.intake = cls.env["plasticos.intake"].create(
            {
                "partner_id": cls.facility.id,
                "facility_id": cls.facility.id,
                "contact_id": cls.contact_a.id,
                "polymer_id": polymer.id,
                "form_id": form.id,
                "quantity_per_load_lbs": 36000,
            }
        )

    def test_contact_editor_syncs_preferred_contact(self):
        self.intake.with_user(self.contact_editor).write({"contact_id": self.contact_b.id})
        self.assertEqual(self.facility.preferred_contact_id, self.contact_b)

    def test_contact_editor_syncs_first_lead_source(self):
        self.intake.with_user(self.contact_editor).write({"lead_source_id": self.source.id})
        self.assertEqual(self.facility.lead_source_id, self.source)

    def test_existing_lead_source_is_not_overwritten(self):
        original = self.env["utm.source"].create({"name": "NC-B Original"})
        self.facility.lead_source_id = original
        self.intake.with_user(self.contact_editor).write({"lead_source_id": self.source.id})
        self.assertEqual(self.facility.lead_source_id, original)

    def test_user_without_partner_write_cannot_change_preferred_contact(self):
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            self.intake.with_user(self.internal_user).write({"contact_id": self.contact_b.id})
        self.assertEqual(self.facility.preferred_contact_id, self.contact_a)
        self.assertEqual(self.intake.contact_id, self.contact_a)

    def test_user_without_partner_write_cannot_set_partner_lead_source(self):
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            self.intake.with_user(self.internal_user).write({"lead_source_id": self.source.id})
        self.assertFalse(self.facility.lead_source_id)
        self.assertFalse(self.intake.lead_source_id)

    def test_intake_edit_without_partner_sync_is_unaffected(self):
        self.intake.with_user(self.internal_user).write({"quantity_per_load_lbs": 40000})
        self.assertEqual(self.intake.quantity_per_load_lbs, 40000)
        self.assertEqual(self.facility.preferred_contact_id, self.contact_a)

    def test_other_company_partner_stays_isolated(self):
        other_company = self.env["res.company"].create({"name": "NC-B Other Co"})
        foreign = self.env["res.partner"].create(
            {"name": "NC-B Foreign Facility", "is_company": True, "company_id": other_company.id}
        )
        foreign_contact = self.env["res.partner"].create(
            {"name": "Foreign Contact", "parent_id": foreign.id, "company_id": other_company.id}
        )
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            self.intake.with_user(self.contact_editor).write(
                {"facility_id": foreign.id, "contact_id": foreign_contact.id}
            )
        self.assertFalse(foreign.preferred_contact_id)

    def test_server_side_superuser_execution_still_syncs(self):
        self.intake.sudo().write({"contact_id": self.contact_b.id, "lead_source_id": self.source.id})
        self.assertEqual(self.facility.preferred_contact_id, self.contact_b)
        self.assertEqual(self.facility.lead_source_id, self.source)
