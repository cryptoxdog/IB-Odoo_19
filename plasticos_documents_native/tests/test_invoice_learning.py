"""Native invoice learning stays intact under the Plasticos bill guard (TASK-072, UNK-005).

Two behaviors of Enterprise ``account_invoice_extract`` / ``account_accountant`` that
Document AI relies on and does not replace:

1. Posting a person-corrected digitized bill queues the corrected values for the OCR
   service (``extract_state`` ``to_validate`` plus a trigger of the validate cron), and
   the cron sends the corrected values, not what the OCR first read.
2. The next bill with the same detected layout gets its vendor from the earlier bill,
   and its line gets the account that vendor's posted bills used for that label.

The IAP service is replaced at ``account.move._contact_iap_extract``; nothing leaves
the test. All values are synthetic. These are runtime tests (``odoo --test-enable``).
"""

from contextlib import contextmanager
from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged

VALIDATE_CRON_XMLID = "account_invoice_extract.ir_cron_ocr_validate"
LAYOUT = 424242
LINE_LABEL = "Synthetic baled LDPE freight"


def _ocr(content):
    return {"selected_value": {"content": content}, "candidates": []}


@tagged("post_install", "-at_install", "accounting", "integrity_controls")
class TestInvoiceLearning(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vendor = cls.env["res.partner"].create(
            {"name": "Synthetic Layout Carrier", "is_company": True, "supplier_rank": 1}
        )
        cls.expense_account = cls.env["account.account"].create(
            {"name": "Synthetic Freight Expense", "code": "699001", "account_type": "expense"}
        )

    @contextmanager
    def _iap(self, response=None):
        """Replace the OCR service; yield the list of ``(pathinfo, params)`` it received."""
        calls = []

        def _contact(move, pathinfo, params):
            calls.append((pathinfo, params))
            return response if response is not None else {"status": "success"}

        with patch.object(type(self.env["account.move"]), "_contact_iap_extract", _contact):
            yield calls

    def _sound_bill(self, ref, price, **extra):
        """A digitized draft bill that the Plasticos guard lets post (not load-related, total recorded)."""
        vals = {
            "move_type": "in_invoice",
            "partner_id": self.vendor.id,
            "ref": ref,
            "invoice_date": "2026-11-10",
            "invoice_source_email": "carrier@example.com",
            "plasticos_not_load_related": True,
            "plasticos_not_load_related_reason": "Synthetic fixture: not a load bill",
            "invoice_line_ids": [(0, 0, {"name": LINE_LABEL, "quantity": 1, "price_unit": price, "tax_ids": False})],
        }
        vals.update(extra)
        bill = self.env["account.move"].create(vals)
        bill.plasticos_document_total = 100.0
        return bill

    # ── 1. Corrections are queued for the OCR service ───────────
    def test_posting_a_corrected_digitized_bill_queues_the_corrected_values(self):
        bill = self._sound_bill(
            "OCR-MISREAD",
            90.0,
            extract_state="waiting_validation",
            extract_document_uuid="synthetic-token-a",
        )
        # The person corrects what the OCR misread.
        bill.write({"ref": "SYN-CORRECTED-001"})
        bill.invoice_line_ids.price_unit = 100.0
        self.assertEqual(bill._plasticos_bill_block_reasons(), [])
        cron = self.env.ref(VALIDATE_CRON_XMLID)
        triggers_before = self.env["ir.cron.trigger"].search_count([("cron_id", "=", cron.id)])

        with self._iap() as calls:
            bill.action_post()
            self.assertEqual(bill.state, "posted")
            self.assertEqual(bill.extract_state, "to_validate")
            self.assertGreater(self.env["ir.cron.trigger"].search_count([("cron_id", "=", cron.id)]), triggers_before)
            self.assertEqual(calls, [], "posting only queues; the cron sends")
            self.env["account.move"]._cron_validate()

        sent = [params for pathinfo, params in calls if pathinfo == "validate"]
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["document_token"], "synthetic-token-a")
        values = sent[0]["values"]
        self.assertEqual(values["invoice_id"]["content"], "SYN-CORRECTED-001")
        self.assertEqual(values["total"]["content"], 100.0)
        self.assertEqual(values["partner"]["content"], self.vendor.name)
        self.assertEqual([line["unit_price"] for line in values["invoice_lines"]["lines"]], [100.0])
        self.assertEqual(bill.extract_state, "done")
        self.assertEqual(bill.state, "posted")

    # ── 2. The next bill of the same layout is predicted ────────
    def test_next_bill_of_the_same_layout_predicts_vendor_and_line_account(self):
        first = self._sound_bill(
            "SYN-LAYOUT-001",
            100.0,
            extract_state="done",
            extract_detected_layout=LAYOUT,
        )
        first.invoice_line_ids.account_id = self.expense_account
        first.action_post()
        self.assertEqual(first.state, "posted")

        second = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "extract_state": "waiting_extraction",
                "extract_document_uuid": "synthetic-token-b",
                "invoice_source_email": "carrier@example.com",
            }
        )
        result = {
            "status": "success",
            "results": [
                {
                    "detected_layout_id": LAYOUT,
                    # A supplier name that matches no partner: only the layout can find the vendor.
                    "supplier": _ocr("Qzx Unmatched Synthetic Header"),
                    "invoice_id": _ocr("SYN-LAYOUT-002"),
                    "date": _ocr("2026-11-12 00:00:00"),
                    "total": _ocr(100.0),
                    "subtotal": _ocr(100.0),
                    "total_tax_amount": _ocr(0.0),
                    "invoice_lines": [
                        {
                            "description": LINE_LABEL,
                            "unit_price": 100.0,
                            "quantity": 1,
                            "taxes": [],
                            "subtotal": 100.0,
                            "total": 100.0,
                        }
                    ],
                }
            ],
        }
        with self._iap(result):
            second._check_ocr_status()

        self.assertEqual(second.extract_state, "waiting_validation")
        self.assertEqual(second.extract_detected_layout, LAYOUT)
        self.assertEqual(second.partner_id, self.vendor)
        line = second.invoice_line_ids
        self.assertEqual(line.mapped("name"), [LINE_LABEL])
        self.assertEqual(line.account_id, self.expense_account)
        self.assertEqual(second.state, "draft", "a digitized bill never posts without a person")
