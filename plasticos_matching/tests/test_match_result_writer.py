"""Odoo database tests for canonical Gate match-result persistence."""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "plasticos", "matching")
class TestMatchResultWriter(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing(
            "plasticos.match.result.writer",
            "plasticos.match.result",
            "plasticos.match.run",
        )
        cls.intake = cls._create_intake()
        cls.buyer = cls._create_partner("Gate Match Buyer", customer_rank=1)
        cls.Run = cls.env["plasticos.match.run"]
        cls.Writer = cls.env["plasticos.match.result.writer"]

    def _successful_run(self, operation_id="odoo:matching:test:plasticos.match.run:1"):
        return self.Run.create(
            {
                "intake_id": self.intake.id,
                "supplier_partner_id": self.intake.partner_id.id,
                "state": "ok",
                "operation_id": operation_id,
                "request_fingerprint": "a" * 64,
                "gate_response_digest": "b" * 64,
                "gate_packet_id": "packet-1",
                "gate_correlation_id": "correlation-1",
                "gate_query_id": "query-1",
                "gate_model_version": "model-1",
            }
        )

    def _eligible_match(self):
        return {
            "buyer_id": self.buyer.id,
            "total_score": 0.85,
            "gates_passed": ["material"],
            "gates_failed": [],
            "match_details": {"feature_contributions": [], "missing_evidence": []},
            "reason": "Eligible Gate candidate",
        }

    def test_persists_exact_gate_result_once_and_links_the_durable_run(self):
        run = self._successful_run()
        created = self.Writer.persist_match_lines(self.intake, [self._eligible_match()], match_run=run)
        self.assertEqual(len(created), 1)
        result = created
        self.assertEqual(result.intake_id, self.intake)
        self.assertEqual(result.buyer_partner_id, self.buyer)
        self.assertEqual(result.match_run_id, run)
        self.assertEqual(result.run_id, run.operation_id)
        self.assertEqual(result.score, 85.0)
        self.assertEqual(result.score_breakdown["gate_packet_id"], "packet-1")

        replay = self.Writer.persist_match_lines(self.intake, [self._eligible_match()], match_run=run)
        self.assertFalse(replay)
        self.assertEqual(
            self.env["plasticos.match.result"].search_count(
                [("intake_id", "=", self.intake.id), ("run_id", "=", run.operation_id)]
            ),
            1,
        )

    def test_zero_candidate_gate_receipt_creates_no_result_but_is_valid(self):
        run = self._successful_run("odoo:matching:test:plasticos.match.run:2")
        created = self.Writer.persist_match_lines(self.intake, [], match_run=run)
        self.assertFalse(created)
        self.assertEqual(
            self.env["plasticos.match.result"].search_count(
                [("intake_id", "=", self.intake.id), ("run_id", "=", run.operation_id)]
            ),
            0,
        )
