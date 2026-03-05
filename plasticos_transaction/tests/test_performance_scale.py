import time

from odoo.tests.common import TransactionCase


class TestPerformanceScale(TransactionCase):
    def test_bulk_creation_performance(self):
        start = time.time()
        for _ in range(1000):
            self.env["plasticos.transaction"].create({})
        duration = time.time() - start
        self.assertLess(duration, 10)
