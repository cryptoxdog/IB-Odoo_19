"""An accepted document on a load is parent-link evidence and blocks unlink."""

import base64

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLoadDocumentAssociation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        parent = cls.env["res.partner"].create({"name": "Document Load Parent", "is_company": True})
        cls.supplier = cls.env["res.partner"].create(
            {"name": "Document Load Supplier", "is_company": True, "parent_id": parent.id, "supplier_rank": 1}
        )
        cls.buyer = cls.env["res.partner"].create(
            {"name": "Document Load Buyer", "is_company": True, "parent_id": parent.id, "customer_rank": 1}
        )

    def test_accepted_document_protects_the_parent_and_blocks_unlink(self):
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        tx = self.env["plasticos.transaction"].create(
            {
                "name": "TX-LOAD-DOC",
                "supplier_id": self.supplier.id,
                "buyer_id": self.buyer.id,
                "sale_order_id": order.id,
                "delivery_term": "appointment",
            }
        )
        load = self.env["plasticos.load"].create({"sale_order_id": order.id})
        self.assertEqual(load.transaction_id, tx)
        tag = self.env["plasticos.document.tag"].search([("code", "=", "BOL")], limit=1)
        self.assertTrue(tag)
        verifier = self.env["res.users"].create(
            {
                "name": "Load Document Verifier",
                "login": "load_cardinality_document_verifier",
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("plasticos_documents.group_documents_user").id,
                        ],
                    )
                ],
            }
        )
        attachment = self.env["ir.attachment"].create(
            {
                "name": "load-cardinality.txt",
                "datas": base64.b64encode(b"load-cardinality"),
                "res_model": "plasticos.document",
                "res_id": 0,
            }
        )
        shell = self.env["plasticos.document"].create(
            {
                "name": "BOL",
                "tag_id": tag.id,
                "res_model": "documents.document",
                "res_id": 0,
                "attachment_id": attachment.id,
            }
        )
        accepted = shell.with_user(verifier).action_associate("plasticos.load", load.id, source_reference="cardinality")
        self.assertEqual(accepted.association_state, "accepted")
        self.assertEqual(accepted.load_id, load)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            load.unlink()
        self.assertTrue(load.exists())
        self.assertEqual(load.transaction_id, tx)
