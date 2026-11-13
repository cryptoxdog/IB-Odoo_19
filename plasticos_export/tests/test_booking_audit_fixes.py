"""Regression witnesses of the Export audit fixes (module version 19.0.1.3.1).

One test group per defect, each written to fail on the code before its fix:

1. stale booking-confirmation evidence on the booking subject withholds the
   loads on that booking (C05-SCOPE-1, BRS-EXP-03-R002, BRS-EXP-03-R007);
2. a revision that does not state a confirmed equipment count is not read as
   zero capacity (POS-INV-03, BRS-EXP-14-R016);
3. a held slot whose cargo was all released is retired, not left held;
4. a retry of a commit that already succeeded is ``already_applied`` after the
   booking moved to a newer revision (V05);
5. rejecting a revision leaves a chatter note and a rejected revision cannot be
   accepted (BRS-EXP-11-R005).

Synthetic data only. No outbound mail.
"""

import base64
import itertools
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import new_test_user, tagged

from ..models.booking_allocation import slot_order
from ..models.document_inherit import BOOKING_CONFIRMATION, EXPORT_RELEASE_OBLIGATIONS
from .test_booking_and_revision import BOOKING, LINK, REVISION, SLOT, ExportFixtureMixin, row_versions

_BYTES = itertools.count(1)
RELEASE_KINDS = ("schedule", "dispatch", "dispatch_packet", "carrier_document")


@tagged("post_install", "-at_install", "plasticos", "plasticos_export")
class TestBookingAuditFixes(ExportFixtureMixin, PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_export_fixture()
        cls.verifier = new_test_user(
            cls.env,
            login="s5b_audit_fix_verifier",
            groups="base.group_user,plasticos_documents.group_documents_user,purchase.group_purchase_user",
        )
        cls.tag = cls.env["plasticos.document.tag"].search([("code", "=", "BOL")], limit=1)
        if not cls.tag:
            raise AssertionError("BLOCKED: BOL document tag is not installed")

    # ── helpers ──────────────────────────────────────────────

    def _po_line(self, qty=40000):
        order = self.env["purchase.order"].create(
            {
                "partner_id": self.suppliers[0].id,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_qty": qty, "product_uom_id": self.lb.id})
                ],
            }
        )
        return order.order_line

    def _commit(self, slot, refs, quantity=None, uom=None, key=None, expected=None):
        expected = expected if expected is not None else slot.booking_id.current_revision_id.id
        return slot.with_user(self.actor).action_commit_cargo(
            refs, quantity, uom.id if uom else None, expected, key or self.key("commit")
        )

    def _commit_po(self, slot):
        outcome = self._commit(slot, {"purchase_line_id": self._po_line().id})
        self.assertEqual(outcome["status"], "applied", outcome)
        return self.env[LINK].browse(outcome["record_id"])

    def _load(self):
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        return self.env["plasticos.load"].create({"sale_order_id": order.id})

    def _commit_load(self, slot, load):
        outcome = self._commit(
            slot, {"source_load_id": load.id, "physical_source_kind": "logistics_load"}, 40000, self.lb
        )
        self.assertEqual(outcome["status"], "applied", outcome)
        return self.env[LINK].browse(outcome["record_id"])

    def _roll(self, booking, terms):
        recorded = self.candidate(booking, terms=terms)
        self.assertEqual(recorded["status"], "applied", recorded)
        outcome = self.accept(booking, recorded["record_id"], expected=booking.current_revision_id.id)
        self.assertEqual(outcome["status"], "applied", outcome)
        return self.env[REVISION].browse(recorded["record_id"])

    def _all_slots(self, booking):
        return self.env[SLOT].with_context(active_test=False).search([("booking_id", "=", booking.id)])

    def _confirmation_evidence(self, booking, verify=True):
        """Accepted booking-confirmation evidence on the booking subject that expires tomorrow."""
        attachment = self.env["ir.attachment"].create(
            {
                "name": "booking-confirmation-evidence.pdf",
                "datas": base64.b64encode(f"confirmation evidence {next(_BYTES)}".encode()),
                "res_model": "plasticos.document",
                "res_id": 0,
            }
        )
        shell = self.env["plasticos.document"].create(
            {
                "name": "Booking confirmation",
                "tag_id": self.tag.id,
                "res_model": "documents.document",
                "res_id": 0,
                "attachment_id": attachment.id,
            }
        )
        row = shell.with_user(self.verifier)._associate_scope(
            BOOKING,
            booking.id,
            "synthetic carrier confirmation",
            obligation_kind=BOOKING_CONFIRMATION,
            operation_revision_key="SYN-BKG/r1",
            coverage_key="whole",
        )
        self.assertEqual((row.res_model, row.res_id), (BOOKING, booking.id))
        self.assertFalse(row.load_id, "evidence on a booking subject carries no load")
        row.write({"expiry_date": fields.Date.today() + timedelta(days=1)})
        if verify:
            row.with_user(self.verifier).action_verify()
        return row

    def _release_outcomes(self, load, later=False):
        Load = self.env["plasticos.load"]
        if not later:
            return {kind: Load.assert_can_release_physical_operation(load.id, kind) for kind in RELEASE_KINDS}
        after_expiry = fields.Date.today() + timedelta(days=5)
        with patch.object(type(self.env["plasticos.document"]), "_evidence_today", return_value=after_expiry):
            return {kind: Load.assert_can_release_physical_operation(load.id, kind) for kind in RELEASE_KINDS}

    # ── fix 1: stale booking confirmation withholds the booking's loads ──

    def test_stale_confirmation_on_the_booking_withholds_its_loads(self):
        """C05-SCOPE-1: decided, no longer current confirmation evidence on the booking gates all four operations."""
        self.assertEqual(
            {kind for kind, needed in EXPORT_RELEASE_OBLIGATIONS.items() if BOOKING_CONFIRMATION in needed},
            set(RELEASE_KINDS),
        )
        booking, _revision = self.accepted_booking(confirmed=2)
        booked_load, unbooked_load = self._load(), self._load()
        self._commit_load(booking.slot_ids.sorted(slot_order)[0], booked_load)
        self._confirmation_evidence(booking)
        # Current evidence withholds nothing.
        current = self._release_outcomes(booked_load)
        self.assertEqual({outcome["status"] for outcome in current.values()}, {"applied"}, current)
        # The same evidence, expired: every operation mapped to booking_confirmation is refused.
        stale = self._release_outcomes(booked_load, later=True)
        self.assertEqual({outcome["status"] for outcome in stale.values()}, {"blocked"}, stale)
        for kind, outcome in stale.items():
            self.assertIn(BOOKING_CONFIRMATION, outcome["reason"], kind)
            self.assertIn("no longer current", outcome["reason"], kind)
        # A load with no Export link is unaffected by that booking's evidence.
        untouched = self._release_outcomes(unbooked_load, later=True)
        self.assertEqual({outcome["status"] for outcome in untouched.values()}, {"applied"}, untouched)

    def test_released_cargo_is_no_longer_withheld_by_the_booking(self):
        """Only live links of the exact load count: released cargo follows no booking evidence."""
        booking, revision = self.accepted_booking(confirmed=1)
        load = self._load()
        link = self._commit_load(booking.slot_ids, load)
        self._confirmation_evidence(booking)
        released = booking.slot_ids.with_user(self.actor).action_release_cargo(
            link.id, revision.id, self.key(), "Synthetic release"
        )
        self.assertEqual(released["status"], "applied", released)
        outcomes = self._release_outcomes(load, later=True)
        self.assertEqual({outcome["status"] for outcome in outcomes.values()}, {"applied"}, outcomes)

    def test_undecided_or_absent_confirmation_withholds_nothing(self):
        """The existing rule stays exact: stale withholds; never decided or never existed does not."""
        absent_booking, _revision = self.accepted_booking(confirmed=1)
        absent_load = self._load()
        self._commit_load(absent_booking.slot_ids, absent_load)
        outcomes = self._release_outcomes(absent_load, later=True)
        self.assertEqual({outcome["status"] for outcome in outcomes.values()}, {"applied"}, outcomes)
        undecided_booking, _revision = self.accepted_booking(confirmed=1)
        undecided_load = self._load()
        self._commit_load(undecided_booking.slot_ids, undecided_load)
        self._confirmation_evidence(undecided_booking, verify=False)
        outcomes = self._release_outcomes(undecided_load, later=True)
        self.assertEqual({outcome["status"] for outcome in outcomes.values()}, {"applied"}, outcomes)

    # ── fix 2: a count that is not stated is not zero ────────

    def test_revision_without_equipment_counts_changes_no_slot(self):
        """POS-INV-03: a cutoff-only revision withdraws no capacity and writes no slot."""
        booking, _first = self.accepted_booking(confirmed=3)
        slots = booking.slot_ids.sorted(slot_order)
        link = self._commit_po(slots[2])
        before = row_versions(slots)
        cutoff_only = self.terms(cargo_cutoff_local="2026-10-05")
        cutoff_only.pop("equipment_counts")
        revision = self._roll(booking, cutoff_only)
        self.assertFalse(revision.equipment_counts)
        self.assertEqual(row_versions(slots), before)
        self.assertEqual(self._all_slots(booking), slots)
        self.assertEqual(slots.mapped("active"), [True, True, True])
        self.assertEqual(slots.mapped("allocation_state"), ["available", "available", "committed"])
        self.assertFalse(any(slots.mapped("hold_reason")))
        self.assertEqual(link.state, "committed")
        self.assertEqual(booking.display_state, "confirmed")
        # The retained slots are still confirmed capacity on the booking and its summary.
        self.assertEqual(booking.slot_confirmed_count, 3)

    def test_unstated_confirmed_count_changes_no_slot(self):
        """A class named with a requested count only: confirmed is not stated, so its slots stay."""
        booking, _first = self.accepted_booking(confirmed=2)
        slots = booking.slot_ids.sorted(slot_order)
        before = row_versions(slots)
        requested_only = self.terms(equipment_counts={"40HC": {"requested": 4, "confirmed": None}})
        revision = self._roll(booking, requested_only)
        self.assertEqual(revision.equipment_counts, {"40HC": {"requested": 4, "confirmed": None}})
        self.assertEqual(row_versions(slots), before)
        self.assertEqual(self._all_slots(booking).filtered("active"), slots)
        # A revision that states another class only leaves the unmentioned class alone and adds the stated one.
        other_class = self._roll(booking, self.terms(confirmed=1, code="20STD"))
        self.assertEqual(row_versions(slots), before)
        live = self.env[SLOT].search([("booking_id", "=", booking.id)])
        self.assertEqual(sorted(live.mapped("slot_key")), ["20STD-1", "40HC-1", "40HC-2"])
        # One stated 20STD slot plus the two retained 40HC slots the revision did not mention.
        self.assertEqual(booking.slot_confirmed_count, 3)
        self.assertEqual((live - slots).created_from_revision_id, other_class)

    def test_stated_zero_and_cancellation_still_withdraw(self):
        """A stated 0 is a number and withdraws; a stated cancellation withdraws every class, counts or not."""
        booking, _first = self.accepted_booking(confirmed=2)
        slots = booking.slot_ids.sorted(slot_order)
        link = self._commit_po(slots[0])
        self._roll(booking, self.terms(confirmed=0))
        self.assertFalse(slots[1].active, "the free slot is retired by a stated zero")
        self.assertTrue(slots[0].active)
        self.assertEqual(slots[0].allocation_state, "held")
        self.assertEqual(link.state, "held")
        cancelled_booking, _first = self.accepted_booking(confirmed=2)
        cancelled_slots = cancelled_booking.slot_ids
        cancel = self.terms(additional_terms={"booking_status": "cancelled"})
        cancel.pop("equipment_counts")
        self._roll(cancelled_booking, cancel)
        self.assertEqual(cancelled_booking.display_state, "cancelled")
        self.assertEqual(cancelled_slots.mapped("active"), [False, False])
        self.assertFalse(cancelled_booking.slot_ids)

    # ── fix 3: an emptied hold is retired ────────────────────

    def test_held_slot_is_retired_once_its_cargo_is_released(self):
        """BRS-EXP-14-R016: a hold exists for cargo to decide; with none left the slot is free excess capacity."""
        booking, _first = self.accepted_booking(confirmed=2)
        kept_slot, held_slot = booking.slot_ids.sorted(slot_order)
        kept = self._commit_po(kept_slot)
        first_held = self._commit_po(held_slot)
        second_held = self._commit_po(held_slot)
        down = self._roll(booking, self.terms(confirmed=1))
        self.assertEqual((kept_slot.allocation_state, held_slot.allocation_state), ("committed", "held"))
        self.assertEqual(booking.display_state, "held")
        release = held_slot.with_user(self.actor).action_release_cargo
        # One of two held links released: cargo remains, so the hold stays for the owner decision.
        self.assertEqual(release(first_held.id, down.id, self.key(), "Synthetic release 1")["status"], "applied")
        self.assertTrue(held_slot.active)
        self.assertEqual(held_slot.allocation_state, "held")
        self.assertEqual(second_held.state, "held")
        # The last held link released: nothing is left to decide, the slot is retired.
        self.assertEqual(release(second_held.id, down.id, self.key(), "Synthetic release 2")["status"], "applied")
        self.assertFalse(held_slot.active)
        self.assertEqual(held_slot.allocation_state, "historical")
        self.assertTrue(held_slot.hold_reason, "the hold reason stays on the retired slot as history")
        self.assertEqual(held_slot.hold_revision_id, down)
        self.assertEqual((first_held.state, second_held.state), ("released", "released"))
        self.assertEqual(booking.display_state, "confirmed")
        self.assertEqual((booking.slot_held_count, booking.slot_committed_count), (0, 1))
        self.assertEqual(self.env[SLOT].search([("booking_id", "=", booking.id)]), kept_slot)
        self.assertEqual(kept.state, "committed")

    # ── fix 4: a replay is recognised before the currentness check ──

    def test_commit_replay_after_a_newer_revision_is_already_applied(self):
        """V05: the same key and payload answer already_applied even after the booking rolled."""
        booking, first = self.accepted_booking(confirmed=2)
        slot = booking.slot_ids.sorted(slot_order)[0]
        line = self._po_line()
        args = ({"purchase_line_id": line.id}, 1000.0, self.lb)
        applied = self._commit(slot, *args, key="audit-replay-1", expected=first.id)
        self.assertEqual(applied["status"], "applied", applied)
        self._roll(booking, self.terms(confirmed=2, erd_local="2026-10-09 08:00"))
        replay = self._commit(slot, *args, key="audit-replay-1", expected=first.id)
        self.assertEqual(replay, {"status": "already_applied", "record_id": applied["record_id"]})
        # Every other case answers as before: a changed payload or a new key on the old revision is stale.
        changed = self._commit(
            slot, {"purchase_line_id": line.id}, 2000.0, self.lb, key="audit-replay-1", expected=first.id
        )
        self.assertEqual(changed["status"], "stale")
        self.assertEqual(changed["reason"], "booking revision changed")
        fresh = self._commit(slot, *args, key="audit-replay-2", expected=first.id)
        self.assertEqual(fresh["status"], "stale")
        self.assertEqual(self.env[LINK].search_count([("booking_id", "=", booking.id)]), 1)

    # ── fix 5: rejection is attributed and final ─────────────

    def test_reject_posts_a_note_and_the_revision_cannot_be_accepted(self):
        """BRS-EXP-11-R005: a rejected candidate stays as history, attributed, and never becomes current."""
        booking = self.make_booking()
        recorded = self.candidate(booking, revision_key="SYN-REV-REJECT")
        revision = self.env[REVISION].browse(recorded["record_id"])
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            revision.with_user(self.outsider).action_reject()
        self.assertEqual(revision.decision, "candidate")
        self.assertTrue(revision.with_user(self.actor).action_reject())
        self.assertEqual(revision.decision, "rejected")
        note = booking.message_ids[:1].body
        self.assertIn("SYN-REV-REJECT", note)
        self.assertIn("rejected", note)
        self.assertIn(self.actor.name, note)
        refused = self.accept(booking, revision.id)
        self.assertEqual(refused["status"], "blocked")
        self.assertEqual(refused["reason"], "a rejected revision cannot be accepted")
        self.assertEqual(revision.decision, "rejected")
        self.assertFalse(booking.current_revision_id)
        self.assertFalse(self._all_slots(booking))
        with self.assertRaises(UserError), self.env.cr.savepoint():
            revision.with_user(self.actor).action_reject()
