"""Post-install field contract: material profile intake delta bridge."""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "contract")
class TestMaterialProfileDeltaFieldContract(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fields = cls.env["plasticos.material.profile"]._fields

    def test_quantity_per_load_lbs_exists(self):
        self.assertIn("quantity_per_load_lbs", self.fields)
        self.assertEqual(self.fields["quantity_per_load_lbs"].type, "float")

    def test_loads_per_month_is_stored_integer(self):
        self.assertIn("loads_per_month", self.fields)
        self.assertEqual(self.fields["loads_per_month"].type, "integer")
        self.assertFalse(getattr(self.fields["loads_per_month"], "compute", False))

    def test_lat_lon_exist(self):
        for name in ("lat", "lon"):
            self.assertIn(name, self.fields)
            self.assertEqual(self.fields[name].type, "float")

    def test_source_type_id_exists(self):
        self.assertIn("source_type_id", self.fields)
        self.assertEqual(self.fields["source_type_id"].comodel_name, "plasticos.source.type")

    def test_target_price_not_on_material_profile(self):
        self.assertNotIn("target_price", self.fields)

    def test_has_residue_not_stored_on_material_profile(self):
        self.assertNotIn("has_residue", self.fields)
