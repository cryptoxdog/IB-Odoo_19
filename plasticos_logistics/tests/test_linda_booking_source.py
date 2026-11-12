"""Linda typed booking source: one sender, final claim and reply attribution (S4, RP-04-E008).

V06 (final send claim, unknown outcome) and V07 (booking reply attribution) at the
Logistics level. The upstream addon never imports ``plasticos_export``: a booking
source exists here only through a resolver this test registers on purpose, and the
first test proves the command is ``not_available`` without it. A partner record
stands in for the downstream booking thread. BRS-EXP-03-R005, BRS-EXP-10-R002/R004.
Delivery goes to a controlled sink; nothing leaves the test database.
"""

import email.utils
import itertools
import smtplib
from contextlib import contextmanager
from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.addons.plasticos_logistics.models.linda_request import PlasticosLogisticsRequest
from odoo.tests.common import tagged

LOGISTICS_REQUEST = "plasticos.logistics.request"
LOGISTICS_RESPONSE = "plasticos.logistics.response"
LINDA_MODE_PARAM = "plasticos_logistics.linda_mode"
SUPPLIER_EMAIL = "bookings@s4-mill.example"
BUYER_EMAIL = "buy@s4-secret-buyer.example"
STAND_IN_MODEL = "res.partner"
MAIL_LOGGER = "odoo.addons.mail.models.mail_mail"
_message_ids = itertools.count(1)


@tagged("post_install", "-at_install", "plasticos", "logistics", "linda")
class TestLindaBookingSource(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Request = cls.env[LOGISTICS_REQUEST]
        cls.Response = cls.env[LOGISTICS_RESPONSE]
        cls.company = cls.env.company
        cls.supplier = cls.env["res.partner"].create(
            {"name": "S4 Booking Mill", "is_company": True, "supplier_rank": 1, "email": SUPPLIER_EMAIL}
        )
        cls.buyer = cls.env["res.partner"].create(
            {"name": "S4 Secret Buyer", "is_company": True, "customer_rank": 1, "email": BUYER_EMAIL}
        )
        cls.booking = cls.env["res.partner"].create({"name": "BKG 6509024800", "company_id": cls.company.id})

    def setUp(self):
        super().setUp()
        # Accepted booking revision as the downstream owner would report it.
        self.source = {"revision_id": 1, "erd": "2026-09-30", "attachments": []}
        self.env["ir.config_parameter"].sudo().set_param(LINDA_MODE_PARAM, "live")

    # ── helpers ──────────────────────────────────────────────

    def _resolver(self, purpose, res_id, audience_partner, **params):
        booking = self.env[STAND_IN_MODEL].browse(res_id).exists()
        if not booking:
            return {"status": "not_available", "reason": "booking_not_found"}
        if audience_partner != self.supplier:
            return {"status": "blocked", "reason": "audience_not_permitted"}
        revision = self.source["revision_id"]
        accepted = params.get("accepted_revision_id")
        if accepted and accepted != revision:
            return {"status": "stale", "reason": "revision_not_current"}
        return {
            "status": "applied",
            "company": self.company,
            "partner": audience_partner,
            "recipient_email": audience_partner.email,
            "model": STAND_IN_MODEL,
            "res_id": booking.id,
            "revision_key": f"rev:{revision}",
            "snapshot": {
                "reference": booking.name,
                "subject": f"Booking {booking.name} revision {revision}",
                "paragraphs": ["Please find the current booking for your loading."],
                "lines": [["Booking", booking.name], ["ERD", self.source["erd"]]],
            },
            "attachment_ids": list(self.source["attachments"]),
            "source_fingerprint": f"fp:{revision}:{self.source['erd']}",
        }

    @contextmanager
    def _booking_registered(self):
        def resolvers(model):
            return {"load": model._linda_resolve_load_source, "booking": self._resolver}

        def source_models(model):
            return {"plasticos.load": "load", STAND_IN_MODEL: "booking"}

        with (
            patch.object(PlasticosLogisticsRequest, "_linda_source_resolvers", resolvers),
            patch.object(PlasticosLogisticsRequest, "_linda_source_models", source_models),
        ):
            yield

    def _request(self, purpose="booking_issue", operation_key="op-1", **overrides):
        args = {
            "booking_id": self.booking.id,
            "accepted_revision_id": self.source["revision_id"],
            "purpose": purpose,
            "audience_partner_id": self.supplier.id,
            "recipient_email": SUPPLIER_EMAIL,
            "attachment_original_ids": list(self.source["attachments"]),
            "source_payload_fingerprint": f"fp:{self.source['revision_id']}:{self.source['erd']}",
            "operation_key": operation_key,
        }
        args.update(overrides)
        return self.Request.request_booking_correspondence(**args)

    def _bookings(self):
        return self.Request.search(
            [("source_kind", "=", "booking"), ("source_res_id", "=", self.booking.id)], order="id"
        )

    @contextmanager
    def _mail_sink(self, error=None):
        sent = []

        def send_email(server, message, *args, **kwargs):
            if error:
                raise error
            sent.append(message)
            return message["Message-Id"]

        server_class = type(self.env["ir.mail_server"])
        with (
            patch.object(server_class, "_disable_send", lambda *args: False),
            patch.object(server_class, "_connect__", lambda *args, **kwargs: None),
            patch.object(server_class, "send_email", send_email),
        ):
            yield sent

    def _process(self, requests):
        self.env["mail.mail"].process_email_queue(email_ids=requests.mail_id.ids)
        requests.invalidate_recordset()

    # ── availability ─────────────────────────────────────────

    def test_without_the_export_resolver_booking_mail_is_not_available(self):
        result = self._request()
        self.assertEqual(result["status"], "not_available")
        self.assertFalse(self._bookings())
        self.assertNotIn("booking", self.Request._linda_source_resolvers())

    # ── one sender, typed branch, idempotent ─────────────────

    def test_booking_issue_is_recorded_on_the_typed_branch_and_sent_once(self):
        with self._booking_registered():
            result = self._request()
            self.assertEqual(result["status"], "applied")
            request = self.Request.browse(result["record_id"])
            self.assertEqual((request.source_kind, request.source_model), ("booking", STAND_IN_MODEL))
            self.assertFalse(request.purchase_order_id or request.sale_order_id, "no fabricated order")
            self.assertEqual(request.template_xmlid, "plasticos_logistics.mail_template_linda_booking_issue")
            self.assertEqual(request.mail_id.model, STAND_IN_MODEL, "replies thread on the source record")
            self.assertEqual(request.mail_id.email_to, SUPPLIER_EMAIL)
            body = request.mail_id.body_html or ""
            self.assertIn(self.booking.name, body)
            self.assertIn("2026-09-30", body)
            self.assertNotIn("{{", body)
            self.assertNotIn(BUYER_EMAIL, body)
            with self._mail_sink() as sink:
                self._process(request)
            self.assertEqual((request.state, len(sink)), ("sent", 1))
            # Retry of the same operation, and a repeat call with a new key, issue nothing new.
            self.assertEqual(self._request()["status"], "already_applied")
            self.assertEqual(self._request(operation_key="op-2")["status"], "already_applied")
            with self._mail_sink() as sink:
                self.env["mail.mail"].process_email_queue()
            self.assertFalse(sink)
        self.assertEqual(len(self._bookings()), 1)

    def test_typed_rows_obey_the_branch_check(self):
        with self._booking_registered():
            request = self.Request.browse(self._request()["record_id"])
        self.assertTrue(request.source_revision_key)
        with self.assertRaises(Exception), self.env.cr.savepoint():  # noqa: B017 - the DB CHECK raises
            self.Request.sudo().create(
                {
                    "company_id": self.company.id,
                    "purpose": "booking_issue",
                    "partner_id": self.supplier.id,
                    "revision": 9,
                    "payload_fingerprint": "x",
                    "source_kind": "booking",
                    "source_model": STAND_IN_MODEL,
                    "source_res_id": self.booking.id,
                }
            )

    # ── five negatives: duplicate, stale, unauthenticated, uncertain SMTP, wrong audience ──

    def test_stale_payload_or_revision_is_refused(self):
        with self._booking_registered():
            stale = self._request(source_payload_fingerprint="fp:old")
            self.assertEqual(stale["status"], "stale")
            self.assertEqual(self._request(accepted_revision_id=7)["status"], "stale")
            self.source["attachments"] = [
                self.env["ir.attachment"].create({"name": "booking.pdf", "raw": b"%PDF-1.4 bkg"}).id
            ]
            self.assertEqual(self._request(attachment_original_ids=[])["status"], "stale")
        self.assertFalse(self._bookings())

    def test_wrong_audience_or_recipient_is_blocked(self):
        with self._booking_registered():
            self.assertEqual(self._request(audience_partner_id=self.buyer.id)["status"], "blocked")
            refused = self._request(recipient_email=BUYER_EMAIL)
            self.assertEqual((refused["status"], refused["reason"]), ("blocked", "recipient_not_audience"))
        self.assertFalse(self._bookings())

    def test_reused_operation_key_with_other_content_is_stale(self):
        with self._booking_registered():
            self._request()
            self.source["revision_id"] = 2
            reused = self._request(purpose="booking_amend")
        self.assertEqual((reused["status"], reused["reason"]), ("stale", "operation_key_reused"))
        self.assertEqual(len(self._bookings()), 1)

    def test_revision_before_claim_withholds_the_old_mail(self):
        """V06: the source moves before the claim, so the queued revision never reaches SMTP."""
        with self._booking_registered():
            first = self.Request.browse(self._request()["record_id"])
            self.source["revision_id"] = 2
            with self._mail_sink() as sink:
                self._process(first)
        self.assertFalse(sink)
        self.assertEqual((first.state, first.state_reason), ("canceled", "source_revision_changed"))
        self.assertEqual(first.mail_id.state, "cancel")

    def test_claim_before_revision_keeps_history_and_holds_the_new_revision(self):
        """V06: a claimed send is in flight; a later revision cannot unsend or replay it."""
        with self._booking_registered():
            first = self.Request.browse(self._request()["record_id"])
            mail = first.mail_id
            self.assertEqual(mail._linda_claim_outgoing(mail), "claimed")
            self.assertEqual(mail._linda_claim_outgoing(mail), "skip", "two workers, one claim")
            self.source["revision_id"] = 2
            second = self._request(operation_key="op-2")
            self.assertEqual((second["status"], second["reason"]), ("blocked", "prior_send_outcome_unknown"))
            with self._mail_sink() as sink:
                self._process(first)
        self.assertFalse(sink, "an uncertain attempt is never replayed")
        self.assertEqual((first.state, first.state_reason), ("unknown", "prior_send_outcome_unknown"))
        self.assertEqual(first.source_revision_key, "rev:1", "the claimed revision stays immutable history")

    def test_interrupted_send_stays_unknown_and_is_not_resent(self):
        with self._booking_registered():
            request = self.Request.browse(self._request()["record_id"])
            with self.assertLogs(MAIL_LOGGER, level="ERROR"), self._mail_sink(smtplib.SMTPServerDisconnected()):
                self._process(request)
            self.assertEqual((request.state, request.state_reason), ("unknown", "send_interrupted"))
            with self._mail_sink() as sink:
                self.env["mail.mail"].process_email_queue()
                self.assertEqual(self._request(operation_key="op-3")["status"], "already_applied")
        self.assertFalse(sink)

    def test_off_mode_records_nothing(self):
        self.env["ir.config_parameter"].sudo().set_param(LINDA_MODE_PARAM, "off")
        with self._booking_registered():
            self.assertEqual(self._request()["status"], "not_available")
        self.assertFalse(self._bookings())

    # ── V07: native booking reply attribution ────────────────

    def _raw(self, body, sender, in_reply_to="", subject="Re: booking"):
        message_id = f"<s4-booking-{next(_message_ids)}@sender.example>"
        headers = [
            f"From: Counterparty <{sender}>",
            "To: logistics2@scrapmanagement.com",
            f"Subject: {subject}",
            f"Message-ID: {message_id}",
            f"Date: {email.utils.formatdate()}",
            "MIME-Version: 1.0",
            "Content-Type: text/plain; charset=utf-8",
        ]
        if in_reply_to:
            headers += [f"In-Reply-To: {in_reply_to}", f"References: {in_reply_to}"]
        return message_id, "\n".join(headers) + "\n\n" + body + "\n"

    def _receive(self, raw, keep_original=True):
        message_id, payload = raw
        self.env["mail.thread"].message_process(
            STAND_IN_MODEL, payload, save_original=keep_original, thread_id=self.booking.id
        )
        message = self.env["mail.message"].search([("message_id", "=", message_id)])
        return self.Response._record_incoming(message)

    def test_booking_reply_is_candidate_evidence_bound_by_exact_ancestry(self):
        with self._booking_registered():
            request = self.Request.browse(self._request()["record_id"])
            with self._mail_sink():
                self._process(request)
            reference = request.mail_id.message_id
            reply = self._receive(self._raw("CONFIRMED", SUPPLIER_EMAIL, in_reply_to=reference))
            self.assertEqual((reply.source_kind, reply.source_res_id), ("booking", self.booking.id))
            self.assertFalse(reply.purchase_order_id or reply.sale_order_id)
            self.assertEqual((reply.request_id, reply.binding), (request, "current"))
            self.assertEqual(reply.disposition, "identity_unverified", "a From match is not authentication")
            forged = self._receive(self._raw("CONFIRMED", BUYER_EMAIL, in_reply_to=reference))
            self.assertEqual((forged.disposition, forged.reason), ("unattributed", "sender_not_issue_recipient"))
            forwarded = self._receive(self._raw("CONFIRMED", SUPPLIER_EMAIL, reference, subject="Fwd: booking"))
            self.assertEqual((forwarded.disposition, forwarded.reason), ("unattributed", "forwarded"))
            orphan = self._receive(self._raw("CONFIRMED", SUPPLIER_EMAIL, in_reply_to=reference), keep_original=False)
            self.assertEqual((orphan.binding, orphan.reason), ("unbound", "original_not_retained"))
            unrelated = self._receive(self._raw("CONFIRMED", SUPPLIER_EMAIL, in_reply_to="<nope@x>"))
            self.assertEqual((unrelated.binding, unrelated.reason), ("unbound", "no_linda_ancestor"))
        self.assertEqual(self.booking.read(["name"])[0]["name"], "BKG 6509024800", "reply text changes no source")

    def test_reply_on_an_unregistered_source_model_records_nothing(self):
        with self._booking_registered():
            request = self.Request.browse(self._request()["record_id"])
            with self._mail_sink():
                self._process(request)
            reference = request.mail_id.message_id
        # Export absent: the booking model is not registered, so the reply is not Linda's.
        self.assertFalse(self._receive(self._raw("CONFIRMED", SUPPLIER_EMAIL, in_reply_to=reference)))
