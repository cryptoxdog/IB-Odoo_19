"""Transaction-owned intake action. Base intake installs without this module."""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "contract")
class TestIntakeMakePoContract(PlasticosTestCase):
    def test_action_make_po_exists(self):
        self.assertTrue(callable(getattr(self.env["plasticos.intake"], "action_make_po", None)))
