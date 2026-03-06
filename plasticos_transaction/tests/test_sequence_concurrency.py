from odoo.addons.plasticos_base.tests.common import PlasticosTestCase


class TestSequenceConcurrency(PlasticosTestCase):
    def test_concurrent_creates_unique_sequence(self):
        tx1 = self.env["plasticos.transaction"].create({})
        tx2 = self.env["plasticos.transaction"].create({})
        self.assertNotEqual(tx1.name, tx2.name)
