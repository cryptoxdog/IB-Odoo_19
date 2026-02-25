import time

from odoo import models


class GraphLoadTester(models.AbstractModel):
    _name = "plasticos.graph.load.tester"

    def run_test(self, intake_ids):
        engine = self.env["plasticos.graph.matching.engine"]

        results = []
        start = time.time()

        for intake_id in intake_ids:
            engine.generate_candidates(intake_id, mode="strict")

        total = time.time() - start
        return {
            "requests": len(intake_ids),
            "total_time_sec": total,
            "avg_latency_ms": (total / len(intake_ids)) * 1000,
        }
