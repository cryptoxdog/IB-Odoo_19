"""AC-069 / A28: the DEC-014 OPT-A document types and review signals (TASK-069)."""

import base64

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged

# DEC-014 OPT-A: native tag xmlid, tag name, doc_type, legacy plasticos.document.tag code.
NEW_TYPES = (
    ("tag_purchase_order", "Purchase Order", "purchase_order", "PO"),
    ("tag_packing_list", "Packing List", "packing_list", "PACKING"),
    ("tag_receiving_report", "Receiving Report", "receiving_report", "RECEIVING"),
    ("tag_certified_scale_ticket", "Certified Scale Ticket (CST)", "certified_scale_ticket", "CST"),
    ("tag_delivery_order_confirmation", "Delivery Order Confirmation", "delivery_order", "DO"),
    ("tag_carrier_certification", "Carrier Certification", "carrier_certification", "CARRIER_CERT"),
    ("tag_customer_invoice", "Customer Invoice", "customer_invoice", "INV"),
    ("tag_financial_document", "Financial Document", "financial_document", "INV"),
    ("tag_carrier_invoice", "Carrier Invoice", "carrier_invoice", "INV"),
    ("tag_credit_note", "Credit Note", "credit_note", "INV"),
    ("tag_debit_note", "Debit Note", "debit_note", "INV"),
    ("tag_statement", "Statement", "statement", "INV"),
    ("tag_payment_confirmation", "Payment Confirmation", "payment_confirmation", "INV"),
    ("tag_delivery_receipt", "Delivery Receipt", "delivery_receipt", "DO"),
    ("tag_order_confirmation", "Order Confirmation", "order_confirmation", "CO"),
    ("tag_material_certification", "Material Certification", "material_certification", "CERT"),
    ("tag_technical_specification", "Technical Specification", "technical_specification", "OTHER"),
    ("tag_unloading_pic", "Unloading Pic", "unloading_pic", "PHOTO"),
    ("tag_delivery_photo", "Delivery Photo", "delivery_photo", "PHOTO"),
    ("tag_damage_photo", "Damage Photo", "damage_photo", "CLAIM_PHOTO"),
)
REVIEW_SIGNALS = (
    ("tag_needs_review", "Needs Review"),
    ("tag_to_split", "To Split"),
    ("tag_evidence_gap", "Evidence Gap"),
    ("tag_duplicate_candidate", "Duplicate Candidate"),
    ("tag_includes_supporting_evidence", "Includes Supporting Evidence"),
)
# The map as it stood before TASK-069; every entry must be unchanged.
PREVIOUS_MAP = {
    "bol": "BOL",
    "invoice": "INV",
    "scale_ticket": "SCALE",
    "loading_pic": "PHOTO",
    "customer_order": "CO",
    "contract": "CONTRACT",
    "certification": "CERT",
    "permit": "PERMIT",
    "lab_report": "LAB",
    "photo": "PHOTO",
    "correspondence": "CORR",
    "other": "OTHER",
}
PREVIOUS_NATIVE_TAGS = {
    "tag_bol": "BOL",
    "tag_vendor_bill": "Vendor Bill",
    "tag_scale_ticket": "Scale Ticket",
    "tag_loading_pic": "Loading Pic",
    "tag_customer_order": "Customer Order",
    "tag_contract": "Contract",
    "tag_certification": "Certification",
    "tag_permit": "Permit",
    "tag_lab_report": "Lab Report",
    "tag_photo": "Photo",
    "tag_correspondence": "Correspondence",
    "tag_verified": "Verified",
}


@tagged("post_install", "-at_install", "documents")
class TestDocumentTypesDec014(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "documents.document" not in cls.env:
            raise AssertionError("BLOCKED: Enterprise documents.document is not installed")
        cls.inbox = cls.env.ref("plasticos_documents_native.folder_plasticos_inbox")
        cls.sync = cls.env["plasticos.document.sync"]

    def test_every_new_type_has_its_tag_selection_value_and_legacy_code(self):
        selection = dict(self.env["documents.document"]._fields["doc_type"].selection)
        for xmlid, name, doc_type, code in NEW_TYPES:
            with self.subTest(doc_type=doc_type):
                self.assertEqual(self.env.ref(f"plasticos_documents_native.{xmlid}").name, name)
                self.assertIn(doc_type, selection)
                self.assertEqual(self.sync.DOC_TYPE_TAG_MAP[doc_type], code)
                self.assertTrue(self.env["plasticos.document.tag"].search([("code", "=", code)]))
        self.assertEqual(self.env.ref("plasticos_documents.tag_purchase_order").code, "PO")
        self.assertEqual(self.env.ref("plasticos_documents.tag_carrier_certification").code, "CARRIER_CERT")

    def test_every_new_type_creates_a_pending_shell_with_its_legacy_code(self):
        for _xmlid, _name, doc_type, code in NEW_TYPES:
            with self.subTest(doc_type=doc_type):
                native = self.env["documents.document"].create(
                    {
                        "name": f"dec014-{doc_type}.pdf",
                        "folder_id": self.inbox.id,
                        "datas": base64.b64encode(f"%PDF-1.4 {doc_type}".encode()),
                        "doc_type": doc_type,
                    }
                )
                self.assertTrue(native.plasticos_doc_id, doc_type)
                self.assertEqual(native.plasticos_doc_id.tag_id.code, code)
                self.assertFalse(native.plasticos_doc_id.verified)

    def test_review_signals_exist_and_map_to_no_doc_type(self):
        selection = dict(self.env["documents.document"]._fields["doc_type"].selection)
        labels = set(selection.values())
        for xmlid, name in REVIEW_SIGNALS:
            with self.subTest(signal=name):
                self.assertEqual(self.env.ref(f"plasticos_documents_native.{xmlid}").name, name)
                self.assertNotIn(name, labels)
        self.assertEqual(set(self.sync.DOC_TYPE_TAG_MAP) - set(selection), set())

    def test_existing_types_and_tags_are_unchanged(self):
        for doc_type, code in PREVIOUS_MAP.items():
            self.assertEqual(self.sync.DOC_TYPE_TAG_MAP[doc_type], code, doc_type)
        for xmlid, name in PREVIOUS_NATIVE_TAGS.items():
            self.assertEqual(self.env.ref(f"plasticos_documents_native.{xmlid}").name, name, xmlid)
