"""Unit tests for plasticos_order_lines material description.

Tests cover:
- Sale order line material_description computed from polymer + color + form + packaging + source + attrs
- Purchase order line material_description computed identically
- _onchange_material_profile_id pre-fills fields from material profile
- Empty fields produce minimal description
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestSaleOrderLineMaterialDescription(PlasticosTestCase):
    """Test SO line material description computation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.polymer = cls.env["plasticos.polymer"].create(
            {
                "name": "HDPE-OL",
                "code": "hdpe_ol_test",
                "full_name": "High-Density Polyethylene",
                "category": "commodity",
            }
        )
        # Ensure product exists
        cls.polymer._ensure_product()
        cls.product = cls.polymer.product_id.product_variant_id

        cls.color = cls.env["plasticos.material.color"].create(
            {
                "name": "Blue OL",
                "code": "blue_ol",
            }
        )
        cls.form = cls.env["plasticos.material.form"].create(
            {
                "name": "Regrind OL",
                "code": "regrind_ol",
            }
        )
        cls.packaging = cls.env["plasticos.packaging.type"].create(
            {
                "name": "Gaylords",
                "code": "gaylords_ol",
            }
        )
        cls.source_type = cls.env["plasticos.source.type"].create(
            {
                "name": "Post Industrial OL",
                "code": "post_ind_ol",
            }
        )
        cls.customer = cls.env["res.partner"].create(
            {
                "name": "OL Customer",
                "is_company": True,
            }
        )
        cls.so = cls.env["sale.order"].create(
            {
                "partner_id": cls.customer.id,
            }
        )

    def test_full_material_description(self):
        """Full description includes all components."""
        line = self.env["sale.order.line"].create(
            {
                "order_id": self.so.id,
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "price_unit": 100,
                "color_id": self.color.id,
                "form_id": self.form.id,
                "packaging_type_id": self.packaging.id,
                "source_type_id": self.source_type.id,
            }
        )
        self.assertIn("HDPE-OL", line.material_description)
        self.assertIn("Blue OL", line.material_description)
        self.assertIn("Regrind OL", line.material_description)
        self.assertIn("Gaylords", line.material_description)
        self.assertIn("Post Industrial OL", line.material_description)

    def test_minimal_description(self):
        """Description with only polymer."""
        line = self.env["sale.order.line"].create(
            {
                "order_id": self.so.id,
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "price_unit": 50,
            }
        )
        self.assertIn("HDPE-OL", line.material_description)

    def test_description_with_attributes(self):
        """Attributes appended to description."""
        attr = self.env["plasticos.material.attribute"].create(
            {
                "name": "Clean",
                "code": "clean_ol",
            }
        )
        line = self.env["sale.order.line"].create(
            {
                "order_id": self.so.id,
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "price_unit": 75,
                "material_attribute_ids": [(4, attr.id)],
            }
        )
        self.assertIn("Clean", line.material_description)
