import time

from odoo.addons.plasticos_base.test_common import PlasticosTestCase


class TestPerformanceScale(PlasticosTestCase):
    def test_bulk_creation_performance(self):
        start = time.time()
        for _ in range(1000):
            self.env["plasticos.transaction"].create({})
        duration = time.time() - start
        self.assertLess(duration, 10)
