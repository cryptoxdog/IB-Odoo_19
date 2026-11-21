"""Pending evidence is company-isolated and an unresolved company fails closed (TASK-065, DEC-005 d, A30)."""

import base64

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import AccessError
from odoo.tests.common import tagged

OPERATIONS_GROUP = "plasticos_security_base.group_operations_manager"


@tagged("post_install", "-at_install", "documents", "multi_company")
class TestPendingCompanyIsolation(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env["res.company"].create({"name": "A30 Company B"})
        internal = cls.env.ref("base.group_user")
        documents_user = cls.env.ref("plasticos_documents.group_documents_user")
        documents_manager = cls.env.ref("plasticos_documents.group_documents_manager")
        cls.user_a = cls._user("a30_user_a", cls.company_a, [internal, documents_user])
        cls.user_b = cls._user("a30_user_b", cls.company_b, [internal, documents_user])
        cls.manager_a = cls._user("a30_manager_a", cls.company_a, [internal, documents_manager])
        cls.base_b = cls._user("a30_base_b", cls.company_b, [internal])
        cls.ops = cls.env["res.users"].create(
            {
                "name": "a30_ops",
                "login": "a30_ops",
                "company_id": cls.company_a.id,
                "company_ids": [(6, 0, [cls.company_a.id, cls.company_b.id])],
                "group_ids": [(6, 0, [internal.id, cls.env.ref(OPERATIONS_GROUP).id])],
            }
        )
        partner = cls.env["res.partner"].create({"name": "A30 Partner", "is_company": True, "supplier_rank": 1})
        order_b = cls.env["sale.order"].create({"partner_id": partner.id, "company_id": cls.company_b.id})
        cls.tx_b = cls.env["plasticos.transaction"].create(
            {"supplier_id": partner.id, "buyer_id": partner.id, "quantity": 1, "sale_order_id": order_b.id}
        )
        cls.tag = cls.env["plasticos.document.tag"].create({"name": "A30 BOL", "code": "A30_BOL"})

    @classmethod
    def _user(cls, login, company, groups):
        return cls.env["res.users"].create(
            {
                "name": login,
                "login": login,
                "company_id": company.id,
                "company_ids": [(6, 0, [company.id])],
                "group_ids": [(6, 0, [group.id for group in groups])],
            }
        )

    def _pending(self, attachment_company, res_model="documents.document", res_id=0):
        attachment = self.env["ir.attachment"].create(
            {
                "name": "a30.pdf",
                "datas": base64.b64encode(b"a30-evidence"),
                "res_model": "plasticos.document",
                "res_id": 0,
                "company_id": attachment_company.id,
            }
        )
        return self.env["plasticos.document"].create(
            {
                "name": "A30 pending",
                "tag_id": self.tag.id,
                "res_model": res_model,
                "res_id": res_id,
                "attachment_id": attachment.id,
            }
        )

    def _visible(self, user, doc):
        return bool(self.env["plasticos.document"].with_user(user).search([("id", "=", doc.id)]))

    def test_pending_evidence_is_visible_only_inside_its_company(self):
        doc = self._pending(self.company_b, "plasticos.transaction", self.tx_b.id)
        self.assertEqual(doc.association_state, "pending")
        self.assertEqual(doc.evidence_company_id, self.company_b)
        self.assertTrue(self._visible(self.user_b, doc))
        self.assertTrue(self._visible(self.base_b, doc))
        for outsider in (self.user_a, self.manager_a):
            self.assertFalse(self._visible(outsider, doc))
            with self.assertRaises(AccessError):
                doc.with_user(outsider).read(["name"])

    def test_unresolved_company_fails_closed_with_one_operations_activity(self):
        # The attachment was filed in company A, the subject transaction belongs to company B.
        doc = self._pending(self.company_a, "plasticos.transaction", self.tx_b.id)
        self.assertFalse(doc.evidence_company_id)
        for user in (self.user_a, self.user_b, self.manager_a, self.base_b, self.ops):
            self.assertFalse(self._visible(user, doc))
        summary = f"Pending evidence company unresolved: {doc.name} (evidence {doc.id})"
        domain = [("res_model", "=", "plasticos.transaction"), ("res_id", "=", self.tx_b.id), ("summary", "=", summary)]
        activity = self.env["mail.activity"].search(domain)
        self.assertEqual(len(activity), 1)
        self.assertTrue(activity.user_id.has_group(OPERATIONS_GROUP))
        doc._route_unresolved_company()
        self.assertEqual(self.env["mail.activity"].search(domain), activity)
        # Once the sources agree the row becomes visible in that company and the activity is closed.
        doc.attachment_id.sudo().company_id = self.company_b
        doc._route_unresolved_company()
        self.assertEqual(doc.evidence_company_id, self.company_b)
        self.assertTrue(self._visible(self.user_b, doc))
        self.assertFalse(self.env["mail.activity"].search(domain))

    def test_accepted_legacy_rows_keep_their_access(self):
        doc = self._pending(self.company_b, "plasticos.transaction", self.tx_b.id)
        accepted = doc.with_user(self.user_b).action_associate(
            "plasticos.transaction", self.tx_b.id, source_reference="a30-fixture"
        )
        row = self.env["plasticos.document"].browse(accepted.id)
        self.assertEqual(row.association_state, "accepted")
        self.assertEqual(row.obligation_kind, "legacy")
        # Accepted legacy evidence is not newly scoped by DEC-005 (d).
        self.assertTrue(self._visible(self.user_a, row))

    def _company_activities(self, doc, record):
        summary = f"Pending evidence company unresolved: {doc.name} (evidence {doc.id})"
        return self.env["mail.activity"].search(
            [("res_model", "=", record._name), ("res_id", "=", record.id), ("summary", "=", summary)]
        )

    def test_dangling_original_is_noted_not_routed(self):
        """A deleted or unknown original never breaks routing: the hidden row is noted instead."""
        missing_id = self.env["plasticos.transaction"].search([], order="id desc", limit=1).id + 100000
        doc = self._pending(self.env["res.company"], "plasticos.transaction", missing_id)
        self.assertFalse(doc.evidence_company_id)
        notes = doc.sudo().message_ids.filtered(
            lambda m: "Not routed: Pending evidence company unresolved" in (m.body or "")
        )
        self.assertEqual(len(notes), 1)

    def test_attachment_company_change_routes_without_a_document_write(self):
        doc = self._pending(self.company_b, "plasticos.transaction", self.tx_b.id)
        self.assertTrue(self._visible(self.user_b, doc))
        doc.attachment_id.sudo().write({"company_id": self.company_a.id})
        self.assertFalse(doc.evidence_company_id)
        self.assertFalse(self._visible(self.user_b, doc))
        activity = self._company_activities(doc, self.tx_b)
        self.assertEqual(len(activity), 1)
        # Owned inside the target's own company (B), never by a manager who cannot reach it.
        self.assertIn(self.company_b, activity.user_id.company_ids)
        doc.attachment_id.sudo().write({"company_id": self.company_b.id})
        self.assertEqual(doc.evidence_company_id, self.company_b)
        self.assertFalse(self._company_activities(doc, self.tx_b))

    def test_subject_company_change_recomputes_the_evidence_company(self):
        partner = self.env["res.partner"].create({"name": "A30 Late Partner", "is_company": True})
        tx = self.env["plasticos.transaction"].create(
            {"supplier_id": partner.id, "buyer_id": partner.id, "quantity": 1}
        )
        doc = self._pending(self.company_a, "plasticos.transaction", tx.id)
        self.assertEqual(doc.evidence_company_id, self.company_a)
        order_b = self.env["sale.order"].create({"partner_id": partner.id, "company_id": self.company_b.id})
        tx.write({"sale_order_id": order_b.id})
        self.assertFalse(doc.evidence_company_id)
        self.assertFalse(self._visible(self.user_a, doc))
        self.assertEqual(len(self._company_activities(doc, tx)), 1)

    def test_moving_the_row_closes_the_activity_on_the_previous_original(self):
        doc = self._pending(self.company_a, "plasticos.transaction", self.tx_b.id)
        self.assertEqual(len(self._company_activities(doc, self.tx_b)), 1)
        partner = self.env["res.partner"].create({"name": "A30 Other Partner", "is_company": True})
        other = self.env["plasticos.transaction"].create(
            {"supplier_id": partner.id, "buyer_id": partner.id, "quantity": 1}
        )
        doc._association_write({"res_id": other.id})
        self.assertFalse(self._company_activities(doc, self.tx_b))
        self.assertEqual(doc.evidence_company_id, self.company_a)
