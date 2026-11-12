"""Export booking candidates, acceptance, rolls and idempotent replay (RP-07-E058).

E1/E2 of TECHNICAL_CONTRACT_v2.7. Each test names the BRS rules it witnesses.
No outbound mail leaves the test database: Linda stays in its default ``off``
mode here, and the notice tests in test_export_owner_handoff.py use ``live``
only against the test mail queue. ``ExportFixtureMixin`` is the shared fixture
of every Export suite; it is a plain mixin, so importing it runs no test twice.
"""

import base64
import itertools

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests.common import new_test_user, tagged

BOOKING = "plasticos.export.booking"
REVISION = "plasticos.export.booking.revision"
SLOT = "plasticos.export.booking.slot"
LINK = "plasticos.export.booking.cargo.link"
_BYTES = itertools.count(1)
_KEYS = itertools.count(1)

ACTOR_GROUPS = [
    "base.group_user",
    "plasticos_security_base.group_logistics",
    "purchase.group_purchase_user",
    "sales_team.group_sale_salesman",
    "stock.group_stock_user",
    "documents.group_documents_user",
]


def actor_groups(env, extra=()):
    refs = [env.ref(xmlid, raise_if_not_found=False) for xmlid in [*ACTOR_GROUPS, *extra]]
    return ",".join(ref.get_external_id()[ref.id] for ref in refs if ref)


class ExportFixtureMixin:
    """Companies, parties, an Export actor and booking helpers shared by every Export suite."""

    @classmethod
    def _setup_export_fixture(cls):
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True, mail_notrack=True))
        cls.company = cls.env.company
        cls.company.email = "export@s5b-company.example"
        cls.company_b = cls.env["res.company"].create({"name": "S5B Other Company", "email": "ops@s5b-other.example"})
        Partner = cls.env["res.partner"]
        cls.issuer = Partner.create({"name": "S5B Forwarder", "is_company": True, "email": "book@s5b-fwd.example"})
        cls.carrier = Partner.create({"name": "S5B Ocean Carrier", "is_company": True, "email": "ops@s5b-ocl.example"})
        cls.line = Partner.create({"name": "S5B Steamship Line", "is_company": True})
        cls.suppliers = Partner.create(
            [
                {"name": f"S5B Mill {n}", "is_company": True, "supplier_rank": 1, "email": f"mill{n}@s5b.example"}
                for n in range(1, 5)
            ]
        )
        cls.buyer = Partner.create(
            {"name": "S5B Overseas Buyer", "is_company": True, "customer_rank": 1, "email": "buy@s5b-buyer.example"}
        )
        cls.product = cls.env["product.product"].create({"name": "S5B HDPE Regrind", "type": "consu"})
        cls.lb = cls.env.ref("uom.product_uom_lb").with_context(active_test=False)
        groups = actor_groups(cls.env)
        cls.actor = new_test_user(
            cls.env,
            login="s5b_export_actor",
            groups=groups,
            company_id=cls.company.id,
            company_ids=[(6, 0, [cls.company.id])],
        )
        cls.outsider = new_test_user(
            cls.env,
            login="s5b_export_outsider",
            groups="base.group_user,purchase.group_purchase_user",
            company_id=cls.company.id,
            company_ids=[(6, 0, [cls.company.id])],
        )
        cls.foreign_actor = new_test_user(
            cls.env,
            login="s5b_export_foreign",
            groups=groups,
            company_id=cls.company_b.id,
            company_ids=[(6, 0, [cls.company_b.id])],
        )

    # ── helpers ──────────────────────────────────────────────

    @staticmethod
    def key(prefix="op"):
        return f"{prefix}-{next(_KEYS)}"

    def make_booking(self, user=None, company=None, cycle=None, **vals):
        user = user or self.actor
        company = company or self.company
        values = {
            "company_id": company.id,
            "issuer_id": self.issuer.id,
            "carrier_id": self.carrier.id,
            "source_occurrence_key": cycle or self.key("cycle"),
        }
        values.update(vals)
        return self.env[BOOKING].with_user(user).with_company(company).create(values)

    def original(self, booking, name="booking-confirmation.pdf"):
        """A native original file on the booking, as native Documents holds it."""
        attachment = self.env["ir.attachment"].create(
            {
                "name": name,
                "datas": base64.b64encode(f"carrier confirmation {next(_BYTES)}".encode()),
                "res_model": BOOKING,
                "res_id": booking.id,
            }
        )
        document = self.env["documents.document"].create(
            {
                "name": name,
                "attachment_id": attachment.id,
                "access_internal": "view",
                "company_id": booking.company_id.id,
            }
        )
        self.assertEqual((document.res_model, document.res_id), (BOOKING, booking.id))
        return document

    def incoming(self, booking, body="Booking confirmation"):
        return self.env["mail.message"].create(
            {
                "model": BOOKING,
                "res_id": booking.id,
                "message_type": "email",
                "body": body,
                "author_id": self.issuer.id,
            }
        )

    @staticmethod
    def terms(confirmed=5, requested=None, code="40HC", number="6509024800", **extra):
        values = {
            "carrier_booking_no": number,
            "pol_text": "Savannah, GA",
            "pod_text": "Haiphong",
            "erd_local": "2026-09-28 08:00",
            "erd_tz": "America/New_York",
            "erd_precision": "datetime",
            "cargo_cutoff_local": "2026-10-02",
            "cargo_cutoff_precision": "date",
            "equipment_counts": {
                code: {"requested": requested if requested is not None else confirmed, "confirmed": confirmed}
            },
        }
        values.update(extra)
        return values

    def candidate(self, booking, revision_key=None, terms=None, user=None, original=True, operation_key=None):
        user = user or self.actor
        document = self.original(booking) if original else self.env["documents.document"]
        message = self.env["mail.message"] if original else self.incoming(booking)
        outcome = booking.with_user(user).record_booking_revision_candidate(
            document.id or False,
            message.id or False,
            revision_key or self.key("rev"),
            terms if terms is not None else self.terms(),
            operation_key or self.key("cand"),
        )
        return outcome

    def accept(self, booking, revision_id, expected=False, user=None, reason="Carrier confirmation reviewed"):
        user = user or self.actor
        return booking.with_user(user).action_accept_booking_revision(revision_id, expected, self.key("acc"), reason)

    def accepted_booking(self, confirmed=5, **booking_vals):
        booking = self.make_booking(**booking_vals)
        recorded = self.candidate(booking, terms=self.terms(confirmed=confirmed))
        self.assertEqual(recorded["status"], "applied", recorded)
        accepted = self.accept(booking, recorded["record_id"])
        self.assertEqual(accepted["status"], "applied", accepted)
        return booking, self.env[REVISION].browse(recorded["record_id"])


@tagged("post_install", "-at_install", "plasticos", "plasticos_export")
class TestBookingAndRevision(ExportFixtureMixin, PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_export_fixture()

    def test_candidate_needs_exact_source_and_changes_nothing_current(self):
        """BRS-EXP-09-R006, BRS-EXP-06-R002, BRS-EXP-11-R006: a proposal is bounded and changes nothing current."""
        booking = self.make_booking()
        no_source = booking.with_user(self.actor).record_booking_revision_candidate(
            False, False, "rev-1", self.terms(), self.key()
        )
        self.assertEqual(no_source["status"], "blocked")
        other = self.make_booking()
        wrong = booking.with_user(self.actor).record_booking_revision_candidate(
            self.original(other).id, False, "rev-1", self.terms(), self.key()
        )
        self.assertEqual(wrong, {"status": "blocked", "reason": "source original belongs to another record"})
        unknown = self.candidate(booking, terms={**self.terms(), "vessel_guess": "MAERSK X"})
        self.assertEqual(unknown["status"], "blocked")
        self.assertIn("Unknown booking terms", unknown["reason"])
        recorded = self.candidate(booking, revision_key="rev-1")
        self.assertEqual(recorded["status"], "applied")
        revision = self.env[REVISION].browse(recorded["record_id"])
        self.assertEqual(revision.decision, "candidate")
        self.assertTrue(revision.source_original_id.attachment_id)
        self.assertFalse(booking.current_revision_id)
        self.assertEqual(booking.display_state, "candidate")
        self.assertFalse(booking.slot_ids)
        from_mail = self.candidate(booking, revision_key="rev-mail", original=False)
        self.assertEqual(from_mail["status"], "applied")
        self.assertTrue(self.env[REVISION].browse(from_mail["record_id"]).source_message_id)

    def test_candidate_replay_is_idempotent_and_a_changed_payload_is_stale(self):
        """BRS-EXP-09-R005: an identical event dedupes; a different payload under the same identity is refused."""
        booking = self.make_booking()
        document = self.original(booking)
        args = (document.id, False, "rev-1", self.terms(), "cand-replay")
        first = booking.with_user(self.actor).record_booking_revision_candidate(*args)
        again = booking.with_user(self.actor).record_booking_revision_candidate(*args)
        self.assertEqual(first["status"], "applied")
        self.assertEqual(again, {"status": "already_applied", "record_id": first["record_id"]})
        changed = booking.with_user(self.actor).record_booking_revision_candidate(
            document.id, False, "rev-1", self.terms(confirmed=4), "cand-replay"
        )
        self.assertEqual(changed["status"], "stale")
        same_source_new_terms = booking.with_user(self.actor).record_booking_revision_candidate(
            document.id, False, "rev-1", self.terms(confirmed=4), "cand-other"
        )
        self.assertEqual(same_source_new_terms["status"], "stale")
        self.assertEqual(len(booking.revision_ids), 1)

    def test_one_booking_five_40hc_becomes_five_distinct_slots(self):
        """BRS-EXP-02-R001, BRS-EXP-02-R002, BRS-EXP-07-R003, BRS-EXP-07-R004, BRS-EXP-13-R001: PHASE1 gate case."""
        booking, revision = self.accepted_booking(confirmed=5)
        self.assertEqual(booking.current_revision_id, revision)
        self.assertEqual(booking.carrier_booking_no, "6509024800")
        self.assertEqual(booking.display_state, "confirmed")
        self.assertEqual(booking.current_pol_text, "Savannah, GA")
        self.assertEqual(booking.current_pod_text, "Haiphong")
        slots = booking.slot_ids
        self.assertEqual(len(slots), 5)
        self.assertEqual(set(slots.mapped("equipment_class")), {"40HC"})
        self.assertEqual(sorted(slots.mapped("slot_key")), [f"40HC-{n}" for n in range(1, 6)])
        self.assertEqual(set(slots.mapped("allocation_state")), {"available"})
        self.assertEqual(booking.slot_confirmed_count, 5)
        self.assertEqual(revision.accepted_by, self.actor)
        self.assertTrue(revision.acceptance_basis)
        self.assertEqual(self.env[SLOT]._fields["equipment_class"].default(self.env[SLOT]), "40HC")
        selectable = [code for code, _label in self.env[SLOT]._fields["equipment_class"].selection]
        self.assertEqual(selectable, ["20STD", "40STD", "40HC", "45STD", "45HC"])

    def test_acceptance_is_compare_and_set_and_a_roll_supersedes(self):
        """V05, BRS-EXP-02-R004, BRS-EXP-11-R005, BRS-EXP-13-R003: currentness moves once; history stays."""
        booking, first = self.accepted_booking(confirmed=5)
        roll = self.candidate(booking, terms=self.terms(confirmed=5, erd_local="2026-10-05 08:00"))
        racing = self.accept(booking, roll["record_id"], expected=False)
        self.assertEqual(racing["status"], "stale")
        self.assertEqual(booking.current_revision_id, first)
        moved = self.accept(booking, roll["record_id"], expected=first.id)
        self.assertEqual(moved["status"], "applied")
        second = self.env[REVISION].browse(roll["record_id"])
        self.assertEqual(booking.current_revision_id, second)
        self.assertEqual(second.supersedes_revision_id, first)
        replay = self.accept(booking, second.id, expected=first.id)
        self.assertEqual(replay["status"], "already_applied")
        late = self.accept(booking, first.id, expected=second.id)
        self.assertEqual(late["status"], "stale")
        self.assertEqual(len(booking.slot_ids), 5)

    def test_accepted_revision_is_immutable_and_never_deleted(self):
        """BRS-EXP-02-R004, BRS-EXP-11-R006: no silent overwrite of a confirmed term."""
        booking, revision = self.accepted_booking(confirmed=2)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            revision.with_user(self.actor).write({"erd_local": "2026-12-01 08:00"})
        with self.assertRaises(UserError), self.env.cr.savepoint():
            revision.with_user(self.actor).unlink()
        with self.assertRaises(UserError), self.env.cr.savepoint():
            booking.with_user(self.actor).write({"current_revision_id": False})
        with self.assertRaises(UserError), self.env.cr.savepoint():
            booking.with_user(self.actor).write({"source_occurrence_key": "another-cycle"})
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self.env[REVISION].with_user(self.actor).create(
                {"booking_id": booking.id, "source_revision_key": "typed", "observed_at": "2026-01-01 00:00:00"}
            )
        with self.assertRaises(UserError), self.env.cr.savepoint():
            booking.with_user(self.actor).unlink()

    def test_times_keep_their_zone_and_precision(self):
        """BRS-EXP-02-R003, BRS-EXP-11-R004, BRS-EXP-13-R002, BRS-EXP-14-R007: UTC only from date, time and zone."""
        booking, revision = self.accepted_booking(confirmed=1)
        self.assertEqual(revision.erd_precision, "datetime")
        self.assertEqual(revision.erd_tz, "America/New_York")
        self.assertEqual(str(revision.erd_utc), "2026-09-28 12:00:00")
        self.assertEqual(revision.cargo_cutoff_precision, "date")
        self.assertEqual(revision.cargo_cutoff_local, "2026-10-02")
        self.assertFalse(revision.cargo_cutoff_utc)
        self.assertFalse(booking.current_cargo_cutoff_utc)
        unknown_with_value = self.candidate(booking, terms=self.terms(erd_precision="unknown"))
        self.assertEqual(unknown_with_value["status"], "blocked")
        bad_zone = self.candidate(booking, terms=self.terms(erd_tz="Mars/Base"))
        self.assertEqual(bad_zone["status"], "blocked")

    def test_other_places_and_references_stay_distinct_source_terms(self):
        """BRS-EXP-13-R004, BRS-EXP-13-R006, BRS-EXP-11-R004: each place keeps its own label; none is borrowed."""
        places = {
            "place_of_receipt": "Dalton, GA",
            "empty_pickup_facility": "Garden City Terminal",
            "loaded_return_terminal": "Ocean Terminal",
            "rail_ramp": None,
            "booking_contact": "desk@s5b-fwd.example",
            "max_cargo_weight_lb": "44000",
        }
        booking = self.make_booking()
        recorded = self.candidate(booking, terms=self.terms(additional_terms=places))
        revision = self.env[REVISION].browse(recorded["record_id"])
        self.assertEqual(revision.additional_terms, places)
        self.assertEqual((revision.pol_text, revision.pod_text), ("Savannah, GA", "Haiphong"))
        self.assertIsNone(revision.additional_terms["rail_ramp"])

    def test_acceptance_needs_identity_and_a_new_number_is_not_a_revision(self):
        """BRS-EXP-02-R001, BRS-EXP-08-R005: issuer, number and booking cycle; a replacement is another booking."""
        booking = self.make_booking(source_occurrence_key=False)
        recorded = self.candidate(booking)
        self.assertEqual(self.accept(booking, recorded["record_id"])["status"], "blocked")
        booking, _first = self.accepted_booking(confirmed=1)
        replacement = self.candidate(booking, terms=self.terms(confirmed=1, number="7700000001"))
        outcome = self.accept(booking, replacement["record_id"], expected=booking.current_revision_id.id)
        self.assertEqual(outcome["status"], "blocked")
        self.assertIn("replacement booking", outcome["reason"])
        twin = self.make_booking(cycle=booking.source_occurrence_key + "-2")
        self.assertTrue(twin)

    def test_reduction_retires_free_slots_and_holds_committed_ones(self):
        """BRS-EXP-14-R016, BRS-EXP-11-R005, BRS-EXP-11-R011: a downsize never releases cargo silently."""
        booking, first = self.accepted_booking(confirmed=3)
        slots = booking.slot_ids.sorted("slot_key")
        order = self.env["purchase.order"].create(
            {
                "partner_id": self.suppliers[0].id,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_qty": 40000, "product_uom_id": self.lb.id})
                ],
            }
        )
        kept = (
            slots[1]
            .with_user(self.actor)
            .action_commit_cargo({"purchase_line_id": order.order_line.id}, None, None, first.id, self.key("commit"))
        )
        committed = (
            slots[2]
            .with_user(self.actor)
            .action_commit_cargo({"purchase_line_id": order.order_line.id}, None, None, first.id, self.key("commit"))
        )
        self.assertEqual((kept["status"], committed["status"]), ("applied", "applied"))
        down = self.candidate(booking, terms=self.terms(confirmed=1))
        self.assertEqual(self.accept(booking, down["record_id"], expected=first.id)["status"], "applied")
        live = self.env[SLOT].search([("booking_id", "=", booking.id)])
        retired = (
            self.env[SLOT]
            .with_context(active_test=False)
            .search([("booking_id", "=", booking.id), ("active", "=", False)])
        )
        # The free slot retires first; one committed slot then has to be held, never released.
        self.assertEqual(retired, slots[0])
        self.assertEqual(slots[1].allocation_state, "committed")
        self.assertEqual(slots[2].allocation_state, "held")
        self.assertIn("reduced confirmed 40HC capacity", slots[2].hold_reason)
        self.assertEqual(self.env[LINK].browse(committed["record_id"]).state, "held")
        self.assertEqual(len(live), 2)
        self.assertEqual(booking.display_state, "held")

    def test_stated_cancellation_cancels_the_booking(self):
        """BRS-EXP-13-R007: status as the source states it; nothing is inferred."""
        booking, first = self.accepted_booking(confirmed=2)
        cancel = self.candidate(
            booking, terms=self.terms(confirmed=2, additional_terms={"booking_status": "cancelled"})
        )
        self.assertEqual(self.accept(booking, cancel["record_id"], expected=first.id)["status"], "applied")
        self.assertEqual(booking.display_state, "cancelled")
        self.assertFalse(booking.slot_ids)
        invented = self.candidate(booking, terms=self.terms(additional_terms={"booking_status": "probably rolled"}))
        self.assertEqual(invented["status"], "blocked")

    def test_commands_refuse_outsiders_and_sudo(self):
        """E3, BRS-EXP-14-R012: commands run as an authorized actor of the booking's company."""
        booking = self.make_booking()
        refused = booking.with_user(self.outsider).record_booking_revision_candidate(
            self.original(booking).id, False, "rev-x", self.terms(), self.key()
        )
        self.assertEqual(refused["status"], "not_available")
        through_sudo = booking.sudo().record_booking_revision_candidate(  # sudo: proves the command refuses sudo
            self.original(booking).id, False, "rev-y", self.terms(), self.key()
        )
        self.assertEqual(through_sudo["status"], "not_available")
        self.assertFalse(booking.revision_ids)

    def _commit_po(self, slot, revision):
        order = self.env["purchase.order"].create(
            {
                "partner_id": self.suppliers[0].id,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_qty": 1000, "product_uom_id": self.lb.id})
                ],
            }
        )
        outcome = slot.with_user(self.actor).action_commit_cargo(
            {"purchase_line_id": order.order_line.id}, None, None, revision.id, self.key("commit")
        )
        self.assertEqual(outcome["status"], "applied", outcome)
        return self.env[LINK].browse(outcome["record_id"])

    def _roll(self, booking, confirmed):
        recorded = self.candidate(booking, terms=self.terms(confirmed=confirmed))
        outcome = self.accept(booking, recorded["record_id"], expected=booking.current_revision_id.id)
        self.assertEqual(outcome["status"], "applied", outcome)
        return self.env[REVISION].browse(recorded["record_id"])

    def test_restored_capacity_lifts_holds_before_adding_slots(self):
        """BRS-EXP-14-R016, BRS-EXP-11-R011 (PR #479 review): a hold ends when the carrier restores capacity."""
        booking, first = self.accepted_booking(confirmed=3)
        slots = booking.slot_ids.sorted("slot_key")
        kept = self._commit_po(slots[1], first)
        held = self._commit_po(slots[2], first)
        self._roll(booking, 1)
        self.assertEqual((slots[1].allocation_state, slots[2].allocation_state), ("committed", "held"))
        self.assertEqual((booking.slot_confirmed_count, booking.slot_held_count), (1, 1))
        # The same lower count again withdraws nothing more: the existing hold already covers it.
        self._roll(booking, 1)
        self.assertEqual((slots[1].allocation_state, slots[2].allocation_state), ("committed", "held"))
        self.assertEqual(kept.state, "committed")
        # Capacity back to three: the held slot is restored first, then one new slot is added.
        self._roll(booking, 3)
        self.assertEqual(slots[2].allocation_state, "committed")
        self.assertFalse(slots[2].hold_reason)
        self.assertFalse(slots[2].hold_revision_id)
        self.assertEqual(held.state, "committed")
        self.assertEqual(booking.display_state, "confirmed")
        self.assertEqual((booking.slot_confirmed_count, booking.slot_held_count), (3, 0))
        live = self.env[SLOT].search([("booking_id", "=", booking.id)])
        self.assertEqual(sorted(live.mapped("slot_key")), ["40HC-2", "40HC-3", "40HC-4"])

    def test_confirmed_count_follows_the_accepted_revision_not_held_slots(self):
        """BRS-EXP-14-R014 (PR #479 review): held slots are not confirmed carrier capacity."""
        booking, first = self.accepted_booking(confirmed=2)
        for slot in booking.slot_ids:
            self._commit_po(slot, first)
        self._roll(booking, 1)
        self.assertEqual((booking.slot_confirmed_count, booking.slot_held_count), (1, 1))
        cancel = self.candidate(
            booking, terms=self.terms(confirmed=1, additional_terms={"booking_status": "cancelled"})
        )
        self.assertEqual(
            self.accept(booking, cancel["record_id"], expected=booking.current_revision_id.id)["status"], "applied"
        )
        self.assertEqual(booking.slot_confirmed_count, 0)
        self.assertEqual(booking.slot_held_count, 2)

    def test_daylight_saving_ambiguity_is_refused_not_guessed(self):
        """BRS-EXP-02-R003, BRS-EXP-06-R002 (PR #479 review): a repeated or skipped local hour has no single UTC."""
        booking = self.make_booking()
        repeated = self.candidate(booking, terms=self.terms(erd_local="2026-11-01 01:30"))
        self.assertEqual(repeated["status"], "blocked")
        self.assertIn("occurs twice", repeated["reason"])
        skipped = self.candidate(booking, terms=self.terms(erd_local="2026-03-08 02:30"))
        self.assertEqual(skipped["status"], "blocked")
        self.assertIn("does not exist", skipped["reason"])
        self.assertFalse(booking.revision_ids)

    def test_form_acceptance_compares_against_the_revision_the_user_saw(self):
        """C05 review D2, V05: a stale form is refused; it never overwrites a newer accepted revision."""
        booking, first = self.accepted_booking(confirmed=1)
        seen_by_form = self.env[REVISION].browse(self.candidate(booking)["record_id"])
        seen_by_form.with_user(self.actor).write({"review_note": "Reviewed against the carrier PDF"})
        expected_when_opened = seen_by_form.booking_current_revision_id.id
        self.assertEqual(expected_when_opened, first.id)
        newer = self.candidate(booking)
        self.assertEqual(self.accept(booking, newer["record_id"], expected=first.id)["status"], "applied")
        stale_form = seen_by_form.with_user(self.actor).with_context(expected_current_revision_id=expected_when_opened)
        with self.assertRaisesRegex(UserError, "stale"), self.env.cr.savepoint():
            stale_form.action_accept_from_form()
        with self.assertRaisesRegex(UserError, "Reload"), self.env.cr.savepoint():
            seen_by_form.with_user(self.actor).action_accept_from_form()
        self.assertEqual(booking.current_revision_id.id, newer["record_id"])
        reloaded = seen_by_form.with_user(self.actor).with_context(
            expected_current_revision_id=seen_by_form.booking_current_revision_id.id
        )
        self.assertTrue(reloaded.action_accept_from_form())
        self.assertEqual(booking.current_revision_id, seen_by_form)
