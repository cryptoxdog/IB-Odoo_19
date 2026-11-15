"""Odoo runtime tests: scheduled EIE enrichment sweep (ADR-012 amendment 2026-11-15).

Selection of buyer facility profiles, candidate building, idempotent result
ingestion, refusal handling and the review-only outcome, against the shapes of
the EIE repository at a606791, docs/contracts/enrichment-sweep.md.
Gate is a test double; no network.
Written for the Enterprise runtime gate; not run in the pure-python tier.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.addons.plasticos_gate.services.gate_config import GateIntegrationError
from odoo.addons.plasticos_gate.services.gate_sweep import SWEEP_ACTION, SWEEP_RESULTS_ACTION
from odoo.tests.common import tagged

from .test_converge_v2_profile_targets import CARTRIDGE_VERSION, _v2_reply

_SEND = "odoo.addons.plasticos_gate.services.gate_client.send_sweep_action"
_ENABLED = "odoo.addons.plasticos_gate.services.gate_config.gate_enrichment_enabled"
SWEEP = "plasticos.enrichment.sweep"
RUN = "plasticos.enrichment.run"
# The resolution echo _v2_reply writes; the sweep requires a sha256 pin and compares it.
PIN_SHA = "test-sha"


def _sweep_reply(entity_id, specs):
    """A converge v2 body as EIE stores it for a sweep result (3.4 step 5): no subject, EIE's targets."""
    targets = [{"field": name, "type": {"type": "float"}} for name in specs]
    body = {
        "subject": {"type": None},
        "entity": {"id": entity_id},
        "targets": targets,
        "cartridge": {"id": "plasticos", "version": CARTRIDGE_VERSION},
        "node": "Facility",
    }
    return _v2_reply(body, specs)


class _SweepGate:
    """Records sweep sends; answers results with ``results(bodies)`` built from the sent requests."""

    def __init__(self, results=None, state="completed", skipped=()):
        self.calls = []
        self.results = results
        self.state = state
        self.skipped = list(skipped)

    def __call__(self, env, *, action, payload, correlation_id=None, idempotency_key=None):
        self.calls.append((action, payload, idempotency_key))
        packet = SimpleNamespace(header=SimpleNamespace(packet_id=f"pkt-{len(self.calls)}", correlation_id="corr-s"))
        if action == SWEEP_ACTION:
            ids = [c["entity_id"] for c in payload["candidates"]]
            return {"packet": packet, "payload": {"sweep_id": "sw-1", "accepted": ids, "rejected": []}}
        assert action == SWEEP_RESULTS_ACTION
        assert "cursor" not in payload, "the first page sends no cursor (section 6.1)"
        reply = {
            "sweep_id": payload["sweep_id"],
            "state": self.state,
            "results": self.results(env) if self.results else [],
            "next_cursor": None,
            "budget": {"effective_usd": 5.0, "spent_usd": 0.4, "remaining_usd": 4.6},
            "skipped": self.skipped,
            "stats": {"enriched": 1},
        }
        return {"packet": packet, "payload": reply}


@tagged("post_install", "-at_install", "plasticos", "enrichment", "gate")
class TestEnrichmentSweep(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing(SWEEP, RUN, "plasticos.facility.profile")
        cls.registry_enter_test_mode_cls()
        tags = cls.env["plasticos.company.role.tag"]
        cls.tag_buyer = tags.search([("code", "=", "buyer")], limit=1) or tags.create(
            {"name": "Buyer", "code": "buyer"}
        )
        cls.hdpe = cls._get_or_create_polymer(code="hdpe", name="HDPE")

    def setUp(self):
        super().setUp()
        for key, value in (
            ("plasticos.gate.converge_contract", "v2"),
            ("plasticos.gate.converge_cartridge_id", "plasticos"),
            ("plasticos.gate.converge_cartridge_version", CARTRIDGE_VERSION),
            ("plasticos.gate.converge_cartridge_sha256", PIN_SHA),
            ("plasticos.gate.sweep_enabled", "1"),
            ("plasticos.gate.sweep_max_candidates", "50"),
            ("plasticos.gate.sweep_cooldown_days", "30"),
            ("plasticos.gate.sweep_process_types", ""),
        ):
            self._set_param(key, value)
        # Isolate from any other open sweep in the database.
        self.env[SWEEP].search([("state", "in", ("sent", "running"))]).write({"state": "done"})
        self.env[SWEEP].search([("sweep_date", "=", fields.Datetime.now().date())]).write({"state": "failed"})

    def _set_param(self, key, value):
        icp = self.env["ir.config_parameter"].sudo()
        previous = icp.get_param(key) or ""
        icp.set_param(key, value)
        self.addCleanup(icp.set_param, key, previous)

    def _buyer_profile(self, name, **vals):
        company = self._create_partner(f"{name} Co", customer_rank=1)
        site = self.env["res.partner"].create(
            {
                "name": name,
                "parent_id": company.id,
                "is_company": True,
                "type": "other",
                "company_role_tag_ids": [(6, 0, self.tag_buyer.ids)],
            }
        )
        return self.env["plasticos.facility.profile"].create({"partner_id": site.id, **vals})

    def _supplier_profile(self, name):
        partner = self._create_partner(name, supplier_rank=1)
        return self.env["plasticos.facility.profile"].create({"partner_id": partner.id})

    @contextmanager
    def _gate(self, gate):
        with patch(_SEND, gate), patch(_ENABLED, return_value=True):
            yield

    def _selected(self):
        model = self.env[SWEEP]
        return model._select_facilities(model._sweep_settings())

    # ── selection ───────────────────────────────────────────────────────

    def test_selects_buyers_only_and_honours_filters(self):
        buyer = self._buyer_profile("Sweep Buyer A", process_type="injection")
        other = self._buyer_profile("Sweep Buyer B", process_type="compounding")
        supplier = self._supplier_profile("Sweep Supplier")
        selected = self._selected()
        self.assertIn(buyer, selected)
        self.assertIn(other, selected)
        self.assertNotIn(supplier, selected, "a supplier-only partner is never swept")
        self._set_param("plasticos.gate.sweep_process_types", "injection")
        selected = self._selected()
        self.assertIn(buyer, selected)
        self.assertNotIn(other, selected)

    def test_review_and_cooldown_exclude_and_oldest_goes_first(self):
        fresh = self._buyer_profile("Sweep Fresh")
        reviewed = self._buyer_profile("Sweep In Review")
        recent = self._buyer_profile("Sweep Recent")
        old = self._buyer_profile("Sweep Old")
        Run = self.env[RUN]
        Run.create({"partner_id": reviewed.partner_id.id, "facility_profile_id": reviewed.id}).write(
            {"state": "review"}
        )
        Run.create({"partner_id": recent.partner_id.id, "facility_profile_id": recent.id}).write({"state": "degraded"})
        old_run = Run.create({"partner_id": old.partner_id.id, "facility_profile_id": old.id})
        old_run.write({"state": "degraded"})
        self.env.cr.execute(
            "UPDATE plasticos_enrichment_run SET create_date = %s WHERE id = %s",
            (fields.Datetime.now() - timedelta(days=90), old_run.id),
        )
        self.env.invalidate_all()
        selected = self._selected()
        self.assertNotIn(reviewed, selected)
        self.assertNotIn(recent, selected)
        self.assertIn(fresh, selected)
        self.assertIn(old, selected)
        self.assertLess(list(selected).index(fresh), list(selected).index(old), "never-enriched first")

    # ── send ────────────────────────────────────────────────────────────

    def test_disabled_or_v1_sends_nothing(self):
        self._buyer_profile("Sweep Disabled")
        gate = _SweepGate()
        self._set_param("plasticos.gate.sweep_enabled", "0")
        with self._gate(gate):
            self.assertFalse(self.env[SWEEP]._cron_send_sweep())
        self._set_param("plasticos.gate.sweep_enabled", "1")
        self._set_param("plasticos.gate.converge_contract", "v1")
        with self._gate(gate):
            self.assertFalse(self.env[SWEEP]._cron_send_sweep())
        self.assertFalse(gate.calls)

    def test_send_builds_res_partner_candidates_and_records_the_sweep(self):
        profile = self._buyer_profile("Sweep Send", accepted_polymer_ids=[(6, 0, self.hdpe.ids)])
        gate = _SweepGate()
        with self._gate(gate):
            sweep = self.env[SWEEP]._cron_send_sweep()
        self.assertTrue(sweep)
        action, payload, key = gate.calls[0]
        self.assertEqual(action, SWEEP_ACTION)
        entity_id = f"res.partner:{profile.partner_id.id}"
        candidate = next(c for c in payload["candidates"] if c["entity_id"] == entity_id)
        self.assertEqual(candidate["node_label"], "Facility")
        self.assertEqual(candidate["entity"].get("processed_polymers"), [{"code": "hdpe"}])
        self.assertEqual(payload["daily_budget_usd"], 5.0)
        self.assertEqual(payload["idempotency_key"], key)
        self.assertEqual(sweep.state, "sent")
        self.assertEqual(sweep.sweep_id, "sw-1")
        self.assertEqual(sweep.facility_map[entity_id], profile.id)
        self.assertEqual(sweep.cartridge_pin, {"id": "plasticos", "version": CARTRIDGE_VERSION, "sha256": PIN_SHA})
        with self._gate(gate):
            self.assertFalse(self.env[SWEEP]._cron_send_sweep(), "one sweep per UTC day")

    def test_same_day_retry_after_a_failed_send_reuses_the_record_and_key(self):
        self._buyer_profile("Sweep Retry")
        from odoo.addons.plasticos_gate.services.gate_config import GateIntegrationError

        def down(env, **kwargs):
            raise GateIntegrationError("gate down", failure_class="retryable")

        with self._gate(down):
            failed = self.env[SWEEP]._cron_send_sweep()
        self.assertEqual(failed.state, "failed")
        key = failed.idempotency_key
        gate = _SweepGate()
        with self._gate(gate):
            retried = self.env[SWEEP]._cron_send_sweep()
        self.assertEqual(retried, failed)
        self.assertEqual(retried.state, "sent")
        self.assertEqual(gate.calls[0][2], key, "the retry replays the same Gate operation")

    # ── results ─────────────────────────────────────────────────────────

    def _send_one(self, name):
        profile = self._buyer_profile(name)
        self._set_param("plasticos.gate.sweep_max_candidates", "1")
        with patch.object(type(self.env[SWEEP]), "_select_facilities", lambda self_, *a, **k: profile):
            with self._gate(_SweepGate()):
                sweep = self.env[SWEEP]._cron_send_sweep()
        return profile, sweep, f"res.partner:{profile.partner_id.id}"

    def test_results_land_in_review_without_writing_and_are_idempotent(self):
        profile, sweep, entity_id = self._send_one("Sweep Result Buyer")

        def results(env):
            reply = _sweep_reply(
                entity_id,
                {"min_density": {"state": "external_claim", "admitted": True, "value": 0.94, "unit": "g/cm3"}},
            )
            return [{"entity_id": entity_id, "response": reply}]

        gate = _SweepGate(results)
        with self._gate(gate):
            self.env[SWEEP]._cron_collect_results()
        runs = self.env[RUN].search([("facility_profile_id", "=", profile.id)])
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs.state, "review")
        self.assertEqual(runs.partner_id, profile.partner_id)
        self.assertFalse(profile.density_min, "nothing is written before human review")
        self.assertEqual(sweep.state, "done")
        self.assertEqual(sweep.ingested, {entity_id: runs.id})

        sweep.write({"state": "running"})
        with self._gate(gate):
            self.env[SWEEP]._cron_collect_results()
        self.assertEqual(self.env[RUN].search_count([("facility_profile_id", "=", profile.id)]), 1)

        runs.action_inject()
        self.assertAlmostEqual(profile.density_min, 0.94, msg="the approved sweep run writes through review")

    def test_unusable_result_becomes_a_degraded_run_with_the_reason(self):
        profile, sweep, entity_id = self._send_one("Sweep Degraded Buyer")
        gate = _SweepGate(lambda env: [{"entity_id": entity_id, "response": {"state": "completed"}}])
        with self._gate(gate):
            self.env[SWEEP]._cron_collect_results()
        run = self.env[RUN].search([("facility_profile_id", "=", profile.id)])
        self.assertEqual(run.state, "degraded")
        self.assertIn("rejected", run.validation_issues[0])
        self.assertFalse(profile.density_min)

    def test_result_for_an_entity_never_sent_creates_no_run(self):
        _profile, sweep, entity_id = self._send_one("Sweep Stranger Buyer")
        stranger = "res.partner:999999999"
        gate = _SweepGate(lambda env: [{"entity_id": stranger, "response": {}}])
        with self._gate(gate):
            self.env[SWEEP]._cron_collect_results()
        self.assertNotIn(stranger, sweep.ingested or {})
        self.assertTrue(any(r["entity_id"] == stranger for r in sweep.rejections))

    def test_malformed_results_page_fails_the_sweep_and_writes_nothing(self):
        profile, sweep, _entity_id = self._send_one("Sweep Malformed Buyer")

        def bad(env, *, action, payload, correlation_id=None, idempotency_key=None):
            packet = SimpleNamespace(header=SimpleNamespace(packet_id="p", correlation_id="c"))
            return {"packet": packet, "payload": {"state": "weird"}}

        with self._gate(bad):
            self.env[SWEEP]._cron_collect_results()
        self.assertEqual(sweep.state, "failed")
        self.assertFalse(self.env[RUN].search([("facility_profile_id", "=", profile.id)]))

    def test_skip_reasons_and_stats_are_recorded_per_candidate(self):
        _profile, sweep, entity_id = self._send_one("Sweep Skipped Buyer")
        gate = _SweepGate(skipped=[{"entity_id": entity_id, "reason": "no_readiness_gaps"}])
        with self._gate(gate):
            self.env[SWEEP]._cron_collect_results()
        self.assertEqual(sweep.state, "done")
        self.assertIn({"entity_id": entity_id, "reason": "no_readiness_gaps", "stage": "skipped"}, sweep.rejections)
        self.assertEqual(sweep.skipped_count, 1)
        self.assertEqual(sweep.stats, {"enriched": 1})

    def test_send_refused_disabled_fails_the_sweep_and_is_never_polled(self):
        self._buyer_profile("Sweep Refused")

        def refused(env, **kwargs):
            raise GateIntegrationError("disabled: L9_ENRICHMENT_SWEEP_ENABLED is false", failure_class="permanent")

        with self._gate(refused):
            sweep = self.env[SWEEP]._cron_send_sweep()
        self.assertEqual((sweep.state, sweep.refusal_code), ("failed", "disabled"))
        gate = _SweepGate()
        with self._gate(gate):
            self.env[SWEEP]._cron_collect_results()
        self.assertFalse(gate.calls, "a failed sweep is not polled")

    def test_sweep_not_found_marks_the_sweep_expired_and_stops_polling(self):
        _profile, sweep, _entity_id = self._send_one("Sweep Expired Buyer")

        def gone(env, **kwargs):
            raise GateIntegrationError(f"sweep_not_found: {sweep.sweep_id}", failure_class="permanent")

        with self._gate(gone):
            self.env[SWEEP]._cron_collect_results()
        self.assertEqual((sweep.state, sweep.refusal_code), ("expired", "sweep_not_found"))
        gate = _SweepGate()
        with self._gate(gate):
            self.env[SWEEP]._cron_collect_results()
        self.assertFalse(gate.calls, "an expired sweep is not polled")

    def test_store_unavailable_keeps_the_sweep_open(self):
        _profile, sweep, _entity_id = self._send_one("Sweep Store Buyer")

        def store_down(env, **kwargs):
            raise GateIntegrationError("sweep_store_unavailable: db down", failure_class="permanent")

        with self._gate(store_down):
            self.env[SWEEP]._cron_collect_results()
        self.assertEqual((sweep.state, sweep.refusal_code), ("sent", "sweep_store_unavailable"))
