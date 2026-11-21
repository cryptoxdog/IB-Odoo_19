"""DEC-010 exception routing and DEC-012 idempotent activities (TASK-060, AC-060, A13-A15, A18)."""

from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.addons.plasticos_documents.models.exception_router import (
    EXC_ASSOCIATION_REVIEW,
    EXC_BLOCKED_BILL,
    EXC_CLASSIFICATION_REVIEW,
    EXC_DUPLICATE_CANDIDATE,
    EXC_EVIDENCE_GAP,
    EXC_MISSING_DOCUMENTS,
    EXC_MISSING_SCALE_TICKET,
    LOGISTICS,
    OPERATIONS,
    Obligation,
)
from odoo.addons.plasticos_logistics.models.load import (
    _ACTUAL_EVENT_INTERNAL_WRITE,
    _ACTUAL_EVENT_INTERNAL_WRITE_TOKEN,
    _FREIGHT_INTERNAL_WRITE,
    _FREIGHT_INTERNAL_WRITE_TOKEN,
)
from odoo.tests import TransactionCase, tagged

LOGISTICS_GROUP = "plasticos_security_base.group_logistics_ops"
OPERATIONS_GROUP = "plasticos_security_base.group_operations_manager"


def _five_business_days(_start_date, _end_date):
    return 5


@tagged("post_install", "-at_install", "documents", "exception_routing")
class TestExceptionRouting(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.router = cls.env["plasticos.exception.router"]
        cls.internal = cls.env.ref("base.group_user")
        cls.logistics_group = cls.env.ref(LOGISTICS_GROUP)
        cls.operations_group = cls.env.ref(OPERATIONS_GROUP)
        cls.cron_user = cls.env.ref("plasticos_base.user_system_cron")
        cls.linda = cls.env.ref("plasticos_logistics.user_linda")
        # Seed users are never modified (AGENTS.md); a dedicated fixture stands in for a service user.
        cls.ops_manager = cls._user("route.ops.manager", cls.operations_group)
        cls.logistics_user = cls._user("route.logistics.user", cls.logistics_group)
        cls.buyer = cls.env["res.partner"].create({"name": "Route Buyer", "customer_rank": 1})
        cls.supplier = cls.env["res.partner"].create({"name": "Route Supplier", "supplier_rank": 1})

    @classmethod
    def _user(cls, login, group):
        return cls.env["res.users"].create(
            {"name": login, "login": login, "group_ids": [(6, 0, [cls.internal.id, group.id])]}
        )

    def _transaction(self, name):
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        return self.env["plasticos.transaction"].create(
            {"name": name, "supplier_id": self.supplier.id, "buyer_id": self.buyer.id, "sale_order_id": order.id}
        )

    def _logistics_owner(self):
        route = self.router.route(self.router.purpose_from_tag_codes(["BOL"]), EXC_MISSING_DOCUMENTS)
        owner = self.router.owner(route, self.env.company)
        self.assertTrue(owner)
        self.assertFalse(owner.has_group(OPERATIONS_GROUP))
        return owner

    def _open(self, record, summary):
        return self.env["mail.activity"].search(
            [("res_model", "=", record._name), ("res_id", "=", record.id), ("summary", "=", summary)]
        )

    # ── The routing matrix (decided by obligation, never by file name or a tag alone) ──
    def test_routing_matrix(self):
        confident_bol = self.router.purpose_from_tag_codes(["BOL"])
        scale = self.router.purpose_from_tag_codes(["SCALE", "CST"])
        invoice = self.router.purpose_from_tag_codes(["INV"])
        mixed = self.router.purpose_from_tag_codes(["BOL", "INV"])
        unknown = self.router.purpose_from_tag_codes([])
        unattributed_bol = self.router.purpose_from_tag_codes(["BOL"], attributed=False)
        cases = [
            (confident_bol, EXC_MISSING_DOCUMENTS, LOGISTICS),
            (scale, EXC_MISSING_SCALE_TICKET, LOGISTICS),
            (confident_bol, EXC_EVIDENCE_GAP, LOGISTICS),
            (invoice, EXC_MISSING_DOCUMENTS, OPERATIONS),
            (mixed, EXC_MISSING_DOCUMENTS, OPERATIONS),
            (unknown, EXC_ASSOCIATION_REVIEW, OPERATIONS),
            (unattributed_bol, EXC_ASSOCIATION_REVIEW, OPERATIONS),
            (confident_bol, EXC_CLASSIFICATION_REVIEW, OPERATIONS),
            (confident_bol, EXC_DUPLICATE_CANDIDATE, OPERATIONS),
            (confident_bol, EXC_BLOCKED_BILL, OPERATIONS),
        ]
        for purpose, exception_class, role in cases:
            with self.subTest(purpose=purpose, exception_class=exception_class):
                route = self.router.route(purpose, exception_class)
                self.assertEqual(route.role, role)
                self.assertTrue(self.env.ref(route.activity_type_xmlid))

    def test_uncertain_classification_with_a_logistics_candidate_goes_to_operations(self):
        """A14: a logistics candidate on an unsettled association is not enough."""
        purpose = self.router.purpose_from_doc_type("bol", attributed=False, attribution_reason="No reference.")
        self.assertEqual(purpose.family, LOGISTICS)
        self.assertFalse(purpose.confident)
        self.assertEqual(self.router.route(purpose, EXC_ASSOCIATION_REVIEW).role, OPERATIONS)
        unclassified = self.router.purpose_from_doc_type(False, attributed=True)
        self.assertEqual(self.router.route(unclassified, EXC_ASSOCIATION_REVIEW).role, OPERATIONS)
        attributed = self.router.purpose_from_doc_type("bol", attributed=True)
        self.assertEqual(self.router.route(attributed, EXC_ASSOCIATION_REVIEW).role, LOGISTICS)
        invoice = self.router.purpose_from_doc_type("invoice", attributed=True)
        self.assertEqual(self.router.route(invoice, EXC_ASSOCIATION_REVIEW).role, OPERATIONS)

    # ── Owners ──
    def test_service_users_and_operations_managers_never_own_logistics_work(self):
        route = self.router.route(self.router.purpose_from_tag_codes(["BOL"]), EXC_MISSING_DOCUMENTS)
        owner = self.router.owner(route, self.env.company)
        self.assertTrue(owner)
        self.assertNotIn(owner, self.cron_user | self.linda)
        self.assertFalse(owner.has_group(OPERATIONS_GROUP))
        ops_route = self.router.route(self.router.purpose_from_tag_codes(["INV"]), EXC_MISSING_DOCUMENTS)
        ops_owner = self.router.owner(ops_route, self.env.company)
        self.assertTrue(ops_owner.has_group(OPERATIONS_GROUP))
        self.assertNotIn(ops_owner, self.cron_user | self.linda)
        self.assertFalse(self.router.owner(route, self.env.company | self.env["res.company"].create({"name": "X"})))

    def test_a_service_user_holding_the_group_is_never_the_owner(self):
        """Linda is excluded by her seed XML id; a stand-in proves the exclusion beats group membership."""
        self.assertIn(self.linda.id, self.router._service_user_ids())
        stand_in = self._user("route.service.standin", self.logistics_group)
        router_cls = type(self.router)
        route = self.router.route(self.router.purpose_from_tag_codes(["BOL"]), EXC_MISSING_DOCUMENTS)
        with patch.object(router_cls, "_service_user_ids", lambda router: [stand_in.id]):
            owner = self.router.owner(route, self.env.company)
            self.assertNotEqual(owner, stand_in)
            self.assertFalse(self.router.owner_is_valid(stand_in, route, self.env.company))
            self.assertTrue(self.router.owner_is_valid(owner, route, self.env.company))

    # ── Idempotent activities (A18) ──
    def test_schedule_reassign_resolve_never_duplicates_or_wrongly_closes(self):
        tx = self._transaction("TX-ROUTE-IDEMPOTENT")
        purpose = self.router.purpose_from_tag_codes(["BOL"])
        bol = Obligation("Missing BOL on TX-ROUTE-IDEMPOTENT", purpose, EXC_MISSING_DOCUMENTS, "BOL missing.")
        first = self.router.schedule(tx, bol, self.env.company)
        self.assertEqual(first.user_id, self._logistics_owner())
        self.assertEqual(first.activity_type_id, self.env.ref("plasticos_documents.activity_type_missing_documents"))
        self.assertEqual(self.router.schedule(tx, bol, self.env.company), first)
        # A person hands it to another Logistics user: the router keeps that choice.
        colleague = self._user("route.logistics.colleague", self.logistics_group)
        first.write({"user_id": colleague.id})
        self.router.schedule(tx, bol, self.env.company)
        self.assertEqual(first.user_id, colleague)
        # Handed to a salesperson or an Operations Manager (older routing): reassigned, not duplicated.
        first.write({"user_id": self.ops_manager.id})
        self.router.schedule(tx, bol, self.env.company)
        self.assertEqual(first.user_id, self._logistics_owner())
        self.assertEqual(len(self._open(tx, bol.summary)), 1)
        # A second obligation on the same record is independent; resolving one keeps the other.
        invoice = Obligation(
            "Invoice discrepancy on TX-ROUTE-IDEMPOTENT",
            self.router.purpose_from_tag_codes(["INV"]),
            EXC_DUPLICATE_CANDIDATE,
            "Amounts differ.",
        )
        other = self.router.schedule(tx, invoice, self.env.company)
        self.router.resolve(tx, bol.summary, "BOL received.")
        self.assertFalse(self._open(tx, bol.summary))
        self.assertEqual(self._open(tx, invoice.summary), other)
        # Reloading after resolution raises the obligation again, once.
        again = self.router.schedule(tx, bol, self.env.company)
        self.assertEqual(len(self._open(tx, bol.summary)), 1)
        self.assertNotEqual(again, first)

    # ── Writers ──
    def test_missing_shipping_documents_go_to_logistics_and_financial_to_operations(self):
        tag = self.env["plasticos.document.tag"].search([("code", "=", "BOL")], limit=1)
        inv = self.env["plasticos.document.tag"].search([("code", "=", "INV")], limit=1)
        self.assertTrue(tag and inv, "BOL and INV tags are module data")
        matrix = self.env["plasticos.document.validation.matrix"]
        for row_tag, category in ((tag, "carrier"), (inv, "supplier")):
            matrix.create({"name": f"Route {row_tag.code}", "doc_category": category, "tag_id": row_tag.id})
        bol_tx = self._transaction("TX-ROUTE-MISSING-BOL")
        inv_tx = self._transaction("TX-ROUTE-MISSING-INV")
        codes = {bol_tx.id: [tag.code], inv_tx.id: [inv.code]}

        def _missing(service, res_model, res_id, purpose=None):
            return codes[res_id]

        model = type(self.env["plasticos.transaction"])
        service = type(self.env["plasticos.compliance.service"])
        page = bol_tx | inv_tx
        with (
            patch.object(service, "get_missing_documents", _missing),
            patch.object(model, "_count_business_days", staticmethod(_five_business_days)),
        ):
            for _run in range(2):
                page.with_user(self.cron_user)._apply_missing_doc_page(page.with_user(self.cron_user))
            bol_activity = self._open(bol_tx, f"ESCALATION: Missing documents on {bol_tx.name}")
            inv_activity = self._open(inv_tx, f"ESCALATION: Missing documents on {inv_tx.name}")
            self.assertEqual(len(bol_activity), 1)
            self.assertEqual(len(inv_activity), 1)
            self.assertEqual(bol_activity.user_id, self._logistics_owner())
            self.assertTrue(inv_activity.user_id.has_group(OPERATIONS_GROUP))
            self.assertNotIn(bol_activity.user_id | inv_activity.user_id, self.cron_user | self.linda)
            # Documents complete: the escalation is closed by the next page.
            codes[bol_tx.id] = []
            page._apply_missing_doc_page(page)
            self.assertFalse(self._open(bol_tx, f"ESCALATION: Missing documents on {bol_tx.name}"))
            self.assertEqual(len(self._open(inv_tx, f"ESCALATION: Missing documents on {inv_tx.name}")), 1)

    def _delivered_load(self, name):
        tx = self._transaction(name)
        load = self.env["plasticos.load"].create({"sale_order_id": tx.sale_order_id.id})
        tx.with_context(bypass_state_guard=True).write({"state": "delivered"})
        when = fields.Datetime.now() - timedelta(days=30)
        load.with_context(**{_FREIGHT_INTERNAL_WRITE: _FREIGHT_INTERNAL_WRITE_TOKEN}).write(
            {"state": "delivered", "delivered_at": when, "dispatched_at": when}
        )
        load.with_context(**{_ACTUAL_EVENT_INTERNAL_WRITE: _ACTUAL_EVENT_INTERNAL_WRITE_TOKEN}).write(
            {"actual_pickup_at": when, "actual_delivery_at": when}
        )
        return load

    def _run_scale_cron(self, load):
        params = self.env["ir.config_parameter"]
        params.set_param("plasticos_documents.scale_ticket_retry_ids", "")
        params.set_param("plasticos_documents.scale_ticket_scan_cursor", str(load.id - 1))
        self.env["plasticos.transaction"].with_context(scale_ticket_batch_size=1).cron_check_scale_tickets()

    def test_missing_scale_ticket_is_one_logistics_activity(self):
        """A13: a confidently attributed scale-ticket exception is exactly one Logistics activity."""
        if not self.env["plasticos.document.tag"].search([("code", "=", "SCALE")], limit=1):
            self.env["plasticos.document.tag"].create({"name": "Scale Ticket", "code": "SCALE"})
        load = self._delivered_load("TX-ROUTE-SCALE")
        summary = f"ESCALATION: Missing scale ticket on {load.name}"
        self._run_scale_cron(load)
        self._run_scale_cron(load)
        activity = self._open(load, summary)
        self.assertEqual(len(activity), 1)
        self.assertEqual(activity.user_id, self._logistics_owner())
        self.assertEqual(
            activity.activity_type_id, self.env.ref("plasticos_documents.activity_type_missing_scale_ticket")
        )

    def test_reroute_moves_old_escalations_once(self):
        """The 19.0.2.1.24 migration: an old Operations to-do moves to Logistics; a rerun changes nothing."""
        load = self._delivered_load("TX-ROUTE-MIGRATE")
        summary = f"ESCALATION: Missing scale ticket on {load.name}"
        old = load.activity_schedule("mail.mail_activity_data_todo", summary=summary, user_id=self.ops_manager.id)
        duplicate = load.activity_schedule("mail.mail_activity_data_todo", summary=summary, user_id=self.ops_manager.id)
        reroute = self.env["plasticos.escalation.reroute"]
        first = reroute.reroute_open_escalations()
        self.assertGreaterEqual(first.rerouted, 1)
        self.assertGreaterEqual(first.before[OPERATIONS], 2)
        self.assertEqual(self._open(load, summary), old)
        self.assertNotIn(duplicate, self._open(load, summary))
        self.assertEqual(old.user_id, self._logistics_owner())
        self.assertEqual(old.activity_type_id, self.env.ref("plasticos_documents.activity_type_missing_scale_ticket"))
        second = reroute.reroute_open_escalations()
        self.assertEqual(second.rerouted, 0)
        self.assertEqual(second.before, second.after)

    def test_current_ticket_closes_the_escalation_and_rearms_it(self):
        """A resolved gap closes its activity and clears the flag, so a later gap escalates again."""
        if not self.env["plasticos.document.tag"].search([("code", "=", "SCALE")], limit=1):
            self.env["plasticos.document.tag"].create({"name": "Scale Ticket", "code": "SCALE"})
        load = self._delivered_load("TX-ROUTE-SCALE-REARM")
        summary = f"ESCALATION: Missing scale ticket on {load.name}"
        self._run_scale_cron(load)
        self.assertTrue(load.scale_ticket_escalated)
        self.assertEqual(len(self._open(load, summary)), 1)
        model = type(self.env["plasticos.transaction"])
        with patch.object(model, "_load_has_current_scale_ticket", lambda self, load, tag: True):
            self._run_scale_cron(load)
        self.assertFalse(load.scale_ticket_escalated)
        self.assertFalse(self._open(load, summary))
        # The ticket is later invalidated: the still-missing ticket is escalated again, once.
        self._run_scale_cron(load)
        self._run_scale_cron(load)
        self.assertTrue(load.scale_ticket_escalated)
        self.assertEqual(len(self._open(load, summary)), 1)
