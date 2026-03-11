"""Unit tests for plasticos_product polymer-product sync.

Tests cover:
- Polymer create auto-creates product.template
- Product has polymer_id link and is_polymer_product=True
- Polymer name update syncs to product
- _ensure_product is idempotent
- action_create_products batch action
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestPolymerProductSync(PlasticosTestCase):
    """Test polymer → product auto-sync."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Polymer = cls.env["plasticos.polymer"]

    def test_polymer_creates_product(self):
        """Creating a polymer auto-creates a linked product."""
        polymer = self.Polymer.create(
            {
                "name": "ABS-Product",
                "code": "abs_product_test",
                "full_name": "Acrylonitrile Butadiene Styrene",
                "category": "commodity",
            }
        )
        self.assertTrue(polymer.product_id)
        self.assertEqual(polymer.product_id.name, "ABS-Product")
        self.assertTrue(polymer.product_id.is_polymer_product)

    def test_polymer_product_link(self):
        """Product has polymer_id back-reference."""
        polymer = self.Polymer.create(
            {
                "name": "PET-Product",
                "code": "pet_product_test",
                "full_name": "Polyethylene Terephthalate",
                "category": "commodity",
            }
        )
        self.assertEqual(polymer.product_id.polymer_id.id, polymer.id)

    def test_polymer_name_syncs_to_product(self):
        """Updating polymer name updates product name."""
        polymer = self.Polymer.create(
            {
                "name": "OLD-NAME",
                "code": "sync_test",
                "full_name": "Old Polymer",
                "category": "commodity",
            }
        )
        polymer.write({"name": "NEW-NAME"})
        self.assertEqual(polymer.product_id.name, "NEW-NAME")

    def test_ensure_product_idempotent(self):
        """Calling _ensure_product twice doesn't create duplicate."""
        polymer = self.Polymer.create(
            {
                "name": "IDEM",
                "code": "idem_test",
                "full_name": "Idempotent Test",
                "category": "commodity",
            }
        )
        product_id = polymer.product_id.id
        polymer._ensure_product()
        self.assertEqual(polymer.product_id.id, product_id)

    def test_batch_create_products(self):
        """action_create_products batch creates products."""
        p1 = self.Polymer.create(
            {
                "name": "BATCH1",
                "code": "batch1_test",
                "full_name": "Batch 1",
                "category": "commodity",
            }
        )
        result = p1.action_create_products()
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertTrue(p1.product_id)
