"""Odoo-runtime coverage for Linda SO-only buyer issuance (WP01b, contract SO-01..SO-09).

Plan acceptance A03, A08, A09, A10, A11, A12, A14, A19. Delivery uses a
controlled sink patched onto ir.mail_server: no message leaves the database.
"""

import smtplib
from contextlib import contextmanager
from unittest.mock import patch

import psycopg2

from odoo.addons.base.models.ir_mail_server import MailDeliveryException
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import new_test_user, tagged
from odoo.tools import mute_logger

LOGISTICS_REQUEST = "plasticos.logistics.request"
SALE_ORDER = "sale.order"
PURCHASE_ORDER = "purchase.order"
LINDA_MODE_PARAM = "plasticos_logistics.linda_mode"
LINDA_SENDER = "logistics2@scrapmanagement.com"
MAIL_LOGGER = "odoo.addons.mail.models.mail_mail"


@tagged("post_install", "-at_install", "plasticos", "logistics", "linda")
class TestLindaSoIssuance(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for model in (LOGISTICS_REQUEST, "plasticos.automation.config", "plasticos.transaction"):
            assert model in cls.env, f"{model} is not in the registry; the Linda SO stack is not installed"
        cls.Request = cls.env[LOGISTICS_REQUEST]
        cls.company = cls.env.company
        cls.config = cls.env["plasticos.automation.config"].get_config()
        cls.config.sale_approval_threshold = 1000000.0
        cls.salesperson = new_test_user(
            cls.env, login="linda_so_sales", groups="sales_team.group_sale_salesman", email="sales@example.com"
        )
        cls.buyer = cls.env["res.partner"].create(
            {"name": "Northwind Compounding", "is_company": True, "customer_rank": 1, "email": "buy@northwind.example"}
        )
        cls.supplier = cls.env["res.partner"].create(
            {"name": "Secret Supplier Regrind", "is_company": True, "supplier_rank": 1, "email": "s@secret.example"}
        )
        cls.product = cls.env["product.product"].create(
            {"name": "HDPE Regrind Natural", "type": "consu", "sale_ok": True, "purchase_ok": True}
        )

    # ── helpers ──────────────────────────────────────────────

    def _set_mode(self, mode):
        self.env["ir.config_parameter"].sudo().set_param(LINDA_MODE_PARAM, mode)

    def _new_so(self, buyer=None, price=0.45, qty=40000.0, **values):
        return self.env[SALE_ORDER].create(
            {
                "partner_id": (buyer or self.buyer).id,
                "company_id": self.company.id,
                "order_line": [(0, 0, {"product_id": self.product.id, "product_uom_qty": qty, "price_unit": price})],
                **values,
            }
        )

    def _requests(self, so):
        return self.Request.search([("sale_order_id", "=", so.id)], order="revision")

    def _legacy_mails(self, so):
        return self.env["mail.mail"].search(
            [
                ("model", "=", SALE_ORDER),
                ("res_id", "=", so.id),
                ("subject", "=", f"Sales Order {so.name} - Confirmation"),
            ]
        )

    def _reopen(self, so):
        """Native cancel then reset to quotation; a later confirmation is a new release."""
        so._action_cancel()
        so.action_draft()

    @contextmanager
    def _mail_sink(self, error=None):
        """Controlled outbound sink: capture instead of delivering, or fail like SMTP would."""
        sent = []

        def send_email(server, message, *args, **kwargs):
            if error:
                raise error
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

    # ── SO-01 / SO-06: release, queue, transport ─────────────

    def test_so_only_live_issue_reaches_sink_once(self):
        """SO-01/A03: a confirmed SO with no PO or load issues exactly one buyer SO."""
        self._set_mode("live")
        po_count = self.env[PURCHASE_ORDER].search_count([])
        load_count = self.env["plasticos.load"].search_count([])
        # A salesperson may confirm only their own orders (native record rule).
        so = self._new_so(user_id=self.salesperson.id)

        so.with_user(self.salesperson).action_confirm()

        self.assertEqual(so.state, "sale")
        request = self._requests(so)
        self.assertEqual(len(request), 1)
        self.assertEqual(
            (request.company_id, request.partner_id, request.purpose, request.revision, request.state),
            (self.company, self.buyer, "so_issue", 1, "queued"),
        )
        self.assertFalse(request.purchase_order_id)
        self.assertIn(so.name, request.display_name)
        mail = request.mail_id
        self.assertEqual(mail.state, "outgoing", "queued mail is not sent evidence")
        self.assertEqual(mail.email_to, "buy@northwind.example")
        self.assertIn(LINDA_SENDER, mail.email_from)
        self.assertIn(LINDA_SENDER, mail.reply_to)
        self.assertFalse(mail.email_cc)
        self.assertFalse(mail.recipient_ids, "recipients come from the request, never followers")
        self.assertEqual(len(mail.attachment_ids), 1)
        # Test mode renders reports as HTML; the binding below proves it is the native SO report.
        self.assertTrue(mail.attachment_ids.name.startswith(f"Order - {so.name}."))
        template = self.env.ref("plasticos_logistics.mail_template_linda_so_issue")
        self.assertEqual(template.report_template_ids, self.env.ref("sale.action_report_saleorder"))
        self.assertFalse(self._legacy_mails(so), "SO-08: no overlapping legacy buyer mail in live mode")
        self.assertEqual(self.env[PURCHASE_ORDER].search_count([]), po_count, "no PO is invented")
        self.assertEqual(self.env["plasticos.load"].search_count([]), load_count, "no load is invented")

        with self._mail_sink() as sink:
            self._process_queue(request)
        self.assertEqual(len(sink), 1)
        self.assertEqual(sink[0]["To"], "buy@northwind.example")
        self.assertFalse(sink[0]["Cc"])
        self.assertEqual((request.state, bool(request.sent_at)), ("sent", True))

    def test_known_failure_and_unknown_outcome_are_not_resent(self):
        """SO-06/A14: refused connection is undelivered; a generic error is unknown; neither auto-retries."""
        self._set_mode("live")
        refused_so, generic_so = self._new_so(), self._new_so(price=0.47)
        (refused_so | generic_so).action_confirm()
        refused, generic = self._requests(refused_so), self._requests(generic_so)

        def refuse(*args, **kwargs):
            raise ConnectionRefusedError("smtp down")

        with self._mail_sink() as sink, patch.object(type(self.env["ir.mail_server"]), "_connect__", refuse):
            self._process_queue(refused)
        self.assertFalse(sink)
        self.assertEqual((refused.state, refused.state_reason), ("exception", "mail_smtp"))

        with self.assertLogs(MAIL_LOGGER, level="ERROR"), self._mail_sink(error=MailDeliveryException("timeout")):
            self._process_queue(generic)
        self.assertEqual(generic.state, "unknown")

        with self._mail_sink() as sink:
            self._process_queue(refused)
            self._process_queue(generic)
        self.assertFalse(sink)
        self.assertEqual((refused.state, generic.state), ("exception", "unknown"))

    def test_interrupted_send_is_unknown(self):
        """SO-06: a disconnect mid-send may have delivered; it is never marked sent or resent."""
        self._set_mode("live")
        so = self._new_so()
        so.action_confirm()
        request = self._requests(so)
        with self.assertLogs(MAIL_LOGGER, level="ERROR"), self._mail_sink(error=smtplib.SMTPServerDisconnected()):
            self._process_queue(request)
        self.assertEqual((request.state, request.state_reason), ("unknown", "send_interrupted"))
        with self._mail_sink() as sink:
            self._process_queue(request)
        self.assertFalse(sink)

    # ── SO-02: native approval gate and transaction compiler ─

    def test_approval_gate_blocks_then_authorized_confirm_issues_once(self):
        """SO-02/A10: over threshold without approval confirms nothing; approved confirm issues once."""
        self._set_mode("live")
        self.config.sale_approval_threshold = 100.0
        so = self._new_so()

        with self.assertRaises(UserError):
            so.action_confirm()
        self.assertEqual(so.state, "draft")
        self.assertFalse(self._requests(so))
        self.assertFalse(so.transaction_id)

        so.approved = True
        so.action_confirm()
        self.assertEqual(so.state, "sale")
        self.assertTrue(so.transaction_id, "native transaction compilation is unchanged")
        self.assertEqual(self._requests(so).state, "queued")

    # ── SO-03: duplicates, replays, later PO link, SQL ───────

    def test_replay_po_link_and_mode_toggle_do_not_reissue(self):
        """SO-03/A08: replays, a later PO link and a mode toggle keep one obligation."""
        self._set_mode("live")
        so = self._new_so()
        so.action_confirm()
        first = self._requests(so)

        with self.assertRaises(UserError):
            so.action_confirm()
        self.Request._issue_sale_orders(so)
        po = self.env[PURCHASE_ORDER].create(
            {
                "partner_id": self.supplier.id,
                "origin": so.name,
                "order_line": [(0, 0, {"product_id": self.product.id, "product_qty": 40000.0, "price_unit": 0.3})],
            }
        )
        if so.transaction_id:
            so.transaction_id.purchase_order_ids = [(4, po.id)]
        po.button_confirm()
        self._set_mode("shadow")
        self._set_mode("live")

        self.assertEqual(self._requests(so), first)

        with self._mail_sink() as sink:
            self._process_queue(first)
        self.assertEqual((len(sink), first.state), (1, "sent"))
        self._reopen(so)
        so.action_confirm()
        with self._mail_sink() as sink:
            self.env["mail.mail"].process_email_queue()
        self.assertFalse(
            [m for m in sink if "northwind" in (m["To"] or "")], "an unchanged reconfirmation is not resent"
        )
        self.assertEqual(self._requests(so), first)

    @mute_logger("odoo.sql_db")
    def test_sql_identity_and_source_constraints(self):
        """SO-03/SO-09: SO uniqueness, exactly-one-source and immutability are enforced by the database."""
        self._set_mode("live")
        so = self._new_so()
        so.action_confirm()
        request = self._requests(so)
        base = {
            "company_id": self.company.id,
            "partner_id": self.buyer.id,
            "revision": 1,
            "payload_fingerprint": "duplicate",
        }
        with self.assertRaises(psycopg2.IntegrityError), self.cr.savepoint():
            self.Request.create({**base, "purpose": "so_issue", "sale_order_id": so.id})
        po = self.env[PURCHASE_ORDER].create({"partner_id": self.supplier.id})
        with self.assertRaises(psycopg2.IntegrityError), self.cr.savepoint():
            self.Request.create({**base, "purpose": "so_issue", "sale_order_id": so.id, "purchase_order_id": po.id})
        with self.assertRaises(psycopg2.IntegrityError), self.cr.savepoint():
            self.Request.create({**base, "purpose": "po_issue", "sale_order_id": so.id})
        with self.assertRaises(psycopg2.IntegrityError), self.cr.savepoint():
            self.Request.create({**base, "purpose": "so_issue"})
        other = self.env["res.company"].create({"name": "Linda SO Other Co"})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.Request.create({**base, "company_id": other.id, "purpose": "so_issue", "sale_order_id": so.id})
        with self.assertRaises(UserError):
            request.write({"sale_order_id": False})
        with self.assertRaises(UserError):
            request.unlink()

    # ── SO-04: stale queue and amendments ────────────────────

    def test_material_edits_cancel_unsent_and_new_release_is_new_revision(self):
        """SO-04/A09: line, terms and note edits withhold the queued PDF; a new release is revision 2."""
        self._set_mode("live")
        for change in (
            lambda so: so.write({"order_line": [(1, so.order_line.id, {"price_unit": 0.5})]}),
            lambda so: so.order_line.write({"product_uom_qty": 42000.0}),
            lambda so: so.write({"note": "<p>Delivery by appointment only.</p>"}),
            lambda so: so.write({"client_order_ref": "NW-PO-77"}),
        ):
            so = self._new_so()
            so.action_confirm()
            stale = self._requests(so)
            change(so)
            with self._mail_sink() as sink:
                self._process_queue(stale)
            self.assertFalse(sink)
            self.assertEqual((stale.state, stale.state_reason), ("canceled", "payload_changed"))
            self.assertEqual(stale.mail_id.state, "cancel")

        self._reopen(so)
        so.action_confirm()
        current = self._requests(so) - stale
        self.assertEqual((current.revision, current.state), (2, "queued"))

    def test_buyer_email_and_address_changes_are_caught_at_send_time(self):
        """SO-04: buyer contact or delivery address changed outside the SO is rechecked by the queue."""
        self._set_mode("live")
        shipping = self.env["res.partner"].create(
            {"name": "Northwind Dock 4", "parent_id": self.buyer.id, "type": "delivery", "street": "1 Dock Rd"}
        )
        so = self._new_so(partner_shipping_id=shipping.id)
        so.action_confirm()
        request = self._requests(so)
        shipping.street = "9 Other Rd"
        with self._mail_sink() as sink:
            self._process_queue(request)
        self.assertFalse(sink)
        self.assertEqual(request.state_reason, "payload_changed")

        other = self._new_so()
        other.action_confirm()
        other_request = self._requests(other)
        self.buyer.email = "receiving@northwind.example"
        with self._mail_sink() as sink:
            self._process_queue(other_request)
        self.assertFalse(sink)
        self.assertEqual(other_request.state, "canceled")

    def test_sent_history_is_kept_when_order_is_amended(self):
        self._set_mode("live")
        so = self._new_so()
        so.action_confirm()
        first = self._requests(so)
        with self._mail_sink():
            self._process_queue(first)
        self._reopen(so)
        so.write({"order_line": [(1, so.order_line.id, {"product_uom_qty": 39000.0})]})
        so.action_confirm()
        second = self._requests(so) - first
        self.assertEqual(first.state, "sent", "prior send evidence is immutable")
        self.assertEqual(second.revision, 2)

    def test_cancel_before_send_cancels_the_unsent_issue(self):
        self._set_mode("live")
        so = self._new_so()
        so.action_confirm()
        request = self._requests(so)
        so._action_cancel()
        self.assertEqual((request.state, request.state_reason), ("canceled", "order_not_confirmed"))
        self.assertEqual(request.mail_id.state, "cancel")

    # ── SO-05: modes and denials ─────────────────────────────

    def test_off_and_shadow_keep_legacy_and_send_nothing_from_linda(self):
        """SO-05/SO-08/A11/A13: off records nothing; shadow records without mail; legacy runs in both."""
        self.env["ir.config_parameter"].sudo().search([("key", "=", LINDA_MODE_PARAM)]).unlink()
        off_so = self._new_so()
        off_so.action_confirm()
        self.assertFalse(self._requests(off_so))
        self.assertEqual(len(self._legacy_mails(off_so)), 1)

        self._set_mode("shadow")
        shadow_so = self._new_so()
        shadow_so.action_confirm()
        request = self._requests(shadow_so)
        self.assertEqual((request.state, bool(request.mail_id)), ("shadow", False))
        self.assertIn(shadow_so.name, request.subject)
        self.assertEqual(len(self._legacy_mails(shadow_so)), 1)

    def test_non_release_contexts_issue_nothing(self):
        """SO-05/A11: imports, installs and automation-skips are not live native releases."""
        self._set_mode("live")
        for key in ("import_mode", "install_mode", "skip_automations"):
            so = self._new_so()
            so.with_context(**{key: True}).action_confirm()
            self.assertEqual(so.state, "sale")
            self.assertFalse(self._requests(so), key)

    def test_draft_cancel_and_bad_contact_block_only_that_order(self):
        """SO-05/A12: draft and canceled orders issue nothing; a bad buyer email blocks only its SO."""
        self._set_mode("live")
        draft = self._new_so()
        draft.write({"note": "<p>still a quotation</p>"})
        canceled = self._new_so()
        canceled._action_cancel()
        self.assertFalse(self._requests(draft) | self._requests(canceled))

        no_mail = self.env["res.partner"].create({"name": "No Mail Buyer", "is_company": True})
        bad, good = self._new_so(buyer=no_mail), self._new_so()
        (bad | good).action_confirm()
        blocked = self._requests(bad)
        self.assertEqual(
            (blocked.state, blocked.state_reason, bool(blocked.mail_id)), ("blocked", "buyer_email_invalid", False)
        )
        self.assertEqual(self._requests(good).state, "queued")

    def test_buyer_company_mismatch_blocks(self):
        self._set_mode("live")
        so = self._new_so()
        so.action_confirm()
        request = self._requests(so)
        self.buyer.sudo().company_id = self.env["res.company"].create({"name": "Linda SO Foreign Co"})
        self.assertEqual(self.Request._so_block_reason(so), "buyer_company_mismatch")
        with self._mail_sink() as sink:
            self._process_queue(request)
        self.assertFalse(sink)
        self.assertEqual(request.state, "canceled")

    # ── SO-07: audience ──────────────────────────────────────

    def test_buyer_message_has_no_supplier_identity(self):
        """SO-07/A19: subject, body, envelope and the native SO report carry no supplier-side identity."""
        self._set_mode("live")
        so = self._new_so()
        po = self.env[PURCHASE_ORDER].create(
            {
                "partner_id": self.supplier.id,
                "origin": so.name,
                "order_line": [(0, 0, {"product_id": self.product.id, "product_qty": 40000.0, "price_unit": 0.3137})],
            }
        )
        po.button_confirm()
        so.action_confirm()
        mail = self._requests(so).mail_id

        report_html = self.env["ir.actions.report"]._render_qweb_html("sale.report_saleorder", so.ids)[0].decode()
        rendered = " ".join(
            [mail.subject or "", mail.body_html or "", mail.email_to or "", mail.email_cc or "", report_html]
        )
        for secret in (self.supplier.name, self.supplier.email, po.name, "0.3137"):
            self.assertNotIn(secret, rendered)
        self.assertFalse(mail.recipient_ids)

    # ── SO-09: PO evidence is unaffected ─────────────────────

    def test_po_issue_still_uses_its_own_identity(self):
        """SO-09: PO requests keep purpose po_issue, an exact PO and no sale order."""
        self._set_mode("live")
        po = self.env[PURCHASE_ORDER].create(
            {
                "partner_id": self.supplier.id,
                "order_line": [(0, 0, {"product_id": self.product.id, "product_qty": 1000.0, "price_unit": 0.3})],
            }
        )
        po.button_confirm()
        request = self.Request.search([("purchase_order_id", "=", po.id)])
        self.assertEqual(
            (request.purpose, request.sale_order_id, request.state), ("po_issue", self.env[SALE_ORDER], "queued")
        )
        self.assertIn(po.name, request.display_name)
