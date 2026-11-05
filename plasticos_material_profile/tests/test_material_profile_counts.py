"""Grouped image, purchase, and sale counts on a material profile."""

import base64
import uuid

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "plasticos")
class TestMaterialProfileCounts(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        suffix = uuid.uuid4().hex[:8].upper()
        parent = cls.env["res.partner"].create({"name": f"Count Parent {suffix}", "is_company": True})
        cls.partner = cls.env["res.partner"].create(
            {"name": f"Count Facility {suffix}", "is_company": True, "parent_id": parent.id}
        )
        cls.polymer = cls.env["plasticos.polymer"].create({"name": f"Count Polymer {suffix}", "code": f"CNT-{suffix}"})
        cls.form = cls.env["plasticos.material.form"].create({"name": f"Count Bale {suffix}", "code": f"CNTB-{suffix}"})
        Profile = cls.env["plasticos.material.profile"]
        cls.first = Profile.create({"partner_id": cls.partner.id, "polymer_id": cls.polymer.id, "form_id": cls.form.id})
        other_form = cls.env["plasticos.material.form"].create(
            {"name": f"Count Regrind {suffix}", "code": f"CNTR-{suffix}"}
        )
        cls.second = Profile.create(
            {"partner_id": cls.partner.id, "polymer_id": cls.polymer.id, "form_id": other_form.id}
        )
        cls.product = cls.env["product.product"].create({"name": f"Count Goods {suffix}", "type": "consu"})

    def test_two_profiles_count_images_and_order_lines(self):
        Attachment = self.env["ir.attachment"]
        Attachment.create(
            {
                "name": "photo.png",
                "res_model": "plasticos.material.profile",
                "res_id": self.first.id,
                "mimetype": "image/png",
                "datas": base64.b64encode(b"png"),
            }
        )
        Attachment.create(
            {
                "name": "note.txt",
                "res_model": "plasticos.material.profile",
                "res_id": self.first.id,
                "mimetype": "text/plain",
                "datas": base64.b64encode(b"text"),
            }
        )
        pair = self.first | self.second
        self.assertEqual(pair.mapped("image_count"), [1, 0])

        self._assert_line_count(pair, "purchase.order.line", "po_line_count")
        self._assert_line_count(pair, "sale.order.line", "so_line_count")

    def _assert_line_count(self, pair, model_name, count_field):
        lines = self.env[model_name]
        if "material_profile_id" not in lines._fields:
            self.assertEqual(pair.mapped(count_field), [0, 0])
            return
        if model_name == "purchase.order.line":
            order = self.env["purchase.order"].create({"partner_id": self.partner.id})
        else:
            order = self.env["sale.order"].create({"partner_id": self.partner.id})
        lines.create(
            {
                "order_id": order.id,
                "product_id": self.product.id,
                "product_qty" if model_name == "purchase.order.line" else "product_uom_qty": 1,
                "material_profile_id": self.first.id,
            }
        )
        self.assertEqual(pair.mapped(count_field), [1, 0])
