"""Document roles follow the PlasticOS role a user holds (operator decision 2026-11-12).

Logistics and Accounting are Documents Users, Operations Manager is a Documents
Manager, Sales Rep holds no documents group, and nobody is implied into the
Documents Extension Manager.
"""

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

DOC_USER = "plasticos_documents.group_documents_user"
DOC_MANAGER = "plasticos_documents.group_documents_manager"
DOC_EXTENSION = "plasticos_documents.group_documents_extension_manager"


@tagged("post_install", "-at_install", "plasticos", "security")
class TestDocumentRoleImplication(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.logistics = cls._role_user("doc_role_logistics", "plasticos_security_base.group_logistics")
        cls.logistics_ops = cls._role_user("doc_role_logistics_ops", "plasticos_security_base.group_logistics_ops")
        cls.accounting = cls._role_user("doc_role_accounting", "plasticos_security_base.group_accounting")
        cls.accounting_ops = cls._role_user("doc_role_accounting_ops", "plasticos_security_base.group_accounting_ops")
        cls.ops_manager = cls._role_user("doc_role_ops_manager", "plasticos_security_base.group_operations_manager")
        cls.sales_rep = cls._role_user("doc_role_sales_rep", "plasticos_security_base.group_sales_rep")
        cls.internal = cls._role_user("doc_role_internal", "base.group_user")

    @classmethod
    def _role_user(cls, login, group_xmlid):
        return cls.Users.create(
            {"name": login, "login": login, "group_ids": [Command.set([cls.env.ref(group_xmlid).id])]}
        )

    def _can(self, user, model, operation):
        return self.env[model].with_user(user).has_access(operation)

    def _document_as(self, user):
        partner = self.env["res.partner"].create({"name": "Doc role supplier", "is_company": True, "supplier_rank": 1})
        transaction = self.env["plasticos.transaction"].create({"supplier_id": partner.id})
        tag = self.env["plasticos.document.tag"].create({"name": "Doc Role Tag", "code": "DOC-ROLE-TAG"})
        attachment = (
            self.env["ir.attachment"]
            .with_user(user)
            .create({"name": "role.txt", "datas": "cm9sZQ==", "res_model": "plasticos.document", "res_id": 0})
        )
        return (
            self.env["plasticos.document"]
            .with_user(user)
            .create(
                {
                    "name": "Doc role evidence",
                    "res_model": "plasticos.transaction",
                    "res_id": transaction.id,
                    "attachment_id": attachment.id,
                    "tag_id": tag.id,
                }
            )
        )

    # ── membership ───────────────────────────────────────────
    def test_logistics_and_accounting_are_documents_users(self):
        for user in (self.logistics, self.logistics_ops, self.accounting, self.accounting_ops):
            self.assertTrue(user.has_group(DOC_USER), user.login)
            self.assertFalse(user.has_group(DOC_MANAGER), user.login)

    def test_operations_manager_is_documents_manager(self):
        self.assertTrue(self.ops_manager.has_group(DOC_MANAGER))
        self.assertTrue(self.ops_manager.has_group(DOC_USER))

    def test_sales_rep_and_plain_internal_hold_no_documents_group(self):
        for user in (self.sales_rep, self.internal):
            self.assertFalse(user.has_group(DOC_USER), user.login)
            self.assertFalse(user.has_group(DOC_MANAGER), user.login)

    def test_nobody_is_implied_into_the_extension_manager(self):
        everyone = (
            self.logistics,
            self.logistics_ops,
            self.accounting,
            self.accounting_ops,
            self.ops_manager,
            self.sales_rep,
            self.internal,
        )
        for user in everyone:
            self.assertFalse(user.has_group(DOC_EXTENSION), user.login)

    def test_implication_reaches_a_user_who_already_held_the_role(self):
        """A group that gains an implication gives it to its existing members.

        This is what an upgrade does to the Logistics and Accounting groups, so
        no migration is needed to materialise the documents group on users.
        """
        role = self.env["res.groups"].create({"name": "Doc Role Upgrade Probe"})
        member = self.Users.create(
            {
                "name": "doc_role_probe",
                "login": "doc_role_probe",
                "group_ids": [Command.set([self.env.ref("base.group_user").id, role.id])],
            }
        )
        self.assertFalse(member.has_group(DOC_USER))
        role.write({"implied_ids": [Command.link(self.env.ref(DOC_USER).id)]})
        self.assertTrue(member.has_group(DOC_USER))

    # ── what the roles can do ────────────────────────────────
    def test_logistics_user_can_create_a_document(self):
        self.assertTrue(self._can(self.logistics, "plasticos.document", "create"))
        document = self._document_as(self.logistics)
        self.assertTrue(document.exists())
        self.assertEqual(document.create_uid, self.logistics)

    def test_accounting_user_can_create_and_write_documents(self):
        self.assertTrue(self._can(self.accounting, "plasticos.document", "create"))
        self.assertTrue(self._can(self.accounting, "plasticos.document", "write"))

    def test_only_the_manager_role_adds_document_delete(self):
        """Documents User adds no delete right over a plain internal user; the manager has it."""
        baseline = self._can(self.internal, "plasticos.document", "unlink")
        self.assertEqual(self._can(self.accounting, "plasticos.document", "unlink"), baseline)
        self.assertEqual(self._can(self.logistics, "plasticos.document", "unlink"), baseline)
        self.assertTrue(self._can(self.ops_manager, "plasticos.document", "unlink"))

    def test_logistics_user_cannot_override(self):
        document = self._document_as(self.logistics)
        with self.assertRaises(AccessError):
            document.with_user(self.logistics).action_override(reason="Not a manager")
        self.assertFalse(document.override)

    def test_sales_rep_cannot_verify_or_override(self):
        document = self._document_as(self.logistics)
        as_rep = document.with_user(self.sales_rep)
        with self.assertRaises(AccessError):
            as_rep._require_verifier()
        with self.assertRaises(AccessError):
            as_rep.action_override(reason="Not a manager")

    def test_documents_user_role_adds_no_compliance_rule_rights(self):
        """The implication grants nothing on compliance rules beyond a plain internal user."""
        for operation in ("write", "create", "unlink"):
            baseline = self._can(self.internal, "plasticos.document.rule", operation)
            self.assertEqual(self._can(self.logistics, "plasticos.document.rule", operation), baseline, operation)
            self.assertEqual(self._can(self.accounting, "plasticos.document.rule", operation), baseline, operation)
