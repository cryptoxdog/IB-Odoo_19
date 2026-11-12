"""Owner boundaries: Linda, Logistics, Documents and native records (RP-07-E060, RP-04-E011).

Export assembles booking context and hands it to its owners; it never sends
mail, writes physical or native commercial facts, or shadows another owner.
Linda runs in ``live`` mode only against the test mail queue: the mail is
queued as ``mail.mail`` and never sent. C05 amendments E3 and E6 are witnessed
here.
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.modules.module import get_module_path
from odoo.tests.common import tagged

from .test_booking_and_revision import BOOKING, ExportFixtureMixin

LINDA_MODE_PARAM = "plasticos_logistics.linda_mode"
REQUEST = "plasticos.logistics.request"
RESPONSE = "plasticos.logistics.response"
BOOKING_TEMPLATES = (
    "plasticos_logistics.mail_template_linda_booking_issue",
    "plasticos_logistics.mail_template_linda_booking_amend",
    "plasticos_logistics.mail_template_linda_booking_cancel",
)


@tagged("post_install", "-at_install", "plasticos", "plasticos_export")
class TestExportOwnerHandoff(ExportFixtureMixin, PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_export_fixture()

    def setUp(self):
        super().setUp()
        self.env["ir.config_parameter"].sudo().set_param(LINDA_MODE_PARAM, "live")  # sudo: test sets the Linda mode

    def _booking_with_supplier(self):
        booking, revision = self.accepted_booking(confirmed=2)
        order = self.env["purchase.order"].create(
            {
                "partner_id": self.suppliers[0].id,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_qty": 40000, "product_uom_id": self.lb.id})
                ],
            }
        )
        outcome = (
            booking.slot_ids[0]
            .with_user(self.actor)
            .action_commit_cargo({"purchase_line_id": order.order_line.id}, None, None, revision.id, self.key("commit"))
        )
        self.assertEqual(outcome["status"], "applied", outcome)
        return booking, revision

    def _notice(self, booking, user=None, purpose="booking_issue", partner=None, email=None, expected=None, key=None):
        partner = partner or self.suppliers[0]
        return booking.with_user(user or self.actor).action_request_booking_notice(
            purpose,
            partner.id,
            email or partner.email,
            expected if expected is not None else booking.current_revision_id.id,
            key or self.key("notice"),
            "supplier loads cargo on this booking",
        )

    def test_notice_goes_through_linda_with_the_exact_original(self):
        """BRS-EXP-03-R005, BRS-EXP-10-R002, BRS-EXP-13-R010: Linda is the one sender; Export never mails."""
        booking, revision = self._booking_with_supplier()
        mails_before = self.env["mail.mail"].search_count([])
        outcome = self._notice(booking)
        self.assertEqual(outcome["status"], "applied", outcome)
        request = self.env[REQUEST].browse(outcome["record_id"])
        self.assertEqual(request.source_kind, "booking")
        self.assertEqual((request.source_model, request.source_res_id), (BOOKING, booking.id))
        self.assertEqual(request.recipient_email, self.suppliers[0].email)
        self.assertIn(revision.source_revision_key, request.source_revision_key)
        snapshot = request._snapshot()
        self.assertEqual(snapshot["attachment_ids"], [revision.source_original_id.attachment_id.id])
        rendered = repr(snapshot)
        self.assertNotIn(self.buyer.email, rendered)
        self.assertIn("2026-09-28 08:00 America/New_York", rendered)
        self.assertIn("2026-10-02 (date only)", rendered)
        self.assertEqual(request.mail_id.state, "outgoing")
        self.assertEqual(self.env["mail.mail"].search_count([]), mails_before + 1)
        replay = self._notice(booking, key="notice-replay")
        self.assertEqual(replay["status"], "already_applied")

    def test_unauthorized_caller_gets_not_available(self):
        """C05 E3: role, record access and company are enforced before Linda returns applied."""
        booking, revision = self._booking_with_supplier()
        Request = self.env[REQUEST]
        # The real Export resolver is what Linda reaches for the booking source kind.
        self.assertEqual(Request._linda_source_resolvers()["booking"].__name__, "_linda_resolve_export_booking")
        self.assertEqual(Request._linda_source_models()[BOOKING], "booking")
        args = (
            booking.id,
            revision.id,
            "booking_issue",
            self.suppliers[0].id,
            self.suppliers[0].email,
            revision._original_attachment_ids(),
            revision._notice_fingerprint(),
        )
        for user in (self.outsider, self.foreign_actor):
            outcome = Request.with_user(user).request_booking_correspondence(*args, self.key("direct"))
            self.assertEqual(outcome["status"], "not_available", (user.login, outcome))
        as_superuser = Request.sudo()  # sudo: proves E3 refuses a sudo caller
        through_sudo = as_superuser.request_booking_correspondence(*args, self.key("direct"))
        self.assertEqual(through_sudo["status"], "not_available")
        allowed = Request.with_user(self.actor).request_booking_correspondence(*args, self.key("direct"))
        self.assertEqual(allowed["status"], "applied", allowed)
        refused = self._notice(booking, user=self.outsider)
        self.assertEqual(refused["status"], "not_available")

    def test_notice_audience_purpose_and_currentness(self):
        """BRS-EXP-10-R001, BRS-EXP-04-R004: exact audience, matching purpose, current revision only."""
        booking, revision = self._booking_with_supplier()
        stranger = self.env["res.partner"].create({"name": "S5B Stranger", "email": "x@s5b-stranger.example"})
        self.assertEqual(self._notice(booking, partner=stranger)["reason"], "audience_not_permitted")
        self.assertEqual(self._notice(booking, purpose="booking_amend")["status"], "blocked")
        self.assertEqual(self._notice(booking, purpose="booking_cancel")["status"], "blocked")
        self.assertEqual(self._notice(booking, expected=revision.id + 100000)["status"], "stale")
        self.assertEqual(self._notice(booking, email="someone-else@s5b.example")["status"], "blocked")
        self.assertEqual(self._notice(booking, purpose="booking_shout")["status"], "not_available")
        roll = self.candidate(booking, terms=self.terms(confirmed=2, erd_local="2026-10-07 08:00"))
        self.assertEqual(self.accept(booking, roll["record_id"], expected=revision.id)["status"], "applied")
        self.assertEqual(self._notice(booking, purpose="booking_issue")["reason"], "booking_already_issued_use_amend")
        self.assertEqual(self._notice(booking, purpose="booking_amend")["status"], "applied")

    def test_carrier_mail_sender_and_recipient_rules(self):
        """C05 E6: only the company's own address sends, fail closed; templates never add default recipients."""
        for xmlid in BOOKING_TEMPLATES:
            self.assertFalse(self.env.ref(xmlid).use_default_to, xmlid)
        self.assertFalse(
            self.env["ir.model.data"].search_count(
                [("module", "=", "plasticos_export"), ("model", "=", "mail.template")]
            )
        )
        booking, _revision = self._booking_with_supplier()
        self.company.email = "not an address"
        blocked = self._notice(booking)
        self.assertEqual(blocked, {"status": "blocked", "reason": "sender_email_missing"})
        self.company.email = False
        self.assertEqual(self._notice(booking)["reason"], "sender_email_missing")
        self.assertFalse(
            self.env[REQUEST].search_count([("source_kind", "=", "booking"), ("source_res_id", "=", booking.id)])
        )

    def test_linda_off_records_nothing(self):
        """External effects stay disabled by default (V19)."""
        booking, _revision = self._booking_with_supplier()
        self.env["ir.config_parameter"].sudo().set_param(LINDA_MODE_PARAM, "off")  # sudo: test sets the Linda mode
        self.assertEqual(self._notice(booking)["status"], "not_available")

    def test_booking_reply_is_recorded_once_and_withheld_without_its_original(self):
        """RP-04-E011, V07, BRS-EXP-09-R005: booking-only trigger; one reply, one response; no PO/SO duplicate."""
        automation = self.env.ref("plasticos_export.automation_linda_incoming_booking_reply")
        self.assertEqual(automation.trigger, "on_create")
        self.assertIn("plasticos.export.booking", automation.filter_domain)
        base = self.env.ref("plasticos_logistics.automation_linda_incoming_reply")
        self.assertIn('"purchase.order", "sale.order"', base.filter_domain)
        self.assertNotIn("plasticos.export.booking", base.filter_domain)
        booking, _revision = self._booking_with_supplier()
        self.assertEqual(self._notice(booking)["status"], "applied")
        message = self.incoming(booking, "Received, thanks")
        responses = self.env[RESPONSE].search([("mail_message_id", "=", message.id)])
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses.source_kind, "booking")
        self.assertEqual(responses.source_res_id, booking.id)
        self.assertNotEqual(responses.binding, "current")
        self.assertEqual(responses.reason, "original_not_retained")
        self.env[RESPONSE]._record_incoming(message)
        self.assertEqual(self.env[RESPONSE].search_count([("mail_message_id", "=", message.id)]), 1)

    def test_export_writes_no_field_on_another_owner_and_has_no_controller(self):
        """BRS-EXP-01-R001, V16, RP-07-E063: no shadow writer, no new partner/CRM/material field, no HTTP route."""
        # Inheriting a model (Linda resolver, load guard, Documents hooks) adds methods only:
        # no field of another owner's model may be defined by plasticos_export.
        other_owners = [
            "plasticos.load",
            "plasticos.document",
            "plasticos.logistics.request",
            "plasticos.logistics.response",
            "plasticos.iso.journey",
            "res.partner",
            "purchase.order",
            "purchase.order.line",
            "sale.order",
            "sale.order.line",
            "stock.move.line",
            "crm.lead",
            "plasticos.material.profile",
        ]
        for model in other_owners:
            if model not in self.env:
                continue
            defined_here = [
                name for name, field in self.env[model]._fields.items() if field._module == "plasticos_export"
            ]
            self.assertFalse(defined_here, model)
        defined_models = sorted(
            name for name, model in self.env.registry.items() if model._original_module == "plasticos_export"
        )
        self.assertEqual(
            defined_models,
            [
                "plasticos.export.booking",
                "plasticos.export.booking.cargo.link",
                "plasticos.export.booking.revision",
                "plasticos.export.booking.revision.accept",
                "plasticos.export.booking.slot",
                "plasticos.export.source.line.claim",
            ],
        )
        import os

        self.assertFalse(os.path.exists(os.path.join(get_module_path("plasticos_export"), "controllers")))
        self.assertIn(BOOKING, self.env["plasticos.document"]._scoped_subject_models())
        self.assertIn("booking", self.env[REQUEST]._linda_source_resolvers())
