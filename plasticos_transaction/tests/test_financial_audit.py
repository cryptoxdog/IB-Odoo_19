from odoo.addons.plasticos_base.test_common import PlasticosTestCase


class TestFinancialAudit(PlasticosTestCase):
    def test_closed_transaction_integrity(self):
        tx = self.env["plasticos.transaction"].create({})
        self.assertNotEqual(tx.name, "New")

        self.assertFalse(tx.commission_locked)

        # Ensure no closed transaction exists with negative margin
        closed = self.env["plasticos.transaction"].search(
            [
                ("state", "=", "closed"),
                ("gross_margin", "<", 0),
            ]
        )
        self.assertFalse(closed)
