"""A sales rep reads deal documents and does not create or edit them (operator decision 2026-11-12).

Deal documents arrive through the central documents mailbox. Pictures on a
material profile are a different path (``ir.attachment`` on the profile) and
stay open to sales reps.
"""

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

PNG_1X1 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
PROFILE = "plasticos.material.profile"


@tagged("post_install", "-at_install", "plasticos", "security")
class TestSalesRepDocumentReadOnly(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.rep_group = cls.env.ref("plasticos_security_base.group_sales_rep")
        cls.rep = users.create(
            {"name": "Doc RO Rep", "login": "doc_ro_sales_rep", "group_ids": [Command.set([cls.rep_group.id])]}
        )
        cls.internal = users.create(
            {
                "name": "Doc RO Internal",
                "login": "doc_ro_internal",
                "group_ids": [Command.set([cls.env.ref("base.group_user").id])],
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {"name": "Doc RO Supplier", "is_company": True, "supplier_rank": 1, "user_id": cls.rep.id}
        )
        cls.transaction = cls.env["plasticos.transaction"].create(
            {"supplier_id": cls.partner.id, "user_id": cls.rep.id}
        )
        tag = cls.env["plasticos.document.tag"].create({"name": "Doc RO Tag", "code": "DOC-RO-TAG"})
        attachment = cls.env["ir.attachment"].create(
            {"name": "ro.txt", "datas": "cm8=", "res_model": "plasticos.document", "res_id": 0}
        )
        cls.document = cls.env["plasticos.document"].create(
            {
                "name": "Doc RO evidence",
                "res_model": "plasticos.transaction",
                "res_id": cls.transaction.id,
                "attachment_id": attachment.id,
                "tag_id": tag.id,
            }
        )

    def _can(self, user, operation):
        return self.env["plasticos.document"].with_user(user).has_access(operation)

    def _documents_locked_down(self):
        """True once a plain internal user no longer creates documents (the Documents ACL lock-down)."""
        return not self._can(self.internal, "create")

    # ── the sales role itself ────────────────────────────────
    def test_sales_role_row_grants_read_only(self):
        row = self.env.ref("plasticos_security_base.access_document_sales")
        self.assertEqual(row.group_id, self.rep_group)
        self.assertEqual(row.model_id.model, "plasticos.document")
        self.assertTrue(row.perm_read)
        self.assertFalse(row.perm_write)
        self.assertFalse(row.perm_create)
        self.assertFalse(row.perm_unlink)

    def test_sales_rep_reads_documents(self):
        self.assertTrue(self._can(self.rep, "read"))
        self.assertEqual(self.document.with_user(self.rep).name, "Doc RO evidence")

    def test_sales_role_adds_no_document_rights_over_a_plain_internal_user(self):
        for operation in ("write", "create", "unlink"):
            self.assertEqual(self._can(self.rep, operation), self._can(self.internal, operation), operation)

    def test_sales_rep_cannot_create_or_write_documents(self):
        if not self._documents_locked_down():
            # Exact condition: base.group_user still holds write/create on plasticos.document
            # (plasticos_documents ACL before its lock-down). The sales role is read-only here
            # either way (tests above); the absolute refusal needs both. Removal trigger: the
            # Documents ACL lock-down is on the branch under test.
            self.skipTest("plasticos_documents still grants every internal user document create")
        as_rep = self.document.with_user(self.rep)
        with self.assertRaises(AccessError):
            as_rep.write({"name": "Edited by rep"})
        with self.assertRaises(AccessError):
            self.env["plasticos.document"].with_user(self.rep).create(
                {
                    "name": "Rep upload",
                    "res_model": "plasticos.transaction",
                    "res_id": self.transaction.id,
                    "attachment_id": self.document.attachment_id.id,
                    "tag_id": self.document.tag_id.id,
                }
            )
        self.assertEqual(self.document.name, "Doc RO evidence")

    def test_the_old_grant_is_what_allowed_sales_rep_create(self):
        """Falsifying half: the previous row values (1,1,1,0) give the rep create and write."""
        self.env["ir.model.access"].create(
            {
                "name": "plasticos.document.sales.previous",
                "model_id": self.env.ref("plasticos_documents.model_plasticos_document").id,
                "group_id": self.rep_group.id,
                "perm_read": True,
                "perm_write": True,
                "perm_create": True,
                "perm_unlink": False,
            }
        )
        self.assertTrue(self._can(self.rep, "create"))
        self.assertTrue(self._can(self.rep, "write"))
        self.document.with_user(self.rep).check_access("write")

    # ── carve-out: pictures on a material profile ────────────
    def _profile(self, name):
        polymer = self.env["plasticos.polymer"].search([], limit=1)
        if not polymer:
            polymer = self.env["plasticos.polymer"].create({"name": "Doc RO Polymer", "code": "DOCRO"})
        partner = self.env["res.partner"].create({"name": name, "is_company": True, "user_id": self.rep.id})
        return self.env[PROFILE].create({"partner_id": partner.id, "polymer_id": polymer.id})

    def test_sales_rep_attaches_a_picture_to_a_material_profile(self):
        profile = self._profile("Doc RO Profile Partner")
        picture = (
            self.env["ir.attachment"]
            .with_user(self.rep)
            .create({"name": "bale.png", "datas": PNG_1X1, "res_model": PROFILE, "res_id": profile.id})
        )
        self.assertEqual(picture.create_uid, self.rep)
        self.assertTrue(picture.mimetype.startswith("image/"))
        as_rep = profile.with_user(self.rep)
        as_rep.invalidate_recordset()
        self.assertIn(picture, as_rep.image_ids)
        self.assertEqual(as_rep.image_count, 1)

    def test_sales_rep_copies_pictures_onto_a_material_profile(self):
        source = self._profile("Doc RO Source Partner")
        target = self._profile("Doc RO Target Partner")
        self.env["ir.attachment"].with_user(self.rep).create(
            {"name": "source.png", "datas": PNG_1X1, "res_model": PROFILE, "res_id": source.id}
        )
        target.with_user(self.rep).copy_images_from(PROFILE, source.id)
        as_rep = target.with_user(self.rep)
        as_rep.invalidate_recordset()
        self.assertEqual(as_rep.image_count, 1)
        self.assertEqual(as_rep.image_ids.create_uid, self.rep)
