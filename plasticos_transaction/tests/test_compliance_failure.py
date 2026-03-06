from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.exceptions import UserError


class TestComplianceFailure(PlasticosTestCase):
    def test_close_blocked_on_compliance_fail(self):
        tx = self.env["plasticos.transaction"].create({})
        tx.action_activate()
        with self.assertRaises(UserError):
            tx.action_close()
