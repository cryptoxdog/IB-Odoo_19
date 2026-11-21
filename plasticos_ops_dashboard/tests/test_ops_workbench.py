"""Operations Manager workbench: queue parity, routing, Return to Logistics, roles and company (TASK-040).

AC-040 / A11 / A16 / A29. The queues are drills over existing records; these tests create the
records through their real owners (the DEC-010 router, the bill-hold entry point) and check what the
Operations Manager sees, what other roles cannot reach, and that the module stores no queue.
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import tagged

OPERATIONS_GROUP = "plasticos_security_base.group_operations_manager"


def _router_api():
    from odoo.addons.plasticos_documents.models import exception_router

    return exception_router


def _workbench_api():
    from odoo.addons.plasticos_ops_dashboard.models import ops_workbench

    return ops_workbench


@tagged("post_install", "-at_install", "ops_workbench")
class TestOpsWorkbench(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        internal = cls.env.ref("base.group_user")
        cls.company_a = cls.env.company
        cls.company_b = cls.env["res.company"].create({"name": "TASK-040 Company B"})
        cls.ops = cls._user("task040_ops_a", [internal, cls.env.ref(OPERATIONS_GROUP)], cls.company_a)
        cls.ops_b = cls._user("task040_ops_b", [internal, cls.env.ref(OPERATIONS_GROUP)], cls.company_b)
        cls.logistics_ops = cls._user(
            "task040_logistics_ops",
            [internal, cls.env.ref("plasticos_security_base.group_logistics_ops")],
            cls.company_a,
        )
        cls.logistics = cls._user(
            "task040_logistics", [internal, cls.env.ref("plasticos_security_base.group_logistics")], cls.company_a
        )
        cls.sales = cls._user(
            "task040_sales", [internal, cls.env.ref("plasticos_security_base.group_sales_rep")], cls.company_a
        )
        cls.partner = cls.env["res.partner"].create({"name": "TASK-040 Partner", "is_company": True})
        order = cls.env["sale.order"].create({"partner_id": cls.partner.id, "company_id": cls.company_a.id})
        cls.tx = cls.env["plasticos.transaction"].create(
            {"supplier_id": cls.partner.id, "buyer_id": cls.partner.id, "quantity": 1, "sale_order_id": order.id}
        )
        cls.router = cls.env["plasticos.exception.router"]
        cls.workbench = cls.env["plasticos.ops.workbench"]

    @classmethod
    def _user(cls, login, groups, company):
        return cls.env["res.users"].create(
            {
                "name": login,
                "login": login,
                "company_id": company.id,
                "company_ids": [(6, 0, [company.id])],
                "group_ids": [(6, 0, [group.id for group in groups])],
            }
        )

    def _schedule(self, record, summary, codes, exception_class, attributed=True, company=None):
        api = _router_api()
        purpose = self.router.purpose_from_tag_codes(codes, attributed=attributed)
        obligation = api.Obligation(summary, purpose, exception_class, "TASK-040 fixture.")
        return self.router.schedule(record, obligation, company or self.company_a)

    def _drill(self, user, key):
        action = self.workbench.with_user(user).action_open_kpi(key)
        return self.env[action["res_model"]].with_user(user).search(action["domain"])

    def test_every_queue_count_equals_its_drill(self):
        """DEC-007: each queue is declared once; its count and its drill use the same domain."""
        api = _router_api()
        self._schedule(self.tx, "TASK-040 ambiguous classification", [], api.EXC_CLASSIFICATION_REVIEW)
        self._schedule(self.tx, "TASK-040 missing BOL", ["BOL"], api.EXC_MISSING_DOCUMENTS)
        values = self.workbench.with_user(self.ops).kpi_values()
        self.assertEqual(set(values), set(_workbench_api().WORKBENCH_KPIS))
        for key, count in values.items():
            with self.subTest(queue=key):
                self.assertEqual(count, len(self._drill(self.ops, key)))

    def test_ambiguous_classification_is_in_the_operations_inbox_and_logistics_work_is_not(self):
        api = _router_api()
        ambiguous = self._schedule(self.tx, "TASK-040 unclassified original", ["BOL"], api.EXC_CLASSIFICATION_REVIEW)
        shipping = self._schedule(self.tx, "TASK-040 attributed BOL missing", ["BOL"], api.EXC_MISSING_DOCUMENTS)
        self.assertTrue(ambiguous.user_id.has_group(OPERATIONS_GROUP))
        self.assertFalse(shipping.user_id.has_group(OPERATIONS_GROUP))
        team = self._drill(self.ops, "team_exceptions")
        self.assertIn(ambiguous, team)
        self.assertIn(ambiguous, self._drill(self.ops, "classification_reviews"))
        # Logistics-owned work never appears in an Operations queue (no duplicated item).
        self.assertNotIn(shipping, team)
        self.assertNotIn(shipping, self._drill(self.ops, "document_gaps"))

    def test_held_digitized_bill_is_in_the_inbox_and_stays_unposted(self):
        """A16: the held bill appears through its hold activity; the workbench posts nothing."""
        bill = self.env["account.move"].create(
            {"move_type": "in_invoice", "partner_id": self.partner.id, "company_id": self.company_a.id}
        )
        self.env["plasticos.document.sync"]._schedule_manager_activity(
            bill, "Digitized vendor bill needs manager review", "Total mismatch: document 100.00, bill 90.00."
        )
        held = self._drill(self.ops, "held_vendor_bills").filtered(lambda a: a.res_model == "account.move")
        self.assertIn(bill.id, held.mapped("res_id"))
        self.assertEqual(bill.state, "draft")
        activity = held.filtered(lambda a: a.res_id == bill.id)
        self.assertFalse(activity.with_user(self.ops).plasticos_can_return_to_logistics)
        self.assertIn("not verified", activity.with_user(self.ops).plasticos_candidate_facts)
        self.assertFalse(hasattr(type(activity), "action_post"))

    def test_return_to_logistics_reassigns_the_one_activity(self):
        api = _router_api()
        activity = self._schedule(
            self.tx, "TASK-040 unattributed BOL", ["BOL"], api.EXC_MISSING_DOCUMENTS, attributed=False
        )
        self.assertTrue(activity.user_id.has_group(OPERATIONS_GROUP))
        before = self.env["mail.activity"].search_count([("summary", "=", activity.summary)])
        activity.with_user(self.ops).action_plasticos_return_to_logistics()
        self.assertFalse(activity.user_id.has_group(OPERATIONS_GROUP))
        self.assertTrue(activity.user_id.has_group("plasticos_security_base.group_logistics_ops"))
        self.assertEqual(self.env["mail.activity"].search_count([("summary", "=", activity.summary)]), before)

    def test_return_to_logistics_is_refused_for_operations_classes_and_other_roles(self):
        api = _router_api()
        classification = self._schedule(self.tx, "TASK-040 conflicting types", [], api.EXC_CLASSIFICATION_REVIEW)
        with self.assertRaises(UserError):
            classification.with_user(self.ops).action_plasticos_return_to_logistics()
        gap = self._schedule(self.tx, "TASK-040 gap", ["BOL"], api.EXC_MISSING_DOCUMENTS, attributed=False)
        with self.assertRaises(AccessError):
            gap.with_user(self.logistics_ops).action_plasticos_return_to_logistics()
        self.assertTrue(gap.user_id.has_group(OPERATIONS_GROUP))

    def test_operations_manager_reads_but_cannot_write_claims(self):
        """DEC-005 (a), A29."""
        claim = self.env["plasticos.claim"].create(
            {"transaction_id": self.tx.id, "case_type": "other", "severity": "low"}
        )
        self.assertEqual(claim.with_user(self.ops).read(["name"])[0]["id"], claim.id)
        with self.assertRaises(AccessError):
            claim.with_user(self.ops).write({"severity": "high"})
        for outsider in (self.sales, self.logistics):
            with self.subTest(user=outsider.login), self.assertRaises(AccessError):
                claim.with_user(outsider).read(["name"])

    def test_sales_and_logistics_cannot_reach_financial_items(self):
        bill = self.env["account.move"].create(
            {"move_type": "in_invoice", "partner_id": self.partner.id, "company_id": self.company_a.id}
        )
        for outsider in (self.sales, self.logistics):
            with self.subTest(user=outsider.login), self.assertRaises(AccessError):
                bill.with_user(outsider).read(["amount_total"])

    def test_workbench_menus_are_operations_only(self):
        """DEC-005 (b), A11: a sales rep or a Logistics user cannot open the workbench."""
        menus = self.env["ir.ui.menu"]
        root = self.env.ref("plasticos_ops_dashboard.menu_ops_root")
        self.assertIn(root.id, menus.with_user(self.ops)._visible_menu_ids())
        for outsider in (self.sales, self.logistics_ops):
            with self.subTest(user=outsider.login):
                self.assertNotIn(root.id, menus.with_user(outsider)._visible_menu_ids())
        action = self.env.ref("plasticos_ops_dashboard.action_ops_team")
        self.assertEqual(action.group_ids, self.env.ref(OPERATIONS_GROUP))

    def test_another_companys_item_never_appears(self):
        """POS-INV-05: a load of company B and its exception stay out of company A's queues."""
        api = _router_api()
        order_b = self.env["sale.order"].create({"partner_id": self.partner.id, "company_id": self.company_b.id})
        load_b = self.env["plasticos.load"].create({"sale_order_id": order_b.id, "company_id": self.company_b.id})
        activity = self._schedule(
            load_b,
            "TASK-040 company B gap",
            ["BOL"],
            api.EXC_MISSING_DOCUMENTS,
            attributed=False,
            company=self.company_b,
        )
        self.assertEqual(activity.user_id, self.ops_b)
        for key in ("team_exceptions", "overdue_exceptions", "document_gaps", "unassigned_exceptions"):
            with self.subTest(queue=key):
                self.assertNotIn(activity, self._drill(self.ops, key))
        self.assertIn(activity, self._drill(self.ops_b, "team_exceptions"))

    def test_module_defines_no_queue_model(self):
        """DEC-004 / A29: presentation only. No stored model; the correction wizard is transient."""
        owned = self.env["ir.model"].search([("model", "=like", "plasticos.ops.%")])
        self.assertEqual(sorted(owned.mapped("model")), ["plasticos.ops.request.correction", "plasticos.ops.workbench"])
        self.assertTrue(self.env["plasticos.ops.workbench"]._abstract)
        self.assertTrue(self.env["plasticos.ops.request.correction"]._transient)

    def _correction(self, activity, user, reason):
        wizard = (
            self.env["plasticos.ops.request.correction"]
            .with_user(user)
            .create({"activity_id": activity.id, "reason": reason})
        )
        return wizard.action_request_correction()

    def test_request_correction_is_internal_and_keeps_the_one_activity(self):
        """CTO ruling on Request Correction: internal note, reason on the same activity, no external mail."""
        api = _router_api()
        activity = self._schedule(self.tx, "TASK-040 BOL wrong load", ["BOL"], api.EXC_MISSING_DOCUMENTS, False)
        owner = activity.user_id
        mails_before = self.env["mail.mail"].search_count([])
        activities_before = self.env["mail.activity"].search_count([("summary", "=", activity.summary)])
        self._correction(activity, self.ops, "BOL names load 12, the original is for load 14.")
        self.assertEqual(activity.user_id, owner)
        self.assertIn("load 14", activity.note)
        self.assertEqual(
            self.env["mail.activity"].search_count([("summary", "=", activity.summary)]), activities_before
        )
        notes = self.tx.message_ids.filtered(lambda m: "Correction requested" in (m.body or ""))
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes.subtype_id, self.env.ref("mail.mt_note"))
        self.assertFalse(notes.partner_ids)
        self.assertEqual(self.env["mail.mail"].search_count([]), mails_before)

    def test_request_correction_requires_operations_and_a_reason(self):
        api = _router_api()
        activity = self._schedule(self.tx, "TASK-040 correction refused", ["BOL"], api.EXC_MISSING_DOCUMENTS, False)
        with self.assertRaises(UserError):
            self._correction(activity, self.ops, "   ")
        with self.assertRaises(AccessError):
            self._correction(activity, self.logistics_ops, "Not an Operations Manager.")

    def test_confirm_classification_opens_the_task_070_command(self):
        """Confirm Classification calls the original's Correct Classification command; it decides nothing."""
        import base64

        native = self.env["documents.document"].create(
            {
                "name": "task040-confirm.pdf",
                "folder_id": self.env.ref("plasticos_documents_native.folder_plasticos_inbox").id,
                "datas": base64.b64encode(b"%PDF-1.4 task040"),
                "doc_type": "bol",
            }
        )
        activity = self.env["mail.activity"].search(
            [("res_model", "=", "documents.document"), ("res_id", "=", native.id)], limit=1
        )
        self.assertTrue(activity)
        action = activity.with_user(self.ops).action_plasticos_confirm_classification()
        self.assertEqual(action["res_model"], "plasticos.document.classification.correction")
        self.assertEqual(action["context"]["default_document_id"], native.id)
        api = _router_api()
        other = self._schedule(self.tx, "TASK-040 not a document", [], api.EXC_CLASSIFICATION_REVIEW)
        with self.assertRaises(UserError):
            other.with_user(self.ops).action_plasticos_confirm_classification()
