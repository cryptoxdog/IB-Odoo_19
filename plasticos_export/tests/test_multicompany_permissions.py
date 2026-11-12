"""Company access and source-linked attachment access (RP-07-E062, RP-07-E047, RP-07-E048).

Another company's user cannot see, count, print or command a booking, its
revisions, slots or cargo links, nor read its source original. A read-only role
reads but never writes. Accepted revisions resist every unscoped write.
BRS-EXP-14-R012. No outbound mail.
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import new_test_user, tagged

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

    def test_sales_rep_reads_only_cargo_on_their_own_sale_orders(self):
        """BRS-EXP-14-R012 (PR #479 review): supplier-side cargo data stays with the parties entitled to it."""
        booking, revision = self._populated_booking()
        own_order = self.env["sale.order"].create({"partner_id": self.buyer.id, "user_id": self.sales_reader.id})
        own_order.order_line = [(0, 0, {"product_id": self.product.id, "product_uom_qty": 1})]
        other_order = self.env["sale.order"].create({"partner_id": self.buyer.id, "user_id": self.actor.id})
        other_order.order_line = [(0, 0, {"product_id": self.product.id, "product_uom_qty": 1})]
        slot = booking.slot_ids.sorted("slot_key")[1]
        own = slot.with_user(self.actor).action_commit_cargo(
            {"sale_line_id": own_order.order_line.id}, None, None, revision.id, self.key()
        )
        other = slot.with_user(self.actor).action_commit_cargo(
            {"sale_line_id": other_order.order_line.id}, None, None, revision.id, self.key()
        )
        Link = self.env[LINK].with_user(self.sales_reader)
        visible = Link.search([("booking_id", "=", booking.id)])
        self.assertEqual(visible.ids, [own["record_id"]])
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            Link.browse(other["record_id"]).read(["supplier_id"])
        everything = self.env[LINK].with_user(self.actor).search([("booking_id", "=", booking.id)])
        self.assertEqual(len(everything), 3)
