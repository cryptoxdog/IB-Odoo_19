"""Odoo-runtime coverage for Linda PO-only supplier issuance (WP01b).

Plan acceptance A01, A08, A09, A11, A12, A13, A14, A19 and both native PO
release paths, plus the cancellation notice and post-cancellation release
cycle (SUPERSESSION 2026-10-24, contract AC-02..AC-24). Delivery uses a
controlled sink patched onto ir.mail_server: no message leaves the test
database.
"""

import re
import smtplib
import subprocess
import tempfile
import zlib
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from odoo import fields
from odoo.addons.base.models.ir_mail_server import MailDeliveryException
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import new_test_user, tagged
from odoo.tools import mute_logger

LOGISTICS_REQUEST = "plasticos.logistics.request"
PURCHASE_ORDER = "purchase.order"
LINDA_MODE_PARAM = "plasticos_logistics.linda_mode"
LINDA_SENDER = "logistics2@scrapmanagement.com"
LEGACY_SUBJECT = "Ready for Pickup Confirmation Required"
PO_ISSUE = "po_issue"
PO_CANCEL = "po_cancel"
SUPPLIER_EMAIL = "sales@acme-regrind.example"
SUPPLIER_PO_REPORT = "plasticos_logistics.report_purchaseorder_supplier"
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
        warehouse = cls.env["stock.warehouse"].search([("company_id", "=", cls.company.id)], limit=1)
        cls.dropship_type = cls.env["stock.picking.type"].create(
            {
                "name": "Linda Dropship",
                "code": "incoming",
                "sequence_code": "LDS",
                "warehouse_id": warehouse.id,
            }
        )
        # The incoming compute points at stock. A customer destination keeps dest_address_id.
        cls.dropship_type.default_location_dest_id = cls.env.ref("stock.stock_location_customers")

    # ── helpers ──────────────────────────────────────────────

    def _set_mode(self, mode):
        self.env["ir.config_parameter"].sudo().set_param(LINDA_MODE_PARAM, mode)

    def _new_po(self, partner=None, price=0.12, qty=40000.0, **values):
        if values.get("dest_address_id") and "picking_type_id" not in values:
            values["picking_type_id"] = self.dropship_type.id
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

    def _requests(self, po, purpose=PO_ISSUE):
        return self.Request.search([("purchase_order_id", "=", po.id), ("purpose", "=", purpose)], order="revision")

    def _notices(self, po):
        return self._requests(po, purpose=PO_CANCEL)

    def _sent_po(self, **values):
        """A live PO whose first issue the sink has already delivered."""
        self._set_mode("live")
        po = self._new_po(**values)
        po.button_confirm()
        first = self._requests(po)
        with self._mail_sink():
            self._process_queue(first)
        self.assertEqual(first.state, "sent")
        return po, first

    def _to_supplier(self, sink):
        return [message for message in sink if message["To"] == SUPPLIER_EMAIL]

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

    def _buyer_markers(self, buyer):
        markers = []
        for value in (buyer.name, buyer.street, buyer.street2, buyer.city, buyer.zip, buyer.phone):
            text = (value or "").strip()
            if len(text) >= 4:
                markers.append(text)
        return markers

    def _pdf_of_report_html(self, html):
        """Convert queued report HTML locally, without calling back into this test transaction.

        Odoo skips wkhtmltopdf during tests unless ``force_report_rendering`` is set.
        That flag makes wkhtmltopdf fetch report CSS from this process, and the request
        waits on the open test transaction. The bytes Linda queues here are the QWeb
        document. This conversion is how those bytes are inspected as a PDF.
        """
        text = html.decode("utf-8", "replace") if isinstance(html, (bytes, bytearray)) else str(html)
        text = re.sub(r"<link\b[^>]*>", "", text, flags=re.I)
        text = re.sub(r"<script\b.*?</script>", "", text, flags=re.I | re.S)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "report.html"
            target = Path(tmp) / "report.pdf"
            source.write_text(text, encoding="utf-8")
            completed = subprocess.run(
                [
                    "/usr/local/bin/wkhtmltopdf",
                    "--disable-external-links",
                    "--disable-javascript",
                    "--quiet",
                    str(source),
                    str(target),
                ],
                check=False,
                timeout=60,
                capture_output=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            return target.read_bytes()

    def _pdf_text(self, raw):
        """Latin-1 PDF bytes plus any FlateDecode streams wkhtmltopdf emitted."""
        raw = bytes(raw or b"")
        parts = [raw.decode("latin-1", "replace")]
        cursor = 0
        while True:
            start = raw.find(b"stream", cursor)
            if start < 0:
                break
            newline = raw.find(b"\n", start)
            end = raw.find(b"endstream", start)
            if newline < 0 or end < 0 or newline > end:
                break
            data = raw[newline + 1 : end].strip(b"\r\n")
            try:
                parts.append(zlib.decompress(data).decode("latin-1", "replace"))
            except zlib.error:
                pass
            cursor = end + len(b"endstream")
        return "\n".join(parts)

    def _mime_payloads(self, message):
        payloads = []
        for part in message.walk():
            if part.get_content_maintype() == "multipart":
                continue
            payload = part.get_payload(decode=True)
            if payload:
                payloads.append(payload)
        return payloads

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
        """A08/AC-10: repeated buttons, direct replay and a later SO link keep one send in one cycle."""
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

        # Without a cancellation the cycle stays open: re-approving a confirmed PO renews
        # native date_approve but issues nothing (adversarial probe 4).
        po.button_approve()
        self.Request._issue_purchase_orders(po)
        with self._mail_sink() as sink:
            self.env["mail.mail"].process_email_queue()
        self.assertFalse(self._to_supplier(sink))
        self.assertEqual(self._requests(po), first)
        self.assertFalse(self._notices(po))

    def test_cancel_before_send_cancels_the_unsent_issue(self):
        """A11: a PO canceled while its issue is queued never sends it; a later release is a new revision."""
        self._set_mode("live")
        po = self._new_po()
        po.button_confirm()
        first = self._requests(po)
        po.button_cancel()
        self.assertEqual((first.state, first.state_reason), ("canceled", "order_not_confirmed"))
        self.assertEqual(first.mail_id.state, "cancel")
        self.assertFalse(self._notices(po), "AC-03: nothing reached the supplier, so nothing is retracted")
        with self._mail_sink() as sink:
            self.env["mail.mail"].process_email_queue()
        self.assertFalse(self._to_supplier(sink), "probe 2: no stale initial mail after cancel")

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

    def test_printed_terms_change_is_material(self):
        """Codex finding: the PDF prints Terms and Conditions; editing them invalidates a queued issue."""
        self._set_mode("live")
        po = self._new_po()
        po.button_confirm()
        request = self._requests(po)
        po.write({"note": "<p>Payment within 15 days, pickup by appointment.</p>"})
        self.assertEqual((request.state, request.state_reason), ("canceled", "payload_changed"))

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
        self.assertFalse(self._notices(po), "AC-05: an RFQ cancellation notifies nobody")

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

    def _dropship_buyer(self):
        self.buyer.write({"street": "900 Hidden Pier", "city": "Sealport", "zip": "99501", "phone": "907-555-0148"})
        return self.buyer

    def test_dropship_template_using_the_native_report_fails_closed(self):
        """Retargeting the dropship template at the native report blocks that send only."""
        self._set_mode("live")
        buyer = self._dropship_buyer()
        template = self.env.ref("plasticos_logistics.mail_template_linda_po_issue_dropship")
        template.report_template_ids = self.env.ref("purchase.action_report_purchase_order")
        po = self._new_po(dest_address_id=buyer.id)
        native_html = self.env["ir.actions.report"]._render_qweb_html("purchase.report_purchaseorder", po.ids)[0]
        native_text = native_html.decode()
        self.assertIn("Shipping address", native_text)
        for marker in self._buyer_markers(buyer):
            self.assertIn(marker, native_text)
        po.button_confirm()
        request = self._requests(po)
        self.assertEqual(
            (request.state, request.state_reason),
            ("blocked", "dropship_report_discloses_buyer_delivery"),
        )
        self.assertFalse(request.mail_id)

        template.report_template_ids = self.env.ref("plasticos_logistics.action_report_purchase_order_supplier")
        other = self.env["res.partner"].create(
            {
                "name": "Second Drop Buyer",
                "is_company": True,
                "street": "12 Other Dock",
                "city": "Harbor",
                "zip": "99502",
                "phone": "907-555-0199",
            }
        )
        second = self._new_po(dest_address_id=other.id)
        second.button_confirm()
        self.assertEqual(self._requests(second).state, "queued")

    def test_dropship_with_an_audience_safe_report_is_issued(self):
        """A dropship PO queues a real supplier-copy PDF, and the sink sends those bytes."""
        self._set_mode("live")
        self.env["res.lang"]._activate_lang("fr_FR")
        self.supplier.lang = "fr_FR"
        buyer = self._dropship_buyer()
        po = self._new_po(dest_address_id=buyer.id)
        self.assertEqual(po.dest_address_id, buyer)
        self.assertEqual(po.partner_id.lang, "fr_FR")

        captured = []
        report_model = type(self.env["ir.actions.report"])
        original = report_model._render_qweb_pdf

        def spy(self_report, report_ref, res_ids=None, data=None):
            content, report_format = original(self_report, report_ref, res_ids=res_ids, data=data)
            report = report_ref if getattr(report_ref, "report_name", None) else self_report._get_report(report_ref)
            captured.append((report.report_name, content, report_format))
            return content, report_format

        with patch.object(report_model, "_render_qweb_pdf", spy):
            po.button_confirm()

        request = self._requests(po)
        self.assertEqual(request.state, "queued")
        self.assertFalse(request.state_reason)
        mail = request.mail_id
        self.assertEqual(mail.email_to, SUPPLIER_EMAIL)
        self.assertFalse(mail.recipient_ids)
        self.assertFalse(mail.email_cc)
        attachment = mail.attachment_ids
        self.assertEqual(len(attachment), 1)
        self.assertTrue(attachment.name.startswith(f"Purchase Order - {po.name}."))
        document = bytes(attachment.raw)
        supplier_renders = [item for item in captured if item[0] == SUPPLIER_PO_REPORT]
        self.assertEqual([item[1] for item in supplier_renders], [document])
        self.assertFalse([item for item in captured if item[0] == "purchase.report_purchaseorder"])

        supplier_html = self.env["ir.actions.report"]._render_qweb_html(SUPPLIER_PO_REPORT, po.ids)[0].decode()
        pdf = self._pdf_of_report_html(document)
        self.assertTrue(pdf.startswith(b"%PDF"))
        pdf_text = self._pdf_text(pdf)
        for marker in self._buyer_markers(buyer):
            self.assertNotIn(marker, mail.body_html or "")
            self.assertNotIn(marker, supplier_html)
            self.assertNotIn(marker, pdf_text)

        with self._mail_sink() as sink:
            self._process_queue(request)
        self.assertEqual(len(sink), 1)
        self.assertEqual(sink[0]["To"], SUPPLIER_EMAIL)
        self.assertNotIn(buyer.email, sink[0].as_string())
        self.assertIn(document, self._mime_payloads(sink[0]))
        self.assertEqual(request.state, "sent")

        other = self.env["res.partner"].create(
            {
                "name": "Other Drop Buyer",
                "is_company": True,
                "street": "44 North Wharf",
                "city": "Coldport",
                "zip": "99601",
                "phone": "907-555-0177",
            }
        )
        second = self._new_po(dest_address_id=other.id)
        second.button_confirm()
        second_request = self._requests(second)
        self.assertEqual(second_request.state, "queued")
        second_document = bytes(second_request.mail_id.attachment_ids.raw)
        second_text = self._pdf_text(self._pdf_of_report_html(second_document))
        for marker in self._buyer_markers(other):
            self.assertNotIn(marker, second_text)

    def test_dropship_send_ignores_a_cached_report(self):
        """A PDF already stored on the PO is not the attachment Linda queues."""
        self._set_mode("live")
        buyer = self._dropship_buyer()
        report = self.env.ref("plasticos_logistics.action_report_purchase_order_supplier")
        report.attachment = "'Linda-PO-%s.pdf' % object.name"
        po = self._new_po(dest_address_id=buyer.id)
        poison = b"%PDF-1.4\n900 Hidden Pier Secret Buyer Holdings 99501 907-555-0148\n"
        cached = self.env["ir.attachment"].create(
            {
                "name": f"Linda-PO-{po.name}.pdf",
                "res_model": PURCHASE_ORDER,
                "res_id": po.id,
                "raw": poison,
                "mimetype": "application/pdf",
            }
        )
        self.assertEqual(report.retrieve_attachment(po), cached)
        seen = {}
        report_model = type(self.env["ir.actions.report"])
        original = report_model._render_qweb_pdf

        def spy(self_report, report_ref, res_ids=None, data=None):
            seen["no_cache"] = bool(self_report.env.context.get("report_pdf_no_attachment"))
            return original(self_report, report_ref, res_ids=res_ids, data=data)

        with patch.object(report_model, "_render_qweb_pdf", spy):
            po.button_confirm()
        self.assertTrue(seen.get("no_cache"))
        attachment = self._requests(po).mail_id.attachment_ids
        self.assertEqual(len(attachment), 1)
        document = bytes(attachment.raw)
        self.assertNotEqual(document, poison)
        pdf_text = self._pdf_text(self._pdf_of_report_html(document))
        for marker in self._buyer_markers(buyer):
            self.assertNotIn(marker, pdf_text)

    def test_dropship_address_change_blocks_the_queued_send(self):
        """A buyer street change after queue cancels that send."""
        self._set_mode("live")
        buyer = self._dropship_buyer()
        po = self._new_po(dest_address_id=buyer.id)
        po.button_confirm()
        request = self._requests(po)
        self.assertEqual(request.state, "queued")
        buyer.street = "44 Changed Wharf"
        with self._mail_sink() as sink:
            self._process_queue(request)
        self.assertFalse(sink)
        self.assertEqual((request.state, request.state_reason), ("canceled", "payload_changed"))

    def test_dropship_report_that_cannot_be_proven_fails_closed(self):
        """One unreadable supplier report blocks that send and does not ban every dropship PO."""
        self._set_mode("live")
        self._dropship_buyer()
        po = self._new_po(dest_address_id=self.buyer.id)

        def unreadable(self_report, report_name, res_ids, data=None):
            raise RuntimeError("report renderer unavailable")

        with patch.object(type(self.env["ir.actions.report"]), "_render_qweb_html", unreadable):
            po.button_confirm()
        request = self._requests(po)
        self.assertEqual((request.state, request.state_reason), ("blocked", "dropship_report_unproven"))
        self.assertFalse(request.mail_id)

        second = self._new_po(dest_address_id=self.buyer.id)
        second.button_confirm()
        self.assertEqual(self._requests(second).state, "queued")
        self.assertTrue(self._requests(second).mail_id)

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

    def test_personal_server_throttling_is_not_an_attempt(self):
        """Native personal-server deferral must not create false transport evidence."""
        from datetime import datetime, timedelta

        self._set_mode("live")
        # Native Odoo permits personal SMTP only to the creating user of the
        # outgoing mail message. A dedicated user avoids ownership false-positives.
        owner = new_test_user(
            self.env,
            login="linda_throttle_owner",
            groups="purchase.group_purchase_manager",
            email="linda-owner@example.com",
        )
        po = self._new_po()
        po.with_user(owner).button_confirm()
        request = self._requests(po)
        personal = (
            self.env["ir.mail_server"]
            .sudo()
            .create(
                {
                    "name": "Linda isolated throttle test server",
                    "smtp_host": "127.0.0.1",
                    "smtp_port": 25,
                    "owner_user_id": owner.id,
                }
            )
        )
        self.assertEqual(request.mail_id.mail_message_id.create_uid, owner)
        request.mail_id.write({"mail_server_id": personal.id})
        # Odoo's throttle uses server-local datetime.now(), not fields.Datetime.now().
        personal.write(
            {
                "owner_limit_time": datetime.now().replace(second=0, microsecond=0),
                "owner_limit_count": personal._get_personal_mail_servers_limit(),
            }
        )
        with self._mail_sink() as sink:
            self._process_queue(request)
        self.assertFalse(sink)
        self.assertEqual((request.state, request.send_attempt_count), ("queued", 0))
        self.assertEqual(request.mail_id.state, "outgoing")
        self.assertTrue(request.mail_id.scheduled_date, "native personal-server throttle deferred it")

        personal.write(
            {
                "owner_limit_time": datetime.now() - timedelta(minutes=2),
                "owner_limit_count": 0,
            }
        )
        request.mail_id.scheduled_date = False
        with self._mail_sink() as sink:
            self._process_queue(request)
        self.assertEqual(len(sink), 1)
        self.assertEqual((request.state, request.send_attempt_count), ("sent", 1))

    def test_personal_server_wrong_owner_is_rejected(self):
        """Native ACL refuses a personal SMTP server owned by another user."""
        self._set_mode("live")
        owner = new_test_user(
            self.env,
            login="linda_mail_owner",
            groups="purchase.group_purchase_manager",
            email="linda-mail-owner@example.com",
        )
        stranger = new_test_user(
            self.env,
            login="linda_mail_stranger",
            groups="base.group_user",
            email="linda-stranger@example.com",
        )
        po = self._new_po()
        po.with_user(owner).button_confirm()
        request = self._requests(po)
        personal = (
            self.env["ir.mail_server"]
            .sudo()
            .create(
                {
                    "name": "Linda wrong-owner server",
                    "smtp_host": "127.0.0.1",
                    "smtp_port": 25,
                    "owner_user_id": stranger.id,
                }
            )
        )
        with self.assertRaises(ValidationError):
            request.mail_id.write({"mail_server_id": personal.id})
        self.assertEqual((request.state, request.send_attempt_count), ("queued", 0))
        self.assertFalse(request.mail_id.mail_server_id)

    def test_second_claim_does_not_send(self):
        """The worker that loses the request-row claim does not open SMTP."""
        self._set_mode("live")
        po = self._new_po()
        po.button_confirm()
        request = self._requests(po)
        mail = request.mail_id
        self.assertEqual(mail._linda_claim_outgoing(mail), "claimed")
        with self._mail_sink() as sink:
            mail._send(auto_commit=False)
        self.assertFalse(sink)
        self.assertEqual(request.send_attempt_count, 1)
        self.assertEqual(mail.state, "outgoing")
        self.assertEqual(mail._linda_claim_outgoing(mail), "skip")

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

    # ── cancellation notice and release cycles (SUPERSESSION 2026-10-24) ──

    def test_sent_po_cancel_notifies_supplier_once(self):
        """AC-02/AC-06/AC-07/AC-23: one supplier notice, inert reset, no repeat on repeated cancel."""
        sale_count = self.env["sale.order"].search_count([])
        po, first = self._sent_po()

        po.button_cancel()

        notice = self._notices(po)
        self.assertEqual(len(notice), 1)
        self.assertEqual(
            (notice.state, notice.origin_request_id, notice.partner_id, notice.recipient_email, notice.company_id),
            ("queued", first, self.supplier, SUPPLIER_EMAIL, self.company),
        )
        self.assertFalse(notice.sale_order_id)
        self.assertEqual((first.state, first.cycle_closed), ("sent", True), "issue evidence stays sent")
        mail = notice.mail_id
        self.assertEqual((mail.state, mail.email_to), ("outgoing", SUPPLIER_EMAIL))
        self.assertIn(LINDA_SENDER, mail.email_from)
        self.assertFalse(mail.email_cc)
        self.assertFalse(mail.recipient_ids, "recipients come from the request, never followers")
        self.assertFalse(mail.attachment_ids, "a cancellation carries no PO PDF")
        self.assertEqual(mail.subject, f"CANCELED: Purchase Order {po.name}")
        self.assertIn(po.name, mail.body_html)
        self.assertIn("has been canceled", mail.body_html)
        for secret in (self.buyer.name, self.buyer.email, "0.12", self.supplier.name):
            self.assertNotIn(secret, f"{mail.subject} {mail.body_html} {mail.email_to}")

        po.button_cancel()
        po.write({"state": "cancel"})
        po.button_draft()
        self.assertEqual(po.state, "draft")
        self.assertEqual(self._notices(po), notice, "repeated cancel creates no second notice")
        self.assertEqual(self._requests(po), first, "reset to draft issues nothing")
        self.assertEqual(mail.state, "outgoing", "the pending notice survives the reset")
        self.assertEqual(self.env["sale.order"].search_count([]), sale_count, "no SO is invented")

        with self._mail_sink() as sink:
            self._process_queue(notice)
        self.assertEqual(len(sink), 1)
        self.assertEqual((sink[0]["To"], sink[0]["Cc"]), (SUPPLIER_EMAIL, None))
        self.assertEqual(notice.state, "sent")
        with self._mail_sink() as sink:
            self.env["mail.mail"].process_email_queue()
        self.assertFalse(self._to_supplier(sink), "AC-18: a sent notice is never replayed")

    def test_raw_cancel_write_does_not_queue_a_notice(self):
        """A state write skips native cancel guards and must not synthesize a notice."""
        po, first = self._sent_po()
        mail_count = self.env["mail.mail"].search_count([])

        po.write({"state": "cancel"})

        self.assertEqual(po.state, "cancel")
        self.assertFalse(self._notices(po))
        self.assertFalse(first.cycle_closed)
        self.assertEqual(self.env["mail.mail"].search_count([]), mail_count)

    def test_ordinary_outgoing_mail_does_not_lock_linda_requests(self):
        """Non-Linda mail is sent without flushing or locking the request table."""
        mail = (
            self.env["mail.mail"]
            .sudo()
            .create(
                {
                    "subject": "Ordinary warehouse note",
                    "email_from": "warehouse@example.com",
                    "email_to": "dock@example.com",
                    "body_html": "<p>not linda</p>",
                }
            )
        )
        statements = []
        cursor = self.env.cr
        original_execute = cursor.execute

        def record_execute(self_cursor, query, params=None, *args, **kwargs):
            statements.append(query if isinstance(query, str) else "")
            return original_execute(query, params, *args, **kwargs)

        flushed = []
        request_model = type(self.env[LOGISTICS_REQUEST])
        original_flush = request_model.flush_model

        def record_flush(records, fnames=None):
            if records._name == LOGISTICS_REQUEST:
                flushed.append(records._name)
            return original_flush(records, fnames)

        with (
            patch.object(type(cursor), "execute", record_execute),
            patch.object(request_model, "flush_model", record_flush),
            self._mail_sink() as sink,
        ):
            mail._send(auto_commit=False)
        self.assertFalse(flushed)
        self.assertFalse(any("FOR UPDATE" in sql and "plasticos_logistics_request" in sql for sql in statements))
        self.assertEqual(len(sink), 1)
        self.assertEqual(mail.state, "sent")

    def test_unchanged_reconfirm_after_cancel_is_a_new_cycle(self):
        """AC-09/AC-17/probes 3, 6, 7: notice first, then a new issue revision, each delivered once."""
        po, first = self._sent_po()
        po.button_cancel()
        notice = self._notices(po)
        po.button_draft()
        po.button_confirm()

        self.assertEqual(po.state, "purchase")
        second = self._requests(po) - first
        self.assertEqual((second.revision, second.state), (2, "queued"))
        self.assertEqual(second.payload_fingerprint, first.payload_fingerprint, "terms did not change")
        self.assertNotEqual(second.mail_id, first.mail_id, "a new native mail, not a replay of the old one")
        self.assertTrue(second.mail_id.attachment_ids.name.startswith(f"Purchase Order - {po.name}."))
        self.assertEqual(notice.state, "queued", "the notice still reports the real cancellation")

        with self._mail_sink() as sink:
            self._process_queue(second)
        self.assertFalse(sink, "the reissue never overtakes the pending cancellation notice")
        self.assertEqual((second.state, second.send_attempt_count, second.mail_id.state), ("queued", 0, "outgoing"))

        with self._mail_sink() as sink:
            self.env["mail.mail"].process_email_queue()
        delivered = self._to_supplier(sink)
        self.assertEqual([message["Subject"] for message in delivered], [f"CANCELED: Purchase Order {po.name}"])
        (notice | second).invalidate_recordset()
        self.assertEqual((notice.state, second.state, second.send_attempt_count), ("sent", "queued", 0))

        with self._mail_sink() as sink:
            self.env["mail.mail"].process_email_queue()
        delivered = self._to_supplier(sink)
        self.assertEqual(len(delivered), 1)
        (notice | second).invalidate_recordset()
        self.assertEqual((notice.state, second.state), ("sent", "sent"))

        po.button_approve()
        self.Request._issue_purchase_orders(po)
        with self._mail_sink() as sink:
            self.env["mail.mail"].process_email_queue()
        self.assertFalse(self._to_supplier(sink), "AC-10: the new cycle does not repeat itself")
        self.assertEqual(self._requests(po), first | second)

    def test_two_step_reapproval_after_cancel_issues_once(self):
        """AC-09/AC-21: native two-step approval still gates the new cycle."""
        self.company.write({"po_double_validation": "two_step", "po_double_validation_amount": 100.0})
        self._set_mode("live")
        po = self._new_po()
        po.with_user(self.buyer_clerk).button_confirm()
        po.with_user(self.manager).button_approve()
        first = self._requests(po)
        with self._mail_sink():
            self._process_queue(first)
        po.with_user(self.manager).button_cancel()
        po.with_user(self.manager).button_draft()

        po.with_user(self.buyer_clerk).button_confirm()
        self.assertEqual(po.state, "to approve")
        self.assertEqual(self._requests(po), first, "'to approve' is not a release")
        po.with_user(self.manager).button_approve()
        self.assertEqual((self._requests(po) - first).revision, 2)
        self.assertEqual(len(self._notices(po)), 1)

    def test_two_cancellation_cycles_create_two_notices(self):
        """AC-11: each cycle's cancellation is its own obligation, delivered once."""
        po, first = self._sent_po()
        po.button_cancel()
        po.button_draft()
        po.button_confirm()
        with self._mail_sink():
            self.env["mail.mail"].process_email_queue()
            self.env["mail.mail"].process_email_queue()
        second = self._requests(po) - first
        self.assertEqual(second.state, "sent")

        po.button_cancel()
        notices = self._notices(po)
        self.assertEqual(len(notices), 2)
        self.assertEqual(notices.origin_request_id, first | second)
        self.assertEqual(sorted(notices.mapped("revision")), [1, 2])
        with self._mail_sink() as sink:
            self.env["mail.mail"].process_email_queue()
        self.assertEqual(len(self._to_supplier(sink)), 1, "the first cycle's notice was already delivered")
        self.assertEqual(set(notices.mapped("state")), {"sent"})

    def test_amendment_after_cancel_issues_the_new_terms(self):
        """AC-12: the reopened, amended order issues its new terms; old history is immutable."""
        po, first = self._sent_po()
        po.button_cancel()
        po.button_draft()
        po.write({"order_line": [(1, po.order_line.id, {"price_unit": 0.14})]})
        po.button_confirm()
        second = self._requests(po) - first
        self.assertEqual(second.payload_fingerprint, self.Request._po_fingerprint(po))
        self.assertNotEqual(second.payload_fingerprint, first.payload_fingerprint)
        self.assertEqual((first.state, first.mail_id.state), ("sent", "sent"))
        self.assertEqual(self._notices(po).origin_request_id, first)

    def test_failed_vs_uncertain_issue_on_cancel(self):
        """AC-04: proven undelivered sends no notice; an attempted, unknown outcome does."""
        self._set_mode("live")
        refused_po, generic_po, inflight_po = self._new_po(), self._new_po(price=0.13), self._new_po(price=0.14)
        (refused_po | generic_po | inflight_po).button_confirm()

        def refuse(*args, **kwargs):
            raise ConnectionRefusedError("smtp down")

        with self._mail_sink(), patch.object(type(self.env["ir.mail_server"]), "_connect__", refuse):
            self._process_queue(self._requests(refused_po))
        with self.assertLogs(MAIL_LOGGER, level="ERROR"), self._mail_sink(error=MailDeliveryException("timeout")):
            self._process_queue(self._requests(generic_po))
        inflight = self._requests(inflight_po)
        # The state a crash mid-SMTP leaves behind: attempt committed, mail still outgoing.
        inflight.write({"send_attempt_count": 1})
        self.assertEqual((self._requests(refused_po).state, self._requests(generic_po).state), ("exception", "unknown"))

        (refused_po | generic_po | inflight_po).button_cancel()

        self.assertFalse(self._notices(refused_po), "a proven undelivered issue is not retracted")
        self.assertEqual(self._notices(generic_po).state, "queued")
        self.assertEqual((inflight.state, inflight.mail_id.state), ("unknown", "cancel"))
        self.assertEqual(self._notices(inflight_po).state, "queued")
        self.assertEqual(self._requests(generic_po).state, "unknown", "never relabeled sent")

    def test_notice_goes_only_to_the_historical_audience(self):
        """AC-13/probe 5: a contact or party change after the send never redirects the notice."""
        po, first = self._sent_po()
        other = self.env["res.partner"].create(
            {"name": "Other Supplier", "is_company": True, "supplier_rank": 1, "email": "other@supplier.example"}
        )
        self.supplier.email = "new-desk@acme-regrind.example"
        po.write({"partner_id": other.id})

        po.button_cancel()

        notice = self._notices(po)
        self.assertEqual(len(notice), 1)
        self.assertEqual((notice.partner_id, notice.recipient_email), (self.supplier, SUPPLIER_EMAIL))
        with self._mail_sink() as sink:
            self.env["mail.mail"].process_email_queue()
        self.assertEqual([message["To"] for message in sink], [SUPPLIER_EMAIL])

    def test_rejected_native_cancel_creates_nothing(self):
        """AC-16/probe 1: a locked PO refuses cancellation; no notice, no state change."""
        po, first = self._sent_po()
        po.button_lock()
        with self.assertRaises(UserError):
            po.button_cancel()
        self.assertEqual((po.state, first.cycle_closed), ("purchase", False))
        self.assertFalse(self._notices(po))

    def test_cancel_modes_and_contexts_send_no_notice(self):
        """AC-15: shadow records without mail; off, unknown modes and non-release contexts send nothing."""
        shadow_po, _first = self._sent_po()
        self._set_mode("shadow")
        shadow_po.button_cancel()
        notice = self._notices(shadow_po)
        self.assertEqual((notice.state, bool(notice.mail_id)), ("shadow", False))
        self.assertIn(shadow_po.name, notice.subject)

        for mode in ("off", "LIVE-ish"):
            po, first = self._sent_po()
            self._set_mode(mode)
            po.button_cancel()
            self.assertFalse(self._notices(po), mode)
            self.assertTrue(first.cycle_closed, "the cycle still ends")
        for key in ("import_mode", "install_mode", "skip_automations"):
            po, first = self._sent_po()
            po.with_context(**{key: True}).button_cancel()
            self.assertEqual(po.state, "cancel")
            self.assertFalse(self._notices(po), key)

    def test_notice_transport_outcomes_are_not_retried(self):
        """AC-18: notice failures are discriminated and never auto-retried."""
        refused_po, _ = self._sent_po()
        generic_po, _ = self._sent_po(price=0.13)
        (refused_po | generic_po).button_cancel()
        refused, generic = self._notices(refused_po), self._notices(generic_po)

        def refuse(*args, **kwargs):
            raise ConnectionRefusedError("smtp down")

        with self._mail_sink(), patch.object(type(self.env["ir.mail_server"]), "_connect__", refuse):
            self._process_queue(refused)
        with self.assertLogs(MAIL_LOGGER, level="ERROR"), self._mail_sink(error=MailDeliveryException("timeout")):
            self._process_queue(generic)
        self.assertEqual((refused.state, generic.state), ("exception", "unknown"))
        with self._mail_sink() as sink:
            self._process_queue(refused)
            self._process_queue(generic)
        self.assertFalse(sink)

    def test_notice_render_failure_keeps_native_cancel(self):
        """A notice that cannot be queued is recorded blocked; the native cancellation stands."""
        po, _first = self._sent_po()
        template_class = type(self.env["mail.template"])

        def broken(*args, **kwargs):
            raise ValueError("render crashed")

        with (
            patch.object(template_class, "send_mail", broken),
            self.assertLogs("odoo.addons.plasticos_logistics.models.linda_request", level="ERROR"),
        ):
            po.button_cancel()
        self.assertEqual(po.state, "cancel")
        self.assertEqual((self._notices(po).state, self._notices(po).state_reason), ("blocked", "render_failed"))

    def test_purchase_user_cancel_records_notice_but_cannot_forge_one(self):
        """AC-20: an authorized cancel records the notice via Linda's sudo; the user cannot forge or edit."""
        po, first = self._sent_po()
        po.with_user(self.buyer_clerk).button_cancel()
        notice = self._notices(po)
        self.assertEqual(notice.state, "queued")
        as_user = notice.with_user(self.buyer_clerk)
        for vals in ({"state": "sent"}, {"recipient_email": "attacker@example.com"}, {"mail_id": False}):
            with self.assertRaises(AccessError):
                as_user.write(vals)
        with self.assertRaises(AccessError):
            self.Request.with_user(self.buyer_clerk).create(
                {
                    "company_id": self.company.id,
                    "purpose": PO_CANCEL,
                    "purchase_order_id": po.id,
                    "partner_id": self.supplier.id,
                    "revision": 9,
                    "payload_fingerprint": "forged",
                    "origin_request_id": first.id,
                }
            )
        with self.assertRaises(UserError):
            as_user.unlink()
        self.assertEqual(notice.state, "queued")

    def test_raw_state_write_does_not_authorize_an_attempted_cancellation(self):
        """A raw cancel write keeps the uncertain attempt and does not queue a notice."""
        self._set_mode("live")
        po = self._new_po()
        po.button_confirm()
        request = self._requests(po)
        request.write({"send_attempt_count": 1})
        mail_count = self.env["mail.mail"].search_count([])

        po.write({"state": "cancel"})

        self.assertEqual(po.state, "cancel")
        self.assertFalse(self._notices(po))
        self.assertFalse(request.cycle_closed)
        self.assertEqual((request.state, request.state_reason), ("unknown", "prior_send_outcome_unknown"))
        self.assertEqual(request.mail_id.state, "cancel")
        self.assertEqual(self.env["mail.mail"].search_count([]), mail_count)

    def test_same_batch_notice_failure_leaves_the_reissue_unattempted(self):
        """A notice that fails in the shared queue run must not hand the reissue to SMTP."""
        po, first = self._sent_po()
        po.button_cancel()
        notice = self._notices(po)
        po.button_draft()
        po.button_confirm()
        second = self._requests(po) - first

        def refuse(*args, **kwargs):
            raise ConnectionRefusedError("smtp down")

        with self._mail_sink(), patch.object(type(self.env["ir.mail_server"]), "_connect__", refuse):
            self.env["mail.mail"].process_email_queue()
        (notice | second).invalidate_recordset()
        self.assertEqual(notice.state, "exception")
        self.assertEqual((second.state, second.send_attempt_count, second.mail_id.state), ("queued", 0, "outgoing"))

        with self._mail_sink() as sink:
            self.env["mail.mail"].process_email_queue()
        self.assertFalse(self._to_supplier(sink))
        second.invalidate_recordset()
        self.assertEqual(second.send_attempt_count, 0)

    def test_unknown_notice_from_an_earlier_batch_holds_the_reissue(self):
        """A previous unknown notice still gates the replacement order."""
        po, first = self._sent_po()
        po.button_cancel()
        notice = self._notices(po)
        with self.assertLogs(MAIL_LOGGER, level="ERROR"), self._mail_sink(error=MailDeliveryException("timeout")):
            self._process_queue(notice)
        self.assertEqual(notice.state, "unknown")
        po.button_draft()
        po.button_confirm()
        second = self._requests(po) - first

        with self._mail_sink() as sink:
            self.env["mail.mail"].process_email_queue()
        self.assertFalse(self._to_supplier(sink))
        second.invalidate_recordset()
        self.assertEqual((second.state, second.send_attempt_count), ("queued", 0))
