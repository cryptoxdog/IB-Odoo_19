"""Collision cases for semantic-kernel models created during CRM sync.

Run on a database that has this addon installed:
``-i plasticos_semantic_kernel --test-tags crm_sync_semantic_kernel``.
"""

import base64

from odoo import Command
from odoo.addons.plasticos_crm_sync.adapters.base import CanonicalLead
from odoo.addons.plasticos_crm_sync.services.orchestrator import SyncOrchestrator, _new_outcomes
from odoo.addons.plasticos_crm_sync.services.owner_crosswalk import OWNER_LOGIN_BY_SOURCE
from odoo.tests import TransactionCase, tagged


class CrmSyncCollisionCase(TransactionCase):
    """Harness copied from CrmSyncOrchestratorCase. Do not import that test module."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.connection = cls.env["plasticos.crm.connection"].create(
            {
                "name": "Test VS",
                "provider": "vanillasoft",
                "project_id": "139705",
                "enabled": False,
            }
        )

    def setUp(self):
        super().setUp()
        self._ensure_mapped_salespeople()

    def _lead(self, external_id, **kwargs):
        values = {
            "provider": "vanillasoft",
            "external_id": external_id,
            "company": "Test Co",
            "first_name": "Ada",
            "last_name": "Lovelace",
            "lead_status_raw": "New",
        }
        values.update(kwargs)
        return CanonicalLead(**values)

    def _facility(self, name):
        parent = self.env["res.partner"].create({"name": f"{name} Parent", "is_company": True})
        return self.env["res.partner"].create({"name": name, "is_company": True, "parent_id": parent.id})

    def _ensure_salesperson(self, login):
        users = self.env["res.users"].with_context(no_reset_password=True)
        user = users.search([("login", "=ilike", login)], limit=1)
        internal = self.env.ref("base.group_user")
        salesman = self.env.ref("sales_team.group_sale_salesman")
        if not user:
            user = users.create(
                {
                    "name": login,
                    "login": login,
                    "email": login,
                    "group_ids": [Command.set([internal.id, salesman.id])],
                }
            )
        elif user.share or not user.has_group("sales_team.group_sale_salesman"):
            user.write({"group_ids": [Command.link(internal.id), Command.link(salesman.id)]})
        return user

    def _ensure_mapped_salespeople(self):
        for login in set(OWNER_LOGIN_BY_SOURCE.values()):
            self._ensure_salesperson(login)


@tagged("post_install", "-at_install", "-standard", "crm_sync_semantic_kernel")
class TestCrmSyncSemanticKernelCollision(CrmSyncCollisionCase):
    """Collision cases on plasticos_semantic_kernel models.

    plasticos_crm_sync does not depend on this optional module, so the standard
    CRM run excludes these. Run them where the kernel is installed:
    ``-i plasticos_semantic_kernel --test-tags crm_sync_semantic_kernel``.
    """

    def test_collision_keeps_cascade_dependents_and_image_attachments(self):
        from odoo import fields

        location = self._facility("Cascade Mill")
        existing_facility = self.env["plasticos.facility.profile"].create({"partner_id": location.id})
        hdpe = self.env["plasticos.polymer"].search([("code", "=", "HDPE")], limit=1)
        drums = self.env["plasticos.material.form"].search([("code", "=", "DRUMS")], limit=1)
        existing = self.env["plasticos.material.profile"].create(
            {
                "partner_id": location.id,
                "facility_profile_id": existing_facility.id,
                "polymer_id": hdpe.id,
                "form_id": drums.id,
            }
        )
        orch = SyncOrchestrator(self.env)
        dto = self._lead("vs-cascade", custom_fields={"Materials": "HDPE Drums"})
        lead = orch._upsert_lead(self.connection, dto)
        provisional = self.env["plasticos.material.profile"].search([("facility_profile_id.crm_lead_id", "=", lead.id)])
        observation = self.env["plasticos.material.observation"].create(
            {
                "material_profile_id": provisional.id,
                "feature_id": "moisture",
                "value_state": "observed",
                "method": "scale",
                "observed_at": fields.Datetime.now(),
                "source_system": "crm-sync-test",
            }
        )
        specification = self.env["plasticos.material.specification"].create(
            {
                "name": "Cascade spec",
                "polymer_id": hdpe.id,
                "form_id": drums.id,
                "legacy_material_profile_id": provisional.id,
            }
        )
        supply = self.env["plasticos.supply.opportunity"].create(
            {
                "name": "Cascade supply",
                "material_profile_id": provisional.id,
                "supplier_partner_id": location.id,
            }
        )
        image = self.env["ir.attachment"].create(
            {
                "name": "bale.png",
                "res_model": "plasticos.material.profile",
                "res_id": provisional.id,
                "mimetype": "image/png",
                "datas": base64.b64encode(b"bale-image"),
            }
        )
        lead.partner_id = location
        orch._upsert_lead(self.connection, dto)
        self.assertFalse(provisional.exists())
        self.assertTrue(observation.exists())
        self.assertEqual(observation.material_profile_id, existing)
        self.assertEqual(specification.legacy_material_profile_id, existing)
        self.assertEqual(supply.material_profile_id, existing)
        self.assertEqual(image.res_model, "plasticos.material.profile")
        self.assertEqual(image.res_id, existing.id)
        self.assertEqual(image.datas, base64.b64encode(b"bale-image"))

    def test_computed_material_reference_blocks_deletion(self):
        from odoo import fields

        location = self._facility("Computed Mill")
        existing_facility = self.env["plasticos.facility.profile"].create({"partner_id": location.id})
        hdpe = self.env["plasticos.polymer"].search([("code", "=", "HDPE")], limit=1)
        drums = self.env["plasticos.material.form"].search([("code", "=", "DRUMS")], limit=1)
        existing = self.env["plasticos.material.profile"].create(
            {
                "partner_id": location.id,
                "facility_profile_id": existing_facility.id,
                "polymer_id": hdpe.id,
                "form_id": drums.id,
            }
        )
        orch = SyncOrchestrator(self.env)
        orch.outcomes = _new_outcomes()
        dto = self._lead("vs-computed", custom_fields={"Materials": "HDPE Drums"})
        lead = orch._upsert_lead(self.connection, dto)
        provisional = self.env["plasticos.material.profile"].search([("facility_profile_id.crm_lead_id", "=", lead.id)])
        observation = self.env["plasticos.material.observation"].create(
            {
                "material_profile_id": provisional.id,
                "feature_id": "weight",
                "value_state": "reported",
                "method": "ticket",
                "observed_at": fields.Datetime.now(),
                "source_system": "crm-sync-test",
            }
        )
        transaction = self.env["plasticos.transaction"].create({"name": "TX-COMPUTED"})
        self.env.cr.execute(
            "UPDATE plasticos_transaction SET supplier_profile_id = %s WHERE id = %s",
            (provisional.id, transaction.id),
        )
        transaction.invalidate_recordset(["supplier_profile_id"])
        comment = self.env.ref("mail.mt_comment")
        survivor_partner = self.env["res.partner"].create({"name": "Computed Survivor Follower"})
        provisional_partner = self.env["res.partner"].create({"name": "Computed Provisional Follower"})
        survivor_follow = self.env["mail.followers"].create(
            {
                "res_model": "plasticos.material.profile",
                "res_id": existing.id,
                "partner_id": survivor_partner.id,
                "subtype_ids": [fields.Command.link(comment.id)],
            }
        )
        provisional_follow = self.env["mail.followers"].create(
            {
                "res_model": "plasticos.material.profile",
                "res_id": provisional.id,
                "partner_id": provisional_partner.id,
                "subtype_ids": [fields.Command.link(comment.id)],
            }
        )
        lead.partner_id = location
        orch._upsert_lead(self.connection, dto)
        self.assertTrue(provisional.exists())
        self.assertEqual(observation.material_profile_id, provisional)
        self.assertEqual(survivor_follow.res_id, existing.id)
        self.assertEqual(survivor_follow.subtype_ids, comment)
        self.assertEqual(provisional_follow.res_id, provisional.id)
        self.assertTrue(any("cannot be moved" in row["message"] for row in orch.error_rows))
        self.assertEqual(orch.outcomes["failed"], 0)
        self.env.cr.execute("SELECT supplier_profile_id FROM plasticos_transaction WHERE id = %s", (transaction.id,))
        self.assertEqual(self.env.cr.fetchone()[0], provisional.id)
