from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError


class TestRPCAbuse(PlasticosTestCase):
    def test_direct_state_write_blocked(self):
        tx = self.env["plasticos.transaction"].create({})
        with self.assertRaises(UserError):
            tx.write({"state": "closed"})
