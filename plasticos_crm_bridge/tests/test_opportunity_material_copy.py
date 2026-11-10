"""The opportunity material copy never writes the live profile or its pictures."""

from __future__ import annotations

import base64

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "plasticos", "crm_bridge", "opportunity")
class TestOpportunityMaterialCopy(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier = cls._create_partner("Copy Supplier Co", supplier_rank=1)
        cls.polymer = cls._get_or_create_polymer()
        cls.other_polymer = cls._get_or_create_polymer(code="LDPE", name="LDPE")
        cls.form = cls._get_or_create_form()
        cls.attribute = cls.env["plasticos.material.attribute"].search([("code", "=", "clean")], limit=1)
        if not cls.attribute:
            cls.attribute = cls.env["plasticos.material.attribute"].create({"name": "Clean", "code": "clean"})
        cls.profile = cls.env["plasticos.material.profile"].create(
            {
                "partner_id": cls.supplier.id,
                "polymer_id": cls.polymer.id,
                "form_id": cls.form.id,
                "material_attribute_ids": [(6, 0, cls.attribute.ids)],
                "freeform_notes": "profile notes",
                "melt_flow_index": 3.5,
                "quantity_per_load_lbs": 40000,
            }
        )
        cls.profile_image = cls.env["ir.attachment"].create(
            {
                "name": "profile.jpg",
                "res_model": "plasticos.material.profile",
                "res_id": cls.profile.id,
                "mimetype": "image/jpeg",
                "datas": base64.b64encode(b"profile-image"),
            }
        )

    def test_editing_the_copy_does_not_write_the_profile_or_its_images(self):
        opportunity = self.env["crm.lead"].create(
            {
                "name": "Copy Opportunity",
                "type": "opportunity",
                "partner_id": self.supplier.id,
                "material_profile_id": self.profile.id,
            }
        )
        material = opportunity.opportunity_material_ids
        self.assertEqual(len(material), 1)
        self.assertEqual(material.polymer_id, self.polymer)
        self.assertEqual(material.freeform_notes, "profile notes")
        self.assertEqual(material.melt_flow_index, 3.5)
        self.assertEqual(material.material_attribute_ids, self.attribute)
        self.assertEqual(len(material.image_attachment_ids), 1)
        self.assertNotEqual(material.image_attachment_ids, self.profile_image)
        self.assertEqual(material.image_attachment_ids.datas, self.profile_image.datas)

        other = self.env["plasticos.material.profile"].create(
            {
                "partner_id": self.supplier.id,
                "polymer_id": self.other_polymer.id,
                "form_id": self.form.id,
                "freeform_notes": "other profile",
            }
        )
        opportunity.material_profile_id = other
        self.assertEqual(opportunity.opportunity_material_ids, material, "the copy is taken once")
        self.assertEqual(material.freeform_notes, "profile notes")

        copy_image = self.env["ir.attachment"].create(
            {
                "name": "copy.jpg",
                "res_model": "plasticos.opportunity.material",
                "res_id": material.id,
                "mimetype": "image/jpeg",
                "datas": base64.b64encode(b"copy-image"),
            }
        )
        original_datas = self.profile_image.datas
        material.write(
            {
                "polymer_id": self.other_polymer.id,
                "freeform_notes": "opportunity notes",
                "melt_flow_index": 9.0,
                "image_attachment_ids": [(6, 0, copy_image.ids)],
            }
        )

        self.assertEqual(self.profile.polymer_id, self.polymer)
        self.assertEqual(self.profile.freeform_notes, "profile notes")
        self.assertEqual(self.profile.melt_flow_index, 3.5)
        self.assertEqual(self.profile.material_attribute_ids, self.attribute)
        self.assertTrue(self.profile_image.exists())
        self.assertEqual(self.profile_image.res_model, "plasticos.material.profile")
        self.assertEqual(self.profile_image.res_id, self.profile.id)
        self.assertEqual(self.profile_image.datas, original_datas)
        self.assertEqual(material.polymer_id, self.other_polymer)
        self.assertEqual(material.freeform_notes, "opportunity notes")
        self.assertEqual(material.image_attachment_ids, copy_image)
