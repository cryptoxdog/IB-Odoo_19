"""Regression coverage for server-resolved Odoo chat intent receipts."""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import tagged
from odoo.tools import mute_logger


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
        # No verified attachments: Odoo's Json column stores [] as SQL NULL and
        # reads it back as False, so the receipt carries no references at all.
        self.assertFalse(receipt.attachment_refs)
        self.assertEqual(len(intake.activity_ids), activity_count)
        self.assertEqual(len(intake.message_ids), message_count)

    def test_same_message_replays_to_prior_receipt_and_different_intent_kind_is_refused(self):
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

    def test_replay_after_a_later_intake_edit_returns_the_original_receipt(self):
        """F191-01: canonical_write_date is historical evidence, never replay material."""
        intake, message = self._canonical_intake_with_message()
        first = self.Receipt.record_intent_from_source_message(intake.id, message.id, "consult")
        receipt = self.Receipt.browse(first["receipt_id"])
        original_snapshot = receipt.canonical_write_date

        intake.write({"quantity_per_load_lbs": 42000})
        self.env.flush_all()
        # Inside one test transaction every ORM write stamps the same cr.now(), so
        # the edit alone cannot move write_date the way a later, separate request
        # does. Push the timestamp forward exactly as that later transaction would.
        self.env.cr.execute(
            "UPDATE plasticos_intake SET write_date = write_date + interval '1 minute' WHERE id = %s",
            (intake.id,),
        )
        intake.invalidate_recordset(["write_date"])
        self.assertNotEqual(intake.write_date, original_snapshot)

        replay = self.Receipt.record_intent_from_source_message(intake.id, message.id, "consult")

        self.assertEqual(replay, first)
        self.assertEqual(self.Receipt.search_count([("source_message_id", "=", message.id)]), 1)
        receipt.invalidate_recordset(["canonical_write_date"])
        self.assertEqual(receipt.canonical_write_date, original_snapshot)
        self.assertNotEqual(receipt.canonical_write_date, intake.write_date)

    @mute_logger("odoo.sql_db")
    def test_unique_collision_inside_create_converges_on_the_stored_receipt(self):
        """F191-01: a session whose pre-check missed the row still gets the winner back."""
        intake, message = self._canonical_intake_with_message()
        first = self.Receipt.record_intent_from_source_message(intake.id, message.id, "consult")
        receipt = self.Receipt.browse(first["receipt_id"])
        values = {
            "company_id": receipt.company_id.id,
            "actor_user_id": receipt.actor_user_id.id,
            "actor_partner_id": receipt.actor_partner_id.id,
            "intake_id": intake.id,
            "source_message_id": message.id,
            "source_message_date": receipt.source_message_date,
            "source_message_body_sha256": receipt.source_message_body_sha256,
            "attachment_refs": [],
            "intent_kind": "consult",
            "canonical_write_date": receipt.canonical_write_date,
            "idempotency_key": receipt.idempotency_key,
            "state": "recorded",
        }

        # Drive the insert path directly, exactly as the loser of a two-session race
        # does after its search missed: the INSERT takes the unique violation, the
        # savepoint is rolled back, and the stored receipt is re-queried and compared.
        winner = self.Receipt._create_first_receipt(values)

        self.assertEqual(winner, receipt)
        self.assertEqual(self.Receipt.search_count([("source_message_id", "=", message.id)]), 1)
        with self.assertRaises(ValidationError):
            self.Receipt._create_first_receipt(dict(values, intent_kind="draft_edit"))

    def test_read_only_intake_author_can_record_intent(self):
        """F191-02: recording needs only read authority on the intake it never mutates."""
        operator_group = self.env.ref("plasticos_mack_workbench.group_mack_workbench_operator")
        author = self.env["res.users"].create(
            {
                "name": "Mack Chat Author",
                "login": "mack-chat-author",
                "email": "mack-chat-author@example.com",
                "group_ids": [(4, operator_group.id)],
            }
        )
        intake = self._create_intake()
        message = intake.with_user(author).message_post(
            body="Please consult on this HDPE lot.",
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )
        self.assertEqual(message.author_id, author.partner_id)

        # Workflow later withdraws write authority on the intake from the author's role.
        self.env["ir.rule"].create(
            {
                "name": "Test: Mack operators read intakes only",
                "model_id": self.env["ir.model"]._get_id("plasticos.intake"),
                "groups": [(4, operator_group.id)],
                "domain_force": "[(0, '=', 1)]",
                "perm_read": False,
                "perm_write": True,
                "perm_create": True,
                "perm_unlink": True,
            }
        )
        intake_as_author = intake.with_user(author)
        intake_as_author.check_access("read")
        with self.assertRaises(AccessError):
            intake_as_author.check_access("write")

        response = self.Receipt.with_user(author).record_intent_from_source_message(intake.id, message.id, "consult")
        receipt = self.Receipt.browse(response["receipt_id"])

        self.assertEqual(receipt.actor_user_id, author)
        self.assertEqual(receipt.intake_id, intake)
        self.assertEqual(receipt.source_message_id, message)
