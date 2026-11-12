"""Commit Cargo, Release Cargo and Bind Container screens (S10 OP10-E05, coordinator C11-SCOPE-2).

Each screen calls the existing frozen slot command as the acting user. The
witnesses cover success, the command's refusal shown as it states it, a double
click that applies once, and a non-Logistics user: no button, no screen, and the
command's own refusal if called directly.
BRS-EXP-14-R014, BRS-EXP-14-R016, BRS-EXP-07-R007, BRS-EXP-08-R005.
"""

from lxml import etree

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import new_test_user, tagged

from ..models.booking_allocation import slot_order
from .test_booking_and_revision import LINK, ExportFixtureMixin

COMMIT = "plasticos.export.slot.commit.cargo"
RELEASE = "plasticos.export.slot.release.cargo"
BIND = "plasticos.export.slot.bind.journey"
SCREEN_BUTTONS = ("action_open_commit_cargo", "action_open_release_cargo", "action_open_bind_journey")


@tagged("post_install", "-at_install", "plasticos", "plasticos_export")
class TestSlotCommandScreens(ExportFixtureMixin, PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_export_fixture()
        cls.sales_reader = new_test_user(
            cls.env,
            login="s10_screen_sales",
            groups="base.group_user,plasticos_security_base.group_sales_rep",
            company_id=cls.company.id,
            company_ids=[(6, 0, [cls.company.id])],
        )

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

    def _screen(self, model, slot, user=None, **values):
        user = user or self.actor
        opener = {
            COMMIT: "action_open_commit_cargo",
            RELEASE: "action_open_release_cargo",
            BIND: "action_open_bind_journey",
        }
        action = getattr(slot.with_user(user), opener[model])()
        self.assertEqual((action["res_model"], action["target"]), (model, "new"))
        return self.env[model].with_user(user).with_context(**action["context"]).create(values)

    def _journey(self, equipment="40HC"):
        outcome = (
            self.env["plasticos.iso.journey"]
            .with_user(self.actor)
            .action_register_iso_journey(
                self.company.id, self.key("iso-cycle"), equipment, False, "MSKU1234565", "SEAL-1", self.key()
            )
        )
        self.assertEqual(outcome["status"], "applied", outcome)
        return self.env["plasticos.iso.journey"].browse(outcome["record_id"])

    def test_commit_screen_commits_once_and_stores_nothing(self):
        """BRS-EXP-14-R014, BRS-EXP-08-R005: the screen commits planned cargo through the command; a double click is one."""
        booking, revision = self.accepted_booking(confirmed=1)
        slot = booking.slot_ids
        line = self._po_line()
        screen = self._screen(
            COMMIT,
            slot,
            purchase_line_id=line.id,
            planned_quantity_known=True,
            planned_quantity=40000,
            uom_id=self.lb.id,
        )
        self.assertEqual(screen.expected_booking_revision_id, revision)
        self.assertEqual(screen.action_confirm(), {"type": "ir.actions.act_window_close"})
        self.assertEqual(screen.action_confirm(), {"type": "ir.actions.act_window_close"})
        links = self.env[LINK].search([("slot_id", "=", slot.id)])
        self.assertEqual(len(links), 1, "a double click commits once")
        self.assertEqual((links.purchase_line_id, links.planned_quantity, links.uom_id), (line, 40000.0, self.lb))
        self.assertEqual(links.allocation_key, screen.operation_key)
        self.assertEqual(slot.allocation_state, "committed")

    def test_commit_screen_shows_the_command_refusal(self):
        """BRS-EXP-14-R016: no source, a stale revision or a unitless quantity is refused as the command states it."""
        booking, _revision = self.accepted_booking(confirmed=1)
        slot = booking.slot_ids
        empty = self._screen(COMMIT, slot)
        with self.assertRaisesRegex(UserError, "blocked.*at least one exact source record"):
            empty.action_confirm()
        # The screen defaults the unit to lb (C13 OP12-E02c); a user who clears it is still refused by the command.
        unitless = self._screen(
            COMMIT,
            slot,
            purchase_line_id=self._po_line().id,
            planned_quantity_known=True,
            planned_quantity=5,
            uom_id=False,
        )
        with self.assertRaisesRegex(UserError, "needs its unit"):
            unitless.action_confirm()
        stale = self._screen(COMMIT, slot, purchase_line_id=self._po_line().id)
        roll = self.candidate(booking, terms=self.terms(confirmed=1, erd_local="2026-10-09 08:00"))
        self.assertEqual(
            self.accept(booking, roll["record_id"], expected=booking.current_revision_id.id)["status"], "applied"
        )
        with self.assertRaisesRegex(UserError, "stale"):
            stale.action_confirm()
        self.assertFalse(self.env[LINK].search_count([("slot_id", "=", slot.id)]))

    def test_release_screen_releases_once_with_a_reason(self):
        """BRS-EXP-14-R016: release needs a reason; a double click releases once and the link stays as history."""
        booking, revision = self.accepted_booking(confirmed=1)
        slot = booking.slot_ids
        committed = slot.with_user(self.actor).action_commit_cargo(
            {"purchase_line_id": self._po_line().id}, None, None, revision.id, self.key()
        )
        link = self.env[LINK].browse(committed["record_id"])
        blank = self._screen(RELEASE, slot, cargo_link_id=link.id, reason=" ")
        with self.assertRaisesRegex(UserError, "reason is required"):
            blank.action_confirm()
        screen = self._screen(RELEASE, slot, cargo_link_id=link.id, reason="Supplier not ready")
        screen.action_confirm()
        screen.action_confirm()
        self.assertEqual(link.state, "released")
        self.assertEqual(slot.allocation_state, "available")
        notes = booking.message_ids.filtered(lambda message: "Supplier not ready" in (message.body or ""))
        self.assertEqual(len(notes), 1, "released once")

    def test_bind_screen_binds_once_and_refuses_a_mismatch(self):
        """BRS-EXP-07-R007: a matching container binds once; a different equipment class is refused, never rewritten."""
        booking, _revision = self.accepted_booking(confirmed=2)
        first, second = booking.slot_ids.sorted(slot_order)
        mismatch = self._screen(BIND, first, journey_id=self._journey("40STD").id, source_basis="Terminal ticket")
        with self.assertRaisesRegex(UserError, "equipment mismatch"):
            mismatch.action_confirm()
        journey = self._journey("40HC")
        screen = self._screen(BIND, first, journey_id=journey.id, source_basis="Terminal ticket")
        screen.action_confirm()
        screen.action_confirm()
        self.assertEqual((first.journey_id, first.journey_binding_state), (journey, "active"))
        taken = self._screen(BIND, second, journey_id=journey.id, source_basis="Terminal ticket")
        with self.assertRaisesRegex(UserError, "bound to another slot"):
            taken.action_confirm()

    def test_non_logistics_user_has_no_button_no_screen_and_the_command_refuses(self):
        """C11-SCOPE-2: a Sales Rep sees no command button, cannot open a screen, and the command refuses them."""
        form = self.env.ref("plasticos_export.view_export_slot_form")
        buttons = {
            node.get("name"): node.get("groups")
            for node in etree.fromstring(form.arch).iter("button")
            if node.get("name") in SCREEN_BUTTONS
        }
        self.assertEqual(set(buttons), set(SCREEN_BUTTONS))
        self.assertEqual(set(buttons.values()), {"plasticos_security_base.group_logistics"})
        booking, revision = self.accepted_booking(confirmed=1)
        slot = booking.slot_ids
        arch = slot.with_user(self.sales_reader).get_views([(form.id, "form")])["views"]["form"]["arch"]
        for name in SCREEN_BUTTONS:
            self.assertNotIn(name, arch)
        for model in (COMMIT, RELEASE, BIND):
            with self.assertRaises(AccessError):
                self.env[model].with_user(self.sales_reader).create({"slot_id": slot.id})
        refused = slot.with_user(self.sales_reader).action_commit_cargo(
            {"purchase_line_id": self._po_line().id}, None, None, revision.id, self.key()
        )
        self.assertEqual(refused["status"], "not_available")
        self.assertFalse(self.env[LINK].search_count([("slot_id", "=", slot.id)]))
        # Review N3: release and bind called directly by a Sales Rep are refused by the commands too.
        committed = slot.with_user(self.actor).action_commit_cargo(
            {"purchase_line_id": self._po_line().id}, None, None, revision.id, self.key()
        )
        self.assertEqual(committed["status"], "applied", committed)
        release = slot.with_user(self.sales_reader).action_release_cargo(
            committed["record_id"], revision.id, self.key(), "rep tries to release"
        )
        self.assertEqual(release["status"], "not_available")
        bind = slot.with_user(self.sales_reader).action_bind_journey(
            self._journey().id, revision.id, self.key(), "rep tries to bind"
        )
        self.assertEqual(bind["status"], "not_available")
        self.assertEqual(self.env[LINK].browse(committed["record_id"]).state, "committed")
        self.assertFalse(slot.journey_id)

    def test_commit_screens_cannot_double_allocate_one_load(self):
        """BRS-EXP-08-R006 at the screen (review N4): two Commit Cargo screens name one load; the second is refused."""
        booking, _revision = self.accepted_booking(confirmed=2)
        first_slot, second_slot = booking.slot_ids.sorted(slot_order)
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        load = self.env["plasticos.load"].create({"sale_order_id": order.id})
        values = {"source_load_id": load.id, "physical_source_kind": "logistics_load"}
        first = self._screen(COMMIT, first_slot, purchase_line_id=self._po_line().id, **values)
        second = self._screen(COMMIT, second_slot, purchase_line_id=self._po_line().id, **values)
        first.action_confirm()
        with self.assertRaisesRegex(UserError, "already committed on another live cargo link"):
            second.action_confirm()
        live = self.env[LINK].search([("source_load_id", "=", load.id), ("state", "in", ("committed", "held"))])
        self.assertEqual(live.slot_id, first_slot)
