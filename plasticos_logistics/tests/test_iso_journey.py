"""J1/J2 physical container journeys (ADR-130, RP-02).

Witnesses V02 (physical identity), BRS-EXP-07-R001/R005 (a container is not a
trailer, booking or facility equipment type), BRS-EXP-04-R002/R003 (FAS evidence
without a stock move, physical handoff independent of a buyer) and BRS-EXP-10-R007
(a journey records no milestone by itself).
"""

from psycopg2 import errors as pg_errors

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import tagged
from odoo.tools import mute_logger

JOURNEY = "plasticos.iso.journey"
SOURCE = "plasticos.iso.journey.source"


@tagged("post_install", "-at_install", "plasticos", "logistics", "export")
class TestIsoJourney(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for model in (JOURNEY, SOURCE):
            assert model in cls.env, f"{model} is not in the registry; plasticos_logistics install is broken"
        cls.company = cls.env.company
        cls.supplier = cls.env["res.partner"].create({"name": "J1 Supplier", "is_company": True, "supplier_rank": 1})
        cls.terminal = cls.env["res.partner"].create({"name": "J1 Rail Ramp", "is_company": True})
        cls.carrier = cls.env["res.partner"].create({"name": "J1 Drayage", "is_company": True, "supplier_rank": 1})

    # ── helpers ──────────────────────────────────────────────────────────

    def _load(self, company=None, **extra):
        values = {
            "company_id": (company or self.company).id,
            "pickup_partner_id": self.supplier.id,
            "delivery_partner_id": self.terminal.id,
            "carrier_id": self.carrier.id,
        }
        values.update(extra)
        return self.env["plasticos.load"].create(values)

    def _attachment(self, record, name="evidence.pdf", company=None):
        return self.env["ir.attachment"].create(
            {
                "name": name,
                "raw": b"%PDF-1.4 journey evidence",
                "res_model": record._name if record else False,
                "res_id": record.id if record else False,
                "company_id": (company or self.company).id,
            }
        )

    def _register(self, cycle, iso="MSCU1234567", equipment="40HC", attachment=None, company=None, seal="SL-1"):
        return self.env[JOURNEY].action_register_iso_journey(
            (company or self.company).id,
            cycle,
            equipment,
            attachment.id if attachment else None,
            iso,
            seal,
            f"op-{cycle}",
        )

    def _bind(self, journey_id, kind, source_id, party, attachment=None, basis="carrier interchange receipt"):
        return self.env[SOURCE].action_bind_journey_source(
            journey_id, kind, source_id, party.id, attachment.id if attachment else None, f"op-{journey_id}", basis
        )

    def _other_company(self):
        other = self.env["res.company"].create({"name": "J1 Other Company"})
        self.env.user.write({"company_ids": [(4, other.id)]})
        return other

    # ── J1 identity ──────────────────────────────────────────────────────

    def test_register_is_idempotent_by_company_and_source_cycle(self):
        first = self._register("CYCLE-A")
        self.assertEqual(first["status"], "applied")
        journey = self.env[JOURNEY].browse(first["record_id"])
        self.assertEqual(journey.identity_state, "attributed")
        self.assertEqual(journey.identity_attested_by, self.env.user)
        replay = self._register("CYCLE-A")
        self.assertEqual(replay, {"status": "already_applied", "record_id": journey.id})
        self.assertEqual(self.env[JOURNEY].search_count([("source_cycle_key", "=", "CYCLE-A")]), 1)

    def test_changed_facts_for_an_existing_cycle_are_refused_not_rewritten(self):
        journey = self.env[JOURNEY].browse(self._register("CYCLE-B")["record_id"])
        result = self._register("CYCLE-B", seal="SL-OTHER")
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(journey.seal_number, "SL-1")

    def test_same_iso_number_recurs_in_another_cycle(self):
        """A container is reused: one ISO number, two physical journeys (another voyage)."""
        first = self._register("VOYAGE-1", iso="TGHU7654321")
        second = self._register("VOYAGE-2", iso="TGHU7654321")
        self.assertEqual((first["status"], second["status"]), ("applied", "applied"))
        self.assertNotEqual(first["record_id"], second["record_id"])

    def test_evidence_makes_the_journey_verified(self):
        evidence = self._attachment(None, "interchange.pdf")
        result = self._register("CYCLE-V", attachment=evidence)
        journey = self.env[JOURNEY].browse(result["record_id"])
        self.assertEqual(journey.identity_state, "verified")
        self.assertEqual(journey.identity_evidence_attachment_id, evidence)

    def test_trailer_or_booking_number_is_not_an_iso_identity(self):
        """BRS-EXP-07-R001: a trailer number or booking number never stands in for a container."""
        for not_iso in ("TRL-53-0091", "6509024800"):
            with self.subTest(not_iso=not_iso):
                self.assertEqual(self._register(f"CYCLE-{not_iso}", iso=not_iso)["status"], "blocked")
        self.assertFalse(self.env[JOURNEY].search([("source_cycle_key", "like", "CYCLE-TRL")]))

    def test_equipment_class_is_not_the_facility_equipment_registry(self):
        """BRS-EXP-07-R005: J1 equipment is the source's class, not plasticos.equipment.type."""
        field = self.env[JOURNEY]._fields["equipment_class"]
        self.assertEqual(field.type, "char")
        self.assertFalse(getattr(field, "comodel_name", None))

    def test_candidate_cannot_be_created_already_attributed(self):
        with self.assertRaises(UserError):
            self.env[JOURNEY].create(
                {"company_id": self.company.id, "equipment_class": "40HC", "identity_state": "verified"}
            )

    def test_candidate_confirmation_requires_its_source_cycle(self):
        candidate = self.env[JOURNEY].create({"company_id": self.company.id, "equipment_class": "20STD"})
        with self.assertRaises(UserError):
            candidate.action_confirm_identity()
        candidate.source_cycle_key = "CYCLE-UI"
        candidate.action_confirm_identity()
        self.assertEqual(candidate.identity_state, "attributed")

    def test_attributed_identity_is_immutable_and_not_deletable(self):
        journey = self.env[JOURNEY].browse(self._register("CYCLE-IMM")["record_id"])
        with self.assertRaises(UserError):
            journey.write({"iso_number": "MSCU7654321"})
        with self.assertRaises(UserError):
            journey.write({"identity_state": "verified"})
        with self.assertRaises(UserError):
            journey.unlink()

    def test_registration_records_no_booking_or_milestone(self):
        """BRS-EXP-10-R007: a journey is identity only; it carries no booking or status milestone."""
        names = set(self.env[JOURNEY]._fields)
        self.assertFalse({name for name in names if "booking" in name})
        self.assertFalse({"state", "gate_in_at", "sailed_at", "delivered_at"} & names)

    def test_duplicate_cycle_is_refused_by_the_database(self):
        self._register("CYCLE-DB")
        with mute_logger("odoo.sql_db"), self.assertRaises(pg_errors.UniqueViolation), self.env.cr.savepoint():
            self.env[JOURNEY].create(
                {"company_id": self.company.id, "equipment_class": "40HC", "source_cycle_key": "CYCLE-DB"}
            )

    # ── J2 sources ───────────────────────────────────────────────────────

    def test_two_feeder_loads_feed_one_container(self):
        journey_id = self._register("CYCLE-FEED")["record_id"]
        first, second = self._load(), self._load()
        for load in (first, second):
            self.assertEqual(self._bind(journey_id, "load", load.id, self.supplier)["status"], "applied")
        journey = self.env[JOURNEY].browse(journey_id)
        self.assertEqual(journey.source_ids.load_id, first | second)
        self.assertEqual(set(journey.source_ids.mapped("state")), {"accepted"})

    def test_one_feeder_load_feeds_two_containers(self):
        load = self._load()
        first = self._register("CYCLE-SPLIT-1", iso="MSCU1111111")["record_id"]
        second = self._register("CYCLE-SPLIT-2", iso="MSCU2222222")["record_id"]
        self.assertEqual(self._bind(first, "load", load.id, self.supplier)["status"], "applied")
        self.assertEqual(self._bind(second, "load", load.id, self.supplier)["status"], "applied")
        self.assertEqual(self.env[SOURCE].search_count([("load_id", "=", load.id)]), 2)

    def test_source_bind_replay_returns_the_existing_row(self):
        journey_id = self._register("CYCLE-REPLAY")["record_id"]
        load = self._load()
        applied = self._bind(journey_id, "load", load.id, self.supplier)
        replay = self._bind(journey_id, "load", load.id, self.supplier)
        self.assertEqual(replay, {"status": "already_applied", "record_id": applied["record_id"]})

    def test_source_bind_replay_with_different_facts_is_blocked(self):
        """Replay returns already_applied only for the exact accepted facts (C01-REAUTH-4 (b))."""
        journey_id = self._register("CYCLE-REPLAY-FACTS")["record_id"]
        load = self._load()
        evidence = self._attachment(load, "interchange.pdf")
        applied = self._bind(journey_id, "load", load.id, self.supplier, attachment=evidence, basis="Seal matches")
        source = self.env[SOURCE].browse(applied["record_id"])
        other_evidence = self._attachment(load, "other.pdf")
        for label, kwargs in (
            ("other party", {"party": self.carrier, "attachment": evidence, "basis": "Seal matches"}),
            ("other evidence", {"party": self.supplier, "attachment": other_evidence, "basis": "Seal matches"}),
            ("no evidence", {"party": self.supplier, "attachment": None, "basis": "Seal matches"}),
            ("other basis", {"party": self.supplier, "attachment": evidence, "basis": "Driver said so"}),
        ):
            with self.subTest(label):
                result = self._bind(journey_id, "load", load.id, kwargs["party"], kwargs["attachment"], kwargs["basis"])
                self.assertEqual(result["status"], "blocked")
                self.assertEqual(result["record_id"], source.id)
        exact = self._bind(journey_id, "load", load.id, self.supplier, attachment=evidence, basis="  Seal matches ")
        self.assertEqual(exact, {"status": "already_applied", "record_id": source.id})
        self.assertEqual(
            (source.source_party_id, source.evidence_attachment_id, source.acceptance_basis),
            (self.supplier, evidence, "Seal matches"),
        )

    def test_fas_delivery_with_no_stock_move_uses_original_evidence(self):
        """BRS-EXP-04-R002/R003: a supplier-delivered FAS leg has evidence but no picking or buyer."""
        journey_id = self._register("CYCLE-FAS")["record_id"]
        receipt = self._attachment(None, "rail-ramp-receipt.pdf")
        pickings = self.env["stock.picking"].search_count([])
        result = self._bind(journey_id, "nonstock_evidence", receipt.id, self.supplier, attachment=receipt)
        self.assertEqual(result["status"], "applied")
        self.assertEqual(self.env["stock.picking"].search_count([]), pickings)
        source = self.env[SOURCE].browse(result["record_id"])
        self.assertFalse(source.load_id or source.stock_move_line_id)

    def test_nonstock_source_without_evidence_is_refused_by_the_database(self):
        journey = self.env[JOURNEY].browse(self._register("CYCLE-NOEVID")["record_id"])
        with mute_logger("odoo.sql_db"), self.assertRaises(pg_errors.CheckViolation), self.env.cr.savepoint():
            self.env[SOURCE].create(
                {
                    "journey_id": journey.id,
                    "company_id": self.company.id,
                    "source_kind": "nonstock_evidence",
                    "source_party_id": self.supplier.id,
                }
            )

    def test_cross_company_load_cannot_feed_a_journey(self):
        other = self._other_company()
        journey_id = self._register("CYCLE-XCO")["record_id"]
        foreign_load = self._load(company=other)
        result = self._bind(journey_id, "load", foreign_load.id, self.supplier)
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(self.env[SOURCE].search([("load_id", "=", foreign_load.id)]))

    def test_source_party_must_be_a_party_of_the_load(self):
        stranger = self.env["res.partner"].create({"name": "Unrelated Party", "is_company": True})
        journey_id = self._register("CYCLE-PARTY")["record_id"]
        result = self._bind(journey_id, "load", self._load().id, stranger)
        self.assertEqual(result["status"], "blocked")

    def test_unattributed_candidate_journey_accepts_no_source(self):
        candidate = self.env[JOURNEY].create({"company_id": self.company.id, "equipment_class": "40HC"})
        self.assertEqual(self._bind(candidate.id, "load", self._load().id, self.supplier)["status"], "blocked")

    def test_accepted_source_is_immutable_and_not_deletable(self):
        journey_id = self._register("CYCLE-ACC")["record_id"]
        source = self.env[SOURCE].browse(self._bind(journey_id, "load", self._load().id, self.supplier)["record_id"])
        with self.assertRaises(UserError):
            source.write({"source_reference": "edited"})
        with self.assertRaises(UserError):
            source.unlink()

    def test_source_state_changes_only_through_accept(self):
        journey_id = self._register("CYCLE-UIACC")["record_id"]
        source = self.env[SOURCE].create(
            {
                "journey_id": journey_id,
                "company_id": self.company.id,
                "source_kind": "load",
                "load_id": self._load().id,
                "source_party_id": self.supplier.id,
            }
        )
        with self.assertRaises(UserError):
            source.write({"state": "accepted"})
        with self.assertRaises(UserError):
            source.action_accept()
        source.acceptance_basis = "Driver interchange slip matches the seal"
        source.action_accept()
        self.assertEqual(source.state, "accepted")

    def test_bare_internal_user_cannot_read_or_create_journeys(self):
        """V11: there is no universal base.group_user grant on J1/J2."""
        user = self.env["res.users"].create(
            {"name": "J1 Bare", "login": "j1.bare", "group_ids": [(6, 0, self.env.ref("base.group_user").ids)]}
        )
        with self.assertRaises(AccessError):
            self.env[JOURNEY].with_user(user).search([])
        with self.assertRaises(AccessError):
            self.env[JOURNEY].with_user(user).create({"company_id": self.company.id, "equipment_class": "40HC"})

    def test_attachment_evidence_from_another_company_is_refused(self):
        other = self._other_company()
        evidence = self._attachment(None, "foreign.pdf", company=other)
        with self.assertRaises(ValidationError):
            self.env[JOURNEY].create(
                {
                    "company_id": self.company.id,
                    "equipment_class": "40HC",
                    "identity_evidence_attachment_id": evidence.id,
                }
            )
