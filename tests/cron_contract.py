"""Live ir.cron bindings for the cron contract tests.

This module must not import Odoo. Pure pytest imports it to lock the
registry to cron XML. The Odoo cron tests import the same rows.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CronBinding:
    """One ir.cron code call: model.method() in a cron XML file."""

    xml_path: str
    model: str
    method: str


CRONS: tuple[CronBinding, ...] = (
    CronBinding("plasticos_claims/data/claim_cron.xml", "plasticos.claim", "_cron_check_sla"),
    CronBinding("plasticos_logistics/data/cron.xml", "plasticos.load", "_cron_escalation_check"),
    CronBinding(
        "plasticos_logistics/data/cron.xml",
        "plasticos.load",
        "_cron_check_dispatch_acknowledgments",
    ),
    CronBinding(
        "plasticos_logistics/data/cron.xml",
        "plasticos.transaction",
        "_cron_supplier_confirmation_followup",
    ),
    CronBinding(
        "plasticos_logistics/data/cron.xml",
        "plasticos.transaction",
        "_cron_auto_create_delivery_orders",
    ),
    CronBinding("plasticos_transaction/data/audit_cron.xml", "plasticos.audit.cron", "run_monthly_audit"),
    CronBinding("plasticos_documents/data/cron.xml", "plasticos.document", "_cron_compliance_audit"),
    CronBinding(
        "plasticos_documents/data/scale_ticket_rule.xml",
        "plasticos.transaction",
        "cron_check_scale_tickets",
    ),
    CronBinding(
        "plasticos_documents/data/cron_missing_docs.xml",
        "plasticos.transaction",
        "cron_check_missing_docs",
    ),
    CronBinding(
        "plasticos_automation/data/contract_renewal_cron.xml",
        "res.partner",
        "cron_contract_renewal_alert",
    ),
    CronBinding(
        "plasticos_automation/data/sale_approval_cron.xml",
        "sale.order",
        "cron_flag_sale_approvals",
    ),
    CronBinding(
        "plasticos_automation/data/stock_alert_cron.xml",
        "product.product",
        "cron_stock_reorder_alert",
    ),
    CronBinding(
        "plasticos_base/data/midnight_recompute_cron.xml",
        "plasticos.midnight.recompute",
        "_cron_midnight_recompute",
    ),
    CronBinding(
        "plasticos_intake_normalizer/data/cron_batch_normalize.xml",
        "plasticos.intake",
        "cron_batch_normalize",
    ),
    CronBinding("plasticos_geolocalize/data/cron_geo_backfill.xml", "res.partner", "cron_geo_backfill"),
    CronBinding("plasticos_offer/data/offer_cron.xml", "plasticos.offer", "cron_expire_offers"),
    CronBinding(
        "plasticos_automation/data/invoice_reminder_cron.xml",
        "account.move",
        "cron_invoice_reminder",
    ),
    CronBinding(
        "plasticos_automation/data/cron_load_sla.xml",
        "plasticos.load",
        "cron_load_sla_check",
    ),
    CronBinding(
        "plasticos_automation/data/cron_supplier_followup.xml",
        "purchase.order",
        "cron_supplier_followup",
    ),
    CronBinding(
        "plasticos_automation/data/cron_trucker_followup.xml",
        "stock.picking",
        "cron_trucker_followup",
    ),
    CronBinding(
        "plasticos_matching/views/match_exclusion_views.xml",
        "plasticos.match.exclusion",
        "_cron_expire_temporary_exclusions",
    ),
    CronBinding(
        "plasticos_crm_sync/data/ir_cron_data.xml",
        "plasticos.crm.connection",
        "_cron_sync_all",
    ),
    CronBinding(
        "plasticos_admin_dashboard/data/cron_refresh_dashboard.xml",
        "plasticos.admin.kpi",
        "action_refresh",
    ),
    CronBinding(
        "plasticos_enrichment/data/cron.xml",
        "plasticos.enrichment.run",
        "action_cron_enrich_pending",
    ),
    CronBinding(
        "plasticos_enrichment/data/cron.xml",
        "plasticos.enrichment.run",
        "action_cron_inference_only",
    ),
    CronBinding(
        "plasticos_enrichment/data/sweep_data.xml",
        "plasticos.enrichment.sweep",
        "_cron_send_sweep",
    ),
    CronBinding(
        "plasticos_enrichment/data/sweep_data.xml",
        "plasticos.enrichment.sweep",
        "_cron_collect_results",
    ),
)

CRON_TEST_FILES: tuple[str, ...] = (
    "plasticos_claims/tests/test_cron_idempotency.py",
    "plasticos_claims/tests/test_cron_runtime.py",
)

# These methods stay negative-only. A new row cannot be aimed into the batch,
# or the in-domain path calls Nominatim. The lock rejects a change to this set.
UNREACHABLE_IN_DOMAIN: dict[str, str] = {
    "cron_check_missing_docs": "create_date cannot be aimed, and the status rule needs age",
    "cron_check_scale_tickets": "create_date cannot be aimed, and a new row is not old enough",
    "cron_geo_backfill": "an addressed partner calls Nominatim",
}


def model_xml_suffix(model: str) -> str:
    """Odoo ir.model external id tail for a dotted model name."""
    return "model_" + model.replace(".", "_")


def is_cron_attribute(name: str) -> bool:
    """True for a cron method name the lock treats as a registry call."""
    return name.startswith("cron_") or name.startswith("_cron_") or name == "run_monthly_audit"
