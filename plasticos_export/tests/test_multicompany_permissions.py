"""Company access and source-linked attachment access (RP-07-E062, RP-07-E047, RP-07-E048).

Another company's user cannot see, count, print or command a booking, its
revisions, slots or cargo links, nor read its source original. A read-only role
reads but never writes. Accepted revisions resist every unscoped write.
BRS-EXP-14-R012. No outbound mail. Since the operator decision of 2026-11-12
(business_rules/SUPERSESSION.md) a same-company Sales Rep reads every cargo
allocation, read only, while the loads and orders behind it stay owner-scoped.
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import new_test_user, tagged
from odoo.tools.safe_eval import safe_eval

from .test_booking_and_revision import BOOKING, LINK, REVISION, SLOT, ExportFixtureMixin


@tagged("post_install", "-at_install", "plasticos", "plasticos_export")
class TestMulticompanyPermissions(ExportFixtureMixin, PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_export_fixture()
        cls.sales_reader = new_test_user(
            cls.env,
            login="s5b_export_sales_reader",
            groups="base.group_user,plasticos_security_base.group_sales_rep",
            company_id=cls.company.id,
            company_ids=[(6, 0, [cls.company.id])],
        )
        cls.sales_rep_b = new_test_user(
            cls.env,
            login="s7_export_sales_rep_b",
            groups="base.group_user,plasticos_security_base.group_sales_rep",
            company_id=cls.company.id,
            company_ids=[(6, 0, [cls.company.id])],
        )

    def _populated_booking(self):
        booking, revision = self.accepted_booking(confirmed=2)
        order = self.env["purchase.order"].create(
            {
                "partner_id": self.suppliers[0].id,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_qty": 1000, "product_uom_id": self.lb.id})
                ],
            }
        )
        outcome = (
            booking.slot_ids[0]
            .with_user(self.actor)
            .action_commit_cargo({"purchase_line_id": order.order_line.id}, None, None, revision.id, self.key())
        )
        self.assertEqual(outcome["status"], "applied")
        return booking, revision

    def test_other_company_sees_and_counts_nothing(self):
        """BRS-EXP-14-R012: record rules cover search, read and grouped counts."""
        booking, revision = self._populated_booking()
        for model, record in (
            (BOOKING, booking),
            (REVISION, revision),
            (SLOT, booking.slot_ids[0]),
            (LINK, self.env[LINK].search([("booking_id", "=", booking.id)])),
        ):
            Model = self.env[model].with_user(self.foreign_actor).with_context(active_test=False)
            self.assertFalse(Model.search([("id", "=", record.id)]), model)
            self.assertFalse(Model._read_group([("id", "in", record.ids)], [], ["__count"])[0][0], model)
            with self.assertRaises(AccessError), self.env.cr.savepoint():
                record.with_user(self.foreign_actor).read(["company_id"])
        visible = self.env[SLOT].with_user(self.actor).search([("booking_id", "=", booking.id)])
        self.assertEqual(len(visible), 2)

    def test_other_company_cannot_command_print_or_read_the_original(self):
        """E3, BRS-EXP-14-R012, BRS-EXP-13-R010: no command, no report, no source file across companies."""
        booking, revision = self._populated_booking()
        outcome = booking.with_user(self.foreign_actor).action_accept_booking_revision(
            revision.id, revision.id, self.key(), "cross-company"
        )
        self.assertEqual(outcome["status"], "not_available")
        slot_outcome = (
            booking.slot_ids[0]
            .with_user(self.foreign_actor)
            .action_release_cargo(1, revision.id, self.key(), "cross-company")
        )
        self.assertEqual(slot_outcome["status"], "not_available")
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            self.env["ir.actions.report"].with_user(self.foreign_actor)._render_qweb_html(
                "plasticos_export.report_booking_summary", booking.ids
            )
        attachment = revision.source_original_id.attachment_id
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            attachment.with_user(self.foreign_actor).read(["datas"])
        attachment.with_user(self.actor).read(["datas"])

    def test_foreign_company_booking_is_refused_at_create(self):
        """RP-07-E047: an actor creates bookings only in a company allowed to them."""
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            self.env[BOOKING].with_user(self.actor).create(
                {"company_id": self.company_b.id, "issuer_id": self.issuer.id, "source_occurrence_key": "x"}
            )

    def test_read_only_role_reads_but_never_writes(self):
        """RP-07-E047: least privilege for the sales reader."""
        booking, revision = self._populated_booking()
        self.assertEqual(booking.with_user(self.sales_reader).carrier_booking_no, "6509024800")
        self.assertEqual(revision.with_user(self.sales_reader).decision, "accepted")
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            booking.with_user(self.sales_reader).write({"carrier_id": self.line.id})
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            self.env[BOOKING].with_user(self.sales_reader).create(
                {"issuer_id": self.issuer.id, "source_occurrence_key": "reader"}
            )
        outcome = booking.with_user(self.sales_reader).record_booking_revision_candidate(
            False, self.incoming(booking).id, "rev-reader", self.terms(), self.key()
        )
        self.assertEqual(outcome["status"], "not_available")

    def test_accepted_revision_resists_stale_replay_and_unscoped_writes(self):
        """RP-07-E047: denial for accepted revision mutation; stale replay changes nothing."""
        booking, revision = self._populated_booking()
        before = revision.read(["erd_local", "decision", "accepted_at", "acceptance_basis"])
        with self.assertRaises(UserError), self.env.cr.savepoint():
            revision.with_user(self.actor).write({"decision": "rejected"})
        with self.assertRaises(UserError), self.env.cr.savepoint():
            revision.write({"acceptance_basis": "rewritten by admin"})
        later = self.candidate(booking, terms=self.terms(confirmed=2, erd_local="2026-11-01 08:00"))
        stale = booking.with_user(self.actor).action_accept_booking_revision(
            later["record_id"], False, self.key(), "replay from an old screen"
        )
        self.assertEqual(stale["status"], "stale")
        self.assertEqual(booking.current_revision_id, revision)
        self.assertEqual(revision.read(["erd_local", "decision", "accepted_at", "acceptance_basis"]), before)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            booking.slot_ids[0].with_user(self.actor).write({"hold_reason": "typed in"})

    # ── Sales Rep allocation audience (operator decision 2026-11-12) ──────────

    def _shared_allocations(self):
        """Two reps' cargo on one booking, plus one link in another company.

        Rep A (``sales_reader``) owns one sale order and its load; rep B owns
        another sale order, its load and a supplier PO line. Logistics commits
        both to the same booking through the Export command.
        """
        booking, revision = self._populated_booking()
        slot_a, slot_b = booking.slot_ids.sorted("slot_key")
        own_order = self.env["sale.order"].create({"partner_id": self.buyer.id, "user_id": self.sales_reader.id})
        own_order.order_line = [(0, 0, {"product_id": self.product.id, "product_uom_qty": 1})]
        other_order = self.env["sale.order"].create({"partner_id": self.buyer.id, "user_id": self.sales_rep_b.id})
        other_order.order_line = [(0, 0, {"product_id": self.product.id, "product_uom_qty": 1})]
        own_load = self.env["plasticos.load"].create({"sale_order_id": own_order.id})
        other_load = self.env["plasticos.load"].create({"sale_order_id": other_order.id})
        purchase = self.env["purchase.order"].create(
            {
                "partner_id": self.suppliers[2].id,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_qty": 700, "product_uom_id": self.lb.id})
                ],
            }
        )
        own = slot_a.with_user(self.actor).action_commit_cargo(
            {
                "sale_line_id": own_order.order_line.id,
                "source_load_id": own_load.id,
                "physical_source_kind": "logistics_load",
            },
            40000,
            self.lb.id,
            revision.id,
            self.key(),
        )
        other = slot_b.with_user(self.actor).action_commit_cargo(
            {
                "sale_line_id": other_order.order_line.id,
                "purchase_line_id": purchase.order_line.id,
                "source_load_id": other_load.id,
                "physical_source_kind": "logistics_load",
            },
            38000,
            self.lb.id,
            revision.id,
            self.key(),
        )
        self.assertEqual((own["status"], other["status"]), ("applied", "applied"), (own, other))
        foreign_booking = self.make_booking(user=self.foreign_actor, company=self.company_b)
        recorded = self.candidate(foreign_booking, terms=self.terms(confirmed=1), user=self.foreign_actor)
        self.assertEqual(recorded["status"], "applied", recorded)
        accepted = self.accept(foreign_booking, recorded["record_id"], user=self.foreign_actor)
        self.assertEqual(accepted["status"], "applied", accepted)
        foreign_purchase = (
            self.env["purchase.order"]
            .with_company(self.company_b)
            .create(
                {
                    "partner_id": self.suppliers[3].id,
                    "company_id": self.company_b.id,
                    "order_line": [
                        (0, 0, {"product_id": self.product.id, "product_qty": 10, "product_uom_id": self.lb.id})
                    ],
                }
            )
        )
        foreign = foreign_booking.slot_ids.with_user(self.foreign_actor).action_commit_cargo(
            {"purchase_line_id": foreign_purchase.order_line.id}, None, None, recorded["record_id"], self.key()
        )
        self.assertEqual(foreign["status"], "applied", foreign)
        Link = self.env[LINK]
        return {
            "booking": booking,
            "revision": revision,
            "own_link": Link.browse(own["record_id"]),
            "other_link": Link.browse(other["record_id"]),
            "foreign_link": Link.browse(foreign["record_id"]),
            "own_load": own_load,
            "other_load": other_load,
            "other_order": other_order,
            "purchase": purchase,
        }

    def test_sales_rep_reads_every_allocation_of_their_companies(self):
        """Operator decision 2026-11-12 (SUPERSESSION.md; BRS-EXP-14-R012, R017, R022).

        Recorded business-rule change: this replaces the PR #479 review test that
        limited a Sales Rep to links on sale orders they own. A Sales Rep now reads
        every cargo link of every booking in their companies, other reps' links
        included, through search, the slot's cargo One2many and the pivot grouping,
        so no booking is overbooked. Nothing outside their companies is visible.
        """
        data = self._shared_allocations()
        booking = data["booking"]
        everything = self.env[LINK].search([("booking_id", "=", booking.id)])
        self.assertEqual(len(everything), 3)
        Link = self.env[LINK].with_user(self.sales_reader)
        self.assertEqual(Link.search([("booking_id", "=", booking.id)]), everything.with_user(self.sales_reader))
        self.assertIn(data["other_link"].id, Link.search([]).ids)
        slots = booking.with_user(self.sales_reader).slot_ids
        self.assertEqual(set(slots.cargo_link_ids.ids), set(everything.ids))
        values = data["other_link"].with_user(self.sales_reader).read(["supplier_id", "planned_quantity"])[0]
        self.assertEqual(values["planned_quantity"], 38000)
        groups = Link.formatted_read_group(
            [("booking_id", "=", booking.id)], ["purchase_order_id", "sale_order_id"], ["planned_quantity:sum"]
        )
        labels = {group["sale_order_id"][1] for group in groups if group["sale_order_id"]}
        self.assertIn(data["other_order"].name, labels)
        self.assertNotIn(data["foreign_link"].id, Link.search([]).ids)
        self.assertFalse(Link.search([("company_id", "=", self.company_b.id)]))
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            data["foreign_link"].with_user(self.sales_reader).read(["allocation_key"])

    def test_sales_rep_finds_another_reps_allocation_by_order_name(self):
        """Operator decision 2026-11-12, BRS-EXP-14-R017: search matches the see-all audience.

        The order-name search fields and the booking and slot "Supplier PO" and
        "Customer SO" filters search the link's own name fields, which bypass the
        order rules. Another rep's allocation is found by its sale order and its
        purchase order name, though the orders themselves stay unreadable.
        """
        from lxml import etree

        data = self._shared_allocations()
        booking, link = data["booking"], data["other_link"]
        so_name, po_name = data["other_order"].name, data["purchase"].name
        Link = self.env[LINK].with_user(self.sales_reader)
        self.assertIn(link.id, Link.search([("sale_order_ref", "ilike", so_name)]).ids)
        self.assertIn(link.id, Link.search([("purchase_order_ref", "ilike", po_name)]).ids)
        self.assertIn(link.id, Link.search([("supplier_ref", "ilike", self.suppliers[2].name)]).ids)
        searches = (
            ("plasticos_export.view_export_booking_search", BOOKING, booking),
            ("plasticos_export.view_export_slot_search", SLOT, link.slot_id),
        )
        for xmlid, model, expected in searches:
            arch = etree.fromstring(self.env.ref(xmlid).arch)
            for node in arch.iter("field"):
                domain = node.get("filter_domain") or ""
                if "_ref" not in domain:
                    continue
                for name in (so_name, po_name):
                    if ("sale_order_ref" in domain) != (name == so_name):
                        continue
                    found = self.env[model].with_user(self.sales_reader).search(safe_eval(domain, {"self": name}))
                    self.assertIn(expected.id, found.ids, f"{xmlid} {node.get('string')} {name}")
        link_search = etree.fromstring(self.env.ref("plasticos_export.view_export_cargo_link_search").arch)
        names = {node.get("name") for node in link_search.iter("field")}
        self.assertTrue({"purchase_order_ref", "sale_order_ref", "supplier_ref"} <= names)
        self.assertFalse({"purchase_order_id", "sale_order_id", "supplier_id"} & names)

    def test_private_supplier_never_blocks_the_sales_rep_list(self):
        """Operator decision 2026-11-12 (review N2): a private supplier shows by name only and never raises.

        A supplier marked private by another user is unreadable to the rep. The
        rep's list shows the link's supplier name field, so list reads and the
        list's default export do not traverse the partner.
        """
        from lxml import etree

        booking, revision = self._populated_booking()
        private = self.env["res.partner"].create(
            {"name": "S7 Private Mill", "is_company": True, "supplier_rank": 1, "is_private": True}
        )
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            private.with_user(self.sales_reader).read(["name"])
        purchase = self.env["purchase.order"].create(
            {
                "partner_id": private.id,
                "order_line": [(0, 0, {"product_id": self.product.id, "product_qty": 5, "product_uom_id": self.lb.id})],
            }
        )
        applied = (
            booking.slot_ids.sorted("slot_key")[1]
            .with_user(self.actor)
            .action_commit_cargo({"purchase_line_id": purchase.order_line.id}, None, None, revision.id, self.key())
        )
        self.assertEqual(applied["status"], "applied", applied)
        exporter = new_test_user(
            self.env,
            login="s7_export_private_supplier_reader",
            groups="base.group_user,base.group_allow_export,plasticos_security_base.group_sales_rep",
            company_id=self.company.id,
            company_ids=[(6, 0, [self.company.id])],
        )
        Link = self.env[LINK].with_user(exporter)
        arch = Link.get_views([(False, "list")])["views"]["list"]["arch"]
        names = [node.get("name") for node in etree.fromstring(arch).iter("field") if node.get("name") in Link._fields]
        self.assertIn("supplier_ref", names)
        self.assertNotIn("supplier_id", names)
        link = Link.browse(applied["record_id"])
        spec = {
            name: ({"fields": {"display_name": {}}} if Link._fields[name].type == "many2one" else {}) for name in names
        }
        values = link.web_read(spec)[0]
        self.assertEqual(values["supplier_ref"], "S7 Private Mill")
        rows = link.export_data(names)["datas"]
        self.assertIn("S7 Private Mill", {str(value) for row in rows for value in row})

    def test_sales_rep_cannot_change_or_command_allocations(self):
        """Operator decision 2026-11-12: Sales Reps see allocations, never change them (BRS-EXP-14-R012)."""
        data = self._shared_allocations()
        booking, revision, link = data["booking"], data["revision"], data["other_link"]
        slot = link.slot_id
        for record in (link, slot, booking):
            for operation in ("write", "create", "unlink"):
                with self.assertRaises(AccessError, msg=f"{record._name} {operation}"), self.env.cr.savepoint():
                    record.with_user(self.sales_reader).check_access(operation)
        # The ACL check above is the access verdict. The Export models refuse a typed
        # change before the ORM reaches that check, so each direct attempt raises the
        # model's UserError; a booking field the model allows is refused by the ACL.
        with self.assertRaises(UserError), self.env.cr.savepoint():
            link.with_user(self.sales_reader).write({"state": "released"})
        with self.assertRaises(UserError), self.env.cr.savepoint():
            link.with_user(self.sales_reader).write({"physical_source_ref": "typed in"})
        with self.assertRaises(UserError), self.env.cr.savepoint():
            link.with_user(self.sales_reader).unlink()
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self.env[LINK].with_user(self.sales_reader).create(
                {"slot_id": slot.id, "allocation_key": "typed", "sale_line_id": data["other_order"].order_line.id}
            )
        with self.assertRaises(UserError), self.env.cr.savepoint():
            slot.with_user(self.sales_reader).write({"hold_reason": "typed in"})
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            booking.with_user(self.sales_reader).write({"carrier_id": self.line.id})
        reader_slot = slot.with_user(self.sales_reader)
        commit = reader_slot.action_commit_cargo(
            {"purchase_line_id": data["purchase"].order_line.id}, None, None, revision.id, self.key()
        )
        self.assertEqual(commit["status"], "not_available", commit)
        release = reader_slot.action_release_cargo(link.id, revision.id, self.key(), "sales planning")
        self.assertEqual(release["status"], "not_available", release)
        bind = reader_slot.action_bind_journey(1, revision.id, self.key(), "sales planning")
        self.assertEqual(bind["status"], "not_available", bind)
        accept = booking.with_user(self.sales_reader).action_accept_booking_revision(
            revision.id, revision.id, self.key(), "sales planning"
        )
        self.assertEqual(accept["status"], "not_available", accept)
        self.assertEqual(link.state, "committed")

    def test_sales_rep_cannot_read_another_reps_load(self):
        """Operator decision 2026-11-12: loads stay owner-scoped; the link shows the name only."""
        data = self._shared_allocations()
        self.assertTrue(data["own_load"].with_user(self.sales_reader).read(["name"]))
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            data["other_load"].with_user(self.sales_reader).read(["name"])
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            data["other_order"].with_user(self.sales_reader).read(["name"])
        link = data["other_link"].with_user(self.sales_reader)
        self.assertEqual(link.source_load_ref, data["other_load"].name)
        self.assertEqual(link.sale_order_ref, data["other_order"].name)
        self.assertEqual(link.purchase_order_ref, data["purchase"].name)
        self.assertFalse(self.sales_reader.has_group("purchase.group_purchase_user"))

    def test_sales_rep_web_reads_another_reps_link_with_display_names(self):
        """Operator decision 2026-11-12: the form and list read path does not raise for another rep's link."""
        from lxml import etree

        data = self._shared_allocations()
        link = data["other_link"].with_user(self.sales_reader)
        names = set()
        for view_type in ("form", "list"):
            arch = link.get_views([(False, view_type)])["views"][view_type]["arch"]
            names |= {node.get("name") for node in etree.fromstring(arch).iter("field")}
        spec = {
            name: ({"fields": {"display_name": {}}} if link._fields[name].type == "many2one" else {})
            for name in names
            if name in link._fields
        }
        values = link.web_read(spec)[0]
        self.assertEqual(values["source_load_id"]["display_name"], data["other_load"].display_name)
        self.assertEqual(values["source_load_ref"], data["other_load"].name)
        self.assertEqual(values["po_constraint_display"], "PO not readable for your role.")

    def test_source_references_open_only_for_logistics(self):
        """Operator decision 2026-11-12, BRS-EXP-14-R017: non-Logistics readers get text or no_open references."""
        from lxml import etree

        def arch_nodes(user, view_type, model=LINK):
            arch = self.env[model].with_user(user).get_views([(False, view_type)])["views"][view_type]["arch"]
            return [node for node in etree.fromstring(arch).iter("field")]

        sources = {"source_load_id", "sale_order_id", "purchase_order_id"}
        refs = {"source_load_ref", "sale_order_ref", "purchase_order_ref"}
        reader_list = {node.get("name") for node in arch_nodes(self.sales_reader, "list")}
        self.assertFalse(reader_list & sources)
        self.assertEqual(reader_list & refs, refs)
        actor_list = {node.get("name") for node in arch_nodes(self.actor, "list")}
        self.assertEqual(actor_list & sources, sources)
        self.assertFalse(actor_list & refs)
        exact = {"purchase_line_id", "sale_line_id", "source_load_id", "stock_move_line_id", "original_attachment_id"}
        reader_form = [node for node in arch_nodes(self.sales_reader, "form") if node.get("name") in exact]
        self.assertEqual({node.get("name") for node in reader_form}, exact)
        self.assertEqual(len(reader_form), len(exact))
        for node in reader_form:
            self.assertIn("no_open", node.get("options") or "", node.get("name"))
        actor_form = [node for node in arch_nodes(self.actor, "form") if node.get("name") in exact]
        self.assertEqual(len(actor_form), len(exact))
        self.assertFalse([node for node in actor_form if "no_open" in (node.get("options") or "")])
        slot_form = etree.fromstring(
            self.env[SLOT].with_user(self.sales_reader).get_views([(False, "form")])["views"]["form"]["arch"]
        )
        inline = {node.get("name") for node in slot_form.iter("field")}
        self.assertFalse(inline & sources)
        self.assertEqual(inline & refs, refs)

    def test_sales_rep_and_logistics_user_sees_the_operations_view(self):
        """Group rules are OR'ed: a user in both Sales Rep and Logistics reads every link with openable references."""
        from lxml import etree

        data = self._shared_allocations()
        both = new_test_user(
            self.env,
            login="s7_export_sales_and_logistics",
            groups="base.group_user,plasticos_security_base.group_sales_rep,plasticos_security_base.group_logistics",
            company_id=self.company.id,
            company_ids=[(6, 0, [self.company.id])],
        )
        visible = self.env[LINK].with_user(both).search([("booking_id", "=", data["booking"].id)])
        self.assertEqual(len(visible), 3)
        arch = self.env[LINK].with_user(both).get_views([(False, "list")])["views"]["list"]["arch"]
        names = {node.get("name") for node in etree.fromstring(arch).iter("field")}
        self.assertIn("source_load_id", names)
        self.assertNotIn("source_load_ref", names)

    def test_container_manifest_renders_for_a_sales_rep(self):
        """Operator decision 2026-11-12, BRS-EXP-14-R022: the manifest prints names, never traverses sources."""
        data = self._shared_allocations()
        html, _kind = (
            self.env["ir.actions.report"]
            .with_user(self.sales_reader)
            ._render_qweb_html("plasticos_export.report_container_manifest", data["booking"].ids)
        )
        text = html.decode()
        self.assertEqual(text.count("o_manifest_link"), 3)
        self.assertIn(data["other_load"].name, text)
        self.assertIn(data["other_order"].name, text)
        self.assertIn(data["purchase"].name, text)

    def test_sales_rep_exports_the_allocation_list(self):
        """Operator decision 2026-11-12, BRS-EXP-14-R012: exporting the list a Sales Rep sees does not raise.

        Native Odoo keeps export behind ``base.group_allow_export``: a rep without it
        gets the native refusal. A rep who holds it exports the rows they read, and
        no source reference is traversed in their access.
        """
        from lxml import etree

        data = self._shared_allocations()
        exporter = new_test_user(
            self.env,
            login="s7_export_sales_exporter",
            groups="base.group_user,base.group_allow_export,plasticos_security_base.group_sales_rep",
            company_id=self.company.id,
            company_ids=[(6, 0, [self.company.id])],
        )
        Link = self.env[LINK].with_user(exporter)
        arch = Link.get_views([(False, "list")])["views"]["list"]["arch"]
        names = [node.get("name") for node in etree.fromstring(arch).iter("field") if node.get("name") in Link._fields]
        self.assertFalse(self.sales_reader.has_group("base.group_allow_export"))
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self.env[LINK].with_user(self.sales_reader).search([("booking_id", "=", data["booking"].id)]).export_data(
                names
            )
        rows = Link.search([("booking_id", "=", data["booking"].id)]).export_data(names)["datas"]
        self.assertEqual(len(rows), 3)
        flat = {str(value) for row in rows for value in row}
        self.assertIn(data["other_load"].name, flat)
        self.assertIn(data["other_order"].name, flat)

    def test_derived_and_company_fields_cannot_be_written(self):
        """C05 review D1, BRS-EXP-14-R012: no row is relabelled across companies; derived state is never forged."""
        booking, revision = self._populated_booking()
        slot = booking.slot_ids.sorted("slot_key")[0]
        link = self.env[LINK].search([("booking_id", "=", booking.id)], limit=1)
        attempts = [
            (booking, {"company_id": self.company_b.id}),
            (booking, {"display_state": "cancelled"}),
            (booking, {"current_pol_text": "Elsewhere"}),
            (booking, {"current_cargo_cutoff_date": "2026-01-01"}),
            (revision, {"company_id": self.company_b.id}),
            (slot, {"company_id": self.company_b.id}),
            (slot, {"allocation_state": "available"}),
            (slot, {"supplier_count": 0}),
            (slot, {"carrier_booking_no": "FORGED"}),
            (link, {"company_id": self.company_b.id}),
            (link, {"booking_id": self.make_booking().id}),
            (link, {"supplier_id": self.suppliers[3].id}),
            (link, {"purchase_order_id": False}),
            (link, {"sale_order_id": False}),
            (link, {"equipment_class": "20STD"}),
        ]
        for record, vals in attempts:
            for user in (self.actor, self.env.user):
                with self.assertRaises(UserError, msg=f"{record._name} {vals}"), self.env.cr.savepoint():
                    record.with_user(user).write(vals)
        self.assertEqual((slot.company_id, link.company_id, booking.company_id), (self.company,) * 3)
        self.assertEqual(booking.display_state, "confirmed")

    def test_sales_rep_opens_cargo_without_purchase_rights(self):
        """C05 review D3: a role without purchase read sees the link, not the PO terms, and nothing raises."""
        booking, revision = self._populated_booking()
        order = self.env["sale.order"].create({"partner_id": self.buyer.id, "user_id": self.sales_reader.id})
        order.order_line = [(0, 0, {"product_id": self.product.id, "product_uom_qty": 1})]
        purchase = self.env["purchase.order"].create(
            {
                "partner_id": self.suppliers[1].id,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_qty": 500, "product_uom_id": self.lb.id})
                ],
            }
        )
        slot = booking.slot_ids.sorted("slot_key")[1]
        applied = slot.with_user(self.actor).action_commit_cargo(
            {"sale_line_id": order.order_line.id, "purchase_line_id": purchase.order_line.id},
            None,
            None,
            revision.id,
            self.key(),
        )
        self.assertEqual(applied["status"], "applied", applied)
        self.assertFalse(self.sales_reader.has_group("purchase.group_purchase_user"))
        form = self.env.ref("plasticos_export.view_export_cargo_link_form")
        link = self.env[LINK].with_user(self.sales_reader).browse(applied["record_id"])
        from lxml import etree

        names = {node.get("name") for node in etree.fromstring(form.arch).iter("field")}
        spec = {
            name: ({"fields": {"display_name": {}}} if link._fields[name].type == "many2one" else {})
            for name in names
            if name in link._fields
        }
        values = link.web_read(spec)[0]
        self.assertEqual(values["po_constraint_display"], "PO not readable for your role.")
        actor_view = self.env[LINK].with_user(self.actor).browse(applied["record_id"])
        self.assertIn("Quantity: 500 lb", actor_view.po_constraint_display)
