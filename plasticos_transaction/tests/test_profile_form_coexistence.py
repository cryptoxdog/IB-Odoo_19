"""Transaction profile binding prefers a resolved form."""

import uuid

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestProfileFormCoexistence(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        parent = cls.env["res.partner"].create({"name": "Coexistence Parent", "is_company": True})
        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "Coexistence Supplier",
                "is_company": True,
                "parent_id": parent.id,
                "supplier_rank": 1,
            }
        )
        cls.form = cls.env.ref("plasticos_material_profile.form_bale")

    def _polymer(self):
        return self.env["plasticos.polymer"].create(
            {"name": "Coexistence Polymer", "code": f"COEX-{uuid.uuid4().hex[:8].upper()}"}
        )

    def _product(self, polymer):
        product = self.env["product.product"].create({"name": polymer.name, "type": "consu"})
        product.product_tmpl_id.polymer_id = polymer
        return product

    def test_specified_profile_wins_over_an_earlier_unspecified_profile(self):
        polymer = self._polymer()
        unspecified = self.env["plasticos.material.profile"].create(
            {"partner_id": self.supplier.id, "polymer_id": polymer.id, "form_id": False}
        )
        specified = self.env["plasticos.material.profile"].create(
            {"partner_id": self.supplier.id, "polymer_id": polymer.id, "form_id": self.form.id}
        )
        tx = self.env["plasticos.transaction"].create(
            {
                "name": f"TX-COEX-{uuid.uuid4().hex[:8]}",
                "supplier_id": self.supplier.id,
                "product_id": self._product(polymer).id,
            }
        )
        tx._compute_profile_refs()
        self.assertEqual(tx.supplier_profile_id, specified)
        self.assertNotEqual(tx.supplier_profile_id, unspecified)

    def test_unspecified_profile_is_selected_when_it_is_the_only_row(self):
        polymer = self._polymer()
        unspecified = self.env["plasticos.material.profile"].create(
            {"partner_id": self.supplier.id, "polymer_id": polymer.id, "form_id": False}
        )
        tx = self.env["plasticos.transaction"].create(
            {
                "name": f"TX-COEX-{uuid.uuid4().hex[:8]}",
                "supplier_id": self.supplier.id,
                "product_id": self._product(polymer).id,
            }
        )
        tx._compute_profile_refs()
        self.assertEqual(tx.supplier_profile_id, unspecified)
