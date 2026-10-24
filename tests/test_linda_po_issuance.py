"""Odoo-runtime coverage for Linda PO-only supplier issuance (WP01b).

Plan acceptance A01, A08, A09, A11, A12, A13, A14, A19 and both native PO
release paths. Delivery uses a controlled sink patched onto ir.mail_server:
no message leaves the test database.
"""

import smtplib
from contextlib import contextmanager
from unittest.mock import patch

from odoo import fields
from odoo.addons.base.models.ir_mail_server import MailDeliveryException
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import new_test_user, tagged
from odoo.tools import mute_logger

LOGISTICS_REQUEST = "plasticos.logistics.request"
PURCHASE_ORDER = "purchase.order"
LINDA_MODE_PARAM = "plasticos_logistics.linda_mode"
LINDA_SENDER = "logistics2@scrapmanagement.com"
LEGACY_SUBJECT = "Ready for Pickup Confirmation Required"
MAIL_LOGGER = "odoo.addons.mail.models.mail_mail"


@tagged("post_install", "-at_install", "plasticos", "integration", "logistics", "linda")
class TestLindaPoIssuance(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        assert LOGISTICS_REQUEST in cls.env, "plasticos_logistics install/upgrade is broken"
        cls.Request = cls.env[LOGISTICS_REQUEST]
        cls.company = cls.env.company
        cls.company.po_double_validation = "one_step"
        cls.manager = new_test_user(
            cls.env, login="linda_po_manager", groups="purchase.group_purchase_manager", email="mgr@example.com"
        )
        cls.buyer_clerk = new_test_user(
            cls.env, login="linda_po_user", groups="purchase.group_purchase_user", email="clerk@example.com"
        )
        cls.supplier = cls.env["res.partner"].create(
            {"name": "Acme Regrind", "is_company": True, "supplier_rank": 1, "email": "sales@acme-regrind.example"}
        )
        cls.buyer = cls.env["res.partner"].create(
            {"name": "Secret Buyer Holdings", "is_company": True, "customer_rank": 1, "email": "buy@secret.example"}
        )
        cls.product = cls.env["product.product"].create(
            {"name": "LDPE Film Bales", "type": "consu", "purchase_ok": True, "sale_ok": True}
        )

    # ── helpers ──────────────────────────────────────────────

    def _set_mode(self, mode):
        self.env["ir.config_parameter"].sudo().set_param(LINDA_MODE_PARAM, mode)

    def _new_po(self, partner=None, price=0.12, qty=40000.0, **values):
        return self.env[PURCHASE_ORDER].create(
            {
                "partner_id": (partner or self.supplier).id,
                "company_id": self.company.id,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_qty": qty, "price_unit": price}),
                ],
                **values,
            }
        )

    def _requests(self, po):
        return self.Request.search([("purchase_order_id", "=", po.id)], order="revision")

    def _legacy_mails(self, po):
        return self.env["mail.mail"].search(
            [("model", "=", PURCHASE_ORDER), ("res_id", "=", po.id), ("subject", "ilike", LEGACY_SUBJECT)]
        )

    @contextmanager
    def _mail_sink(self, error=None, fail_once=None):
        """Controlled outbound sink: capture instead of delivering, or fail like SMTP would.

        ``error`` fails every send; ``fail_once`` fails only the first one.
        """
        sent = []
        pending = [fail_once] if fail_once else []

        def send_email(server, message, *args, **kwargs):
            if error:
                raise error
            if pending:
                raise pending.pop()
            sent.append(message)
            return message["Message-Id"]

        server_class = type(self.env["ir.mail_server"])
        # Odoo disables sending under tests unless _disable_send is patched; no SMTP connection is opened.
        with (
            patch.object(server_class, "_disable_send", lambda *args: False),
            patch.object(server_class, "_connect__", lambda *args, **kwargs: None),
            patch.object(server_class, "send_email", send_email),
        ):
            yield sent

    def _process_queue(self, request):
        self.env["mail.mail"].process_email_queue(email_ids=request.mail_id.ids)
        request.invalidate_recordset()

    # ── release paths ────────────────────────────────────────

    def test_po_only_live_issue_reaches_sink_once(self):
        """A01/A14: confirmed PO with no SO, transaction or load issues exactly one supplier PO."""
        self._set_mode("live")
        counts = {model: self.env[model].search_count([]) for model in ("sale.order", "plasticos.transaction")}
        load_count = self.env["plasticos.load"].search_count([])
        po = self._new_po()

        po.with_user(self.manager).button_confirm()

        self.assertEqual(po.state, "purchase")
        request = self._requests(po)
        self.assertEqual(len(request), 1)
        self.assertEqual(request.state, "queued")
        self.assertEqual(
            (request.company_id, request.partner_id, request.purpose, request.revision),
            (self.company, self.supplier, "po_issue", 1),
        )
        mail = request.mail_id
        self.assertEqual(mail.state, "outgoing", "queued mail is not sent evidence")
        self.assertEqual(mail.email_to, "sales@acme-regrind.example")
        self.assertIn(LINDA_SENDER, mail.email_from)
        self.assertFalse(mail.email_cc)
        self.assertFalse(mail.recipient_ids, "recipients come from the request, never followers")
        self.assertEqual(len(mail.attachment_ids), 1)
        # Test mode renders reports as HTML; the real PDF is verified outside test mode.
        self.assertTrue(mail.attachment_ids.name.startswith(f"Purchase Order - {po.name}."))
        self.assertFalse(self._legacy_mails(po), "legacy supplier-ready mail must not overlap in live mode")
        for model, before in counts.items():
            self.assertEqual(self.env[model].search_count([]), before, f"{model} must not be invented")
        self.assertEqual(self.env["plasticos.load"].search_count([]), load_count)

        with self._mail_sink() as sink:
            self._process_queue(request)
        self.assertEqual(len(sink), 1)
        self.assertEqual(sink[0]["To"], "sales@acme-regrind.example")
        self.assertEqual(request.state, "sent")
        self.assertTrue(request.sent_at)

    def test_attachment_is_the_native_po_report(self):
        """A19: the supplier attachment comes from the native purchase order report, nothing custom."""
        self._set_mode("live")
        template = self.env.ref("plasticos_logistics.mail_template_linda_po_issue")
        self.assertEqual(template.report_template_ids, self.env.ref("purchase.action_report_purchase_order"))
        po = self._new_po()
        po.button_confirm()
        attachment = self._requests(po).mail_id.attachment_ids
        self.assertEqual(len(attachment), 1)
        self.assertTrue(attachment.name.startswith(f"Purchase Order - {po.name}."))
        self.assertTrue(attachment.raw, "the rendered report is attached at queue time")

    def test_two_step_sends_only_after_manager_approval(self):
        """Native two-step approval is untouched: 'to approve' never issues, approval does once."""
        self._set_mode("live")
        self.company.write({"po_double_validation": "two_step", "po_double_validation_amount": 100.0})
        po = self._new_po()

        po.with_user(self.buyer_clerk).button_confirm()
        self.assertEqual(po.state, "to approve")
        self.assertFalse(self._requests(po))

        po.with_user(self.manager).button_approve()
        self.assertEqual(po.state, "purchase")
        self.assertEqual(len(self._requests(po)), 1)

    def test_below_threshold_user_confirmation_is_a_native_release(self):
        """A purchase user confirming within the native threshold releases without another approval."""
        self._set_mode("live")
        self.company.write({"po_double_validation": "two_step", "po_double_validation_amount": 1000000.0})
        po = self._new_po()
        po.with_user(self.buyer_clerk).button_confirm()
        self.assertEqual(po.state, "purchase")
        self.assertEqual(self._requests(po).state, "queued")

    # ── duplicates and replays ───────────────────────────────

    def test_replay_and_later_so_link_do_not_reissue(self):
        """A08: repeated buttons, direct replay, a later SO link and an unchanged reconfirmation keep one send."""
        self._set_mode("live")
        po = self._new_po()
        po.button_confirm()
        first = self._requests(po)

        po.button_confirm()
        po.button_approve()
        self.Request._issue_purchase_orders(po)
        so = self.env["sale.order"].create({"partner_id": self.buyer.id})
        po.write({"origin": so.name})
        self.assertEqual(self._requests(po), first)

        with self._mail_sink() as sink:
            self._process_queue(first)
        self.assertEqual((len(sink), first.state), (1, "sent"))

        po.button_cancel()
        po.button_draft()
        po.button_confirm()
        with self._mail_sink() as sink:
            self.env["mail.mail"].process_email_queue()
        self.assertFalse(sink, "an unchanged reconfirmation must not resend a delivered PO")
        self.assertEqual(self._requests(po), first)

    def test_cancel_before_send_cancels_the_unsent_issue(self):
        """A11: a PO canceled while its issue is queued never sends it; a later release is a new revision."""
        self._set_mode("live")
        po = self._new_po()
        po.button_confirm()
        first = self._requests(po)
        po.button_cancel()
        self.assertEqual((first.state, first.state_reason), ("canceled", "order_not_confirmed"))
        self.assertEqual(first.mail_id.state, "cancel")

        po.button_draft()
        po.button_confirm()
        self.assertEqual((self._requests(po) - first).revision, 2)

    @mute_logger("odoo.sql_db")
    def test_identity_is_unique_and_immutable(self):
        self._set_mode("live")
        po = self._new_po()
        po.button_confirm()
        request = self._requests(po)
        with self.assertRaises(Exception), self.cr.savepoint():
            self.Request.create(
                {
                    "company_id": request.company_id.id,
                    "purpose": "po_issue",
                    "purchase_order_id": po.id,
                    "partner_id": self.supplier.id,
                    "revision": 1,
                    "payload_fingerprint": "duplicate",
                }
            )
        with self.assertRaises(Exception):
            request.write({"revision": 7})
        with self.assertRaises(Exception):
            request.unlink()

    # ── stale queue and amendments ───────────────────────────

    def test_material_change_cancels_unsent_and_new_release_is_new_revision(self):
        """A09: an edited PO never lets the queued old document leave; the next release issues revision 2."""
        self._set_mode("live")
        po = self._new_po()
        po.button_confirm()
        stale = self._requests(po)

        po.order_line.write({"price_unit": 0.15})
        po.write({"order_line": [(1, po.order_line.id, {"price_unit": 0.16})]})

        self.assertEqual(stale.state, "canceled")
        self.assertEqual(stale.mail_id.state, "cancel")
        with self._mail_sink() as sink:
            self.env["mail.mail"].process_email_queue(email_ids=stale.mail_id.ids)
        self.assertFalse(sink)

        po.button_cancel()
        po.button_draft()
        po.button_confirm()
        current = self._requests(po) - stale
        self.assertEqual(current.revision, 2)
        self.assertEqual(current.state, "queued")

    def test_purchase_users_can_cancel_and_edit_a_queued_po(self):
        """Review finding: canceling or editing a queued PO must not need mail.mail rights."""
        self._set_mode("live")
        for user in (self.manager, self.buyer_clerk):
            po = self._new_po()
            po.with_user(user).button_confirm()
            request = self._requests(po)
            po.with_user(user).write({"order_line": [(1, po.order_line.id, {"price_unit": 0.19})]})
            self.assertEqual((request.state, request.state_reason), ("canceled", "payload_changed"))

            po2 = self._new_po()
            po2.with_user(user).button_confirm()
            po2.with_user(user).button_cancel()
            self.assertEqual(self._requests(po2).state, "canceled")

    def test_roles_without_request_rights_still_release_natively(self):
        """A role that may confirm POs but has no right on Linda requests still gets its native approval.

        plasticos_security_base grants purchase.order rights to sales reps and logistics without any
        purchase group; this builds the same shape locally so the test holds whichever modules load.
        """
        self._set_mode("live")
        confirmer = self.env["res.groups"].create({"name": "Linda test PO confirmer"})
        for model in ("purchase.order", "purchase.order.line"):
            self.env["ir.model.access"].create(
                {
                    "name": f"linda test {model}",
                    "model_id": self.env["ir.model"]._get_id(model),
                    "group_id": confirmer.id,
                    "perm_read": True,
                    "perm_write": True,
                    "perm_create": True,
                }
            )
        user = new_test_user(
            self.env, login="linda_po_confirmer", groups="stock.group_stock_user", email="c@example.com"
        )
        user.write({"group_ids": [(4, confirmer.id)]})
        self.assertFalse(self.Request.with_user(user).has_access("create"), "fixture must lack request rights")
        po = self._new_po()

        po.with_user(user).button_confirm()

        self.assertEqual(po.state, "purchase")
        self.assertEqual(self._requests(po).state, "queued")

    def test_render_failure_blocks_only_the_issue(self):
        """A failed render/queue records a blocked issue and leaves the native approval in place."""
        self._set_mode("live")
        po = self._new_po()
        template_class = type(self.env["mail.template"])

        def broken(*args, **kwargs):
            raise ValueError("wkhtmltopdf crashed")

        with (
            patch.object(template_class, "send_mail", broken),
            self.assertLogs("odoo.addons.plasticos_logistics.models.linda_request", level="ERROR"),
        ):
            po.button_confirm()

        self.assertEqual(po.state, "purchase")
        request = self._requests(po)
        self.assertEqual((request.state, request.state_reason), ("blocked", "render_failed"))
        self.assertFalse(request.mail_id)

    def test_order_date_change_is_material(self):
        """Review finding: fields printed on the PDF (here the order deadline) invalidate a queued issue."""
        self._set_mode("live")
        po = self._new_po()
        po.button_confirm()
        request = self._requests(po)
        po.write({"date_order": fields.Datetime.add(po.date_order, days=3)})
        self.assertEqual((request.state, request.state_reason), ("canceled", "payload_changed"))

    def test_recipient_change_is_caught_at_send_time(self):
        """A09: a supplier address change outside the PO is rechecked when the queue runs."""
        self._set_mode("live")
        po = self._new_po()
        po.button_confirm()
        request = self._requests(po)

        self.supplier.email = "new-desk@acme-regrind.example"
        with self._mail_sink() as sink:
            self._process_queue(request)

        self.assertFalse(sink)
        self.assertEqual(request.state, "canceled")
        self.assertEqual(request.state_reason, "payload_changed")

    def test_sent_history_is_kept_when_order_is_amended(self):
        self._set_mode("live")
        po = self._new_po()
        po.button_confirm()
        first = self._requests(po)
        with self._mail_sink():
            self._process_queue(first)
        self.assertEqual(first.state, "sent")

        po.button_cancel()
        po.button_draft()
        po.write({"order_line": [(1, po.order_line.id, {"product_qty": 42000.0})]})
        po.button_confirm()

        second = self._requests(po) - first
        self.assertEqual(first.state, "sent", "prior send evidence is immutable")
        self.assertEqual(second.revision, 2)

    # ── modes and denials ────────────────────────────────────

    def test_off_mode_keeps_legacy_and_records_nothing(self):
        """A11: off is the default; Linda records nothing and the legacy PO action still runs."""
        self.env["ir.config_parameter"].sudo().search([("key", "=", LINDA_MODE_PARAM)]).unlink()
        po = self._new_po()
        po.button_confirm()
        self.assertFalse(self._requests(po))
        self.assertEqual(len(self._legacy_mails(po)), 1)

    def test_unknown_mode_fails_closed(self):
        self._set_mode("LIVE-ish")
        po = self._new_po()
        po.button_confirm()
        self.assertFalse(self._requests(po))

    def test_shadow_records_evidence_without_mail(self):
        """A13: shadow inspects the issue but delivers nothing and claims nothing sent."""
        self._set_mode("shadow")
        po = self._new_po()
        po.button_confirm()
        request = self._requests(po)
        self.assertEqual(request.state, "shadow")
        self.assertFalse(request.mail_id)
        self.assertIn(po.name, request.subject)
        linda_mails = self.env["mail.mail"].search(
            [("model", "=", PURCHASE_ORDER), ("res_id", "=", po.id), ("email_from", "ilike", LINDA_SENDER)]
        )
        self.assertFalse(linda_mails)

    def test_non_release_contexts_issue_nothing(self):
        """A11: imports, installs and automation-skips are not live native releases."""
        self._set_mode("live")
        for key in ("import_mode", "install_mode", "skip_automations"):
            po = self._new_po()
            po.with_context(**{key: True}).button_confirm()
            self.assertEqual(po.state, "purchase")
            self.assertFalse(self._requests(po), key)

    def test_draft_and_rfq_states_issue_nothing(self):
        self._set_mode("live")
        po = self._new_po()
        po.write({"partner_ref": "RFQ-ONLY"})
        po.button_cancel()
        self.assertFalse(self._requests(po))

    def test_invalid_supplier_contact_blocks_only_that_order(self):
        """A12: a bad supplier address blocks this PO; another valid PO still issues."""
        self._set_mode("live")
        bad_supplier = self.env["res.partner"].create({"name": "No Mail Recycling", "is_company": True})
        bad = self._new_po(partner=bad_supplier)
        good = self._new_po()

        (bad | good).button_confirm()

        blocked = self._requests(bad)
        self.assertEqual((blocked.state, blocked.state_reason), ("blocked", "supplier_email_invalid"))
        self.assertFalse(blocked.mail_id)
        self.assertEqual(self._requests(good).state, "queued")

    def test_supplier_company_mismatch_blocks(self):
        self._set_mode("live")
        other = self.env["res.company"].create({"name": "Linda Other Co"})
        po = self._new_po()
        po.button_confirm()
        request = self._requests(po)
        self.supplier.sudo().company_id = other
        self.assertEqual(self.Request._po_block_reason(po), "supplier_company_mismatch")
        with self._mail_sink() as sink:
            self._process_queue(request)
        self.assertFalse(sink)
        self.assertEqual(request.state, "canceled")

    # ── audience blinding ────────────────────────────────────

    def test_supplier_message_has_no_buyer_identity(self):
        """A19: subject, body, recipients and PO document carry no buyer-side identity."""
        self._set_mode("live")
        so = self.env["sale.order"].create({"partner_id": self.buyer.id})
        po = self._new_po(origin=so.name)
        po.button_confirm()
        mail = self._requests(po).mail_id

        report_html = self.env["ir.actions.report"]._render_qweb_html("purchase.report_purchaseorder", po.ids)[0]
        rendered = " ".join([mail.subject or "", mail.body_html or "", mail.email_to or "", report_html.decode()])
        for secret in (self.buyer.name, self.buyer.email, so.name):
            self.assertNotIn(secret, rendered)

    def test_dropship_destination_is_blocked(self):
        """G-18: the native PO PDF prints the dropship address, so such a PO is not auto-issued."""
        self._set_mode("live")
        po = self._new_po(dest_address_id=self.buyer.id)
        po.button_confirm()
        request = self._requests(po)
        self.assertEqual((request.state, request.state_reason), ("blocked", "dropship_destination_disclosed"))
        self.assertFalse(request.mail_id)

    # ── delivery outcomes ────────────────────────────────────

    def test_connection_failure_is_undelivered_and_not_retried(self):
        """A14: a refused SMTP connection proves non-delivery; the queue does not resend it."""
        self._set_mode("live")
        po = self._new_po()
        po.button_confirm()
        request = self._requests(po)

        def refuse(*args, **kwargs):
            raise ConnectionRefusedError("smtp down")

        with self._mail_sink() as sink, patch.object(type(self.env["ir.mail_server"]), "_connect__", refuse):
            self._process_queue(request)
        self.assertFalse(sink)
        self.assertEqual((request.state, request.state_reason), ("exception", "mail_smtp"))
        self.assertEqual(request.mail_id.state, "exception")

        with self._mail_sink() as sink:
            self._process_queue(request)
        self.assertFalse(sink)
        self.assertEqual(request.state, "exception")

    def test_generic_send_failure_is_unknown_not_failed(self):
        """A14: Odoo wraps post-DATA errors generically; the message may have arrived, so it is unknown."""
        self._set_mode("live")
        po = self._new_po()
        po.button_confirm()
        request = self._requests(po)

        with self.assertLogs(MAIL_LOGGER, level="ERROR"), self._mail_sink(error=MailDeliveryException("timeout")):
            self._process_queue(request)
        self.assertEqual((request.state, request.state_reason), ("unknown", "unknown"))
        self.assertNotEqual(request.state, "sent")

        with self._mail_sink() as sink:
            self._process_queue(request)
        self.assertFalse(sink, "an unknown outcome is never retried by the queue")

    def test_abort_mid_batch_leaves_unattempted_mail_queued(self):
        """A14: a disconnect on one mail does not mark later, never-attempted mails as uncertain."""
        self._set_mode("live")
        first_po, second_po = self._new_po(), self._new_po(price=0.13)
        (first_po | second_po).button_confirm()
        first, second = self._requests(first_po), self._requests(second_po)

        with (
            self.assertLogs(MAIL_LOGGER, level="ERROR"),
            self._mail_sink(fail_once=smtplib.SMTPServerDisconnected()),
        ):
            self.env["mail.mail"].process_email_queue(email_ids=(first.mail_id | second.mail_id).ids)
        (first | second).invalidate_recordset()
        # The queue sends in ascending mail id: the first PO's mail is attempted and drops.
        self.assertEqual((first.state, first.state_reason), ("unknown", "send_interrupted"))
        self.assertEqual((second.state, second.send_attempt_count), ("queued", 0))

        with self._mail_sink() as sink:
            self._process_queue(second)
        self.assertEqual(len(sink), 1)
        self.assertEqual(second.state, "sent")

    def test_uncertain_delivery_becomes_unknown_and_is_not_resent(self):
        """A14: a disconnect mid-send may have delivered; the next queue run must not resend."""
        self._set_mode("live")
        po = self._new_po()
        po.button_confirm()
        request = self._requests(po)

        with self.assertLogs(MAIL_LOGGER, level="ERROR"), self._mail_sink(error=smtplib.SMTPServerDisconnected()):
            self._process_queue(request)
        self.assertEqual((request.state, request.state_reason), ("unknown", "send_interrupted"))
        self.assertEqual(request.send_attempt_count, 1)

        with self._mail_sink() as sink:
            self._process_queue(request)
        self.assertFalse(sink)
        self.assertEqual(request.state, "unknown", "an uncertain delivery is never marked sent")

    def test_attempt_rolled_back_to_outgoing_is_not_resent(self):
        """A14: when a crash rolls the mail back to outgoing, the committed attempt marker stops a resend."""
        self._set_mode("live")
        po = self._new_po()
        po.button_confirm()
        request = self._requests(po)
        # The state the queue sees after a crash mid-SMTP: marker committed, mail back to outgoing.
        request.write({"send_attempt_count": 1})

        with self._mail_sink() as sink:
            self._process_queue(request)

        self.assertFalse(sink)
        self.assertEqual((request.state, request.state_reason), ("unknown", "prior_send_outcome_unknown"))
        self.assertEqual(request.mail_id.state, "cancel")

    def test_mode_switched_off_before_send_cancels_queue(self):
        self._set_mode("live")
        po = self._new_po()
        po.button_confirm()
        request = self._requests(po)
        self._set_mode("off")
        with self._mail_sink() as sink:
            self._process_queue(request)
        self.assertFalse(sink)
        self.assertEqual((request.state, request.state_reason), ("canceled", "mode_not_live"))

    def test_request_dates_are_recorded(self):
        self._set_mode("live")
        po = self._new_po()
        before = fields.Datetime.now()
        po.button_confirm()
        self.assertGreaterEqual(self._requests(po).queued_at, before)
