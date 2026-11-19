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

from psycopg2 import errors as pg_errors

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger

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
        with (
            mute_logger("odoo.sql_db"),
            self.assertRaises(pg_errors.UniqueViolation),
            self.env.cr.savepoint(),
        ):
            self.env[EQUIPMENT].create({"name": "Another flatbed", "code": "flatbed"})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env[EQUIPMENT].create({"name": "Bad", "code": "Step Deck"})


@tagged("post_install", "-at_install", "plasticos", "logistics", "export")
class TestJourneyMilestonesAndResale(_S9Case):
    """BRS-EXP-08-R007 / AC-EXP-08-007 (Logistics facts)."""

    def _afloat_journey(self, cycle="S9-AFLOAT"):
        """An unsold container afloat: every fact kind recorded from the journey's own originals."""
        journey = self._journey(cycle)
        load = self._load()
        bound = self.env[SOURCE].action_bind_journey_source(
            journey.id, "load", load.id, self.supplier.id, None, f"op-bind-{cycle}", "supplier loading sheet"
        )
        self.assertEqual(bound["status"], "applied")
        commands = self.env[FACT]
        ticket = self._attach(journey, "scale-ticket.pdf")
        lb = self.env.ref("uom.product_uom_lb")
        results = [
            commands.action_record_gate_in(
                journey.id, self._ago(72), self.terminal.id, self._attach(journey, "eir.pdf").id, "g1"
            ),
            commands.action_record_departure(
                journey.id, self._ago(24), "MSC Aurora", "AU545W", self._attach(journey, "sailed.pdf").id, "d1"
            ),
            commands.action_record_regulatory_parties(
                journey.id, self.filer.id, self.consignee.id, self._attach(journey, "filing.pdf").id, "r1"
            ),
            commands.action_record_container_tare(journey.id, 8775, lb.id, "scale_ticket", ticket.id, "T-1", "t1"),
            commands.action_record_verified_gross_mass(
                journey.id, 48975, lb.id, "scale_ticket", ticket.id, "T-1", "v1"
            ),
        ]
        self.assertEqual([result["status"] for result in results], ["applied"] * 5)
        return journey, load

    def _raw_fact_rows(self, journey):
        """Every stored column of the journey's fact rows, and their physical row ids, straight from SQL."""
        self.env.flush_all()
        self.env.cr.execute(
            "SELECT ctid::text, row_to_json(f)::text FROM plasticos_iso_journey_fact f "
            "WHERE journey_id = %s ORDER BY id",
            [journey.id],
        )
        return self.env.cr.fetchall()

    def test_afloat_resale_cannot_rewrite_any_journey_fact(self):
        """AC-EXP-08-007 (Logistics side): after a real buyer change, no path rewrites a recorded fact.

        The container is afloat and unsold. A buyer SO is then put on its load. Every fact kind
        is attacked through every path (ORM write, unlink, re-record with different values);
        each attempt is refused, and every fact row is byte-identical, at the same physical
        row (ctid), before and after. The Export cargo-link variant is C11 08-R007.
        """
        journey, load = self._afloat_journey()
        before = self._raw_fact_rows(journey)
        self.assertEqual(len(before), 5)

        order = self.env["sale.order"].create({"partner_id": self.buyer.id, "company_id": self.company.id})
        load.sale_order_id = order
        self.assertEqual(load.sale_order_id, order, "the buyer change on the load really happened")

        lb = self.env.ref("uom.product_uom_lb")
        doc = self._attach(journey, "buyer-instructions.pdf")
        rewrites = {
            "gate_in": {"occurred_at": self._ago(1), "facility_partner_id": self.buyer.id},
            "departure": {"occurred_at": self._ago(1), "vessel": "Buyer Vessel"},
            "regulatory_parties": {"customs_filer_id": self.buyer.id, "delivery_partner_id": self.buyer.id},
            "container_tare": {"weight": 1.0},
            "verified_gross_mass": {"weight": 1.0},
        }
        commands = self.env[FACT]
        rerecord = {
            "gate_in": lambda: commands.action_record_gate_in(journey.id, self._ago(70), self.buyer.id, doc.id, "g2"),
            "departure": lambda: commands.action_record_departure(
                journey.id, self._ago(2), "Buyer Vessel", "B1", doc.id, "d2"
            ),
            "regulatory_parties": lambda: commands.action_record_regulatory_parties(
                journey.id, self.buyer.id, self.buyer.id, doc.id, "r2"
            ),
            "container_tare": lambda: commands.action_record_container_tare(
                journey.id, 1, lb.id, "scale_ticket", doc.id, "B-1", "t2"
            ),
            "verified_gross_mass": lambda: commands.action_record_verified_gross_mass(
                journey.id, 1, lb.id, "scale_ticket", doc.id, "B-1", "v2"
            ),
        }
        for kind, values in rewrites.items():
            fact = self._fact(journey, kind)
            with self.subTest(kind=kind, path="write"), self.assertRaises(UserError), self.env.cr.savepoint():
                fact.write(values)
            with self.subTest(kind=kind, path="unlink"), self.assertRaises(UserError), self.env.cr.savepoint():
                fact.unlink()
            with self.subTest(kind=kind, path="re-record"):
                self.assertEqual(rerecord[kind]()["status"], "blocked")
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self.env[FACT].create(
                {
                    "journey_id": journey.id,
                    "company_id": self.company.id,
                    "fact_kind": "gate_in",
                    "occurred_at": self._ago(1),
                    "facility_partner_id": self.buyer.id,
                    "evidence_attachment_id": doc.id,
                    "recorded_at": fields.Datetime.now(),
                    "recorded_by": self.env.user.id,
                }
            )
        self.assertEqual(self._raw_fact_rows(journey), before)

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

    def _linda_reply(self, order, binding="current", disposition="unresolved", purpose="po_issue", load=None):
        """A Linda reply answering a real request: a PO issue to the supplier, or a typed load request to its carrier."""
        evidence = self.env["plasticos.logistics.request"].sudo()  # sudo: Linda records its requests only under sudo
        self._linda_revision = getattr(self, "_linda_revision", 0) + 1
        values = {
            "company_id": self.company.id,
            "purpose": purpose,
            "revision": self._linda_revision,
            "payload_fingerprint": f"s9-{self._linda_revision}",
            "subject": "S9 test request",
        }
        if purpose in ("po_issue", "po_cancel"):
            values.update({"partner_id": order.partner_id.id, "purchase_order_id": order.id})
            thread = order
        else:
            values.update(
                {
                    "partner_id": load.carrier_id.id,
                    "source_kind": "load",
                    "source_model": "plasticos.load",
                    "source_res_id": load.id,
                    "source_revision_key": f"s9-rev-{self._linda_revision}",
                }
            )
            thread = load
        request = evidence.create(values)
        message = thread.message_post(body="Booking complete. Ticket 1728952.")
        reply = {
            "company_id": self.company.id,
            "mail_message_id": message.id,
            "request_id": request.id,
            "binding": binding,
            "interpretation": "ai_not_run" if disposition == "unresolved" else "not_interpreted",
            "disposition": disposition,
        }
        if thread is order:
            reply["purchase_order_id"] = order.id
        else:
            reply.update({"source_kind": "load", "source_res_id": load.id})
        responses = self.env["plasticos.logistics.response"].sudo()  # sudo: Linda records replies only under sudo
        return responses.create(reply)

    def test_supplier_linda_reply_cannot_be_labelled_terminal_or_carrier(self):
        """AC-EXP-09-007 / AC-EXP-11-010 negative (B3): a supplier's reply is supplier-reported, whatever the label.

        A supplier "booking complete" reply cited on a gate-in proposal labelled terminal- or
        carrier-issued is refused, and no gate-in or departure fact is written.
        """
        po, _tx, loads = self._five_container_order()
        journey = self._journey("S9-B3")
        bound = self.env[SOURCE].action_bind_journey_source(
            journey.id, "load", loads[0].id, self.supplier.id, None, "op-b3-bind", "supplier loading sheet"
        )
        self.assertEqual(bound["status"], "applied")
        reply = self._linda_reply(po)
        email = self._attach(journey, "booking complete.eml")
        for kind, label, extra in (
            ("gate_accepted", "terminal_issued", {"facility_partner_id": self.terminal.id}),
            ("gate_accepted", "carrier_issued", {"facility_partner_id": self.terminal.id}),
            ("sailed", "carrier_issued", {"vessel": "MSC Aurora"}),
        ):
            with self.subTest(kind=kind, label=label):
                result = self._propose(
                    {
                        "event_kind": kind,
                        "journey_id": journey.id,
                        "occurred_at": self._ago(30),
                        "evidence_attachment_id": email.id,
                        "linda_response_id": reply.id,
                        "asserted_by": label,
                        **extra,
                    },
                    f"b3-{kind}-{label}",
                )
                self.assertEqual(result["status"], "blocked")
        self.assertFalse(self.env[FACT].search([("journey_id", "=", journey.id)]))
        # The same supplier reply honestly labelled supports only Load 1's loaded event.
        load_doc = self._attach(loads[0], "booking complete.eml")
        honest = self._propose(
            {
                "event_kind": "loaded",
                "load_id": loads[0].id,
                "occurred_at": self._ago(30),
                "evidence_attachment_id": load_doc.id,
                "linda_response_id": reply.id,
                "asserted_by": "supplier_reported",
            },
            "b3-honest",
        )
        self.assertEqual(honest["status"], "applied")

    def _logistics_user(self, login):
        groups = self.env.ref("base.group_user") | self.env.ref("plasticos_security_base.group_logistics")
        return self.env["res.users"].create(
            {
                "name": login,
                "login": login,
                "company_id": self.company.id,
                "company_ids": [(6, 0, self.company.ids)],
                "group_ids": [(6, 0, groups.ids)],
            }
        )

    def _journey_of(self, load, cycle):
        journey = self._journey(cycle)
        bound = self.env[SOURCE].action_bind_journey_source(
            journey.id, "load", load.id, self.supplier.id, None, f"bind-{cycle}", "supplier loading sheet"
        )
        self.assertEqual(bound["status"], "applied")
        return journey

    def test_supplier_hauling_its_own_load_is_never_carrier_issued(self):
        """B4: a supplier that is also the load's carrier speaks as the supplier; its reply never writes gate-in or sailing."""
        user = self._logistics_user("s9-b4-supplier-haul")
        load = self._load(carrier_id=self.supplier.id)
        reply = self._linda_reply(None, purpose="load_ack_notice", load=load)
        journey = self._journey_of(load, "S9-B4-SELFHAUL")
        doc = self._attach(journey, "ack.eml")
        proposals = self.env[PROPOSAL].with_user(user)
        for kind, label, extra in (
            ("sailed", "carrier_issued", {"vessel": "MSC Aurora"}),
            ("sailed", "supplier_reported", {"vessel": "MSC Aurora"}),
            ("gate_accepted", "carrier_issued", {"facility_partner_id": self.terminal.id}),
        ):
            with self.subTest(kind=kind, label=label):
                result = proposals.action_propose_shipment_event(
                    {
                        "event_kind": kind,
                        "journey_id": journey.id,
                        "occurred_at": self._ago(5),
                        "evidence_attachment_id": doc.id,
                        "linda_response_id": reply.id,
                        "asserted_by": label,
                        **extra,
                    },
                    f"b4-selfhaul-{kind}-{label}",
                )
                self.assertEqual(result["status"], "blocked")
        self.assertFalse(self.env[FACT].search([("journey_id", "=", journey.id)]))
        load_doc = self._attach(load, "ack-load.eml")
        values = {
            "event_kind": "loaded",
            "load_id": load.id,
            "occurred_at": self._ago(5),
            "evidence_attachment_id": load_doc.id,
            "linda_response_id": reply.id,
        }
        refused = proposals.action_propose_shipment_event({**values, "asserted_by": "carrier_issued"}, "b4-sh-c")
        self.assertEqual(refused["status"], "blocked")
        honest = proposals.action_propose_shipment_event({**values, "asserted_by": "supplier_reported"}, "b4-sh-s")
        self.assertEqual(honest["status"], "applied")

    def test_trucker_reply_cannot_attest_a_sailing_but_supports_loaded(self):
        """B4: a road carrier's dispatch acknowledgement never attests a vessel departure; it may support loaded."""
        user = self._logistics_user("s9-b4-trucker")
        load = self._load()
        reply = self._linda_reply(None, purpose="load_ack_notice", load=load)
        journey = self._journey_of(load, "S9-B4-TRUCKER")
        proposals = self.env[PROPOSAL].with_user(user)
        sailed = proposals.action_propose_shipment_event(
            {
                "event_kind": "sailed",
                "journey_id": journey.id,
                "occurred_at": self._ago(5),
                "vessel": "MSC Aurora",
                "evidence_attachment_id": self._attach(journey, "ack.eml").id,
                "linda_response_id": reply.id,
                "asserted_by": "carrier_issued",
            },
            "b4-trucker-sailed",
        )
        self.assertEqual(sailed["status"], "blocked")
        self.assertFalse(self.env[FACT].search([("journey_id", "=", journey.id)]))
        loaded = proposals.action_propose_shipment_event(
            {
                "event_kind": "loaded",
                "load_id": load.id,
                "occurred_at": self._ago(5),
                "evidence_attachment_id": self._attach(load, "ack-load.eml").id,
                "linda_response_id": reply.id,
                "asserted_by": "carrier_issued",
            },
            "b4-trucker-loaded",
        )
        self.assertEqual(loaded["status"], "applied")
        proposals.browse(loaded["record_id"]).action_accept()
        self.assertTrue(load.actual_pickup_at)

    def test_load_typed_reply_for_a_sibling_load_is_refused(self):
        """B4 / P1: a load-typed reply about a sibling load cannot support this load's event."""
        user = self._logistics_user("s9-b4-sibling")
        load, sibling = self._load(), self._load()
        reply = self._linda_reply(None, purpose="load_ack_notice", load=sibling)
        result = (
            self.env[PROPOSAL]
            .with_user(user)
            .action_propose_shipment_event(
                {
                    "event_kind": "loaded",
                    "load_id": load.id,
                    "occurred_at": self._ago(5),
                    "evidence_attachment_id": self._attach(load, "ack.eml").id,
                    "linda_response_id": reply.id,
                    "asserted_by": "carrier_issued",
                },
                "b4-sibling",
            )
        )
        self.assertEqual(result["status"], "blocked")

    def test_carrier_linda_reply_is_carrier_issued_only_from_the_load_carrier(self):
        """A reply to a typed load request sent to the load's carrier is carrier-issued, never terminal-issued."""
        load = self._load()
        reply = self._linda_reply(None, purpose="load_ack_notice", load=load)
        doc = self._attach(load, "carrier-ack.eml")
        values = {
            "event_kind": "loaded",
            "load_id": load.id,
            "occurred_at": self._ago(3),
            "evidence_attachment_id": doc.id,
            "linda_response_id": reply.id,
        }
        self.assertEqual(
            self._propose({**values, "asserted_by": "supplier_reported"}, "c-supplier")["status"], "blocked"
        )
        self.assertEqual(self._propose({**values, "asserted_by": "carrier_issued"}, "c-carrier")["status"], "applied")

    def test_linda_reply_must_be_current_and_about_this_shipment(self):
        """AC-EXP-09-007: a cited Linda reply must answer the current request on this exact shipment."""
        po, _tx, loads = self._five_container_order()
        load_1 = loads[0]
        email = self._attach(load_1, "booking-complete.eml")
        other_po = self.env["purchase.order"].create({"partner_id": self.supplier.id, "company_id": self.company.id})
        values = {
            "event_kind": "loaded",
            "load_id": load_1.id,
            "occurred_at": self._ago(30),
            "evidence_attachment_id": email.id,
            "asserted_by": "supplier_reported",
        }
        refused = {
            "stale": self._linda_reply(po, binding="stale", disposition="stale"),
            "unbound": self._linda_reply(po, binding="unbound", disposition="unbound"),
            "unattributed": self._linda_reply(po, disposition="unattributed"),
            "another order": self._linda_reply(other_po),
        }
        for label, reply in refused.items():
            with self.subTest(label=label):
                result = self._propose({**values, "linda_response_id": reply.id}, f"linda-{label}")
                self.assertEqual(result["status"], "blocked")
        current = self._linda_reply(po)
        result = self._propose({**values, "linda_response_id": current.id}, "linda-current")
        self.assertEqual(result["status"], "applied")
        self.env["plasticos.shipment.event.proposal"].browse(result["record_id"]).action_accept()
        self.assertTrue(load_1.actual_pickup_at)
        self.assertEqual([load.actual_pickup_at for load in loads[1:]], [False] * 4)

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

    def test_documents_basis_without_documents_is_not_available(self):
        """Without the Documents owner the Documents basis answers not_available and never crashes."""
        from odoo.addons.plasticos_logistics.models.iso_journey_fact import PlasticosIsoJourneyFact

        journey = self._journey("S9-VGM-NODOCS")
        fact_class = type(self.env[FACT])
        with patch.object(fact_class, "_documents_vgm_evidence", PlasticosIsoJourneyFact._documents_vgm_evidence):
            result = self._weigh(
                "verified_gross_mass", journey, 9, self.lb, "documents_verified_gross_mass", None, "rev-1"
            )
        self.assertEqual(result["status"], "not_available")
        self.assertFalse(self._fact(journey, "verified_gross_mass"))
        ticket = self._attach(journey, "ticket.pdf")
        self.assertEqual(
            self._weigh("verified_gross_mass", journey, 9, self.lb, "scale_ticket", ticket, "T-1")["status"], "applied"
        )

    def test_documents_vgm_verdict_cannot_record_tare(self):
        """Negative: a VGM verdict proves gross mass only, so it never records a container tare."""
        journey = self._journey("S9-TARE-FROM-VGM")
        calls = []

        def evidence(records, journey_id, revision_key):
            calls.append((journey_id, revision_key))
            return None, None, ("blocked", "the Documents verdict was consulted")

        with patch.object(type(self.env[FACT]), "_documents_vgm_evidence", evidence):
            result = self._weigh(
                "container_tare", journey, 8775, self.lb, "documents_verified_gross_mass", None, "rev-1"
            )
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(calls, "the Documents verdict is not even consulted for a tare")
        self.assertFalse(self._fact(journey, "container_tare"))

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


@tagged("post_install", "-at_install", "plasticos", "logistics", "export")
class TestS9ReviewClosure(_S9Case):
    """C10-SCOPE-4 review closure, witnessed as non-superuser users (criterion 5)."""

    def _user(self, login, group_xmlid, company=None):
        company = company or self.company
        groups = self.env.ref("base.group_user") | self.env.ref(group_xmlid)
        return self.env["res.users"].create(
            {
                "name": login,
                "login": login,
                "company_id": company.id,
                "company_ids": [(6, 0, company.ids)],
                "group_ids": [(6, 0, groups.ids)],
            }
        )

    def _gate_in(self, journey, key="g", facility=None, when=None):
        doc = self._attach(journey, f"eir-{key}.pdf")
        return self.env[FACT].action_record_gate_in(
            journey.id, when or self._ago(5), (facility or self.terminal).id, doc.id, key
        )

    # ── B1: journey facts are not readable outside Logistics ─────────────

    def test_sales_rep_cannot_read_journey_facts_or_their_menu(self):
        """B1: a Sales Rep (or Accounting user) gets AccessError on facts and sees no J1 identity through them."""
        journey = self._journey("S9-B1")
        self.assertEqual(self._gate_in(journey)["status"], "applied")
        menu = self.env.ref("plasticos_logistics.menu_iso_journey_fact")
        for group in ("plasticos_security_base.group_sales_rep", "plasticos_security_base.group_accounting"):
            user = self._user(f"s9-b1-{group.split('.')[-1]}", group)
            with self.subTest(group=group):
                with self.assertRaises(AccessError):
                    self.env[FACT].with_user(user).search_read(
                        [("journey_id", "=", journey.id)], ["journey_id", "facility_partner_id"]
                    )
                with self.assertRaises(AccessError):
                    self.env[JOURNEY].with_user(user).browse(journey.id).read(["iso_number"])
                self.assertNotIn(menu.id, self.env["ir.ui.menu"].with_user(user)._visible_menu_ids())
        logistics = self._user("s9-b1-logistics", "plasticos_security_base.group_logistics")
        rows = self.env[FACT].with_user(logistics).search_read([("journey_id", "=", journey.id)], ["fact_kind"])
        self.assertEqual([row["fact_kind"] for row in rows], ["gate_in"])
        self.assertIn(menu.id, self.env["ir.ui.menu"].with_user(logistics)._visible_menu_ids())

    # ── N8: company B cannot read or cite company A ──────────────────────

    def test_company_b_user_cannot_read_or_cite_company_a(self):
        """A company-B Logistics user cannot read company-A facts or proposals, nor cite A's records."""
        company_b = self.env["res.company"].create({"name": "S9 Company B"})
        user_b = self._user("s9-company-b", "plasticos_security_base.group_logistics", company=company_b)
        journey_a = self._journey("S9-A-FACTS")
        self.assertEqual(self._gate_in(journey_a)["status"], "applied")
        load_a = self._load()
        doc_a = self._attach(load_a, "a-ticket.pdf")
        proposal_a = self.env[PROPOSAL].action_propose_shipment_event(
            {
                "event_kind": "loaded",
                "load_id": load_a.id,
                "occurred_at": self._ago(2),
                "evidence_attachment_id": doc_a.id,
                "asserted_by": "carrier_issued",
            },
            "a-proposal",
        )
        self.assertEqual(proposal_a["status"], "applied")
        as_b = self.env(user=user_b, context={"allowed_company_ids": company_b.ids})
        self.assertFalse(as_b[FACT].search([("journey_id", "=", journey_a.id)]))
        self.assertFalse(as_b[PROPOSAL].search([("id", "=", proposal_a["record_id"])]))
        with self.assertRaises(AccessError):
            as_b[PROPOSAL].action_propose_shipment_event(
                {
                    "event_kind": "loaded",
                    "load_id": load_a.id,
                    "occurred_at": self._ago(2),
                    "evidence_attachment_id": doc_a.id,
                    "asserted_by": "carrier_issued",
                },
                "b-on-a",
            )
        load_b = self.env[LOAD].create(
            {
                "company_id": company_b.id,
                "pickup_partner_id": self.supplier.id,
                "delivery_partner_id": self.terminal.id,
                "carrier_id": self.carrier.id,
            }
        )
        cited = as_b[PROPOSAL].action_propose_shipment_event(
            {
                "event_kind": "loaded",
                "load_id": load_b.id,
                "occurred_at": self._ago(2),
                "evidence_attachment_id": doc_a.id,
                "asserted_by": "carrier_issued",
            },
            "b-cites-a",
        )
        self.assertEqual(cited["status"], "blocked")
        with self.assertRaises(AccessError):
            as_b[FACT].action_record_gate_in(journey_a.id, self._ago(1), self.terminal.id, doc_a.id, "b-gate")

    # ── N3: parties must be visible and in the journey's company ─────────

    def test_parties_from_another_company_are_refused(self):
        other = self.env["res.company"].create({"name": "S9 Party Co"})
        foreign = self.env["res.partner"].create({"name": "S9 Foreign Terminal", "company_id": other.id})
        journey = self._journey("S9-N3")
        self.assertEqual(self._gate_in(journey, "foreign", facility=foreign)["status"], "blocked")
        doc = self._attach(journey, "filing.pdf")
        self.assertEqual(
            self.env[FACT].action_record_regulatory_parties(journey.id, foreign.id, False, doc.id, "r")["status"],
            "blocked",
        )
        result = self.env[PROPOSAL].action_propose_shipment_event(
            {
                "event_kind": "gate_accepted",
                "journey_id": journey.id,
                "occurred_at": self._ago(3),
                "facility_partner_id": foreign.id,
                "evidence_attachment_id": doc.id,
                "asserted_by": "terminal_issued",
            },
            "n3-proposal",
        )
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(self.env[FACT].search([("journey_id", "=", journey.id)]))

    # ── N2: a concurrent duplicate is answered, never an IntegrityError ──

    def test_concurrent_duplicate_record_and_propose_are_answered(self):
        """The losing writer of a duplicate fact or proposal gets already_applied or blocked."""
        journey = self._journey("S9-N2")
        doc = self._attach(journey, "eir.pdf")
        when = self._ago(5)
        first = self.env[FACT].action_record_gate_in(journey.id, when, self.terminal.id, doc.id, "g")
        self.assertEqual(first["status"], "applied")
        fact_class = type(self.env[FACT])
        original = fact_class._existing_result
        calls = []

        def miss_first(model, *args):
            calls.append(args)
            return None if len(calls) == 1 else original(model, *args)

        with patch.object(fact_class, "_existing_result", miss_first), mute_logger("odoo.sql_db"):
            same = self.env[FACT].action_record_gate_in(journey.id, when, self.terminal.id, doc.id, "g")
        self.assertEqual(same, {"status": "already_applied", "record_id": first["record_id"]})
        calls.clear()
        with patch.object(fact_class, "_existing_result", miss_first), mute_logger("odoo.sql_db"):
            other = self.env[FACT].action_record_gate_in(journey.id, self._ago(6), self.terminal.id, doc.id, "g")
        self.assertEqual(other["status"], "blocked")

        load = self._load()
        ticket = self._attach(load, "ticket.pdf")
        values = {
            "event_kind": "loaded",
            "load_id": load.id,
            "occurred_at": self._ago(2),
            "evidence_attachment_id": ticket.id,
            "asserted_by": "carrier_issued",
        }
        winner = self.env[PROPOSAL].action_propose_shipment_event(values, "race")
        proposal_class = type(self.env[PROPOSAL])
        original_search = proposal_class.search
        hidden = []

        def hide_first_key_lookup(model, domain, *args, **kwargs):
            if ("operation_key", "=", "race") in domain and not hidden:
                hidden.append(True)
                return model.browse()
            return original_search(model, domain, *args, **kwargs)

        with patch.object(proposal_class, "search", hide_first_key_lookup), mute_logger("odoo.sql_db"):
            loser = self.env[PROPOSAL].action_propose_shipment_event(values, "race")
        self.assertEqual(loser, {"status": "already_applied", "record_id": winner["record_id"]})

    # ── N5: decisions, rejected replay, generated key ────────────────────

    def test_decision_fields_rejected_replay_and_generated_key(self):
        load = self._load()
        doc = self._attach(load, "ticket.pdf")
        values = {
            "event_kind": "loaded",
            "load_id": load.id,
            "occurred_at": self._ago(2),
            "evidence_attachment_id": doc.id,
            "asserted_by": "carrier_issued",
        }
        for decision in (
            {"decided_at": fields.Datetime.now()},
            {"decision_note": "approved by me"},
            {"command_status": "applied"},
        ):
            with self.subTest(decision=decision), self.assertRaises(UserError), self.env.cr.savepoint():
                self.env[PROPOSAL].create({**values, **decision})
        generated = self.env[PROPOSAL].create(values)
        self.assertTrue(generated.operation_key.startswith("form:"))
        first = self.env[PROPOSAL].action_propose_shipment_event(values, "to-reject")
        self.env[PROPOSAL].browse(first["record_id"]).action_reject("wrong ticket")
        replay = self.env[PROPOSAL].action_propose_shipment_event(values, "to-reject")
        self.assertEqual(replay["status"], "rejected")
        self.assertEqual(replay["record_id"], first["record_id"])

    # ── N8: replay at stored precision ───────────────────────────────────

    def test_weight_replay_is_compared_at_stored_precision(self):
        journey = self._journey("S9-N8-W")
        ticket = self._attach(journey, "ticket.pdf")
        lb = self.env.ref("uom.product_uom_lb")
        fact = self.env[FACT]
        first = fact.action_record_verified_gross_mass(journey.id, 48975, lb.id, "scale_ticket", ticket.id, "T", "w")
        noise = fact.action_record_verified_gross_mass(
            journey.id, 48975.0004, lb.id, "scale_ticket", ticket.id, "T", "w"
        )
        changed = fact.action_record_verified_gross_mass(
            journey.id, 48975.01, lb.id, "scale_ticket", ticket.id, "T", "w"
        )
        self.assertEqual(first["status"], "applied")
        self.assertEqual(noise, {"status": "already_applied", "record_id": first["record_id"]})
        self.assertEqual(changed["status"], "blocked")
