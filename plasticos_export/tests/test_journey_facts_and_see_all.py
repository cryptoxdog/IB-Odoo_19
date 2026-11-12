"""Logistics journey facts on the slot, resale afloat, and the Sales Rep see-all closure (S10 on the S9 merge).

BRS-EXP-07-R006: the container tare and VGM weight are Logistics facts of the
bound journey (``plasticos.iso.journey.fact``), read live and never copied.
BRS-EXP-08-R007: a buyer assigned after sailing is a new cargo allocation that
replaces the buyerless one; the recorded gate-in, departure, filer and delivery
partner, and the booking's revision, do not change.
OP10-E06 (review N7, N8 of C07): a Sales Rep searches bookings by container and
seal, gets no openable journey and no journey button, and exports cargo links
without an AccessError; a journey reader keeps them; Logistics is unchanged.
"""

from datetime import timedelta

from lxml import etree

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import AccessError
from odoo.tests.common import new_test_user, tagged
from odoo.tools.safe_eval import safe_eval

from ..models.export_scope import CARGO_LINK_SOURCE_LINKS
from ..models.owner_facts import NO_CONTAINER_BOUND, NOT_RECORDED_BY_LOGISTICS
from .test_booking_and_revision import BOOKING, LINK, ExportFixtureMixin

FACT = "plasticos.iso.journey.fact"
JOURNEY = "plasticos.iso.journey"
COMMIT = "plasticos.export.slot.commit.cargo"
SLOT = "plasticos.export.booking.slot"
JOURNEY_READERS = "plasticos_security_base.group_logistics"


@tagged("post_install", "-at_install", "plasticos", "plasticos_export")
class TestJourneyFactsAndSeeAll(ExportFixtureMixin, PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_export_fixture()
        Partner = cls.env["res.partner"]
        cls.terminal = Partner.create({"name": "S10 Terminal", "is_company": True})
        cls.filer = Partner.create({"name": "S10 Customs Broker", "is_company": True})
        cls.agent = Partner.create({"name": "S10 Destination Agent", "is_company": True})
        cls.kg = cls.env.ref("uom.product_uom_kgm")
        rep_groups = "base.group_user,base.group_allow_export,plasticos_security_base.group_sales_rep"
        cls.rep = new_test_user(
            cls.env,
            login="s10_see_all_rep",
            groups=rep_groups,
            company_id=cls.company.id,
            company_ids=[(6, 0, [cls.company.id])],
        )
        cls.rep_b = new_test_user(
            cls.env,
            login="s10_see_all_rep_b",
            groups=rep_groups,
            company_id=cls.company.id,
            company_ids=[(6, 0, [cls.company.id])],
        )
        cls.system_user = new_test_user(
            cls.env,
            login="s10_journey_reader_system",
            groups="base.group_user,base.group_system,plasticos_security_base.group_sales_rep",
            company_id=cls.company.id,
            company_ids=[(6, 0, [cls.company.id])],
        )
        cls.ops_manager = new_test_user(
            cls.env,
            login="s10_journey_reader_ops",
            groups="base.group_user,plasticos_security_base.group_operations_manager",
            company_id=cls.company.id,
            company_ids=[(6, 0, [cls.company.id])],
        )

    # ── fixtures ─────────────────────────────────────────────

    @staticmethod
    def _ago(hours):
        return (fields.Datetime.now() - timedelta(hours=hours)).replace(microsecond=0)

    def _attach(self, journey, name):
        return self.env["ir.attachment"].create(
            {"name": name, "raw": f"%PDF-1.4 {name}".encode(), "res_model": JOURNEY, "res_id": journey.id}
        )

    def _bound_slot(self, iso="MSKU7654321", seal="SL-S10"):
        booking, _revision = self.accepted_booking(confirmed=1)
        slot = booking.slot_ids
        outcome = (
            self.env[JOURNEY]
            .with_user(self.actor)
            .action_register_iso_journey(self.company.id, self.key("cycle"), "40HC", False, iso, seal, self.key())
        )
        self.assertEqual(outcome["status"], "applied", outcome)
        journey = self.env[JOURNEY].browse(outcome["record_id"])
        bound = slot.with_user(self.actor).action_bind_journey(
            journey.id, booking.current_revision_id.id, self.key("bind"), "Terminal ticket"
        )
        self.assertEqual(bound["status"], "applied", bound)
        return booking, slot, journey

    def _record(self, method, journey, *args):
        outcome = getattr(self.env[FACT].with_user(self.actor), method)(journey.id, *args, self.key("fact"))
        self.assertEqual(outcome["status"], "applied", outcome)
        return self.env[FACT].browse(outcome["record_id"])

    def _afloat(self, journey):
        """Gate-in, departure and filing parties recorded by Logistics from originals on the journey."""
        self._record(
            "action_record_gate_in", journey, self._ago(30), self.terminal.id, self._attach(journey, "eir.pdf").id
        )
        self._record(
            "action_record_departure", journey, self._ago(20), "SYN VESSEL", "S10V", self._attach(journey, "bl.pdf").id
        )
        self._record(
            "action_record_regulatory_parties",
            journey,
            self.filer.id,
            self.agent.id,
            self._attach(journey, "filing.pdf").id,
        )

    def _facts(self, journey):
        rows = self.env[FACT].search([("journey_id", "=", journey.id)], order="id")
        return [
            (
                row.id,
                row.fact_kind,
                row.occurred_at,
                row.vessel,
                row.customs_filer_id,
                row.delivery_partner_id,
                row.write_date,
            )
            for row in rows
        ]

    def _po_line(self):
        order = self.env["purchase.order"].create(
            {
                "partner_id": self.suppliers[0].id,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_qty": 40000, "product_uom_id": self.lb.id})
                ],
            }
        )
        return order.order_line

    def _sale_line(self, user, date_order=None):
        values = {
            "partner_id": self.buyer.id,
            "user_id": user.id,
            "order_line": [(0, 0, {"product_id": self.product.id, "product_uom_qty": 40000})],
        }
        if date_order:
            values["date_order"] = date_order
        return self.env["sale.order"].create(values).order_line

    # ── BRS-EXP-07-R006: tare and VGM weight from Logistics ──

    def test_07_r006_tare_and_vgm_weight_are_read_from_the_journey_facts(self):
        """BRS-EXP-07-R006 positive: the slot shows the scale-ticket tare and VGM weight Logistics recorded."""
        _booking, slot, journey = self._bound_slot()
        view = slot.with_user(self.actor)
        self.assertEqual(view.owner_container_tare, NOT_RECORDED_BY_LOGISTICS)
        self.assertEqual(view.owner_container_vgm_weight, NOT_RECORDED_BY_LOGISTICS)
        self._record(
            "action_record_container_tare",
            journey,
            3900,
            self.kg.id,
            "scale_ticket",
            self._attach(journey, "tare-ticket.pdf").id,
            "TKT-TARE-1",
        )
        self._record(
            "action_record_verified_gross_mass",
            journey,
            24100,
            self.kg.id,
            "scale_ticket",
            self._attach(journey, "vgm-ticket.pdf").id,
            "TKT-VGM-1",
        )
        self.env.invalidate_all()
        view = slot.with_user(self.actor)
        self.assertEqual(view.owner_container_tare, f"3900 {self.kg.name} (Scale Ticket: TKT-TARE-1)")
        self.assertEqual(view.owner_container_vgm_weight, f"24100 {self.kg.name} (Scale Ticket: TKT-VGM-1)")

    def test_07_r006_negative_export_derives_no_tare_or_vgm(self):
        """BRS-EXP-07-R006 negative: no journey, no fact or no access is said so; Export writes no fact."""
        booking, _revision = self.accepted_booking(confirmed=1)
        unbound = booking.slot_ids.with_user(self.actor)
        self.assertEqual(unbound.equipment_class, "40HC")
        self.assertEqual(unbound.owner_container_tare, NO_CONTAINER_BOUND)
        self.assertEqual(unbound.owner_container_vgm_weight, NO_CONTAINER_BOUND)
        before = self.env[FACT].search_count([])
        _booking, slot, _journey = self._bound_slot()
        self.assertEqual(slot.with_user(self.actor).owner_container_vgm_weight, NOT_RECORDED_BY_LOGISTICS)
        # A reader without Logistics read on the journey facts gets the restricted marker, never a false value.
        expected = NOT_RECORDED_BY_LOGISTICS if self._rep_reads_facts() else RESTRICTED
        self.assertEqual(slot.with_user(self.rep).owner_container_tare, expected)
        self.assertEqual(self.env[FACT].search_count([]), before, "reading the slot records no fact")

    # ── BRS-EXP-08-R007: resale afloat ───────────────────────

    def _buyerless_then_sold(self, sale_date=None):
        booking, slot, journey = self._bound_slot()
        line = self._po_line()
        first = slot.with_user(self.actor).action_commit_cargo(
            {"purchase_line_id": line.id}, None, None, booking.current_revision_id.id, self.key("buyerless")
        )
        self.assertEqual(first["status"], "applied", first)
        self._afloat(journey)
        facts = self._facts(journey)
        revision = booking.current_revision_id
        revision_terms = (revision.erd_utc, revision.cargo_cutoff_local, revision.write_date)
        sale = self._sale_line(self.rep, sale_date)
        action = slot.with_user(self.actor).action_open_commit_cargo()
        screen = (
            self.env[COMMIT]
            .with_user(self.actor)
            .with_context(**action["context"])
            .create(
                {
                    "purchase_line_id": line.id,
                    "sale_line_id": sale.id,
                    "replaces_link_id": first["record_id"],
                    "correction_reason": "Sold afloat to the overseas buyer",
                }
            )
        )
        screen._onchange_replaces_link_id()
        screen.action_confirm()
        return booking, slot, journey, facts, revision, revision_terms, first, sale

    def test_08_r007_container_afloat_is_sold_without_rewriting_its_facts(self):
        """BRS-EXP-08-R007 positive: the buyer SO links later; gate-in and departure facts stay as recorded."""
        booking, slot, journey, facts, revision, terms, first, sale = self._buyerless_then_sold()
        buyerless = self.env[LINK].browse(first["record_id"])
        sold = self.env[LINK].search([("replaces_link_id", "=", buyerless.id)])
        self.assertEqual(buyerless.state, "released")
        self.assertEqual((sold.state, sold.sale_line_id, sold.slot_id), ("committed", sale, slot))
        self.assertEqual(self._facts(journey), facts, "no Logistics fact was rewritten by the sale")
        self.assertEqual(booking.current_revision_id, revision)
        self.assertEqual((revision.erd_utc, revision.cargo_cutoff_local, revision.write_date), terms)
        self.env.invalidate_all()
        history = slot.with_user(self.actor).owner_shipment_history
        self.assertIn(f"at {self.terminal.display_name}", history)
        self.assertIn("on SYN VESSEL S10V", history)
        self.assertIn(f"delivery partner: {self.agent.display_name}", history)
        self.assertLess(history.index(buyerless.allocation_key), history.index(sold.allocation_key))
        self.assertIn("buyer SO no buyer sale", history)
        self.assertIn(f"buyer SO {sale.order_id.name}", history)
        self.assertIn(f"replaces {buyerless.allocation_key}", history)
        self.assertIn(f"by {self.actor.name}", history)

    def test_08_r007_negative_buyer_change_moves_no_date_party_or_filer(self):
        """BRS-EXP-08-R007 negative: a backdated SO moves no booking date, delivery partner or customs filer."""
        backdated = self._ago(24 * 60)
        booking, slot, journey, facts, revision, terms, _first, sale = self._buyerless_then_sold(backdated)
        self.assertLess(sale.order_id.date_order, self._ago(20))
        self.assertEqual(self._facts(journey), facts)
        parties = self.env[FACT].search([("journey_id", "=", journey.id), ("fact_kind", "=", "regulatory_parties")])
        self.assertEqual((parties.customs_filer_id, parties.delivery_partner_id), (self.filer, self.agent))
        self.assertNotEqual(parties.delivery_partner_id, sale.order_id.partner_id)
        self.assertEqual((revision.erd_utc, revision.cargo_cutoff_local, revision.write_date), terms)
        self.assertEqual(booking.current_revision_id, revision)
        self.assertEqual(
            self.env[FACT].search_count([("journey_id", "=", journey.id)]), 3, "the sale recorded no Logistics fact"
        )
        self.env.invalidate_all()
        rep_history = slot.with_user(self.rep).owner_shipment_history
        if self._rep_reads_facts():
            self.assertIn(f"delivery partner: {self.agent.display_name}", rep_history)
        else:
            self.assertIn(f"Container facts: {RESTRICTED}", rep_history)
            self.assertNotIn(self.agent.display_name, rep_history)
            self.assertNotIn(journey.display_name, rep_history)
        self.assertIn(f"buyer SO {sale.order_id.name}", rep_history)

    # ── OP10-E06: Sales Rep see-all without AccessError ──────

    def _search_filter(self, label, value):
        arch = etree.fromstring(self.env.ref("plasticos_export.view_export_booking_search").arch)
        node = next(node for node in arch.iter("field") if node.get("string") == label)
        return safe_eval(node.get("filter_domain"), {"self": value})

    def test_rep_searches_bookings_by_container_and_seal(self):
        """OP10-E06 (N7): a Sales Rep finds bookings by container number and seal with no AccessError."""
        booking, _slot, _journey = self._bound_slot(iso="TGHU8765432", seal="SEAL-N7")
        Booking = self.env[BOOKING].with_user(self.rep)
        self.assertEqual(Booking.search(self._search_filter("Container No.", "TGHU8765")), booking)
        self.assertEqual(Booking.search(self._search_filter("Seal", "SEAL-N7")), booking)
        actor = self.env[BOOKING].with_user(self.actor)
        self.assertEqual(actor.search(self._search_filter("Container No.", "TGHU8765")), booking)

    def _form_arch(self, user, xmlid):
        view = self.env.ref(xmlid)
        return etree.fromstring(
            self.env[view.model].with_user(user).get_views([(view.id, "form")])["views"]["form"]["arch"]
        )

    def _rep_reads_facts(self):
        """Whether the Logistics owner lets a Sales Rep read journey facts (S9 review: it will not)."""
        return self.env[FACT].with_user(self.rep).has_access("read")

    def test_rep_gets_no_journey_link_or_journey_button(self):
        """OP10-E06: a rep gets no journey Many2one and no journey button; journey readers keep both."""
        for user, reader in ((self.rep, False), (self.actor, True), (self.ops_manager, True), (self.system_user, True)):
            arch = self._form_arch(user, "plasticos_export.view_export_slot_form")
            buttons = [node.get("name") for node in arch.iter("button")]
            journey_nodes = [node for node in arch.iter("field") if node.get("name") == "journey_id"]
            self.assertEqual(len(journey_nodes), 1 if reader else 0, user.login)
            self.assertEqual("action_open_journey" in buttons, reader, user.login)
            self.assertIn("iso_number", [node.get("name") for node in arch.iter("field")], user.login)
        self.assertTrue(self.ops_manager.has_group(JOURNEY_READERS), "Operations Manager implies Logistics")
        self.assertFalse(self.system_user.has_group(JOURNEY_READERS))

    def test_rep_exports_cargo_links_without_access_error(self):
        """OP10-E06 (N8): a rep exports every offered and every listed field over another rep's order and load."""
        booking, slot, _journey = self._bound_slot()
        sale = self._sale_line(self.rep_b)
        load = self.env["plasticos.load"].create({"sale_order_id": sale.order_id.id})
        outcome = slot.with_user(self.actor).action_commit_cargo(
            {
                "purchase_line_id": self._po_line().id,
                "sale_line_id": sale.id,
                "source_load_id": load.id,
                "physical_source_kind": "logistics_load",
            },
            None,
            None,
            booking.current_revision_id.id,
            self.key("n8"),
        )
        self.assertEqual(outcome["status"], "applied", outcome)
        Link = self.env[LINK].with_user(self.rep)
        links = Link.search([("slot_id", "=", slot.id)])
        self.assertEqual(len(links), 1, "the rep sees another rep's allocation")
        offered = Link.fields_get(attributes=["exportable", "type", "string"])
        exportable = sorted(name for name, field in offered.items() if field.get("exportable", True))
        self.assertFalse(CARGO_LINK_SOURCE_LINKS & set(exportable))
        rows = links.export_data(exportable)["datas"]
        self.assertEqual(len(rows), 1)
        listed = [
            node.get("name")
            for node in etree.fromstring(Link.get_views([(False, "list")])["views"]["list"]["arch"]).iter("field")
        ]
        self.assertTrue(listed)
        self.assertEqual(len(links.export_data(listed)["datas"]), 1)
        self.assertIn(sale.order_id.name, links.export_data(["sale_order_ref"])["datas"][0])
        slot_fields = self.env[SLOT].with_user(self.rep).fields_get(attributes=["exportable"])
        self.assertFalse(slot_fields["journey_id"]["exportable"])
        # Logistics, Operations and System keep what they had.
        for user in (self.actor, self.ops_manager):
            offered = self.env[LINK].with_user(user).fields_get(attributes=["exportable"])
            self.assertTrue(all(offered[name].get("exportable", True) for name in CARGO_LINK_SOURCE_LINKS), user.login)
        for user in (self.actor, self.ops_manager, self.system_user):
            slot_fields = self.env[SLOT].with_user(user).fields_get(attributes=["exportable"])
            self.assertTrue(slot_fields["journey_id"].get("exportable", True), user.login)
        actor_link = self.env[LINK].with_user(self.actor).browse(links.ids)
        self.assertEqual((actor_link.source_load_id, actor_link.sale_order_id), (load, sale.order_id))

    def test_rep_reads_the_slot_display_without_access_error_or_journey(self):
        """OP10-E06 / S9 review: a rep reads every slot form field with no AccessError and no fact or journey link."""
        booking, slot, journey = self._bound_slot(iso="CAIU1234569", seal="SEAL-REP")
        self._afloat(journey)
        self._record(
            "action_record_container_tare",
            journey,
            3900,
            self.kg.id,
            "scale_ticket",
            self._attach(journey, "tare.pdf").id,
            "TKT-REP",
        )
        self.env.invalidate_all()
        arch = self._form_arch(self.rep, "plasticos_export.view_export_slot_form")
        rep_slot = self.env[SLOT].with_user(self.rep).browse(slot.id)
        names = {node.get("name") for node in arch.iter("field") if node.get("name") in rep_slot._fields}
        relational = {
            name: rep_slot._fields[name].comodel_name for name in names if rep_slot._fields[name].type == "many2one"
        }
        self.assertNotIn(JOURNEY, relational.values())
        self.assertNotIn(FACT, relational.values())
        spec = {name: ({"fields": {"display_name": {}}} if name in relational else {}) for name in names}
        values = rep_slot.web_read(spec)[0]
        self.assertEqual(values["iso_number"], "CAIU1234569")
        if not self._rep_reads_facts():
            self.assertEqual(values["owner_container_tare"], RESTRICTED)
            self.assertEqual(values["owner_container_vgm_weight"], RESTRICTED)
            with self.assertRaises(AccessError):
                self.env[FACT].with_user(self.rep).search_read([("journey_id", "=", journey.id)], ["weight"])
        self.assertNotIn(journey.display_name, str(values))
        actor_slot = self.env[SLOT].with_user(self.actor).browse(slot.id)
        self.assertEqual(actor_slot.owner_container_tare, f"3900 {self.kg.name} (Scale Ticket: TKT-REP)")
