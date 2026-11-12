"""S9 Logistics facts the deferred Export rules need.

Witnesses:

* BRS-EXP-07-R002 (AC-EXP-07-002): domestic road equipment on the load.
* BRS-EXP-08-R007 (AC-EXP-08-007): gate-in, departure, customs filer and
  delivery partner are J1 facts that a later buyer allocation cannot rewrite.
* BRS-EXP-09-R007 (AC-EXP-09-007) and BRS-EXP-11-R010 (AC-EXP-11-010): typed
  shipment-event proposals; only the owner command changes state.

The Oct 8 case: a supplier's "booking complete" email and scale ticket 1728952
support a reviewable loaded event for Load 1 of a five-container purchase
order. The other four loads stay open and terminal gate-in stays unverified.
"""

from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

LOAD = "plasticos.load"
JOURNEY = "plasticos.iso.journey"
SOURCE = "plasticos.iso.journey.source"
FACT = "plasticos.iso.journey.fact"
PROPOSAL = "plasticos.shipment.event.proposal"
EQUIPMENT = "plasticos.road.equipment.type"


class _S9Case(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for model in (EQUIPMENT, PROPOSAL, JOURNEY, FACT):
            assert model in cls.env, f"{model} is not in the registry; plasticos_logistics install is broken"
        cls.company = cls.env.company
        cls.currency = cls.company.currency_id
        partner = cls.env["res.partner"]
        cls.supplier = partner.create(
            {"name": "S9 Mill", "is_company": True, "supplier_rank": 1, "street": "1 Mill Rd", "city": "Houston"}
        )
        cls.terminal = partner.create(
            {"name": "S9 Barbours Cut", "is_company": True, "street": "9 Terminal Way", "city": "Houston"}
        )
        cls.carrier = partner.create(
            {"name": "S9 Drayage", "is_company": True, "supplier_rank": 1, "email": "ops@dray.example"}
        )
        cls.buyer = partner.create({"name": "S9 Late Buyer", "is_company": True, "customer_rank": 1})
        cls.filer = partner.create({"name": "S9 Customs Broker", "is_company": True})
        cls.consignee = partner.create({"name": "S9 Destination Agent", "is_company": True})

    def _load(self, **extra):
        values = {
            "company_id": self.company.id,
            "pickup_partner_id": self.supplier.id,
            "delivery_partner_id": self.terminal.id,
            "reference_weight": 40200,
            "carrier_id": self.carrier.id,
            "rate_currency_id": self.currency.id,
        }
        values.update(extra)
        return self.env[LOAD].create(values)

    def _attach(self, record, name="evidence.pdf"):
        return self.env["ir.attachment"].create(
            {"name": name, "raw": b"%PDF-1.4 s9 evidence", "res_model": record._name, "res_id": record.id}
        )

    def _journey(self, cycle, iso="MSCU1234567"):
        result = self.env[JOURNEY].action_register_iso_journey(
            self.company.id, cycle, "40HC", None, iso, "SL-9", f"op-{cycle}"
        )
        self.assertEqual(result["status"], "applied")
        return self.env[JOURNEY].browse(result["record_id"])

    @staticmethod
    def _ago(hours):
        return (fields.Datetime.now() - timedelta(hours=hours)).replace(microsecond=0)

    def _journey_facts(self, journey):
        """Every recorded fact of the journey, field by field."""
        facts = self.env[FACT].search([("journey_id", "=", journey.id)], order="fact_kind")
        facts.invalidate_recordset()
        names = (
            "fact_kind",
            "occurred_at",
            "facility_partner_id",
            "vessel",
            "voyage",
            "customs_filer_id",
            "delivery_partner_id",
            "evidence_attachment_id",
            "recorded_at",
            "recorded_by",
        )
        return [
            {name: (fact[name].id if fact._fields[name].type == "many2one" else fact[name]) for name in names}
            for fact in facts
        ]

    def _fact(self, journey, kind):
        return self.env[FACT].search([("journey_id", "=", journey.id), ("fact_kind", "=", kind)])


@tagged("post_install", "-at_install", "plasticos", "logistics", "export")
class TestRoadEquipment(_S9Case):
    """BRS-EXP-07-R002 / AC-EXP-07-002."""

    def test_operator_specifies_53_48_or_flatbed_on_the_load(self):
        """AC-EXP-07-002 positive: each supported domestic type is selectable on the native load and findable."""
        for xmlid in ("road_equipment_trailer_53", "road_equipment_trailer_48", "road_equipment_flatbed"):
            with self.subTest(xmlid=xmlid):
                equipment = self.env.ref(f"plasticos_logistics.{xmlid}")
                load = self._load(road_equipment_type_id=equipment.id)
                self.assertEqual(load.road_equipment_type_id, equipment)
                self.assertIn(load, self.env[LOAD].search([("road_equipment_type_id", "=", equipment.id)]))
        self.assertEqual(self.env[LOAD]._fields["road_equipment_type_id"].comodel_name, EQUIPMENT)

    def test_flatbed_is_its_own_type_with_no_assumed_length(self):
        """AC-EXP-07-002 negative: a flatbed does not mean 48 ft; the actual move states its own dimensions."""
        flatbed = self.env.ref("plasticos_logistics.road_equipment_flatbed")
        trailer_48 = self.env.ref("plasticos_logistics.road_equipment_trailer_48")
        self.assertNotEqual(flatbed, trailer_48)
        self.assertFalse(flatbed.nominal_length_ft)
        self.assertEqual(trailer_48.nominal_length_ft, 48)
        load = self._load(road_equipment_type_id=flatbed.id, road_equipment_requirements="40 ft deck, tarped")
        self.assertEqual(load.road_equipment_requirements, "40 ft deck, tarped")

    def test_equipment_infers_no_weight_and_no_container(self):
        """AC-EXP-07-002 negative: choosing a trailer derives no payload, VGM or container journey."""
        journeys = self.env[JOURNEY].search_count([])
        load = self._load(reference_weight=40200)
        load.road_equipment_type_id = self.env.ref("plasticos_logistics.road_equipment_trailer_53")
        self.assertEqual(load.reference_weight, 40200)
        self.assertEqual(self.env[JOURNEY].search_count([]), journeys)

    def test_more_types_are_data_and_codes_are_unique(self):
        """Other types are added as data; a duplicate catalog entry is refused."""
        reefer = self.env[EQUIPMENT].create({"name": "53 ft Reefer", "code": "reefer_53", "nominal_length_ft": 53})
        self.assertEqual(self._load(road_equipment_type_id=reefer.id).road_equipment_type_id, reefer)
        with self.assertRaises(Exception), self.env.cr.savepoint():
            self.env[EQUIPMENT].create({"name": "Another flatbed", "code": "flatbed"})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env[EQUIPMENT].create({"name": "Bad", "code": "Step Deck"})


@tagged("post_install", "-at_install", "plasticos", "logistics", "export")
class TestJourneyMilestonesAndResale(_S9Case):
    """BRS-EXP-08-R007 / AC-EXP-08-007 (Logistics facts)."""

    def _afloat_journey(self, cycle="S9-AFLOAT"):
        journey = self._journey(cycle)
        load = self._load()
        bound = self.env[SOURCE].action_bind_journey_source(
            journey.id, "load", load.id, self.supplier.id, None, f"op-bind-{cycle}", "supplier loading sheet"
        )
        self.assertEqual(bound["status"], "applied")
        gate_doc = self._attach(journey, "eir-gate-in.pdf")
        sail_doc = self._attach(journey, "carrier-departure.pdf")
        filing_doc = self._attach(journey, "filing-authority.pdf")
        commands = self.env[FACT]
        self.assertEqual(
            commands.action_record_gate_in(journey.id, self._ago(72), self.terminal.id, gate_doc.id, "g1")["status"],
            "applied",
        )
        self.assertEqual(
            commands.action_record_departure(journey.id, self._ago(24), "MSC Aurora", "AU545W", sail_doc.id, "d1")[
                "status"
            ],
            "applied",
        )
        self.assertEqual(
            commands.action_record_regulatory_parties(
                journey.id, self.filer.id, self.consignee.id, filing_doc.id, "r1"
            )["status"],
            "applied",
        )
        return journey, load

    def test_afloat_container_is_sold_without_rewriting_its_facts(self):
        """AC-EXP-08-007 positive: an unsold container afloat gets a new buyer SO; gate-in and departure stay."""
        journey, load = self._afloat_journey()
        before = self._journey_facts(journey)
        self.assertEqual([fact["fact_kind"] for fact in before], ["departure", "gate_in", "regulatory_parties"])
        self.assertEqual(self._fact(journey, "departure").vessel, "MSC Aurora")
        self.assertEqual(self._fact(journey, "gate_in").recorded_by, self.env.user)
        order = self.env["sale.order"].create({"partner_id": self.buyer.id, "company_id": self.company.id})
        load.sale_order_id = order
        self.assertEqual(load.sale_order_id, order)
        self.assertEqual(self._journey_facts(journey), before)
        regulatory = self._fact(journey, "regulatory_parties")
        self.assertEqual((regulatory.customs_filer_id, regulatory.delivery_partner_id), (self.filer, self.consignee))

    def test_buyer_change_cannot_silently_change_filer_delivery_partner_or_departure(self):
        """AC-EXP-08-007 negative: no write, delete or replay rewrites the filer, delivery partner or sailing."""
        journey, _load = self._afloat_journey("S9-NEG")
        before = self._journey_facts(journey)
        regulatory = self._fact(journey, "regulatory_parties")
        departure = self._fact(journey, "departure")
        for record, values in (
            (regulatory, {"customs_filer_id": self.buyer.id}),
            (regulatory, {"delivery_partner_id": self.buyer.id}),
            (departure, {"occurred_at": self._ago(1)}),
        ):
            with self.subTest(values=values), self.assertRaises(UserError), self.env.cr.savepoint():
                record.write(values)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            departure.unlink()
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self.env[FACT].create(
                {
                    "journey_id": journey.id,
                    "company_id": self.company.id,
                    "fact_kind": "gate_in",
                    "occurred_at": self._ago(1),
                    "facility_partner_id": self.terminal.id,
                    "evidence_attachment_id": departure.evidence_attachment_id.id,
                    "recorded_at": fields.Datetime.now(),
                    "recorded_by": self.env.user.id,
                }
            )
        doc = self._attach(journey, "buyer-instructions.pdf")
        commands = self.env[FACT]
        refused = (
            commands.action_record_regulatory_parties(journey.id, self.buyer.id, self.buyer.id, doc.id, "r2"),
            commands.action_record_departure(journey.id, self._ago(2), "Other Vessel", "X1", doc.id, "d2"),
            commands.action_record_gate_in(journey.id, self._ago(70), self.terminal.id, doc.id, "g2"),
        )
        self.assertEqual([result["status"] for result in refused], ["blocked"] * 3)
        self.assertEqual(self._journey_facts(journey), before)

    def test_same_facts_replay_is_idempotent(self):
        journey = self._journey("S9-REPLAY")
        doc = self._attach(journey, "eir.pdf")
        when = self._ago(5)
        first = self.env[FACT].action_record_gate_in(journey.id, when, self.terminal.id, doc.id, "g")
        replay = self.env[FACT].action_record_gate_in(journey.id, when, self.terminal.id, doc.id, "g")
        self.assertEqual(first["status"], "applied")
        self.assertEqual(replay, {"status": "already_applied", "record_id": first["record_id"]})
        self.assertEqual(len(self._fact(journey, "gate_in")), 1)

    def test_facts_need_their_own_original_and_order(self):
        """BRS-EXP-10-R007: gate-in before sailing, the journey's own original, no future time, attributed identity."""
        journey = self._journey("S9-ORDER")
        doc = self._attach(journey, "carrier.pdf")
        commands = self.env[FACT]
        self.assertEqual(
            commands.action_record_departure(journey.id, self._ago(3), "MSC Aurora", "", doc.id, "d")["status"],
            "blocked",
        )
        loose = self._attach(self._load(), "load-doc.pdf")
        self.assertEqual(
            commands.action_record_gate_in(journey.id, self._ago(3), self.terminal.id, loose.id, "g")["status"],
            "blocked",
        )
        future = fields.Datetime.now() + timedelta(days=1)
        self.assertEqual(
            commands.action_record_gate_in(journey.id, future, self.terminal.id, doc.id, "g")["status"], "blocked"
        )
        self.assertEqual(
            commands.action_record_gate_in(journey.id, self._ago(3), self.terminal.id, doc.id, "g")["status"],
            "applied",
        )
        self.assertEqual(
            commands.action_record_departure(journey.id, self._ago(4), "MSC Aurora", "", doc.id, "d")["status"],
            "blocked",
        )
        candidate = self.env[JOURNEY].create({"company_id": self.company.id, "equipment_class": "40HC"})
        candidate_doc = self._attach(candidate, "eir.pdf")
        self.assertEqual(
            commands.action_record_gate_in(candidate.id, self._ago(3), self.terminal.id, candidate_doc.id, "g")[
                "status"
            ],
            "blocked",
        )
        self.assertFalse(self._fact(journey, "departure"))
        self.assertFalse(self._fact(candidate, "gate_in"))

    def test_journey_stays_identity_only(self):
        """The S2 J1 contract holds: facts live beside the journey, not on it."""
        self.assertFalse(
            {"gate_in_at", "sailed_at", "departed_at", "customs_filer_id"} & set(self.env[JOURNEY]._fields)
        )


@tagged("post_install", "-at_install", "plasticos", "logistics", "export")
class TestShipmentEventProposals(_S9Case):
    """BRS-EXP-09-R007 / AC-EXP-09-007 and BRS-EXP-11-R010 / AC-EXP-11-010."""

    def _five_container_order(self):
        """One 200000-lb supplier PO, five loads under one purchase-backed transaction, nothing moved."""
        product = self.env["product.product"].create({"name": "S9 HDPE regrind", "type": "consu"})
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.supplier.id,
                "company_id": self.company.id,
                "order_line": [(0, 0, {"product_id": product.id, "product_qty": 200000, "price_unit": 0.1})],
            }
        )
        po.button_confirm()
        tx = self.env["plasticos.transaction"].create(
            {"name": "TX-S9-OCT8", "supplier_id": self.supplier.id, "purchase_order_ids": [(6, 0, po.ids)]}
        )
        loads = self.env[LOAD]
        for index in range(5):
            load = self._load(name=f"S9-OCT8-L{index + 1}")
            bound = self.env[LOAD].action_bind_exact_transaction_load(
                tx.id, load.id, {"route": "purchase"}, f"op-oct8-{index}"
            )
            self.assertEqual(bound["status"], "applied")
            loads |= load
        return po, tx, loads

    def _snapshot(self, po, tx, loads, journey):
        loads.invalidate_recordset()
        tx.invalidate_recordset()
        po.invalidate_recordset()
        return {
            "loads": [(load.state, load.actual_pickup_at, load.actual_delivery_at) for load in loads],
            "tx": tx.state,
            "po": po.state,
            "received": po.order_line.mapped("qty_received"),
            "pickings": po.picking_ids.mapped("state"),
            "invoices": po.invoice_count,
            "journey": self._journey_facts(journey),
        }

    def _propose(self, values, key):
        return self.env[PROPOSAL].action_propose_shipment_event(values, key)

    def test_oct8_booking_complete_supports_load_1_only(self):
        """AC-EXP-09-007 / AC-EXP-11-010 positive: Load 1 recognized; siblings open; gate-in unverified; PO balance."""
        po, tx, loads = self._five_container_order()
        load_1, siblings = loads[0], loads[1:]
        journey = self._journey("S9-OCT8-C1")
        email = self._attach(load_1, "Re: booking complete - Oct 8.eml")
        before = self._snapshot(po, tx, loads, journey)
        loaded_at = self._ago(30)
        proposed = self._propose(
            {
                "event_kind": "loaded",
                "load_id": load_1.id,
                "occurred_at": loaded_at,
                "evidence_attachment_id": email.id,
                "asserted_by": "supplier_reported",
                "source_reference": "booking complete; ticket 1728952",
            },
            "oct8-load1-loaded",
        )
        self.assertEqual(proposed["status"], "applied")
        proposal = self.env[PROPOSAL].browse(proposed["record_id"])
        self.assertEqual(proposal.state, "candidate")
        # Proposing changes nothing: no load, transaction, order, stock or journey fact.
        self.assertEqual(self._snapshot(po, tx, loads, journey), before)

        proposal.action_accept()
        self.assertEqual((proposal.state, proposal.command_status), ("accepted", "applied"))
        self.assertEqual(load_1.actual_pickup_at, loaded_at)
        self.assertEqual(load_1.pickup_evidence_attachment_id, email)
        after = self._snapshot(po, tx, loads, journey)
        self.assertEqual(after["loads"][1:], before["loads"][1:])
        self.assertEqual([load.actual_pickup_at for load in siblings], [False] * 4)
        self.assertEqual(load_1.state, before["loads"][0][0])
        self.assertNotIn(load_1.state, ("delivered", "closed"))
        self.assertEqual(
            (after["tx"], after["po"], after["invoices"]), (before["tx"], before["po"], before["invoices"])
        )
        self.assertEqual(after["received"], [0.0])
        self.assertEqual(after["pickings"], before["pickings"])
        self.assertNotIn("done", after["pickings"])
        self.assertFalse(self._fact(journey, "gate_in"))
        self.assertEqual(after["journey"], before["journey"])

    def test_booking_complete_cannot_attest_gate_in_or_sailing(self):
        """AC-EXP-09-007 / AC-EXP-11-010 negative: the keyword closes nothing and gate-in never appears."""
        po, tx, loads = self._five_container_order()
        journey = self._journey("S9-OCT8-NEG")
        email = self._attach(journey, "booking complete.eml")
        before = self._snapshot(po, tx, loads, journey)
        proposals = self.env[PROPOSAL].search_count([])
        for kind, extra in (
            ("gate_accepted", {"facility_partner_id": self.terminal.id}),
            ("sailed", {"vessel": "MSC Aurora"}),
        ):
            with self.subTest(kind=kind):
                result = self._propose(
                    {
                        "event_kind": kind,
                        "journey_id": journey.id,
                        "occurred_at": self._ago(30),
                        "evidence_attachment_id": email.id,
                        "asserted_by": "supplier_reported",
                        "source_reference": "booking complete",
                        **extra,
                    },
                    f"oct8-{kind}",
                )
                self.assertEqual(result["status"], "blocked")
        self.assertEqual(self.env[PROPOSAL].search_count([]), proposals)
        self.assertEqual(self._snapshot(po, tx, loads, journey), before)
        self.assertFalse(any(load.state in ("delivered", "closed") for load in loads))

    def test_proposal_never_writes_state_directly(self):
        """BRS-EXP-11-R010: no direct write; a proposal is immutable evidence and decided only by its commands."""
        load = self._load()
        doc = self._attach(load, "ticket.pdf")
        proposal = self.env[PROPOSAL].browse(
            self._propose(
                {
                    "event_kind": "loaded",
                    "load_id": load.id,
                    "occurred_at": self._ago(2),
                    "evidence_attachment_id": doc.id,
                    "asserted_by": "carrier_issued",
                },
                "direct-write",
            )["record_id"]
        )
        for values in ({"state": "accepted"}, {"occurred_at": self._ago(1)}, {"load_id": self._load().id}):
            with self.subTest(values=values), self.assertRaises(UserError), self.env.cr.savepoint():
                proposal.write(values)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self.env[PROPOSAL].create(
                {
                    "event_kind": "loaded",
                    "load_id": load.id,
                    "occurred_at": self._ago(2),
                    "evidence_attachment_id": doc.id,
                    "asserted_by": "carrier_issued",
                    "operation_key": "born-accepted",
                    "state": "accepted",
                }
            )
        proposal.action_reject("wrong ticket")
        self.assertEqual(proposal.state, "rejected")
        self.assertFalse(load.actual_pickup_at)
        with self.assertRaises(UserError):
            proposal.action_accept()
        self.assertFalse(load.actual_pickup_at)

    def test_gate_in_and_sailing_proposals_run_the_journey_commands(self):
        """Terminal-issued gate-in and carrier-issued sailing reach J1 only through its owner commands."""
        journey = self._journey("S9-PROPOSE-J1")
        eir = self._attach(journey, "terminal-eir.pdf")
        departure = self._attach(journey, "carrier-sailing.pdf")
        sail = self.env[PROPOSAL].browse(
            self._propose(
                {
                    "event_kind": "sailed",
                    "journey_id": journey.id,
                    "occurred_at": self._ago(10),
                    "vessel": "MSC Aurora",
                    "voyage": "AU545W",
                    "evidence_attachment_id": departure.id,
                    "asserted_by": "carrier_issued",
                },
                "sail-1",
            )["record_id"]
        )
        # The owner refuses a sailing without a gate-in; the proposal stays a candidate.
        with self.assertRaises(UserError), self.env.cr.savepoint():
            sail.action_accept()
        self.assertEqual(sail.state, "candidate")
        self.assertFalse(self._fact(journey, "departure"))
        gate = self.env[PROPOSAL].browse(
            self._propose(
                {
                    "event_kind": "gate_accepted",
                    "journey_id": journey.id,
                    "occurred_at": self._ago(20),
                    "facility_partner_id": self.terminal.id,
                    "evidence_attachment_id": eir.id,
                    "asserted_by": "terminal_issued",
                },
                "gate-1",
            )["record_id"]
        )
        gate.action_accept()
        sail.action_accept()
        self.assertEqual((gate.command_status, sail.command_status), ("applied", "applied"))
        self.assertEqual(self._fact(journey, "gate_in").facility_partner_id, self.terminal)
        self.assertEqual(self._fact(journey, "departure").vessel, "MSC Aurora")

    def test_supplier_ready_runs_the_load_command_with_its_guards(self):
        """supplier_ready accepted runs action_confirm_ready; a load not awaiting readiness is refused."""
        load = self._load()
        doc = self._attach(load, "ready.eml")
        values = {
            "event_kind": "supplier_ready",
            "load_id": load.id,
            "evidence_attachment_id": doc.id,
            "asserted_by": "supplier_reported",
        }
        early = self.env[PROPOSAL].browse(self._propose(values, "ready-early")["record_id"])
        with self.assertRaises(UserError), self.env.cr.savepoint():
            early.action_accept()
        self.assertEqual((load.state, early.state), ("draft", "candidate"))
        load._transition("awaiting_ready")
        early.action_accept()
        self.assertEqual(load.state, "ready_confirmed")
        second = self.env[PROPOSAL].browse(self._propose(values, "ready-again")["record_id"])
        second.action_accept()
        self.assertEqual(second.command_status, "already_applied")

    def test_propose_replay_and_contradiction(self):
        load = self._load()
        doc = self._attach(load, "ticket.pdf")
        values = {
            "event_kind": "loaded",
            "load_id": load.id,
            "occurred_at": self._ago(3),
            "evidence_attachment_id": doc.id,
            "asserted_by": "carrier_issued",
            "source_reference": "ticket 1728952",
        }
        first = self._propose(values, "replay")
        self.assertEqual(
            self._propose(values, "replay"), {"status": "already_applied", "record_id": first["record_id"]}
        )
        changed = self._propose({**values, "source_reference": "ticket 9"}, "replay")
        self.assertEqual(changed["status"], "blocked")
        missing = self._propose({**values, "evidence_attachment_id": self._attach(self._load()).id}, "loose")
        self.assertEqual(missing["status"], "blocked")


@tagged("post_install", "-at_install", "plasticos", "logistics", "export")
class TestContainerTareAndVgm(_S9Case):
    """C10-SCOPE-2 (for BRS-EXP-07-R006): tare and VGM weight are Logistics journey facts from verified evidence."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.lb = cls.env.ref("uom.product_uom_lb")
        cls.kg = cls.env.ref("uom.product_uom_kgm")
        cls.unit = cls.env.ref("uom.product_uom_unit")

    def _weigh(self, kind, journey, weight, uom, basis, attachment, reference, key="w"):
        command = getattr(self.env[FACT], f"action_record_{kind}")
        return command(journey.id, weight, uom.id, basis, attachment.id if attachment else None, reference, key)

    def test_tare_and_vgm_from_a_scale_ticket(self):
        """Positive: a scale ticket on the journey records tare and VGM, each with its unit; replay is idempotent."""
        journey = self._journey("S9-VGM-TICKET")
        ticket = self._attach(journey, "scale-ticket-1728952.pdf")
        tare = self._weigh("container_tare", journey, 8775, self.lb, "scale_ticket", ticket, "1728952")
        vgm = self._weigh("verified_gross_mass", journey, 48975, self.lb, "scale_ticket", ticket, "1728952")
        self.assertEqual((tare["status"], vgm["status"]), ("applied", "applied"))
        tare_fact, vgm_fact = self._fact(journey, "container_tare"), self._fact(journey, "verified_gross_mass")
        self.assertEqual((tare_fact.weight, tare_fact.weight_uom_id), (8775.0, self.lb))
        self.assertEqual((vgm_fact.weight, vgm_fact.weight_basis), (48975.0, "scale_ticket"))
        self.assertEqual(vgm_fact.evidence_attachment_id, ticket)
        replay = self._weigh("verified_gross_mass", journey, 48975, self.lb, "scale_ticket", ticket, "1728952")
        self.assertEqual(replay, {"status": "already_applied", "record_id": vgm_fact.id})
        changed = self._weigh("verified_gross_mass", journey, 49000, self.lb, "scale_ticket", ticket, "1728952")
        self.assertEqual(changed["status"], "blocked")
        self.assertEqual(self._fact(journey, "verified_gross_mass").weight, 48975.0)

    def test_vgm_from_the_documents_verdict(self):
        """Positive: an applied Documents verified_gross_mass verdict on the journey supplies the original.

        Only the Documents verdict facade is stubbed: Documents owns verification, Logistics only obeys it.
        """
        self.assertIn("plasticos.document", self.env, "plasticos_documents is part of the admitted fixture")
        journey = self._journey("S9-VGM-DOCS")
        original = self._attach(journey, "vgm-declaration.pdf")
        tag = self.env["plasticos.document.tag"].search([], limit=1)
        self.assertTrue(tag, "the Documents fixture seeds document tags")
        document = self.env["plasticos.document"].create(
            {
                "name": "VGM declaration",
                "res_model": JOURNEY,
                "res_id": journey.id,
                "attachment_id": original.id,
                "tag_id": tag.id,
            }
        )
        calls = []

        def verdict(model, company_id, subject_kind, subject_id, obligation_kind, revision):
            calls.append((company_id, subject_kind, subject_id, obligation_kind, revision))
            return {"status": "applied", "record_id": document.id}

        with patch.object(type(self.env["plasticos.document"]), "get_scoped_evidence_verdict", verdict):
            other = self._attach(journey, "not-the-verified-original.pdf")
            mismatch = self._weigh(
                "verified_gross_mass", journey, 22000, self.kg, "documents_verified_gross_mass", other, "booking-rev-3"
            )
            result = self._weigh(
                "verified_gross_mass", journey, 22000, self.kg, "documents_verified_gross_mass", None, "booking-rev-3"
            )
        self.assertEqual(mismatch["status"], "blocked")
        self.assertEqual(result["status"], "applied")
        self.assertEqual(calls[-1], (self.company.id, JOURNEY, journey.id, "verified_gross_mass", "booking-rev-3"))
        fact = self._fact(journey, "verified_gross_mass")
        self.assertEqual((fact.verified_document_id, fact.evidence_attachment_id), (document.id, original))
        self.assertEqual((fact.weight, fact.weight_uom_id), (22000.0, self.kg))

    def test_documents_basis_refuses_dangling_or_foreign_documents(self):
        """Negative: the verdict's document must exist and be about this exact journey in its company."""
        journey = self._journey("S9-VGM-DANGLING")
        other_journey = self._journey("S9-VGM-OTHER", iso="TGHU7654321")
        tag = self.env["plasticos.document.tag"].search([], limit=1)
        foreign = self.env["plasticos.document"].create(
            {
                "name": "VGM of another container",
                "res_model": JOURNEY,
                "res_id": other_journey.id,
                "attachment_id": self._attach(other_journey, "other-vgm.pdf").id,
                "tag_id": tag.id,
            }
        )
        missing_id = (self.env["plasticos.document"].search([], order="id desc", limit=1).id or 0) + 1000
        document_class = type(self.env["plasticos.document"])
        for label, record_id in (("dangling", missing_id), ("other journey", foreign.id)):
            with (
                self.subTest(label=label),
                patch.object(
                    document_class,
                    "get_scoped_evidence_verdict",
                    lambda *args, record_id=record_id: {"status": "applied", "record_id": record_id},
                ),
            ):
                result = self._weigh(
                    "verified_gross_mass", journey, 9, self.lb, "documents_verified_gross_mass", None, "rev-1"
                )
                self.assertEqual(result["status"], "blocked")
        self.assertFalse(self._fact(journey, "verified_gross_mass"))

    def test_documents_basis_without_documents_is_not_available(self):
        """Without plasticos_documents the Documents basis answers not_available and never crashes."""
        from odoo.addons.plasticos_logistics.models import iso_journey_fact

        journey = self._journey("S9-VGM-NODOCS")
        with patch.object(iso_journey_fact, "DOCUMENT", "plasticos.document.not.installed"):
            result = self._weigh(
                "verified_gross_mass", journey, 9, self.lb, "documents_verified_gross_mass", None, "rev-1"
            )
        self.assertEqual(result["status"], "not_available")
        self.assertFalse(self._fact(journey, "verified_gross_mass"))
        ticket = self._attach(journey, "ticket.pdf")
        self.assertEqual(
            self._weigh("verified_gross_mass", journey, 9, self.lb, "scale_ticket", ticket, "T-1")["status"], "applied"
        )

    def test_tare_and_vgm_are_never_inferred(self):
        """Negative: no weight from the equipment class or a trailer type; unverified evidence is refused."""
        journey = self._journey("S9-VGM-NEG")
        self.env[LOAD].create(
            {
                "company_id": self.company.id,
                "road_equipment_type_id": self.env.ref("plasticos_logistics.road_equipment_trailer_53").id,
            }
        )
        self.assertFalse(self.env[FACT].search([("journey_id", "=", journey.id)]))
        ticket = self._attach(journey, "ticket.pdf")
        loose = self._attach(self._load(), "ticket-on-load.pdf")
        refused = {
            "no basis": self._weigh("container_tare", journey, 8775, self.lb, "equipment_class", ticket, "40HC"),
            "not a weight unit": self._weigh("container_tare", journey, 1, self.unit, "scale_ticket", ticket, "t"),
            "zero": self._weigh("verified_gross_mass", journey, 0, self.lb, "scale_ticket", ticket, "t"),
            "no ticket number": self._weigh("verified_gross_mass", journey, 9, self.lb, "scale_ticket", ticket, ""),
            "not the journey's original": self._weigh(
                "verified_gross_mass", journey, 9, self.lb, "scale_ticket", loose, "t"
            ),
        }
        document_class = type(self.env["plasticos.document"])
        with patch.object(
            document_class,
            "get_scoped_evidence_verdict",
            lambda *args: {"status": "blocked", "reason": "evidence awaits verification"},
        ):
            refused["unverified documents"] = self._weigh(
                "verified_gross_mass", journey, 9, self.lb, "documents_verified_gross_mass", None, "rev-1"
            )
        for label, result in refused.items():
            with self.subTest(label=label):
                self.assertEqual(result["status"], "blocked")
        self.assertFalse(self.env[FACT].search([("journey_id", "=", journey.id)]))


@tagged("post_install", "-at_install", "plasticos", "logistics", "export")
class TestShipmentProposalAccess(_S9Case):
    """C10-SCOPE-3: only Logistics proposes and decides; a Sales Rep cannot create or accept a proposal."""

    def _user(self, login, group_xmlid):
        groups = self.env.ref("base.group_user") | self.env.ref(group_xmlid)
        return self.env["res.users"].create(
            {
                "name": login,
                "login": login,
                "company_id": self.company.id,
                "company_ids": [(6, 0, self.company.ids)],
                "group_ids": [(6, 0, groups.ids)],
            }
        )

    def test_sales_rep_cannot_create_or_accept_a_proposal(self):
        load = self._load()
        doc = self._attach(load, "ticket.pdf")
        values = {
            "event_kind": "loaded",
            "load_id": load.id,
            "occurred_at": self._ago(2),
            "evidence_attachment_id": doc.id,
            "asserted_by": "carrier_issued",
        }
        rep = self._user("s9-sales-rep", "plasticos_security_base.group_sales_rep")
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            self.env[PROPOSAL].with_user(rep).create({**values, "operation_key": "rep-create"})
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            self.env[PROPOSAL].with_user(rep).action_propose_shipment_event(values, "rep-propose")
        logistics = self._user("s9-logistics", "plasticos_security_base.group_logistics")
        result = self.env[PROPOSAL].with_user(logistics).action_propose_shipment_event(values, "logistics-propose")
        self.assertEqual(result["status"], "applied")
        proposal = self.env[PROPOSAL].browse(result["record_id"])
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            proposal.with_user(rep).action_accept()
        self.assertEqual(proposal.state, "candidate")
        self.assertFalse(load.actual_pickup_at)
        proposal.with_user(logistics).action_accept()
        self.assertEqual(proposal.state, "accepted")
        self.assertTrue(load.actual_pickup_at)
