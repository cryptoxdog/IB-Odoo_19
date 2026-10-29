"""Compliance recompute does not post. Explicit account.move.action_post still can."""

from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "accounting", "documents")
class TestComplianceDoesNotPost(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "Compliance Post Partner", "is_company": True, "customer_rank": 1, "supplier_rank": 1}
        )

    def test_compute_compliance_does_not_call_auto_post(self):
        tx = self.env["plasticos.transaction"].create(
            {"supplier_id": self.partner.id, "buyer_id": self.partner.id, "quantity": 1}
        )
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_date": "2026-10-28",
                "invoice_line_ids": [(0, 0, {"name": "Line", "quantity": 1, "price_unit": 10.0})],
            }
        )
        tx.customer_invoice_id = invoice
        with patch.object(type(tx), "_auto_post_pending_invoices", side_effect=AssertionError("autopost")):
            tx._compute_compliance()
        self.assertEqual(invoice.state, "draft")
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")
