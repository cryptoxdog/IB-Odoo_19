"""Least-privilege ACL, evidence unlink guard, escalation owner, and the missing-docs cursor.

BRS-POS-03-R004 (authoritative verification writer), BRS-POS-03-R005 (attributable
verification), BRS-POS-03-R007 (operation-scoped compliance) and BRS-POS-09-R003
(one internal Activity per unresolved obligation).
"""

import base64
from unittest.mock import patch

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import AccessError
from odoo.tests.common import tagged

UNASSIGNED_MARKER = "Missing-document escalation has no owner."
CURSOR_KEY = "plasticos_documents.missing_doc_scan_cursor"
LOGGER = "odoo.addons.plasticos_documents.models.transaction_docs"


def _five_business_days(_start_date, _end_date):
    return 5


@tagged("post_install", "-at_install", "documents", "integrity_controls")
class TestDocumentAccessControls(PlasticosTestCase):
    """An internal user reads compliance policy and evidence. Only the scoped groups change it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        internal = cls.env.ref("base.group_user")
        purchase = cls.env.ref("purchase.group_purchase_user")
        groups = {
            "internal": [internal.id],
            "verifier": [internal.id, purchase.id, cls.env.ref("plasticos_documents.group_documents_user").id],
            "manager": [internal.id, purchase.id, cls.env.ref("plasticos_documents.group_documents_manager").id],
            "extension": [
                internal.id,
                cls.env.ref("plasticos_documents.group_documents_extension_manager").id,
            ],
        }
        for name, group_ids in groups.items():
            user = cls.env["res.users"].create(
                {
                    "name": f"Integrity {name}",
                    "login": f"integrity_controls_{name}",
                    "group_ids": [(6, 0, group_ids)],
                }
            )
            setattr(cls, name, user)
        cls.partner = cls.env["res.partner"].create(
            {"name": "Integrity Partner", "is_company": True, "customer_rank": 1, "supplier_rank": 1}
        )
        cls.tag = cls.env["plasticos.document.tag"].create({"name": "Integrity Tag", "code": "INTEGRITYTAG"})
        cls.rule = cls.env["plasticos.document.rule"].create(
            {"name": "Integrity Rule", "tag_id": cls.tag.id, "res_model": "plasticos.transaction"}
        )
        cls.matrix = cls.env["plasticos.document.validation.matrix"].create(
            {"name": "Integrity Matrix", "doc_category": "supplier", "tag_id": cls.tag.id}
        )

    def _attachment(self):
        return self.env["ir.attachment"].create(
            {
                "name": "integrity.txt",
                "datas": base64.b64encode(b"integrity-bytes"),
                "res_model": "plasticos.document",
                "res_id": 0,
            }
        )

    def _shell(self):
        return self.env["plasticos.document"].create(
            {
                "name": "Integrity shell",
                "tag_id": self.tag.id,
                "res_model": "documents.document",
                "res_id": 0,
                "attachment_id": self._attachment().id,
            }
        )

    def _accepted(self):
        transaction = self.env["plasticos.transaction"].create(
            {"supplier_id": self.partner.id, "buyer_id": self.partner.id, "quantity": 44000}
        )
        row = (
            self._shell()
            .with_user(self.verifier)
            .action_associate("plasticos.transaction", transaction.id, source_reference="integrity-controls")
        )
        return self.env["plasticos.document"].browse(row.id), transaction

    def test_internal_user_reads_policy_and_evidence(self):
        shell = self._shell()
        for record in (self.rule, self.tag, self.matrix, shell):
            self.assertEqual(record.with_user(self.internal).read(["name"])[0]["id"], record.id)
        missing = (
            self.env["plasticos.compliance.service"]
            .with_user(self.internal)
            .get_missing_documents("plasticos.transaction", 0)
        )
        self.assertIn(self.tag.code, missing)

    def test_internal_user_cannot_disable_or_delete_compliance_policy(self):
        for record in (self.rule, self.tag, self.matrix):
            with self.assertRaises(AccessError):
                record.with_user(self.internal).write({"active": False})
            with self.assertRaises(AccessError):
                record.with_user(self.internal).unlink()
        with self.assertRaises(AccessError):
            self.env["plasticos.document.rule"].with_user(self.internal).create(
                {"name": "forged", "tag_id": self.tag.id, "res_model": "plasticos.load"}
            )
        self.assertTrue(self.rule.active)
        self.assertTrue(self.matrix.active)

    def test_internal_user_cannot_create_write_or_delete_documents(self):
        shell = self._shell()
        attachment = self._attachment()
        with self.assertRaises(AccessError):
            self.env["plasticos.document"].with_user(self.internal).create(
                {
                    "name": "forged",
                    "tag_id": self.tag.id,
                    "res_model": "documents.document",
                    "res_id": 0,
                    "attachment_id": attachment.id,
                }
            )
        with self.assertRaises(AccessError):
            shell.with_user(self.internal).write({"name": "renamed"})
        with self.assertRaises(AccessError):
            shell.with_user(self.internal).unlink()
        self.assertTrue(shell.exists())

    def test_verifier_cannot_change_policy_and_manager_can(self):
        with self.assertRaises(AccessError):
            self.rule.with_user(self.verifier).write({"active": False})
        with self.assertRaises(AccessError):
            self.tag.with_user(self.verifier).write({"name": "renamed"})
        self.rule.with_user(self.manager).write({"required_for_invoice": True})
        self.assertTrue(self.rule.required_for_invoice)
        self.tag.with_user(self.manager).write({"name": "Integrity Tag Renamed"})
        self.assertEqual(self.tag.name, "Integrity Tag Renamed")

    def test_matrix_stays_with_the_extension_manager(self):
        with self.assertRaises(AccessError):
            self.matrix.with_user(self.manager).write({"sequence": 99})
        self.matrix.with_user(self.extension).write({"sequence": 42})
        self.assertEqual(self.matrix.sequence, 42)

    def test_unlink_guard_refuses_accepted_and_decided_evidence(self):
        row, _transaction = self._accepted()
        self.assertEqual(row.association_state, "accepted")
        with self.assertRaises(AccessError):
            row.with_user(self.verifier)._refuse_evidence_unlink()
        with self.assertRaises(AccessError):
            row.with_user(self.verifier).unlink()
        row.with_user(self.verifier).action_verify()
        self.assertTrue(row.verified)
        with self.assertRaises(AccessError):
            row.with_user(self.verifier)._refuse_evidence_unlink()
        self.assertTrue(row.exists())
        # A pending, undecided shell is not evidence; the guard itself lets it through.
        self._shell().with_user(self.verifier)._refuse_evidence_unlink()

    def test_manager_unlinks_accepted_evidence_and_compliance_recomputes(self):
        row, transaction = self._accepted()
        row.with_user(self.manager)._refuse_evidence_unlink()
        row.with_user(self.manager).unlink()
        self.assertFalse(row.exists())
        self.assertEqual(transaction.compliance_status, "missing")


@tagged("post_install", "-at_install", "documents", "integrity_controls")
class TestMissingDocEscalationOwner(PlasticosTestCase):
    """The escalation Activity belongs to an Operations Manager, never to the cron user."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "Escalation Partner", "is_company": True, "customer_rank": 1, "supplier_rank": 1}
        )
        cls.tag = cls.env["plasticos.document.tag"].create({"name": "Escalation Tag", "code": "ESCALATIONTAG"})
        cls.env["plasticos.document.validation.matrix"].create(
            {"name": "Escalation Supplier", "doc_category": "supplier", "tag_id": cls.tag.id}
        )
        cls.managers = cls.env["res.groups"].create({"name": "Integrity Escalation Managers"})
        cls.cron_user = cls.env.ref("plasticos_base.user_system_cron")

    def _user(self, login, groups, active=True):
        return self.env["res.users"].create(
            {
                "name": login,
                "login": login,
                "active": active,
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id, *groups.ids])],
            }
        )

    def _transaction(self, name):
        return self.env["plasticos.transaction"].create(
            {"name": name, "supplier_id": self.partner.id, "buyer_id": self.partner.id, "quantity": 44000}
        )

    def _activities(self, transaction):
        return self.env["mail.activity"].search(
            [
                ("res_model", "=", "plasticos.transaction"),
                ("res_id", "=", transaction.id),
                ("summary", "=", f"ESCALATION: Missing documents on {transaction.name}"),
            ]
        )

    def _notes(self, transaction):
        return transaction.message_ids.filtered(lambda message: UNASSIGNED_MARKER in (message.body or ""))

    def _run_page(self, page, group):
        tag = self.tag

        def _missing(self, res_model, res_id, purpose=None):
            return [tag.code]

        model = type(self.env["plasticos.transaction"])
        service = type(self.env["plasticos.compliance.service"])
        with (
            patch.object(service, "get_missing_documents", _missing),
            patch.object(model, "_count_business_days", staticmethod(_five_business_days)),
            patch.object(model, "_escalation_manager_group", lambda self: group),
        ):
            return page.with_user(self.cron_user)._apply_missing_doc_page(page.with_user(self.cron_user))

    def test_escalation_group_is_operations_manager(self):
        model = self.env["plasticos.transaction"]
        operations = self.env.ref("plasticos_security_base.group_operations_manager")
        self.assertEqual(model._escalation_manager_group(), operations)
        self.assertEqual(model._scale_ticket_manager_group(), operations)
        sales = self._user("integrity.sales.only", self.env.ref("plasticos_security_base.group_sales_rep"))
        logistics = self._user("integrity.logistics.only", self.env.ref("plasticos_security_base.group_logistics"))
        owner = model._get_logistics_manager(operations)
        self.assertNotIn(owner, sales | logistics)
        if owner:
            self.assertTrue(owner.has_group("plasticos_security_base.group_operations_manager"))

    def test_owner_is_active_internal_non_cron_and_deterministic(self):
        model = self.env["plasticos.transaction"]
        self.assertFalse(model._get_logistics_manager(self.env["res.groups"]))
        self.assertFalse(model._get_logistics_manager(self.managers))
        self.cron_user.write({"group_ids": [fields.Command.link(self.managers.id)]})
        self._user("integrity.manager.inactive", self.managers, active=False)
        self.assertFalse(model._get_logistics_manager(self.managers))
        first = self._user("integrity.manager.first", self.managers)
        self._user("integrity.manager.second", self.managers)
        self.assertEqual(model._get_logistics_manager(self.managers), first)
        self.assertEqual(model._get_logistics_manager(self.managers), first)

    def test_owner_is_scoped_to_the_record_company(self):
        """POS-INV-05: a manager of another legal company never owns the escalation."""
        model = self.env["plasticos.transaction"]
        other = self.env["res.company"].create({"name": "Integrity Other Company"})
        foreign = self.env["res.users"].create(
            {
                "name": "integrity.manager.foreign",
                "login": "integrity.manager.foreign",
                "company_id": other.id,
                "company_ids": [(6, 0, [other.id])],
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id, self.managers.id])],
            }
        )
        home = self.env.company
        self.assertFalse(model._get_logistics_manager(self.managers, home))
        self.assertEqual(model._get_logistics_manager(self.managers, other), foreign)
        local = self._user("integrity.manager.local", self.managers)
        owners = model._escalation_owners(self.managers, {1: home, 2: other, 3: home | other, 4: home.browse()})
        self.assertEqual(owners[1], local)
        self.assertEqual(owners[2], foreign)
        self.assertFalse(owners[3])
        self.assertEqual(owners[4], foreign)

    def test_implied_membership_counts(self):
        senior = self.env["res.groups"].create(
            {"name": "Integrity Senior Managers", "implied_ids": [fields.Command.link(self.managers.id)]}
        )
        owner = self._user("integrity.manager.implied", senior)
        self.assertEqual(self.env["plasticos.transaction"]._get_logistics_manager(self.managers), owner)

    def test_escalation_is_assigned_to_the_manager_once(self):
        owner = self._user("integrity.manager.owner", self.managers)
        first = self._transaction("TX-INTEGRITY-OWNER-A")
        second = self._transaction("TX-INTEGRITY-OWNER-B")
        page = first | second
        result = self._run_page(page, self.managers)
        self.assertEqual(result, {"processed": 2, "failures": 0})
        for transaction in page:
            activities = self._activities(transaction)
            self.assertEqual(len(activities), 1)
            self.assertEqual(activities.user_id, owner)
            self.assertNotEqual(activities.user_id, self.cron_user)
            self.assertEqual(transaction.missing_doc_status, "escalated")
            self.assertFalse(self._notes(transaction))
        self._run_page(page, self.managers)
        for transaction in page:
            self.assertEqual(len(self._activities(transaction)), 1)

    def test_no_manager_is_logged_noted_once_and_counted(self):
        first = self._transaction("TX-INTEGRITY-NOOWNER-A")
        second = self._transaction("TX-INTEGRITY-NOOWNER-B")
        page = first | second
        with self.assertLogs(LOGGER, level="ERROR") as captured:
            result = self._run_page(page, self.managers)
        self.assertEqual(result, {"processed": 2, "failures": 2})
        self.assertTrue(any("no Operations Manager" in line for line in captured.output))
        for transaction in page:
            self.assertFalse(self._activities(transaction))
            self.assertEqual(len(self._notes(transaction)), 1)
            self.assertEqual(transaction.missing_doc_status, "escalated")
        with self.assertLogs(LOGGER, level="ERROR"):
            again = self._run_page(page, self.managers)
        self.assertEqual(again["failures"], 2)
        for transaction in page:
            page.invalidate_recordset(["message_ids"])
            self.assertEqual(len(self._notes(transaction)), 1)
            self.assertFalse(self._activities(transaction))


@tagged("post_install", "-at_install", "documents", "integrity_controls")
class TestMissingDocCursor(PlasticosTestCase):
    """The cron walks every active transaction; it does not re-read the oldest page forever."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "Cursor Partner", "is_company": True, "customer_rank": 1, "supplier_rank": 1}
        )
        cls.transactions = cls.env["plasticos.transaction"]
        for index in range(5):
            cls.transactions |= cls.env["plasticos.transaction"].create(
                {
                    "name": f"TX-INTEGRITY-CURSOR-{index}",
                    "supplier_id": cls.partner.id,
                    "buyer_id": cls.partner.id,
                    "quantity": 44000,
                }
            )
        cls.transactions.with_context(bypass_state_guard=True).write({"state": "active"})
        cls.transactions = cls.transactions.sorted("id")

    def _pages(self, model, runs):
        pages = []

        def recorder(self, transactions):
            pages.append(transactions)
            return {"processed": len(transactions), "failures": 0}

        with patch.object(type(self.env["plasticos.transaction"]), "_apply_missing_doc_page", recorder):
            results = [model.cron_check_missing_docs() for _run in range(runs)]
        return pages, results

    def _cursor(self):
        return self.env["ir.config_parameter"].get_param(CURSOR_KEY)

    def test_cursor_advances_past_the_first_page_and_wraps(self):
        self.assertEqual(self.transactions.mapped("state"), ["active"] * 5)
        self.env["ir.config_parameter"].set_param(CURSOR_KEY, str(self.transactions[0].id - 1))
        model = self.env["plasticos.transaction"].with_context(missing_doc_batch_size=2)
        pages, results = self._pages(model, 3)
        self.assertEqual(
            [page.ids for page in pages],
            [self.transactions[:2].ids, self.transactions[2:4].ids, self.transactions[4:].ids],
        )
        self.assertFalse(set(pages[0].ids) & set(pages[1].ids))
        self.assertEqual(results[0], {"processed": 2, "failures": 0, "skipped": False})
        # The short last page wraps; the following run starts again from the lowest id.
        self.assertEqual(self._cursor(), "0")
        pages, _results = self._pages(model, 1)
        self.assertEqual(len(pages[0]), 2)
        self.assertEqual(self._cursor(), str(pages[0][-1].id))

    def test_inactive_transactions_stay_out_of_the_page(self):
        draft = self.env["plasticos.transaction"].create(
            {
                "name": "TX-INTEGRITY-CURSOR-DRAFT",
                "supplier_id": self.partner.id,
                "buyer_id": self.partner.id,
                "quantity": 44000,
            }
        )
        self.assertNotEqual(draft.state, "active")
        self.env["ir.config_parameter"].set_param(CURSOR_KEY, str(self.transactions[0].id - 1))
        model = self.env["plasticos.transaction"].with_context(missing_doc_batch_size=50)
        pages, _results = self._pages(model, 1)
        self.assertNotIn(draft, pages[0])
        self.assertTrue(set(self.transactions.ids) <= set(pages[0].ids))

    def test_cron_user_without_settings_access_keeps_the_cursor(self):
        cron_user = self.env.ref("plasticos_base.user_system_cron")
        self.assertFalse(cron_user.has_group("base.group_system"))
        self.env["ir.config_parameter"].set_param(CURSOR_KEY, str(self.transactions[0].id - 1))
        model = self.env["plasticos.transaction"].with_user(cron_user).with_context(missing_doc_batch_size=2)
        pages, _results = self._pages(model, 1)
        self.assertEqual(pages[0].ids, self.transactions[:2].ids)
        self.assertEqual(self._cursor(), str(self.transactions[1].id))
        scale = self.env["plasticos.transaction"].with_user(cron_user)
        scale._set_scale_ticket_retry_ids([])
        self.assertEqual(scale._scale_ticket_retry_ids(), [])
