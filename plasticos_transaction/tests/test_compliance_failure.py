from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestComplianceFailure(TransactionCase):
    def test_close_blocked_on_compliance_fail(self):
        tx = self.env["plasticos.transaction"].create({})
        tx.action_activate()
        with self.assertRaises(UserError):
            tx.action_close()
