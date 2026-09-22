"""Regression coverage for server-resolved Odoo chat intent receipts."""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "plasticos", "mack_workbench")
class TestMackChatIntentReceipt(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing(
            "plasticos.mack.chat.intent.receipt",
            "plasticos.intake",
            "mail.message",
        )
        cls.Receipt = cls.env["plasticos.mack.chat.intent.receipt"]

    def _canonical_intake_with_message(self, body="Please review this HDPE offer."):
        intake = self._create_intake()
        message = intake.message_post(body=body, message_type="comment", subtype_xmlid="mail.mt_note")
        return intake, message

    def test_server_resolves_native_message_actor_and_canonical_snapshot(self):
        intake, message = self._canonical_intake_with_message()
        activity_count = len(intake.activity_ids)
        message_count = len(intake.message_ids)
        canonical_write_date = intake.write_date

        response = self.Receipt.record_intent_from_source_message(
            intake.id,
            message.id,
            "consult",
        )
        receipt = self.Receipt.browse(response["receipt_id"])

        self.assertEqual(response["receipt_ref"], receipt.name)
        self.assertEqual(response["state"], "recorded")
        self.assertEqual(response["source_message_id"], message.id)
        self.assertEqual(receipt.company_id, self.env.company)
        self.assertEqual(receipt.actor_user_id, self.env.user)
        self.assertEqual(receipt.actor_partner_id, self.env.user.partner_id)
        self.assertEqual(receipt.intake_id, intake)
        self.assertEqual(receipt.source_message_id, message)
        self.assertEqual(receipt.source_message_date, message.date)
        self.assertEqual(receipt.canonical_write_date, canonical_write_date)
        self.assertEqual(receipt.intent_kind, "consult")
        self.assertEqual(receipt.state, "recorded")
        self.assertEqual(receipt.attachment_refs, [])
        self.assertEqual(len(intake.activity_ids), activity_count)
        self.assertEqual(len(intake.message_ids), message_count)

    def test_idempotent_replay_returns_prior_receipt_only_for_same_material(self):
        intake, message = self._canonical_intake_with_message()

        first = self.Receipt.record_intent_from_source_message(intake.id, message.id, "draft_edit")
        second = self.Receipt.record_intent_from_source_message(intake.id, message.id, "draft_edit")

        self.assertEqual(first, second)
        self.assertEqual(
            self.Receipt.search_count([("source_message_id", "=", message.id)]),
            1,
        )
        with self.assertRaises(ValidationError):
            self.Receipt.record_intent_from_source_message(intake.id, message.id, "prepare_request")

    def test_forged_source_thread_and_attachment_reference_fail_closed(self):
        intake, message = self._canonical_intake_with_message()
        other_intake, _other_message = self._canonical_intake_with_message(body="Unrelated intake message.")
        unrelated_message = self.env.user.partner_id.message_post(
            body="This does not belong to an intake thread.",
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )

        with self.assertRaises(ValidationError):
            self.Receipt.record_intent_from_source_message(intake.id, unrelated_message.id, "consult")
        with self.assertRaises(ValidationError):
            self.Receipt.record_intent_from_source_message(other_intake.id, message.id, "consult")
        with self.assertRaises(ValidationError):
            self.Receipt.record_intent_from_source_message(intake.id, message.id, "consult", attachment_ids=[999999])

    def test_verified_message_attachment_reference_is_recorded_without_copying_payload(self):
        intake = self._create_intake()
        message = intake.message_post(
            body="The attached specification supports a consult request.",
            message_type="comment",
            subtype_xmlid="mail.mt_note",
            attachments=[("specification.txt", b"HDPE specification evidence")],
        )
        attachment = message.attachment_ids
        self.assertEqual(len(attachment), 1)

        response = self.Receipt.record_intent_from_source_message(
            intake.id,
            message.id,
            "consult",
            attachment_ids=[attachment.id],
        )
        receipt = self.Receipt.browse(response["receipt_id"])

        self.assertEqual(
            receipt.attachment_refs,
            [{"attachment_id": attachment.id, "checksum": attachment.checksum or None}],
        )
        self.assertNotIn("HDPE specification evidence", str(receipt.attachment_refs))

    def test_generic_creation_mutation_and_deletion_are_denied(self):
        intake, message = self._canonical_intake_with_message()
        response = self.Receipt.record_intent_from_source_message(intake.id, message.id, "consult")
        receipt = self.Receipt.browse(response["receipt_id"])

        with self.assertRaises(AccessError):
            self.Receipt.create({})
        with self.assertRaises(AccessError):
            receipt.write({"intent_kind": "draft_edit"})
        with self.assertRaises(AccessError):
            receipt.unlink()
