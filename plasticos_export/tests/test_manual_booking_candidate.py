"""Manual 'Record booking candidate' screen (S10 OP10-E03, BRS-EXP-09-R001 manual fallback).

The screen hands typed source terms to the frozen
``record_booking_revision_candidate`` command, as the acting user, with every
guard of the command. It keeps the original with native Documents, never makes
a revision current and stores no second file. The native Documents AI path is
not activated; its witness stays NOT_RUN pending the operator.
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import tagged

from ..wizard.manual_booking_candidate import MANUAL_CANDIDATE
from .test_booking_and_revision import REVISION, ExportFixtureMixin


@tagged("post_install", "-at_install", "plasticos", "plasticos_export")
class TestManualBookingCandidate(ExportFixtureMixin, PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_export_fixture()

    def _screen(self, booking, user=None, **values):
        user = user or self.actor
        action = booking.with_user(user).action_open_manual_candidate()
        self.assertEqual((action["res_model"], action["target"]), (MANUAL_CANDIDATE, "new"))
        Wizard = self.env[MANUAL_CANDIDATE].with_user(user).with_context(**action["context"])
        return Wizard.create(values)

    def test_09_r001_manual_entry_records_a_candidate_with_its_original(self):
        """BRS-EXP-09-R001 manual fallback positive: typed terms become an editable candidate; the original stays."""
        booking = self.make_booking()
        original = self.original(booking, name="carrier-booking.pdf")
        screen = self._screen(
            booking,
            source_original_id=original.id,
            source_revision_key="SYN-BKG-0001/2030-01-02",
            carrier_booking_no="0065090248",
            pol_text="Port Alpha",
            erd_local="2030-01-05",
            erd_precision="date",
            cargo_cutoff_local="2030-01-09 16:00",
            cargo_cutoff_tz="America/Los_Angeles",
            cargo_cutoff_precision="datetime",
            booking_status="confirmed",
            vessel="Synthetic Vessel",
            line_ids=[(0, 0, {"equipment_class": "40HC", "confirmed_stated": True, "confirmed_count": 1})],
        )
        action = screen.action_record()
        revision = self.env[REVISION].browse(action["res_id"])
        self.assertEqual(revision.booking_id, booking)
        self.assertEqual(revision.decision, "candidate")
        self.assertEqual(revision.source_original_id, original)
        self.assertTrue(revision.source_original_id.attachment_id)
        self.assertEqual(revision.carrier_booking_no, "0065090248", "leading zeros are kept")
        self.assertEqual((revision.erd_local, revision.erd_precision, revision.erd_utc), ("2030-01-05", "date", False))
        self.assertTrue(revision.cargo_cutoff_utc)
        self.assertFalse(revision.pod_text, "an unstated port of discharge stays unknown")
        self.assertEqual(revision.equipment_counts, {"40HC": {"requested": None, "confirmed": 1}})
        self.assertEqual(revision.additional_terms, {"booking_status": "confirmed", "vessel": "Synthetic Vessel"})
        self.assertFalse(booking.current_revision_id, "a candidate changes nothing current")
        self.assertFalse(booking.slot_ids)
        again = screen.action_record()
        self.assertEqual(again["res_id"], revision.id, "pressing Record twice records the candidate once")
        self.assertEqual(self.env[REVISION].search_count([("booking_id", "=", booking.id)]), 1)

    def test_09_r001_manual_entry_keeps_every_command_guard(self):
        """BRS-EXP-09-R001 negative: no second file store, no source-less entry, no other booking's original."""
        Wizard = self.env[MANUAL_CANDIDATE]
        self.assertFalse(
            [name for name, field in Wizard._fields.items() if field.type == "binary"],
            "the screen stores no file of its own; originals stay with native Documents",
        )
        booking = self.make_booking()
        no_source = self._screen(booking, source_revision_key="r-1")
        with self.assertRaisesRegex(UserError, "blocked.*source original or source message"):
            no_source.action_record()
        other = self.make_booking()
        foreign = self._screen(booking, source_revision_key="r-2", source_original_id=self.original(other).id)
        with self.assertRaisesRegex(UserError, "belongs to another record"):
            foreign.action_record()
        twice = self._screen(
            booking,
            source_revision_key="r-3",
            source_original_id=self.original(booking).id,
            line_ids=[(0, 0, {"equipment_class": "40HC"}), (0, 0, {"equipment_class": "40HC"})],
        )
        with self.assertRaisesRegex(UserError, "listed twice"):
            twice.action_record()
        self.assertFalse(self.env[REVISION].search_count([("booking_id", "=", booking.id)]))
        with self.assertRaises(AccessError):
            self.env[MANUAL_CANDIDATE].with_user(self.outsider).create(
                {"booking_id": booking.id, "source_revision_key": "r-4"}
            )

    def test_09_r001_foreign_company_actor_is_refused_by_the_command(self):
        """BRS-EXP-09-R001 negative: the screen runs the command as the acting user, never through sudo."""
        booking = self.make_booking()
        original = self.original(booking)
        screen = (
            self.env[MANUAL_CANDIDATE]
            .with_user(self.foreign_actor)
            .create({"booking_id": booking.id, "source_revision_key": "r-5", "source_original_id": original.id})
        )
        with self.assertRaisesRegex(UserError, "not_available"):
            screen.action_record()
        self.assertFalse(self.env[REVISION].search_count([("booking_id", "=", booking.id)]))
