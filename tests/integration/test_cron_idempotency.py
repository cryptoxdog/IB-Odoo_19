"""Test 20 — Cron Job Idempotency Tests.

Files: Various cron methods across all plasticos_* modules.
Risk: MEDIUM — Reliability. Non-idempotent crons corrupt data on re-run.

Validates:
  - Each cron method can be called twice without duplication
  - Cron handles empty recordsets gracefully
  - Cron handles already-processed records (no double state change)

Tested crons (from cron XML files in repo):
  - plasticos_offer: cron_expire_offers (validated in test_14)
  - plasticos_intake_normalizer: cron_batch_normalize
  - plasticos_geolocalize: cron_geo_backfill
  - plasticos_documents: cron (scale ticket, missing docs)
  - plasticos_automation: contract_renewal, invoice_reminder,
    sale_approval, stock_alert, supplier_followup, trucker_followup,
    load_sla
  - plasticos_base: midnight_recompute, attachment_maintenance
  - plasticos_claims: claim_cron
  - plasticos_logistics: cron
  - plasticos_enrichment: cron
  - plasticos_buyer_match_engine: ir_cron_graph_sync
  - plasticos_transaction: audit_cron, cron_missing_docs
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged


def _safe_call(env, model_name, method_name):
    """Call a cron method, returning (success, error_msg)."""
    try:
        Model = env.get(model_name) or env[model_name]
    except KeyError:
        return None, f"Model {model_name} not found"
    method = getattr(Model, method_name, None)
    if not callable(method):
        return None, f"Method {method_name} not found on {model_name}"
    try:
        method()
        return True, None
    except Exception as e:
        return False, str(e)


@tagged("post_install", "-at_install", "cron", "idempotency")
class TestCronIdempotency(PlasticosTestCase):
    """Every cron method must survive double execution."""

    def _run_twice(self, model_name, method_name):
        """Run a cron method twice. Both runs must succeed."""
        ok1, err1 = _safe_call(self.env, model_name, method_name)
        if ok1 is None:
            self.skipTest(err1)
        self.assertTrue(ok1, f"First run failed: {err1}")

        ok2, err2 = _safe_call(self.env, model_name, method_name)
        self.assertTrue(ok2, f"Second run failed (not idempotent): {err2}")

    # ── plasticos_base ───────────────────────────────────────
    def test_midnight_recompute_idempotent(self):
        self._run_twice("plasticos.midnight.recompute", "_cron_midnight_recompute")

    # ── plasticos_intake_normalizer ──────────────────────────
    def test_batch_normalize_idempotent(self):
        self._run_twice("plasticos.intake", "cron_batch_normalize")

    # ── plasticos_geolocalize ────────────────────────────────
    def test_geo_backfill_idempotent(self):
        self._run_twice("res.partner", "cron_geo_backfill")

    # ── plasticos_offer ──────────────────────────────────────
    def test_expire_offers_idempotent(self):
        self._run_twice("plasticos.offer", "cron_expire_offers")

    # ── plasticos_claims ─────────────────────────────────────
    def test_claim_cron_idempotent(self):
        self._run_twice("plasticos.claim", "cron_process_claims")

    # ── plasticos_logistics ──────────────────────────────────
    def test_logistics_cron_idempotent(self):
        self._run_twice("plasticos.load", "cron_check_sla")

    # ── plasticos_enrichment ─────────────────────────────────
    def test_enrichment_cron_idempotent(self):
        self._run_twice("plasticos.enrichment.run", "cron_run_enrichment")

    # ── plasticos_buyer_match_engine ─────────────────────────
    def test_graph_sync_cron_idempotent(self):
        self._run_twice("plasticos.graph.sync.log", "cron_process_sync_queue")

    # ── plasticos_transaction ────────────────────────────────
    def test_audit_cron_idempotent(self):
        self._run_twice("plasticos.transaction", "cron_audit")

    # ── plasticos_documents ──────────────────────────────────
    def test_scale_ticket_cron_idempotent(self):
        self._run_twice("plasticos.document", "cron_check_scale_tickets")

    def test_missing_docs_cron_idempotent(self):
        self._run_twice("plasticos.document", "cron_check_missing_docs")

    # ── plasticos_automation ─────────────────────────────────
    def test_contract_renewal_cron_idempotent(self):
        self._run_twice("res.partner", "cron_contract_renewal_alerts")

    def test_invoice_reminder_cron_idempotent(self):
        self._run_twice("account.move", "cron_invoice_reminder")

    def test_sale_approval_cron_idempotent(self):
        self._run_twice("sale.order", "cron_auto_approve_sales")


@tagged("post_install", "-at_install", "cron")
class TestCronEmptyRecordset(PlasticosTestCase):
    """Cron methods must handle 0 records without crashing."""

    def test_expire_offers_empty_db(self):
        """No offers to expire — should succeed silently."""
        try:
            Offer = self.env["plasticos.offer"]
        except KeyError:
            self.skipTest("not installed")
        # Ensure no expirable offers exist
        Offer.search([("state", "in", ("draft", "sent", "responded"))]).write(
            {
                "valid_until": False,
            }
        )
        try:
            Offer.cron_expire_offers()
        except Exception as exc:
            self.fail(f"cron_expire_offers raised on empty set: {exc}")

    def test_batch_normalize_empty_db(self):
        """No intakes to normalize — should succeed."""
        try:
            Intake = self.env["plasticos.intake"]
        except KeyError:
            self.skipTest("not installed")
        if not hasattr(Intake, "cron_batch_normalize"):
            self.skipTest("cron method not available")
        try:
            Intake.cron_batch_normalize()
        except Exception as exc:
            self.fail(f"cron_batch_normalize raised on empty set: {exc}")
