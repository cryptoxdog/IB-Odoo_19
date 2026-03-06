from odoo.addons.plasticos_base.tests.common import PlasticosTestCase


class TestSequenceRace(PlasticosTestCase):
    def test_sequence_unique_under_flush(self):
        txs = []
        for _ in range(20):
            txs.append(self.env["plasticos.transaction"].create({}))
        names = [t.name for t in txs]
        self.assertEqual(len(names), len(set(names)), "Transaction names must be unique.")
