"""B4 posting guard on digitized or emailed vendor bills, and B5 on draft bills."""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests.common import tagged

SUMMARY = "Digitized vendor bill needs manager review"


@tagged("post_install", "-at_install", "accounting", "integrity_controls")
class TestDigitizedBillGuard(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "extract_state" not in cls.env["account.move"]._fields:
            raise AssertionError("BLOCKED: account_invoice_extract is not installed")
        cls.company = cls.env.company
        cls.vendor = cls.env["res.partner"].create({"name": "B4 Trucker", "is_company": True, "supplier_rank": 1})
        internal = cls.env.ref("base.group_user")
        manager_group = cls.env.ref("plasticos_security_base.group_operations_manager")
        cls.manager_group = manager_group
        cls.manager = cls.env["res.users"].create(
            {
                "name": "B4 Operations Manager",
                "login": "b4_ops_manager",
                "group_ids": [(6, 0, [internal.id, manager_group.id])],
            }
        )
        cls.sale = cls.env["sale.order"].create({"partner_id": cls.vendor.id})
        cls.sale_other = cls.env["sale.order"].create({"partner_id": cls.vendor.id})
        cls.tx = cls.env["plasticos.transaction"].create(
            {"supplier_id": cls.vendor.id, "buyer_id": cls.vendor.id, "quantity": 1}
        )
        cls.company_b = cls.env["res.company"].create({"name": "B4 Other Company"})
        cls.purchase_b = (
            cls.env["purchase.order"]
            .with_company(cls.company_b)
            .create({"partner_id": cls.vendor.id, "company_id": cls.company_b.id})
        )
        cls.counter = 0

    def _bill(self, digitized=True, total=100.0, **extra):
        type(self).counter += 1
        vals = {
            "move_type": "in_invoice",
            "partner_id": self.vendor.id,
            "ref": f"B4-INV-{self.counter:04d}",
            "invoice_date": "2026-11-10",
            "invoice_line_ids": [(0, 0, {"name": "Freight", "quantity": 1, "price_unit": 100.0, "tax_ids": False})],
        }
        if digitized:
            vals["invoice_source_email"] = "trucker@example.com"
            vals["extract_state"] = "waiting_validation"
        vals.update(extra)
        bill = self.env["account.move"].create(vals)
        if total is not None:
            bill.plasticos_document_total = total
        return bill

    def _activities(self, bill):
        return self.env["mail.activity"].search(
            [("res_model", "=", "account.move"), ("res_id", "=", bill.id), ("summary", "=", SUMMARY)]
        )

    def _assert_held(self, bill, fragment):
        reasons = bill._plasticos_bill_block_reasons()
        self.assertTrue(any(fragment in reason for reason in reasons), reasons)
        result = bill.action_post()
        self.assertEqual(bill.state, "draft")
        self.assertEqual(result["tag"], "display_notification")
        self.assertIn(fragment, result["params"]["message"])
        activity = self._activities(bill)
        self.assertEqual(len(activity), 1)
        self.assertIn(self.manager_group, activity.user_id.all_group_ids)
        self.assertIn(fragment, activity.note)
        bill.action_post()
        self.assertEqual(bill.state, "draft")
        self.assertEqual(len(self._activities(bill)), 1)
        with self.assertRaises(UserError):
            bill._post(soft=False)
        self.assertEqual(bill.state, "draft")

    # ── Positive ─────────────────────────────────────────────
    def test_sound_digitized_bill_posts(self):
        bill = self._bill()
        self.assertEqual(bill._plasticos_bill_block_reasons(), [])
        bill.action_post()
        self.assertEqual(bill.state, "posted")
        self.assertFalse(self._activities(bill))

    def test_manual_vendor_bill_is_not_guarded(self):
        bill = self._bill(digitized=False, total=None, ref=False)
        self.assertFalse(bill._plasticos_is_digitized_bill())
        self.assertEqual(bill._plasticos_bill_block_reasons(), [])

    def test_customer_invoice_from_email_is_not_guarded(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.vendor.id,
                "invoice_source_email": "someone@example.com",
                "invoice_line_ids": [(0, 0, {"name": "Sale", "quantity": 1, "price_unit": 10.0})],
            }
        )
        self.assertEqual(invoice._plasticos_bill_block_reasons(), [])

    def test_vendor_refund_from_email_is_guarded(self):
        refund = self._bill(move_type="in_refund", total=None)
        self.assertTrue(refund._plasticos_is_digitized_bill())
        self._assert_held(refund, "document total is not recorded")

    # ── Each blocking reason ─────────────────────────────────
    def test_unfinished_extraction_blocks(self):
        for state in ("waiting_extraction", "extract_not_ready", "error_status", "not_enough_credit"):
            with self.subTest(state=state):
                self._assert_held(self._bill(extract_state=state), "not finished or failed")

    def test_emailed_bill_never_sent_for_digitization_blocks(self):
        self._assert_held(self._bill(extract_state="no_extract_requested"), "not sent for digitization")

    def test_missing_vendor_blocks(self):
        self._assert_held(self._bill(partner_id=False), "vendor is missing")

    def test_missing_reference_blocks(self):
        self._assert_held(self._bill(ref=False), "bill reference is missing")

    def test_missing_date_blocks(self):
        self._assert_held(self._bill(invoice_date=False), "bill date is missing")

    def test_total_that_does_not_reconcile_blocks(self):
        self._assert_held(self._bill(total=105.0), "document total is")

    def test_total_within_currency_rounding_passes(self):
        bill = self._bill(total=100.004)
        self.assertEqual(bill._plasticos_bill_block_reasons(), [])
        off_by_a_cent = self._bill(total=100.01)
        self.assertTrue(off_by_a_cent._plasticos_bill_block_reasons())

    def test_unrecorded_total_blocks_and_is_never_defaulted(self):
        bill = self._bill(total=None)
        self._assert_held(bill, "document total is not recorded")
        self.assertFalse(bill.plasticos_document_total)

    def test_native_duplicate_blocks(self):
        first = self._bill(ref="B4-DUP-1")
        second = self._bill(ref="B4-DUP-1")
        second.invalidate_recordset(["duplicated_ref_ids"])
        self.assertIn(first, second.duplicated_ref_ids)
        self._assert_held(second, "possible duplicate")

    # ── Correction and revalidation ──────────────────────────
    def test_manager_correction_then_normal_post(self):
        bill = self._bill(total=105.0, ref=False)
        self._assert_held(bill, "bill reference is missing")
        bill.write({"ref": "B4-CORRECTED"})
        bill.plasticos_document_total = 100.0
        self.assertEqual(bill._plasticos_bill_block_reasons(), [])
        bill.action_post()
        self.assertEqual(bill.state, "posted")

    def test_guard_revalidates_on_every_post(self):
        bill = self._bill()
        self.assertEqual(bill._plasticos_bill_block_reasons(), [])
        bill.write({"ref": False})
        self._assert_held(bill, "bill reference is missing")

    def test_batch_posts_sound_bills_and_holds_the_rest(self):
        sound = self._bill()
        unsound = self._bill(ref=False)
        (sound | unsound).action_post()
        self.assertEqual(sound.state, "posted")
        self.assertEqual(unsound.state, "draft")
        self.assertEqual(len(self._activities(unsound)), 1)
        self.assertFalse(self._activities(sound))

    def test_document_total_is_manager_only(self):
        field = self.env["account.move"]._fields["plasticos_document_total"]
        self.assertIn("plasticos_security_base.group_operations_manager", field.groups)

    # ── Auto-post ────────────────────────────────────────────
    def test_digitized_bill_never_auto_posts(self):
        self.company.autopost_bills = True
        self.vendor.autopost_bills = "always"
        bill = self._bill()
        self.assertEqual(bill._plasticos_bill_block_reasons(), [])
        bill._autopost_bill()
        self.assertEqual(bill.state, "draft")

    def test_manual_bill_for_an_always_partner_still_uses_native_auto_post(self):
        self.assertFalse(self._bill(digitized=False, total=None)._plasticos_is_digitized_bill())

    def test_extracted_total_is_recorded_only_when_the_extraction_read_one(self):
        def ocr(value):
            return {"total": {"selected_value": {"content": value}, "candidates": []}}

        bill = self._bill(total=None)
        for missing in ({}, {"total": {}}, ocr(None), ocr(0.0), ocr(True), ocr("100.00")):
            with self.subTest(ocr=missing):
                bill._plasticos_record_extracted_total(missing)
                self.assertFalse(bill.plasticos_document_total)
        bill._plasticos_record_extracted_total(ocr(100.0))
        self.assertEqual(bill.plasticos_document_total, 100.0)
        self.assertEqual(bill.state, "draft")
        posted = self._bill()
        posted.action_post()
        posted._plasticos_record_extracted_total(ocr(250.0))
        self.assertEqual(posted.plasticos_document_total, 100.0)

    # ── B5 on draft bills ────────────────────────────────────
    def _email(self, bill, subject, body=""):
        return bill.message_post(
            message_type="email",
            subtype_xmlid="mail.mt_comment",
            subject=subject,
            body=body,
            email_from="trucker@example.com",
            author_id=self.vendor.id,
        )

    def test_email_with_one_order_number_sets_an_empty_origin(self):
        bill = self._bill()
        message = self._email(bill, f"Freight bill {self.sale.name}")
        self.assertEqual(bill.invoice_origin, self.sale.name)
        note = bill.message_ids.filtered(lambda m: "Source document set to" in (m.body or ""))
        self.assertEqual(len(note), 1)
        self.assertIn(self.sale.name, note.body)
        self.assertIn(message.message_id, note.body)
        self.assertEqual(bill.state, "draft")

    def test_non_empty_origin_is_never_overwritten(self):
        bill = self._bill(invoice_origin="KEEP-ME")
        self._email(bill, f"Freight bill {self.sale.name}")
        self.assertEqual(bill.invoice_origin, "KEEP-ME")

    def test_posted_bill_is_never_touched(self):
        bill = self._bill()
        bill.action_post()
        self.assertEqual(bill.state, "posted")
        self._email(bill, f"Freight bill {self.sale.name}")
        self.assertFalse(bill.invoice_origin)

    def test_conflicting_references_leave_the_origin_empty_and_block_posting(self):
        bill = self._bill()
        self._email(bill, f"{self.sale.name} / {self.sale_other.name}")
        self.assertFalse(bill.invoice_origin)
        self._assert_held(bill, "References disagree")

    def test_reference_in_another_company_sets_nothing_and_does_not_block(self):
        bill = self._bill()
        self._email(bill, f"Bill for {self.purchase_b.name}")
        self.assertFalse(bill.invoice_origin)
        self.assertEqual(bill._plasticos_bill_block_reasons(), [])

    def test_transaction_without_an_order_sets_no_origin(self):
        bill = self._bill()
        self._email(bill, f"Freight bill {self.tx.name}")
        self.assertFalse(bill.invoice_origin)
        self.assertEqual(bill._plasticos_bill_block_reasons(), [])

    def test_no_reference_changes_nothing(self):
        bill = self._bill()
        self._email(bill, "invoice attached")
        self.assertFalse(bill.invoice_origin)
        self.assertEqual(bill._plasticos_bill_block_reasons(), [])

    def test_forwarded_email_uses_the_fresh_reference(self):
        bill = self._bill()
        body = f"<p>For {self.sale.name}</p><blockquote>earlier: {self.sale_other.name}</blockquote>"
        self._email(bill, "Fwd: freight bill", body)
        self.assertEqual(bill.invoice_origin, self.sale.name)
        self.assertEqual(bill._plasticos_bill_block_reasons(), [])
