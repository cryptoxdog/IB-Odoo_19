"""Batch relationship computes keep the existing predicates."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestRelationshipBatch(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.parent = cls.env["res.partner"].create({"name": "Batch Parent", "is_company": True})
        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "Batch Supplier Plant",
                "is_company": True,
                "parent_id": cls.parent.id,
                "supplier_rank": 1,
            }
        )
        cls.buyer = cls.env["res.partner"].create(
            {
                "name": "Batch Buyer Plant",
                "is_company": True,
                "parent_id": cls.parent.id,
                "customer_rank": 1,
            }
        )
        cls.polymer = cls.env.ref("plasticos_material_profile.polymer_pp")
        cls.form = cls.env.ref("plasticos_material_profile.form_bale")
        cls.profile = cls.env["plasticos.material.profile"].create(
            {
                "partner_id": cls.supplier.id,
                "polymer_id": cls.polymer.id,
                "form_id": cls.form.id,
            }
        )
        cls.product = cls.env["product.product"].create({"name": "Batch PP", "type": "consu"})
        cls.product.product_tmpl_id.polymer_id = cls.polymer

    def test_profile_refs_match_polymer_for_a_recordset(self):
        first = self.env["plasticos.transaction"].create(
            {"name": "TX-BATCH-1", "supplier_id": self.supplier.id, "product_id": self.product.id}
        )
        second = self.env["plasticos.transaction"].create(
            {"name": "TX-BATCH-2", "supplier_id": self.supplier.id, "product_id": self.product.id}
        )
        (first | second)._compute_profile_refs()
        self.assertEqual(first.supplier_profile_id, self.profile)
        self.assertEqual(second.supplier_profile_id, self.profile)

    def test_buyer_facility_recomputes_when_the_profile_is_created(self):
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        tx = self.env["plasticos.transaction"].create({"name": "TX-BATCH-FAC", "sale_order_id": order.id})
        self.assertFalse(tx.buyer_facility_id)
        facility = self.env["plasticos.facility.profile"].create({"partner_id": self.buyer.id})
        tx.invalidate_recordset(["buyer_facility_id"])
        self.assertEqual(tx.buyer_facility_id, facility)

    def test_purchase_delivery_term_uses_m2m_membership(self):
        purchase = self.env["purchase.order"].create({"partner_id": self.supplier.id})
        tx = self.env["plasticos.transaction"].create(
            {
                "name": "TX-BATCH-PO",
                "supplier_id": self.supplier.id,
                "delivery_term": "fcfs",
                "purchase_order_ids": [(6, 0, purchase.ids)],
            }
        )
        purchase._compute_delivery_term_from_transaction()
        self.assertEqual(purchase.delivery_term, tx.delivery_term)
        self.assertEqual(purchase.delivery_term, "fcfs")

    def test_supplier_material_uses_the_first_purchase_partner_profile(self):
        purchase = self.env["purchase.order"].create({"partner_id": self.supplier.id})
        tx = self.env["plasticos.transaction"].create(
            {
                "name": "TX-BATCH-MAT",
                "purchase_order_ids": [(6, 0, purchase.ids)],
            }
        )
        self.assertEqual(tx.supplier_material_id, self.profile)
