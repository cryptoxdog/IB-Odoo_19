"""Service users cannot verify business evidence; a human Documents User can (TASK-064, N-008, A19)."""

import base64

from odoo import SUPERUSER_ID
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import AccessError
from odoo.tests.common import tagged

SERVICE_REFUSAL = "Service and portal users cannot verify business evidence"


@tagged("post_install", "-at_install", "documents", "verification")
class TestVerifyServiceUsers(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        internal = cls.env.ref("base.group_user")
        documents_user = cls.env.ref("plasticos_documents.group_documents_user")
        cls.human = cls.env["res.users"].create(
            {
                "name": "A19 Human Verifier",
                "login": "a19_human_verifier",
                "group_ids": [(6, 0, [internal.id, documents_user.id])],
            }
        )
        cls.linda = cls.env.ref("plasticos_logistics.user_linda")
        cls.cron_user = cls.env.ref("plasticos_base.user_system_cron")
        # Seed users are not modified (AGENTS.md: tests must not mutate seed data). The refusal message
        # proves the human-only guard refused them, whatever groups production wiring gives them.
        partner = cls.env["res.partner"].create({"name": "A19 Partner", "is_company": True, "supplier_rank": 1})
        cls.tx = cls.env["plasticos.transaction"].create(
            {"supplier_id": partner.id, "buyer_id": partner.id, "quantity": 1000}
        )
        cls.tag = cls.env["plasticos.document.tag"].create({"name": "A19 BOL", "code": "A19_BOL"})

    def _accepted(self):
        attachment = self.env["ir.attachment"].create(
            {
                "name": "a19.txt",
                "datas": base64.b64encode(b"a19-evidence"),
                "res_model": "plasticos.document",
                "res_id": 0,
            }
        )
        shell = self.env["plasticos.document"].create(
            {
                "name": "A19 BOL",
                "tag_id": self.tag.id,
                "res_model": "documents.document",
                "res_id": 0,
                "attachment_id": attachment.id,
            }
        )
        row = shell.with_user(self.human).action_associate(
            "plasticos.transaction", self.tx.id, source_reference="a19-fixture"
        )
        return self.env["plasticos.document"].browse(row.id)

    def test_linda_cannot_verify(self):
        doc = self._accepted()
        with self.assertRaisesRegex(AccessError, SERVICE_REFUSAL):
            doc.with_user(self.linda).action_verify()
        self.assertFalse(doc.verified)

    def test_cron_user_cannot_verify(self):
        doc = self._accepted()
        with self.assertRaisesRegex(AccessError, SERVICE_REFUSAL):
            doc.with_user(self.cron_user).action_verify()
        with self.assertRaisesRegex(AccessError, SERVICE_REFUSAL):
            doc.with_user(self.cron_user).sudo().action_verify()
        self.assertFalse(doc.verified)

    def test_superuser_context_without_a_human_cannot_verify(self):
        doc = self._accepted()
        self.assertEqual(self.env.uid, SUPERUSER_ID)
        with self.assertRaisesRegex(AccessError, "superuser context cannot verify"):
            doc.action_verify()
        with self.assertRaisesRegex(AccessError, "superuser context cannot verify"):
            doc.sudo().action_verify()
        self.assertFalse(doc.verified)

    def test_human_documents_user_verifies_an_exact_accepted_scope(self):
        doc = self._accepted()
        doc.with_user(self.human).action_verify()
        self.assertTrue(doc.verified)
        self.assertEqual(doc.verified_by, self.human)
