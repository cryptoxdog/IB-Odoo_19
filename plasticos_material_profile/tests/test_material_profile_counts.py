"""Grouped image, purchase, and sale counts on a material profile."""

import uuid
from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged

_COUNT_FIELDS = ["image_count", "po_line_count", "so_line_count"]


@tagged("post_install", "-at_install", "plasticos")
class TestMaterialProfileCounts(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        suffix = uuid.uuid4().hex[:8].upper()
        parent = cls.env["res.partner"].create({"name": f"Count Parent {suffix}", "is_company": True})
        cls.partner = cls.env["res.partner"].create(
            {"name": f"Count Facility {suffix}", "is_company": True, "parent_id": parent.id}
        )
        cls.polymer = cls.env["plasticos.polymer"].create({"name": f"Count Polymer {suffix}", "code": f"CNT-{suffix}"})
        cls.other_polymer = cls.env["plasticos.polymer"].create(
            {"name": f"Count Polymer B {suffix}", "code": f"CNTB-{suffix}"}
        )
        cls.form = cls.env["plasticos.material.form"].create({"name": f"Count Bale {suffix}", "code": f"CNTF-{suffix}"})
        profile_model = cls.env["plasticos.material.profile"]
        cls.first = profile_model.create(
            {"partner_id": cls.partner.id, "polymer_id": cls.polymer.id, "form_id": cls.form.id}
        )
        cls.second = profile_model.create(
            {"partner_id": cls.partner.id, "polymer_id": cls.other_polymer.id, "form_id": cls.form.id}
        )
        cls.product = cls.env["product.product"].create({"name": f"Count Goods {suffix}", "type": "consu"})

    def test_counts_are_batched_across_two_profiles(self):
        attachment_model = self.env["ir.attachment"]
        attachment_model.create(
            {
                "name": "lot.png",
                "res_model": "plasticos.material.profile",
                "res_id": self.first.id,
                "mimetype": "image/png",
                "raw": b"png",
            }
        )
        attachment_model.create(
            {
                "name": "lot.pdf",
                "res_model": "plasticos.material.profile",
                "res_id": self.first.id,
                "mimetype": "application/pdf",
                "raw": b"pdf",
            }
        )
        pair = self.first | self.second
        self.assertEqual(pair.mapped("image_count"), [1, 0])
        self._assert_line_count(pair, "purchase.order.line", "po_line_count")
        self._assert_line_count(pair, "sale.order.line", "so_line_count")
        self._assert_second_profile_does_not_double_queries(pair)
        self._assert_new_record_stays_zero(pair)
        self._assert_absent_line_field_counts_zero(pair)

    def _assert_line_count(self, pair, model_name, count_field):
        lines = self.env[model_name]
        if "material_profile_id" not in lines._fields:
            self.assertEqual(pair.mapped(count_field), [0, 0])
            return
        if model_name == "purchase.order.line":
            order = self.env["purchase.order"].create({"partner_id": self.partner.id})
            qty_field = "product_qty"
        else:
            order = self.env["sale.order"].create({"partner_id": self.partner.id})
            qty_field = "product_uom_qty"
        lines.create(
            {
                "order_id": order.id,
                "product_id": self.product.id,
                qty_field: 1,
                "material_profile_id": self.first.id,
            }
        )
        self.assertEqual(pair.mapped(count_field), [1, 0])

    def _assert_second_profile_does_not_double_queries(self, pair):
        pair.mapped("image_count")
        pair.mapped("po_line_count")
        pair.mapped("so_line_count")
        one = pair[:1]
        one_cost = self._count_query_cost(one)
        two_cost = self._count_query_cost(pair)
        self.assertGreaterEqual(one_cost, 1)
        self.assertLess(two_cost, one_cost * 2)

    def _assert_new_record_stays_zero(self, pair):
        fresh = self.env["plasticos.material.profile"].new({})
        mixed = fresh | pair
        self.assertEqual(mixed.mapped("image_count"), [0, 1, 0])
        self.assertEqual(mixed.mapped("po_line_count"), [0, 1, 0])
        self.assertEqual(mixed.mapped("so_line_count"), [0, 1, 0])

    def _assert_absent_line_field_counts_zero(self, pair):
        for model_name, count_field in (
            ("purchase.order.line", "po_line_count"),
            ("sale.order.line", "so_line_count"),
        ):
            model_cls = type(self.env[model_name])
            hidden = {name: field for name, field in model_cls._fields.items() if name != "material_profile_id"}
            pair.invalidate_recordset([count_field])
            with patch.object(model_cls, "_fields", hidden):
                self.assertNotIn("material_profile_id", self.env[model_name]._fields)
                self.assertEqual(pair.mapped(count_field), [0, 0])
            pair.invalidate_recordset([count_field])

    def _count_query_cost(self, records):
        records.invalidate_recordset(_COUNT_FIELDS)
        before = self.env.cr.sql_log_count
        records.mapped("image_count")
        records.mapped("po_line_count")
        records.mapped("so_line_count")
        return self.env.cr.sql_log_count - before
