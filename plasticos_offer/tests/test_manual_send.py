"""Send Offer is a real email through native Odoo Mail, never a status-only change.

Runs under ``odoo --test-enable``. Odoo does not hand mail to SMTP in test mode
(``ir.mail_server.send_email`` skips sending), so these tests prove the native
outgoing message, its notifications and attachments, and the Sent transition;
they do not and cannot prove external delivery.

``send_offer_email`` is the shared fixture other modules use to put an offer in
Sent the only way the product allows: open Send Offer, submit the composer.
"""

from __future__ import annotations

import base64
from datetime import timedelta
from unittest.mock import patch

from odoo import Command, fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests.common import tagged

PNG_A = base64.b64encode(b"\x89PNG\r\n\x1a\nplasticos-offer-picture-a")
PNG_B = base64.b64encode(b"\x89PNG\r\n\x1a\nplasticos-offer-picture-b")


def ensure_offer_recipient(offer):
    """Fixture: give the buyer one contact with an email when the offer has no deliverable recipient."""
    if offer.recipient_partner_ids or offer.buyer_id.email:
        return offer.recipient_partner_ids or offer.buyer_id
    contact = offer.env["res.partner"].create(
        {
            "name": f"{offer.buyer_id.name} Purchasing",
            "parent_id": offer.buyer_id.id,
            "type": "contact",
            "email": f"purchasing-{offer.buyer_id.id}@buyer.example.com",
        }
    )
    offer.recipient_partner_ids = [Command.link(contact.id)]
    return contact


def open_offer_composer(offer, **composer_vals):
    """Open Send Offer and build its composer exactly as the dialog would. Sends nothing."""
    action = offer.action_send()
    return offer.env["mail.compose.message"].with_context(action["context"]).create(composer_vals)


def send_offer_email(offers, **composer_vals):
    """Fixture: send each offer through Send Offer → native composer → Send."""
    for offer in offers:
        ensure_offer_recipient(offer)
        open_offer_composer(offer, **composer_vals).action_send_mail()
    return offers


@tagged("post_install", "-at_install", "offer", "offer_send", "critical")
class TestOfferManualSend(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.offer")
        cls.Offer = cls.env["plasticos.offer"]
        cls.Attachment = cls.env["ir.attachment"]
        cls.supplier = cls._create_partner("Send Supplier Co", supplier_rank=1, email="sales@supplier.example.com")
        cls.buyer = cls._create_partner("Send Buyer Co", customer_rank=1)
        cls.alice = cls.env["res.partner"].create(
            {"name": "Alice Buyer", "parent_id": cls.buyer.id, "type": "contact", "email": "alice@buyer.example.com"}
        )
        cls.bob = cls.env["res.partner"].create(
            {"name": "Bob Buyer", "parent_id": cls.buyer.id, "type": "contact", "email": "bob@buyer.example.com"}
        )
        cls.other_buyer = cls._create_partner("Other Buyer Co", customer_rank=1)
        cls.carol = cls.env["res.partner"].create(
            {"name": "Carol Other", "parent_id": cls.other_buyer.id, "type": "contact", "email": "carol@other.example"}
        )

    def _offer(self, **vals):
        base = {
            "supplier_id": self.supplier.id,
            "buyer_id": self.buyer.id,
            "price_per_lb": 0.31,
            "quantity_lbs": 40000,
            "loads": 1,
            "valid_until": fields.Date.today() + timedelta(days=14),
            "material_summary": "HDPE Regrind",
            "material_description": "Material: HDPE Regrind\nColor: Natural",
            "recipient_partner_ids": [Command.set((self.alice | self.bob).ids)],
        }
        base.update(vals)
        return self.Offer.create(base)

    def _image(self, name, datas, res_model="res.partner", res_id=None):
        return self.Attachment.create(
            {
                "name": name,
                "datas": datas,
                "mimetype": "image/png",
                "res_model": res_model,
                "res_id": res_id or self.supplier.id,
            }
        )

    def _messages(self, offer):
        return self.env["mail.message"].search(
            [("model", "=", "plasticos.offer"), ("res_id", "=", offer.id), ("message_type", "=", "comment")]
        )

    # ── Opening the composer changes nothing ──────────────────

    def test_send_offer_opens_composer_and_leaves_draft(self):
        picture = self._image("bale.png", PNG_A)
        offer = self._offer(material_image_ids=[Command.set(picture.ids)])
        action = offer.action_send()
        self.assertEqual(action["res_model"], "mail.compose.message")
        self.assertEqual(action["target"], "new")
        context = action["context"]
        self.assertEqual(context["default_partner_ids"], (self.alice | self.bob).ids)
        self.assertEqual(context["default_attachment_ids"], picture.ids)
        self.assertIn("HDPE Regrind", context["default_subject"])
        self.assertIn(offer._plasticos_short_reference(), context["default_subject"])
        self.assertTrue(context["default_notify_skip_followers"])
        self.assertEqual(offer.state, "draft")
        self.assertFalse(self._messages(offer))

    def test_discarded_composer_leaves_draft(self):
        offer = self._offer()
        composer = open_offer_composer(offer)
        composer.unlink()
        self.assertEqual(offer.state, "draft")
        self.assertFalse(offer.sent_message_id)
        self.assertFalse(self._messages(offer))

    # ── Submitting sends through native Odoo Mail ──────────────

    def test_submitted_email_marks_sent_with_mail_evidence(self):
        picture = self._image("bale.png", PNG_A)
        offer = self._offer(material_image_ids=[Command.set(picture.ids)])
        composer = open_offer_composer(offer, subject="Edited subject for buyer", body="<p>Edited body</p>")
        composer.action_send_mail()

        self.assertEqual(offer.state, "sent")
        message = offer.sent_message_id
        self.assertTrue(message)
        self.assertTrue(offer.sent_date)
        self.assertEqual(message.model, "plasticos.offer")
        self.assertEqual(message.res_id, offer.id)
        self.assertEqual(message.subject, "Edited subject for buyer")
        self.assertIn("Edited body", str(message.body))
        self.assertEqual(message.partner_ids, self.alice | self.bob)
        notified = (
            self.env["mail.notification"]
            .sudo()
            .search([("mail_message_id", "=", message.id), ("notification_type", "=", "email")])
            .mapped("res_partner_id")
        )
        self.assertEqual(notified, self.alice | self.bob)
        self.assertEqual(len(message.attachment_ids), 1)
        sent_picture = message.attachment_ids
        self.assertEqual(sent_picture.res_model, "plasticos.offer", "the sent picture is stored on the offer")
        self.assertEqual(sent_picture.res_id, offer.id)
        self.assertEqual(sent_picture.checksum, picture.checksum, "same bytes as the source picture")
        self.assertEqual(sent_picture.mimetype, "image/png")
        self.assertEqual(picture.res_model, "res.partner", "the source picture keeps its owner")

    def test_removed_source_picture_does_not_break_the_sent_email(self):
        picture = self._image("bale.png", PNG_A)
        offer = self._offer(material_image_ids=[Command.set(picture.ids)])
        send_offer_email(offer)
        sent_picture = offer.sent_message_id.attachment_ids
        picture.unlink()
        self.assertTrue(sent_picture.exists())
        self.assertEqual(base64.b64decode(sent_picture.datas), base64.b64decode(PNG_A))

    def test_duplicate_picture_content_is_attached_once(self):
        first = self._image("bale.png", PNG_A)
        same_bytes = self._image("bale-copy.png", PNG_A)
        other = self._image("closeup.png", PNG_B)
        offer = self._offer(material_image_ids=[Command.set((first | same_bytes | other).ids)])
        self.assertEqual(set(offer.action_send()["context"]["default_attachment_ids"]), {first.id, other.id})
        send_offer_email(offer)
        self.assertEqual(len(offer.sent_message_id.attachment_ids), 2)

    def test_followers_are_not_notified(self):
        outsider = self.env["res.partner"].create({"name": "Follower Outsider", "email": "outsider@example.com"})
        offer = self._offer()
        offer.message_subscribe(partner_ids=(outsider | self.supplier).ids)
        send_offer_email(offer)
        notified = (
            self.env["mail.notification"]
            .sudo()
            .search([("mail_message_id", "=", offer.sent_message_id.id)])
            .mapped("res_partner_id")
        )
        self.assertNotIn(outsider, notified)
        self.assertNotIn(self.supplier, notified)
        self.assertEqual(notified, self.alice | self.bob)

    # ── Refusals: the offer stays Draft and nothing is posted ──

    def test_cross_buyer_recipient_is_refused_at_submit(self):
        offer = self._offer()
        composer = open_offer_composer(offer)
        composer.partner_ids = [Command.link(self.carol.id)]
        with self.assertRaisesRegex(UserError, "may only be emailed to contacts of"):
            composer.action_send_mail()
        self.assertEqual(offer.state, "draft")
        self.assertFalse(self._messages(offer))

    def test_recipient_on_the_offer_must_belong_to_the_buyer(self):
        offer = self._offer(recipient_partner_ids=[Command.set(self.carol.ids)])
        with self.assertRaisesRegex(UserError, "may only be emailed to contacts of"):
            offer.action_send()

    def test_no_deliverable_recipient_blocks_send(self):
        offer = self._offer(recipient_partner_ids=[Command.clear()])
        with self.assertRaisesRegex(UserError, "no email recipient"):
            offer.action_send()
        no_email = self.env["res.partner"].create({"name": "No Email", "parent_id": self.buyer.id, "type": "contact"})
        offer.recipient_partner_ids = [Command.set(no_email.ids)]
        with self.assertRaisesRegex(UserError, "no email address"):
            offer.action_send()

    def test_unpriced_or_empty_offer_cannot_be_sent(self):
        with self.assertRaisesRegex(UserError, "buyer price"):
            self._offer(price_per_lb=0.0).action_send()
        with self.assertRaisesRegex(UserError, "quantity"):
            self._offer(quantity_lbs=0.0).action_send()

    def test_foreign_attachment_is_refused(self):
        offer = self._offer()
        stranger = self._image("other-supplier.png", PNG_B, res_model="res.partner", res_id=self.other_buyer.id)
        composer = open_offer_composer(offer)
        composer.attachment_ids = [Command.link(stranger.id)]
        with self.assertRaisesRegex(UserError, "do not belong to offer"):
            composer.action_send_mail()
        self.assertEqual(offer.state, "draft")

    def test_native_send_failure_records_no_sent_state(self):
        offer = self._offer()
        composer = open_offer_composer(offer)
        with (
            patch.object(type(offer), "message_post", side_effect=RuntimeError("mail transport down")),
            self.assertRaises(RuntimeError),
        ):
            composer.action_send_mail()
        offer.invalidate_recordset()
        self.assertEqual(offer.state, "draft")
        self.assertFalse(offer.sent_message_id)

    def test_replayed_send_does_not_email_twice(self):
        offer = self._offer()
        first = open_offer_composer(offer)
        second = open_offer_composer(offer)
        first.action_send_mail()
        with self.assertRaisesRegex(UserError, "already sent"):
            second.action_send_mail()
        self.assertEqual(len(self._messages(offer)), 1)
        with self.assertRaises(UserError):
            offer.action_send()

    def test_scheduled_offer_email_is_refused(self):
        offer = self._offer()
        composer = open_offer_composer(offer)
        composer.scheduled_date = fields.Datetime.to_string(fields.Datetime.now() + timedelta(days=1))
        with self.assertRaisesRegex(UserError, "Scheduled sending is not available"):
            composer.action_schedule_message()
        self.assertEqual(offer.state, "draft")

    def test_ordinary_composer_on_an_offer_does_not_mark_sent(self):
        offer = self._offer()
        composer = self.env["mail.compose.message"].create(
            {
                "model": "plasticos.offer",
                "res_ids": str([offer.id]),
                "composition_mode": "comment",
                "partner_ids": [Command.set(self.alice.ids)],
                "body": "<p>Question about pickup hours</p>",
            }
        )
        composer.action_send_mail()
        self.assertEqual(offer.state, "draft")

    def test_status_only_sent_write_is_refused(self):
        offer = self._offer()
        with self.assertRaisesRegex(UserError, "can only become Sent"):
            offer.write({"state": "sent"})
        self.assertEqual(offer.state, "draft")

    def test_existing_chatter_message_is_not_send_evidence(self):
        offer = self._offer()
        offer.message_post(body="Internal note", message_type="comment", subtype_xmlid="mail.mt_note")
        for message in offer.message_ids:
            with self.assertRaisesRegex(UserError, "can only become Sent"):
                offer.write({"state": "sent", "sent_message_id": message.id})
        self.assertEqual(offer.state, "draft")

    def test_earlier_send_cannot_be_replayed_after_reset(self):
        offer = self._offer()
        send_offer_email(offer)
        first_message = offer.sent_message_id
        offer.action_reject()
        offer.action_reset_to_draft()
        with self.assertRaisesRegex(UserError, "can only become Sent"):
            offer.write({"state": "sent", "sent_message_id": first_message.id})
        send_offer_email(offer)
        self.assertEqual(offer.state, "sent")
        self.assertGreater(offer.sent_message_id.id, first_message.id)

    def test_duplicated_sent_offer_starts_as_draft(self):
        offer = self._offer()
        send_offer_email(offer)
        duplicate = offer.copy()
        self.assertEqual(duplicate.state, "draft")
        self.assertFalse(duplicate.sent_message_id)

    def test_removed_picture_is_not_emailed(self):
        kept = self._image("kept.png", PNG_A)
        removed = self._image("removed.png", PNG_B, res_model="plasticos.offer")
        offer = self._offer(material_image_ids=[Command.set((kept | removed).ids)])
        removed.res_id = offer.id
        offer.material_image_ids = [Command.unlink(removed.id)]
        self.assertTrue(removed.exists(), "the widget forgets the link; the offer-owned file stays")
        self.assertEqual(offer.action_send()["context"]["default_attachment_ids"], kept.ids)

    def test_body_escapes_material_text(self):
        offer = self._offer(material_description="<script>alert(1)</script>\nColor: <b>Red</b>")
        body = str(offer.action_send()["context"]["default_body"])
        self.assertNotIn("<script>", body)
        self.assertIn("&lt;script&gt;", body)
        self.assertIn("&lt;b&gt;Red&lt;/b&gt;", body)

    def test_sent_content_is_frozen(self):
        offer = self._offer()
        send_offer_email(offer)
        with self.assertRaisesRegex(UserError, "immutable"):
            offer.write({"material_description": "Different material"})
        with self.assertRaisesRegex(UserError, "immutable"):
            offer.write({"recipient_partner_ids": [Command.link(self.carol.id)]})
        with self.assertRaisesRegex(UserError, "immutable"):
            offer.write({"price_per_lb": 0.5})

    # ── Bulk action: no status-only Sent ─────────────────────

    def test_bulk_send_never_marks_several_offers_sent(self):
        offers = self._offer() | self._offer()
        wizard = (
            self.env["plasticos.offer.bulk.action.wizard"]
            .with_context(active_ids=offers.ids)
            .create({"action_type": "send"})
        )
        with self.assertRaisesRegex(UserError, "own composer"):
            wizard.action_execute()
        self.assertEqual(set(offers.mapped("state")), {"draft"})

    def test_bulk_send_of_one_offer_opens_its_composer(self):
        offer = self._offer()
        wizard = (
            self.env["plasticos.offer.bulk.action.wizard"]
            .with_context(active_ids=offer.ids)
            .create({"action_type": "send"})
        )
        action = wizard.action_execute()
        self.assertEqual(action["res_model"], "mail.compose.message")
        self.assertEqual(offer.state, "draft")
