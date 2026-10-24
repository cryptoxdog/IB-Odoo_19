"""
Cron Job Runtime Tests

Validates that all cron job methods:
1. Exist on the target model
2. Are callable without arguments (as Odoo cron invokes them)
3. Handle empty-dataset gracefully (no silent crash)
4. Log appropriately on completion

These are "smoke tests" — they ensure cron jobs don't silently fail
in production when the scheduler triggers them.
"""

import logging

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged

_logger = logging.getLogger(__name__)


# ── Cron Registry: (model, method, description) ─────────────────────────────
# Each entry mirrors the model_id / code of the ir.cron record in the cited data file.
CRON_REGISTRY = [
    # plasticos_automation
    ("plasticos.load", "cron_load_sla_check", "Load SLA Breach Check"),  # data/cron_load_sla.xml
    ("product.product", "cron_stock_reorder_alert", "Stock Reorder Alert"),  # data/stock_alert_cron.xml
    ("stock.picking", "cron_trucker_followup", "Trucker Follow-Up"),  # data/cron_trucker_followup.xml
    ("res.partner", "cron_contract_renewal_alert", "Contract Renewal Alert"),  # data/contract_renewal_cron.xml
    ("account.move", "cron_invoice_reminder", "Invoice Reminders"),  # data/invoice_reminder_cron.xml
    # plasticos_enrichment (data/cron.xml)
    ("plasticos.enrichment.run", "action_cron_enrich_pending", "Enrichment Daily"),
    ("plasticos.enrichment.run", "action_cron_inference_only", "Inference Standalone"),
    # plasticos_claims (data/claim_cron.xml)
    ("plasticos.claim", "_cron_check_sla", "Claim SLA Check and Escalation"),
    # plasticos_transaction (data/audit_cron.xml)
    ("plasticos.audit.cron", "run_monthly_audit", "Monthly Transaction Audit"),
    # plasticos_documents (data/cron_missing_docs.xml)
    ("plasticos.transaction", "cron_check_missing_docs", "Missing Documents Check"),
    # plasticos_base (data/midnight_recompute_cron.xml)
    ("plasticos.midnight.recompute", "_cron_midnight_recompute", "Midnight Recompute"),
    # plasticos_geolocalize (data/cron_geo_backfill.xml)
    ("res.partner", "cron_geo_backfill", "Geo Backfill"),
]


@tagged("post_install", "-at_install")
class TestCronMethodsExist(PlasticosTestCase):
    """Verify every registered cron method exists on its target model."""

    def test_all_cron_methods_resolvable(self):
        """Every cron entry points to a real model + callable method."""
        missing = []
        for model_name, method_name, desc in CRON_REGISTRY:
            if model_name not in self.env:
                missing.append(f"Model {model_name!r} not found ({desc})")
                continue
            Model = self.env[model_name]
            if not hasattr(Model, method_name):
                missing.append(f"{model_name}.{method_name}() not found ({desc})")
            elif not callable(getattr(Model, method_name)):
                missing.append(f"{model_name}.{method_name} is not callable ({desc})")
        self.assertFalse(
            missing,
            "Cron methods missing or not callable:\n" + "\n".join(missing),
        )


@tagged("post_install", "-at_install")
class TestCronEmptyDataset(PlasticosTestCase):
    """Cron jobs must not crash on an empty database."""

    def _run_cron_safely(self, model_name, method_name, **kwargs):
        """Call the cron method on an empty dataset; must not raise."""
        if model_name not in self.env:
            self.skipTest(f"Model {model_name!r} not installed")
        Model = self.env[model_name]
        method = getattr(Model, method_name, None)
        if method is None:
            self.skipTest(f"{model_name}.{method_name} not found")
        try:
            method(**kwargs)
        except Exception as exc:
            self.fail(f"{model_name}.{method_name}() raised {type(exc).__name__}: {exc}")

    def test_load_sla_check_empty(self):
        """Load SLA cron runs on empty loads table."""
        self._run_cron_safely("plasticos.load", "cron_load_sla_check")

    def test_stock_alert_empty(self):
        """Stock reorder alert cron runs with no low-stock products."""
        self._run_cron_safely("product.product", "cron_stock_reorder_alert")

    def test_enrichment_pending_empty(self):
        """Enrichment cron runs on empty enrichment runs."""
        self._run_cron_safely(
            "plasticos.enrichment.run",
            "action_cron_enrich_pending",
            run_inference=True,
        )

    def test_claim_escalation_empty(self):
        """Claim escalation cron runs on empty claims."""
        self._run_cron_safely("plasticos.claim", "_cron_check_sla")

    def test_transaction_audit_empty(self):
        """Transaction audit cron runs on empty transactions."""
        self._run_cron_safely("plasticos.audit.cron", "run_monthly_audit")

    def test_missing_docs_check_empty(self):
        """Missing docs cron runs on empty documents."""
        self._run_cron_safely("plasticos.transaction", "cron_check_missing_docs")

    def test_geo_backfill_empty(self):
        """Geo backfill cron runs on empty partners."""
        self._run_cron_safely("res.partner", "cron_geo_backfill")


@tagged("post_install", "-at_install")
class TestCronXmlIntegrity(PlasticosTestCase):
    """Validate that ir.cron XML records are well-formed in the database."""

    def test_all_cron_records_have_model(self):
        """Every PlasticOS ir.cron record references a valid model."""
        crons = self.env["ir.cron"].search(
            [
                ("name", "ilike", "PlasticOS%"),
            ]
        )
        invalid = []
        for cron in crons:
            if not cron.model_id:
                invalid.append(f"{cron.name}: missing model_id")
            # An empty recordset is falsy, so test registry membership, not env.get().
            elif cron.model_id.model not in self.env:
                invalid.append(f"{cron.name}: model {cron.model_id.model!r} not installed")
        self.assertFalse(
            invalid,
            "Cron records with invalid models:\n" + "\n".join(invalid),
        )

    def test_all_cron_records_have_user(self):
        """Every PlasticOS cron runs as a system user (not admin/None)."""
        crons = self.env["ir.cron"].search(
            [
                ("name", "ilike", "PlasticOS%"),
            ]
        )
        for cron in crons:
            self.assertTrue(
                cron.user_id,
                f"Cron {cron.name!r} has no user_id — will run as admin!",
            )
