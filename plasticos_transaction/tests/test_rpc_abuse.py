from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestRPCAbuse(TransactionCase):
    def test_direct_state_write_blocked(self):
        tx = self.env["plasticos.transaction"].create({})
        with self.assertRaises(UserError):
            tx.write({"state": "closed"})
