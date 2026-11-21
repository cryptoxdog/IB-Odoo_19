"""plasticos.admin.dashboard — RevOps Command Center (SQL VIEW).

Design philosophy:
  - ONE screen. Zero tabs. Zero navigation switches.
  - Admins already have Sales and Logistics dashboards 1-click away via menu.
    This dashboard shows only what those don't: aggregate KPIs, pipeline health,
    AI engine stats, and rep performance — all in a single scrollable form view.
  - The form view IS the dashboard. Three layout sections:
      Section A: Pipeline Health + Urgency Alerts (top, compact)
      Section B: Rep Performance — Week / Month / Year (middle)
      Section C: AI Engine Stats (bottom, collapsible)
  - All KPIs are computed as @api.model methods — no SQL VIEW for the
    header model since KPIs are aggregates, not row-per-entity.
  - The intake + offer queues are embedded as list sub-views within
    the same form via One2many-style act_window buttons/stat buttons.
  - One click max to action: every alert/KPI has a drill button that
    opens the actionable list (sales dashboard or logistics dashboard
    pre-filtered).

Models created:
  plasticos.admin.kpi          — singleton KPI record (computed on demand)
  plasticos.rep.performance    — SQL VIEW: one row per rep × period
"""

import logging
from collections import namedtuple
from datetime import timedelta

from odoo import api, fields, models, tools
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

PLASTICOS_TRANSACTION = "plasticos.transaction"
PLASTICOS_OFFER = "plasticos.offer"
PLASTICOS_WEB_LEAD = "plasticos.web.lead"
PLASTICOS_INTAKE = "plasticos.intake"
PLASTICOS_DOCUMENT = "plasticos.document"
PLASTICOS_LINDA_APPROVAL = "plasticos.linda.approval"
MAIL_ACTIVITY = "mail.activity"

_TX_TERMINAL_STATES = ["closed", "cancelled"]
_TX_PRE_SHIPPING_STATES = ["draft", "active", "pending_supplier", "supplier_not_ready", "supplier_ready"]
_TX_SHIPPING_STATES = ["do_created", "dispatched", "in_progress", "in_transit"]
_TX_DELIVERED_STATES = ["delivered", "invoiced"]
_TX_IN_MOTION_STATES = ["dispatched", "in_progress", "in_transit"]
_INVOICE_SETTLED_PAYMENT_STATES = ["paid", "in_payment", "reversed"]
_INTAKE_CLOSED_STATUSES = ["won", "lost", "expired"]
_OFFER_OPEN_STATES = ["draft", "sent", "responded"]
_LEGACY_SALE_XMLID_PREFIX = "legacy_erp_so_"
_MANUAL_OVERRIDE_MARKER = "Manual override"

# KPI aggregate kinds (KPI_AGGREGATES); a KPI not listed there is a record count.
AGG_COUNT = "count"
AGG_SUM = "sum"
AGG_AVG_AGE_DAYS = "avg_age_days"

# Period boundaries in the user's timezone.
KpiPeriods = namedtuple("KpiPeriods", ["today", "tomorrow", "week_start", "month_start", "year_start"])

# DEC-002: closed-deal and earned-commission periods use commission_earned_date,
# never write_date. These are operational figures, not accounting revenue.
_CLOSED_DEAL_HELP = (
    "Operational closed-deal figure: live (non-historical) closed transactions of this company, "
    "attributed to the period of their commission_earned_date. Not accounting-recognized revenue; "
    "posted invoices, invoice aging and cash are separate figures with their own dates."
)

# DEC-012 exception activity types (plasticos_documents, TASK-060) and the owner roles the
# exception router writes into each activity note ("Routed to <role>: <reason>").
EXCEPTION_ACTIVITY_TYPES = (
    "plasticos_documents.activity_type_missing_documents",
    "plasticos_documents.activity_type_missing_scale_ticket",
    "plasticos_documents.activity_type_association_review",
    "plasticos_documents.activity_type_classification_review",
    "plasticos_documents.activity_type_evidence_gap",
    "plasticos_documents.activity_type_split_review",
    "plasticos_documents.activity_type_duplicate_candidate",
    "plasticos_documents.activity_type_blocked_bill",
)

# DEC-008: the company path of each source model. A model absent here carries no company.
_COMPANY_PATHS = {
    PLASTICOS_TRANSACTION: "sale_order_id.company_id",
    PLASTICOS_DOCUMENT: "subject_company_id",
    PLASTICOS_LINDA_APPROVAL: "company_id",
}

# Source models the Admin may lack read access to. Without access the KPI is
# unavailable, never 0.
_OPTIONAL_ACCESS_MODELS = frozenset({PLASTICOS_DOCUMENT, PLASTICOS_LINDA_APPROVAL, MAIL_ACTIVITY})

# DEC-007 KPI-drill parity: each urgency KPI is declared once as
# (drill title, source model, domain builder). The displayed count is
# search_count(domain) and the drill opens the same model with the same domain,
# so the two can never diverge.
URGENCY_KPIS = {
    "tx_negative_margin": ("⚠ Negative Margin Deals", PLASTICOS_TRANSACTION, "_urgency_domain_negative_margin"),
    "tx_delivered_uninvoiced": (
        "⚠ Delivered — No Posted Invoice",
        PLASTICOS_TRANSACTION,
        "_urgency_domain_delivered_uninvoiced",
    ),
    "tx_missing_docs": ("⚠ Missing Docs", PLASTICOS_TRANSACTION, "_urgency_domain_missing_docs"),
    "tx_sup_not_ready": ("⚠ Supplier Not Ready", PLASTICOS_TRANSACTION, "_urgency_domain_supplier_not_ready"),
    "tx_stalled_followup": ("⚠ 3+ Followups No Response", PLASTICOS_TRANSACTION, "_urgency_domain_stalled_followup"),
    "offer_expiring_soon": ("⏰ Offers Expiring ≤3 Days", PLASTICOS_OFFER, "_urgency_domain_expiring_offers"),
    "lead_error_open": ("Lead Triage Errors", PLASTICOS_WEB_LEAD, "_urgency_domain_lead_errors"),
    "commission_unlocked": (
        "Commission Unlocked on Closed TXs",
        PLASTICOS_TRANSACTION,
        "_urgency_domain_commission_unlocked",
    ),
}

# Every other actionable Admin KPI, declared the same way (TASK-031, F-005).
KPI_DECLARATIONS = {
    **URGENCY_KPIS,
    # Intake pipeline
    "intake_draft": ("Intakes: Draft", PLASTICOS_INTAKE, "_kpi_domain_intake_draft"),
    "intake_matched": ("Intakes: Matched", PLASTICOS_INTAKE, "_kpi_domain_intake_matched"),
    "intake_offer_sent": ("Intakes: Offer Sent", PLASTICOS_INTAKE, "_kpi_domain_intake_offer_sent"),
    "intake_processing": ("Intakes: Processing", PLASTICOS_INTAKE, "_kpi_domain_intake_processing"),
    "intake_total_open": ("Open Intakes", PLASTICOS_INTAKE, "_kpi_domain_intake_total_open"),
    "intake_won_mtd": ("Intakes Won (MTD)", PLASTICOS_INTAKE, "_kpi_domain_intake_won_mtd"),
    "intake_lost_mtd": ("Intakes Lost (MTD)", PLASTICOS_INTAKE, "_kpi_domain_intake_lost_mtd"),
    "avg_intake_age_days": ("Aging Intakes", PLASTICOS_INTAKE, "_kpi_domain_intake_aging"),
    # Offers
    "offer_draft": ("Offers: Draft", PLASTICOS_OFFER, "_kpi_domain_offer_draft"),
    "offer_sent": ("Offers: Sent", PLASTICOS_OFFER, "_kpi_domain_offer_sent"),
    "offer_responded": ("Offers: Responded", PLASTICOS_OFFER, "_kpi_domain_offer_responded"),
    "offer_accepted_mtd": ("Offers Accepted (MTD)", PLASTICOS_OFFER, "_kpi_domain_offer_accepted_mtd"),
    "offer_rejected_mtd": ("Offers Rejected (MTD)", PLASTICOS_OFFER, "_kpi_domain_offer_rejected_mtd"),
    "offer_expired_mtd": ("Offers Expired (MTD)", PLASTICOS_OFFER, "_kpi_domain_offer_expired_mtd"),
    # Transactions
    "tx_open": ("Open Transactions", PLASTICOS_TRANSACTION, "_kpi_domain_tx_open"),
    "tx_in_motion": ("Transactions In Motion", PLASTICOS_TRANSACTION, "_kpi_domain_tx_in_motion"),
    "tx_closed_mtd": ("Closed Deals MTD (earned date)", PLASTICOS_TRANSACTION, "_kpi_domain_closed_mtd"),
    "pipeline_value_open": ("Open Pipeline", PLASTICOS_TRANSACTION, "_kpi_domain_pipeline_open"),
    # Closed-deal financials (DEC-002)
    "revenue_mtd": ("Closed-Deal Revenue MTD", PLASTICOS_TRANSACTION, "_kpi_domain_closed_mtd"),
    "revenue_ytd": ("Closed-Deal Revenue YTD", PLASTICOS_TRANSACTION, "_kpi_domain_closed_ytd"),
    "gm_mtd": ("Closed-Deal Gross Margin MTD", PLASTICOS_TRANSACTION, "_kpi_domain_closed_mtd"),
    "gm_ytd": ("Closed-Deal Gross Margin YTD", PLASTICOS_TRANSACTION, "_kpi_domain_closed_ytd"),
    "net_margin_mtd": ("Closed-Deal Net Margin MTD", PLASTICOS_TRANSACTION, "_kpi_domain_closed_mtd"),
    "net_margin_ytd": ("Closed-Deal Net Margin YTD", PLASTICOS_TRANSACTION, "_kpi_domain_closed_ytd"),
    "commission_mtd": ("Earned Commission MTD", PLASTICOS_TRANSACTION, "_kpi_domain_closed_mtd"),
    "commission_ytd": ("Earned Commission YTD", PLASTICOS_TRANSACTION, "_kpi_domain_closed_ytd"),
    # Web leads
    "lead_received_today": ("Leads Today", PLASTICOS_WEB_LEAD, "_kpi_domain_lead_today"),
    "lead_received_wtd": ("Leads WTD", PLASTICOS_WEB_LEAD, "_kpi_domain_lead_wtd"),
    "lead_received_mtd": ("Leads MTD", PLASTICOS_WEB_LEAD, "_kpi_domain_lead_mtd"),
    "lead_hot_mtd": ("HOT Leads MTD", PLASTICOS_WEB_LEAD, "_kpi_domain_lead_hot_mtd"),
    "lead_cold_mtd": ("COLD Leads MTD", PLASTICOS_WEB_LEAD, "_kpi_domain_lead_cold_mtd"),
    # AI engine
    "ai_leads_normalized_mtd": ("AI Normalized MTD", PLASTICOS_WEB_LEAD, "_kpi_domain_ai_normalized_mtd"),
    "ai_leads_vision_mtd": ("Vision Analyzed MTD", PLASTICOS_WEB_LEAD, "_kpi_domain_ai_vision_mtd"),
    "ai_hot_auto_mtd": ("Auto-HOT MTD", PLASTICOS_WEB_LEAD, "_kpi_domain_ai_hot_auto_mtd"),
    "ai_cold_auto_mtd": ("Auto-COLD MTD", PLASTICOS_WEB_LEAD, "_kpi_domain_lead_cold_mtd"),
    "ai_error_mtd": ("AI Errors MTD", PLASTICOS_WEB_LEAD, "_kpi_domain_ai_error_mtd"),
    "ai_intakes_auto_created": ("Auto-Intakes MTD", PLASTICOS_INTAKE, "_kpi_domain_ai_intakes_auto_created"),
    "ai_manual_override_mtd": ("Manual Overrides MTD", PLASTICOS_WEB_LEAD, "_kpi_domain_ai_manual_override_mtd"),
    "ai_pending_review": ("HOT Intakes Pending Buyer Match", PLASTICOS_INTAKE, "_kpi_domain_ai_pending_review"),
    # Stage funnel Transaction -> Shipping -> Documents -> Invoicing -> Payment (open transactions)
    "funnel_transaction": ("Funnel: Transaction", PLASTICOS_TRANSACTION, "_kpi_domain_funnel_transaction"),
    "funnel_shipping": ("Funnel: Shipping", PLASTICOS_TRANSACTION, "_kpi_domain_funnel_shipping"),
    "funnel_documents": ("Funnel: Documents", PLASTICOS_TRANSACTION, "_kpi_domain_funnel_documents"),
    "funnel_invoicing": ("Funnel: Invoicing", PLASTICOS_TRANSACTION, "_kpi_domain_funnel_invoicing"),
    "funnel_payment": ("Funnel: Payment", PLASTICOS_TRANSACTION, "_kpi_domain_funnel_payment"),
    # Open exceptions by owner role (DEC-012)
    "exceptions_operations_open": ("Open Exceptions: Operations", MAIL_ACTIVITY, "_kpi_domain_exceptions_operations"),
    "exceptions_logistics_open": ("Open Exceptions: Logistics", MAIL_ACTIVITY, "_kpi_domain_exceptions_logistics"),
    # Document processing and Linda
    "documents_verified_mtd": ("Documents Verified MTD", PLASTICOS_DOCUMENT, "_kpi_domain_documents_verified_mtd"),
    "documents_review_backlog": ("Documents Awaiting Association", PLASTICOS_DOCUMENT, "_kpi_domain_documents_backlog"),
    "linda_held_mtd": ("Linda Commands Held MTD", PLASTICOS_LINDA_APPROVAL, "_kpi_domain_linda_held_mtd"),
    "linda_held_pending": ("Linda Commands Awaiting Approval", PLASTICOS_LINDA_APPROVAL, "_kpi_domain_linda_pending"),
}

# Aggregate per KPI; a KPI not listed is a record count.
KPI_AGGREGATES = {
    "pipeline_value_open": (AGG_SUM, "revenue_total"),
    "revenue_mtd": (AGG_SUM, "revenue_total"),
    "revenue_ytd": (AGG_SUM, "revenue_total"),
    "gm_mtd": (AGG_SUM, "gross_margin"),
    "gm_ytd": (AGG_SUM, "gross_margin"),
    "net_margin_mtd": (AGG_SUM, "net_margin"),
    "net_margin_ytd": (AGG_SUM, "net_margin"),
    "commission_mtd": (AGG_SUM, "commission_amount"),
    "commission_ytd": (AGG_SUM, "commission_amount"),
    "avg_intake_age_days": (AGG_AVG_AGE_DAYS, "create_date"),
}

# Ratios: (numerator KPI, denominator KPIs). Value = numerator / sum(denominators) x 100.
# The drill opens the denominator set. An empty denominator is unavailable, not 0.
RATIO_KPIS = {
    "intake_win_rate_mtd": ("intake_won_mtd", ("intake_won_mtd", "intake_lost_mtd")),
    "offer_accept_rate_mtd": ("offer_accepted_mtd", ("offer_accepted_mtd", "offer_rejected_mtd")),
    "gm_pct_mtd": ("gm_mtd", ("revenue_mtd",)),
    "gm_pct_ytd": ("gm_ytd", ("revenue_ytd",)),
    "lead_hot_rate_mtd": ("lead_hot_mtd", ("lead_hot_mtd", "lead_cold_mtd")),
    "ai_hot_rate_mtd": ("ai_hot_auto_mtd", ("ai_hot_auto_mtd", "ai_cold_auto_mtd")),
}

# ─────────────────────────────────────────────────────────────────────────────
# KPI SINGLETON
# ─────────────────────────────────────────────────────────────────────────────


class PlasticosAdminKpi(models.Model):
    """Singleton record holding all RevOps KPIs for the admin command center.

    One record per company (DEC-008). Transaction-based KPIs count only
    transactions whose sale order belongs to the record's company; a
    transaction without a sale order has no resolvable company and is counted
    for none. Refreshed by action_refresh() (button or cron). All KPI fields are
    stored=False computed fields reading live from the DB.
    """

    _name = "plasticos.admin.kpi"
    _description = "Admin RevOps KPI Snapshot"
    _rec_name = "id"

    _company_unique = models.Constraint(
        "UNIQUE(company_id)",
        "There is exactly one Admin KPI record per company.",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        readonly=True,
        index=True,
        ondelete="cascade",
        default=lambda self: self.env.company,
        help="Company whose transactions this KPI record counts.",
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    last_refresh = fields.Datetime(string="Last Refreshed", readonly=True)

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION A — PIPELINE HEALTH (live counts)
    # ══════════════════════════════════════════════════════════════════════════

    # Intakes
    intake_draft = fields.Integer(string="Intakes: Draft", compute="_compute_kpis", store=False)
    intake_matched = fields.Integer(string="Intakes: Matched", compute="_compute_kpis", store=False)
    intake_offer_sent = fields.Integer(string="Intakes: Offer Sent", compute="_compute_kpis", store=False)
    intake_processing = fields.Integer(string="Intakes: Processing", compute="_compute_kpis", store=False)
    intake_won_mtd = fields.Integer(string="Intakes Won (MTD)", compute="_compute_kpis", store=False)
    intake_lost_mtd = fields.Integer(string="Intakes Lost (MTD)", compute="_compute_kpis", store=False)
    intake_total_open = fields.Integer(string="Open Intakes", compute="_compute_kpis", store=False)

    # Offers
    offer_draft = fields.Integer(string="Offers: Draft", compute="_compute_kpis", store=False)
    offer_sent = fields.Integer(string="Offers: Sent", compute="_compute_kpis", store=False)
    offer_responded = fields.Integer(string="Offers: Responded", compute="_compute_kpis", store=False)
    offer_accepted_mtd = fields.Integer(string="Offers Accepted (MTD)", compute="_compute_kpis", store=False)
    offer_rejected_mtd = fields.Integer(string="Offers Rejected (MTD)", compute="_compute_kpis", store=False)
    offer_expired_mtd = fields.Integer(string="Offers Expired (MTD)", compute="_compute_kpis", store=False)
    offer_expiring_soon = fields.Integer(string="Expiring ≤3 Days", compute="_compute_kpis", store=False)

    # Deal Conversion
    offer_accept_rate_mtd = fields.Float(
        string="Offer Accept Rate %",
        compute="_compute_kpis",
        store=False,
        digits=(5, 1),
        help="Accepted / (Accepted+Rejected) × 100 MTD",
    )
    intake_win_rate_mtd = fields.Float(
        string="Intake Win Rate %",
        compute="_compute_kpis",
        store=False,
        digits=(5, 1),
        help="Won / (Won+Lost) × 100 MTD",
    )
    avg_intake_age_days = fields.Float(
        string="Avg Intake Age (days)", compute="_compute_kpis", store=False, digits=(5, 1)
    )

    # Transaction Pipeline
    tx_open = fields.Integer(string="Open Transactions", compute="_compute_kpis", store=False)
    tx_in_motion = fields.Integer(string="In Motion", compute="_compute_kpis", store=False)
    tx_delivered_uninvoiced = fields.Integer(string="Delivered-Uninvoiced", compute="_compute_kpis", store=False)
    tx_missing_docs = fields.Integer(string="Missing Docs", compute="_compute_kpis", store=False)
    tx_negative_margin = fields.Integer(string="Negative Margin ⚠", compute="_compute_kpis", store=False)
    tx_sup_not_ready = fields.Integer(string="Supplier Not Ready ⚠", compute="_compute_kpis", store=False)
    tx_stalled_followup = fields.Integer(string="3+ Followups No Resp ⚠", compute="_compute_kpis", store=False)
    tx_closed_mtd = fields.Integer(
        string="Closed Deals MTD (earned date)",
        compute="_compute_kpis",
        store=False,
        help=_CLOSED_DEAL_HELP,
    )

    # Web Leads
    lead_received_today = fields.Integer(string="Leads Today", compute="_compute_kpis", store=False)
    lead_received_wtd = fields.Integer(string="Leads WTD", compute="_compute_kpis", store=False)
    lead_received_mtd = fields.Integer(string="Leads MTD", compute="_compute_kpis", store=False)
    lead_hot_mtd = fields.Integer(string="HOT Leads MTD", compute="_compute_kpis", store=False)
    lead_cold_mtd = fields.Integer(string="COLD Leads MTD", compute="_compute_kpis", store=False)
    lead_error_open = fields.Integer(string="Lead Errors (open)", compute="_compute_kpis", store=False)
    lead_hot_rate_mtd = fields.Float(string="Lead→HOT Rate %", compute="_compute_kpis", store=False, digits=(5, 1))

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION B — FINANCIAL SNAPSHOT
    # ══════════════════════════════════════════════════════════════════════════

    revenue_mtd = fields.Float(
        string="Closed-Deal Revenue MTD", compute="_compute_kpis", store=False, help=_CLOSED_DEAL_HELP
    )
    revenue_ytd = fields.Float(
        string="Closed-Deal Revenue YTD", compute="_compute_kpis", store=False, help=_CLOSED_DEAL_HELP
    )
    gm_mtd = fields.Float(
        string="Closed-Deal Gross Margin MTD", compute="_compute_kpis", store=False, help=_CLOSED_DEAL_HELP
    )
    gm_ytd = fields.Float(
        string="Closed-Deal Gross Margin YTD", compute="_compute_kpis", store=False, help=_CLOSED_DEAL_HELP
    )
    gm_pct_mtd = fields.Float(
        string="Closed-Deal GM % MTD", compute="_compute_kpis", store=False, digits=(5, 1), help=_CLOSED_DEAL_HELP
    )
    gm_pct_ytd = fields.Float(
        string="Closed-Deal GM % YTD", compute="_compute_kpis", store=False, digits=(5, 1), help=_CLOSED_DEAL_HELP
    )
    net_margin_mtd = fields.Float(
        string="Closed-Deal Net Margin MTD", compute="_compute_kpis", store=False, help=_CLOSED_DEAL_HELP
    )
    net_margin_ytd = fields.Float(
        string="Closed-Deal Net Margin YTD", compute="_compute_kpis", store=False, help=_CLOSED_DEAL_HELP
    )
    commission_mtd = fields.Float(
        string="Earned Commission MTD", compute="_compute_kpis", store=False, help=_CLOSED_DEAL_HELP
    )
    commission_ytd = fields.Float(
        string="Earned Commission YTD", compute="_compute_kpis", store=False, help=_CLOSED_DEAL_HELP
    )
    commission_unlocked = fields.Integer(string="Comm Unlocked (closed)", compute="_compute_kpis", store=False)
    pipeline_value_open = fields.Float(
        string="Open Pipeline Value",
        compute="_compute_kpis",
        store=False,
        help="Sum of revenue_total on non-closed, non-cancelled transactions",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION C — AI ENGINE STATS
    # ══════════════════════════════════════════════════════════════════════════

    ai_leads_normalized_mtd = fields.Integer(
        string="AI Normalized MTD",
        compute="_compute_kpis",
        store=False,
        help="Leads processed with ai_normalized != null MTD",
    )
    ai_leads_vision_mtd = fields.Integer(
        string="Vision Analyzed MTD",
        compute="_compute_kpis",
        store=False,
        help="Leads with ai_vision_results != null MTD",
    )
    ai_hot_auto_mtd = fields.Integer(
        string="Auto-HOT MTD",
        compute="_compute_kpis",
        store=False,
        help="HOT leads auto-classified by AI (not manually overridden)",
    )
    ai_cold_auto_mtd = fields.Integer(string="Auto-COLD MTD", compute="_compute_kpis", store=False)
    ai_error_mtd = fields.Integer(
        string="AI Errors MTD",
        compute="_compute_kpis",
        store=False,
        help="Leads that hit state=error during triage MTD",
    )
    ai_hot_rate_mtd = fields.Float(string="AI HOT Rate %", compute="_compute_kpis", store=False, digits=(5, 1))
    ai_intakes_auto_created = fields.Integer(
        string="Auto-Intakes MTD",
        compute="_compute_kpis",
        store=False,
        help="Intakes created automatically from HOT web leads MTD",
    )
    ai_manual_override_mtd = fields.Integer(
        string="Manual Overrides MTD",
        compute="_compute_kpis",
        store=False,
        help="Cold leads manually forced to HOT by admin MTD",
    )
    ai_pending_review = fields.Integer(
        string="Pending Review",
        compute="_compute_kpis",
        store=False,
        help="HOT intakes from web leads with no partner yet (need buyer-match action)",
    )
    ai_normalized_enabled = fields.Boolean(string="AI Normalizer Active", compute="_compute_ai_config", store=False)
    ai_vision_enabled = fields.Boolean(string="Vision Active", compute="_compute_ai_config", store=False)
    ai_openai_key_set = fields.Boolean(string="OpenAI Key Set", compute="_compute_ai_config", store=False)

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION G — BUSINESS HEALTH & BOTTLENECKS (TASK-031)
    # ══════════════════════════════════════════════════════════════════════════

    funnel_transaction = fields.Integer(
        string="Funnel: Transaction",
        compute="_compute_kpis",
        store=False,
        help="Open transactions before shipping: draft, active, pending/not ready/ready supplier.",
    )
    funnel_shipping = fields.Integer(
        string="Funnel: Shipping",
        compute="_compute_kpis",
        store=False,
        help="Transactions with a delivery order or in motion: DO created, dispatched, in progress, in transit.",
    )
    funnel_documents = fields.Integer(
        string="Funnel: Documents",
        compute="_compute_kpis",
        store=False,
        help="Delivered transactions whose required documents are missing.",
    )
    funnel_invoicing = fields.Integer(
        string="Funnel: Invoicing",
        compute="_compute_kpis",
        store=False,
        help="Delivered transactions with documents complete and no posted customer invoice.",
    )
    funnel_payment = fields.Integer(
        string="Funnel: Payment",
        compute="_compute_kpis",
        store=False,
        help="Delivered transactions with documents complete and a posted customer invoice not yet paid.",
    )
    exceptions_operations_open = fields.Integer(
        string="Open Exceptions: Operations",
        compute="_compute_kpis",
        store=False,
        help="Open document-exception activities the exception router assigned to the Operations Manager role.",
    )
    exceptions_logistics_open = fields.Integer(
        string="Open Exceptions: Logistics",
        compute="_compute_kpis",
        store=False,
        help="Open document-exception activities the exception router assigned to the Logistics role.",
    )
    documents_verified_mtd = fields.Integer(
        string="Documents Verified MTD",
        compute="_compute_kpis",
        store=False,
        help="Plasticos documents of this company verified since the start of the month.",
    )
    documents_review_backlog = fields.Integer(
        string="Documents Awaiting Association",
        compute="_compute_kpis",
        store=False,
        help="Plasticos documents of this company whose association is pending or under review.",
    )
    linda_held_mtd = fields.Integer(
        string="Linda Commands Held MTD",
        compute="_compute_kpis",
        store=False,
        help="Linda commands held for Operations Manager approval since the start of the month (refusals excluded).",
    )
    linda_held_pending = fields.Integer(
        string="Linda Commands Awaiting Approval",
        compute="_compute_kpis",
        store=False,
    )
    linda_intervention_rate = fields.Float(
        string="Linda Intervention Rate %",
        compute="_compute_kpis",
        store=False,
        digits=(5, 1),
        help="Held / (held + auto-applied). Unavailable: straight-through Linda commands are applied at once "
        "and leave no ledger row, so the auto-applied count has no source.",
    )

    # Availability: False renders "n/a", distinct from a true 0 (TASK-031).
    intake_win_rate_mtd_available = fields.Boolean(compute="_compute_kpis", store=False)
    offer_accept_rate_mtd_available = fields.Boolean(compute="_compute_kpis", store=False)
    gm_pct_mtd_available = fields.Boolean(compute="_compute_kpis", store=False)
    gm_pct_ytd_available = fields.Boolean(compute="_compute_kpis", store=False)
    lead_hot_rate_mtd_available = fields.Boolean(compute="_compute_kpis", store=False)
    ai_hot_rate_mtd_available = fields.Boolean(compute="_compute_kpis", store=False)
    avg_intake_age_days_available = fields.Boolean(compute="_compute_kpis", store=False)
    exceptions_operations_open_available = fields.Boolean(compute="_compute_kpis", store=False)
    exceptions_logistics_open_available = fields.Boolean(compute="_compute_kpis", store=False)
    documents_verified_mtd_available = fields.Boolean(compute="_compute_kpis", store=False)
    documents_review_backlog_available = fields.Boolean(compute="_compute_kpis", store=False)
    linda_held_mtd_available = fields.Boolean(compute="_compute_kpis", store=False)
    linda_held_pending_available = fields.Boolean(compute="_compute_kpis", store=False)
    linda_intervention_rate_available = fields.Boolean(compute="_compute_kpis", store=False)

    # ══════════════════════════════════════════════════════════════════════════
    # COMPUTE
    # ══════════════════════════════════════════════════════════════════════════

    @api.depends()
    def _compute_kpis(self):
        """Every KPI value comes from its declaration (DEC-007); unavailable is never 0."""
        for rec in self:
            values = {name: rec._kpi_value(name) for name in KPI_DECLARATIONS}
            for name, (numerator, denominators) in RATIO_KPIS.items():
                parts = [values[numerator], *(values[d] for d in denominators)]
                denominator = None if None in parts else sum(values[d] for d in denominators)
                values[name] = round(values[numerator] / denominator * 100, 1) if denominator else None
            values["linda_intervention_rate"] = None
            for name, value in values.items():
                flag = f"{name}_available"
                if flag in rec._fields:
                    rec[flag] = value is not None
                elif value is None:
                    raise UserError(f"KPI {name} has no availability flag and could not be computed.")
                rec[name] = value or 0

    @api.depends()
    def _compute_ai_config(self):
        for rec in self:
            config_model = "plasticos.web.lead.config"
            if config_model not in self.env:
                rec.ai_normalized_enabled = False
                rec.ai_vision_enabled = False
                rec.ai_openai_key_set = False
                continue
            try:
                config = self.env[config_model].sudo().get_config()  # sudo: reports key presence; keys are system-only
                rec.ai_normalized_enabled = bool(getattr(config, "ai_enabled", False))
                rec.ai_vision_enabled = bool(getattr(config, "vision_enabled", False))
                rec.ai_openai_key_set = bool(getattr(config, "openai_api_key", ""))
            except Exception:
                rec.ai_normalized_enabled = False
                rec.ai_vision_enabled = False
                rec.ai_openai_key_set = False

    # ── Singleton helper ──────────────────────────────────────────────────────

    @api.model
    def _get_or_create(self, company=None):
        """Return the KPI record of ``company`` (default: the current company), creating it if missing."""
        company = company or self.env.company
        rec = self.search([("company_id", "=", company.id)], limit=1)
        if not rec:
            rec = self.create({"company_id": company.id})
        return rec

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_refresh(self):
        """Force re-compute all KPIs, then stamp the refresh time."""
        self._compute_kpis()
        self._compute_ai_config()
        self.write({"last_refresh": fields.Datetime.now()})
        return True

    def action_open_pending_approval(self):
        """Won opportunities with an accepted offer and no sale order. No count badge."""
        Lead = self.env["crm.lead"]
        offered = (
            self.env["plasticos.offer"]
            .search(
                [
                    ("state", "=", "accepted"),
                    ("opportunity_id.type", "=", "opportunity"),
                    ("opportunity_id.stage_id.is_won", "=", True),
                ]
            )
            .mapped("opportunity_id")
        )
        ordered = Lead.browse()
        if offered and "opportunity_id" in self.env["sale.order"]._fields:
            ordered = (
                self.env["sale.order"]
                .search([("opportunity_id", "in", offered.ids), ("state", "!=", "cancel")])
                .opportunity_id
            )
        pending = offered - ordered
        return {
            "type": "ir.actions.act_window",
            "name": "Pending approval",
            "res_model": "crm.lead",
            "view_mode": "list,form",
            "domain": [("id", "in", pending.ids)],
            "target": "current",
        }

    # ── DEC-007 KPI declarations ─────────────────────────────────────────────

    def _kpi_company(self):
        """The company a KPI record counts for; the current company outside a single record."""
        if len(self) == 1 and self.company_id:
            return self.company_id
        return self.env.company

    def _kpi_domain(self, kpi_name):
        """Return the one domain that both computes and drills the KPI.

        Sources with a company path are scoped to the record's company (DEC-008).
        Intakes, offers, web leads and activities carry no company.
        """
        _title, model_name, builder = KPI_DECLARATIONS[kpi_name]
        domain = getattr(self, builder)()
        company_path = _COMPANY_PATHS.get(model_name)
        if company_path:
            domain = [(company_path, "=", self._kpi_company().id), *domain]
        return domain

    def _kpi_value(self, kpi_name):
        """The KPI value from its declaration, or None when it is unavailable."""
        _title, model_name, _builder = KPI_DECLARATIONS[kpi_name]
        if model_name not in self.env:
            return None
        Model = self.env[model_name]
        if model_name in _OPTIONAL_ACCESS_MODELS and not Model.has_access("read"):
            return None
        domain = self._kpi_domain(kpi_name)
        aggregate = KPI_AGGREGATES.get(kpi_name, (AGG_COUNT,))
        if aggregate[0] == AGG_COUNT:
            return Model.search_count(domain)
        if aggregate[0] == AGG_SUM:
            [(total,)] = Model._read_group(domain, aggregates=[f"{aggregate[1]}:sum"])
            return total or 0.0
        records = Model.search(domain)
        if not records:
            return None
        now = fields.Datetime.now()
        ages = [(now - record[aggregate[1]]).total_seconds() / 86400 for record in records]
        return round(sum(ages) / len(ages), 1)

    def _kpi_drill(self, kpi_name):
        title, model_name, _builder = KPI_DECLARATIONS[kpi_name]
        return {
            "type": "ir.actions.act_window",
            "name": title,
            "res_model": model_name,
            "view_mode": "list,form",
            "domain": self._kpi_domain(kpi_name),
            "target": "current",
        }

    def _ratio_drill(self, ratio_name):
        """A ratio drills to its denominator set: the records it is a share of."""
        _numerator, denominators = RATIO_KPIS[ratio_name]
        action = self._kpi_drill(denominators[0])
        if len(denominators) > 1:
            action["domain"] = ["|"] * (len(denominators) - 1)
            for name in denominators:
                action["domain"] += self._kpi_domain(name)
        action["name"] = self._fields[ratio_name].string
        return action

    def action_open_kpi(self):
        """Drill for the KPI named in the button context (declared KPIs and ratios only)."""
        kpi_name = self.env.context.get("kpi")
        if kpi_name in RATIO_KPIS:
            return self._ratio_drill(kpi_name)
        if kpi_name not in KPI_DECLARATIONS:
            raise UserError(f"Unknown Admin KPI: {kpi_name!r}")
        return self._kpi_drill(kpi_name)

    def action_open_exceptions_by_owner(self):
        """All open document exceptions, grouped by owner role note and assignee (DEC-012)."""
        action = self._kpi_drill("exceptions_operations_open")
        action["name"] = "Open Exceptions by Owner"
        action["domain"] = [("activity_type_id", "in", self._exception_type_ids())]
        action["context"] = {"group_by": ["user_id", "activity_type_id"]}
        return action

    # ── Domain builders (no company term; _kpi_domain adds it) ──────────────

    @api.model
    def _kpi_periods(self):
        today = fields.Date.context_today(self)
        return KpiPeriods(
            today=today,
            tomorrow=today + timedelta(days=1),
            week_start=today - timedelta(days=today.weekday()),
            month_start=today.replace(day=1),
            year_start=today.replace(month=1, day=1),
        )

    @api.model
    def _kpi_domain_intake_draft(self):
        return [("status", "=", "draft")]

    @api.model
    def _kpi_domain_intake_matched(self):
        return [("status", "=", "matched")]

    @api.model
    def _kpi_domain_intake_offer_sent(self):
        return [("status", "=", "offer_sent")]

    @api.model
    def _kpi_domain_intake_processing(self):
        return [("status", "=", "processing")]

    @api.model
    def _kpi_domain_intake_total_open(self):
        return [("status", "not in", _INTAKE_CLOSED_STATUSES)]

    @api.model
    def _kpi_domain_intake_won_mtd(self):
        return [("status", "=", "won"), ("create_date", ">=", self._kpi_periods().month_start)]

    @api.model
    def _kpi_domain_intake_lost_mtd(self):
        return [("status", "=", "lost"), ("create_date", ">=", self._kpi_periods().month_start)]

    @api.model
    def _kpi_domain_intake_aging(self):
        return [("status", "not in", [*_INTAKE_CLOSED_STATUSES, "draft"])]

    @api.model
    def _kpi_domain_offer_draft(self):
        return [("state", "=", "draft")]

    @api.model
    def _kpi_domain_offer_sent(self):
        return [("state", "=", "sent")]

    @api.model
    def _kpi_domain_offer_responded(self):
        return [("state", "=", "responded")]

    @api.model
    def _kpi_domain_offer_accepted_mtd(self):
        return [("state", "=", "accepted"), ("create_date", ">=", self._kpi_periods().month_start)]

    @api.model
    def _kpi_domain_offer_rejected_mtd(self):
        return [("state", "=", "rejected"), ("create_date", ">=", self._kpi_periods().month_start)]

    @api.model
    def _kpi_domain_offer_expired_mtd(self):
        return [("state", "=", "expired"), ("create_date", ">=", self._kpi_periods().month_start)]

    @api.model
    def _kpi_domain_tx_open(self):
        return [("state", "not in", _TX_TERMINAL_STATES)]

    @api.model
    def _kpi_domain_tx_in_motion(self):
        return [("state", "in", _TX_IN_MOTION_STATES)]

    @api.model
    def _kpi_domain_pipeline_open(self):
        return [("state", "not in", _TX_TERMINAL_STATES), ("revenue_total", ">", 0)]

    @api.model
    def _kpi_domain_closed_mtd(self):
        return self._live_closed_domain([("commission_earned_date", ">=", self._kpi_periods().month_start)])

    @api.model
    def _kpi_domain_closed_ytd(self):
        return self._live_closed_domain([("commission_earned_date", ">=", self._kpi_periods().year_start)])

    @api.model
    def _kpi_domain_lead_today(self):
        periods = self._kpi_periods()
        return [("create_date", ">=", periods.today), ("create_date", "<", periods.tomorrow)]

    @api.model
    def _kpi_domain_lead_wtd(self):
        return [("create_date", ">=", self._kpi_periods().week_start)]

    @api.model
    def _kpi_domain_lead_mtd(self):
        return [("create_date", ">=", self._kpi_periods().month_start)]

    @api.model
    def _kpi_domain_lead_hot_mtd(self):
        return [("decision", "=", "hot"), ("create_date", ">=", self._kpi_periods().month_start)]

    @api.model
    def _kpi_domain_lead_cold_mtd(self):
        return [("decision", "=", "cold"), ("create_date", ">=", self._kpi_periods().month_start)]

    @api.model
    def _kpi_domain_ai_normalized_mtd(self):
        return [("ai_normalized", "!=", False), ("create_date", ">=", self._kpi_periods().month_start)]

    @api.model
    def _kpi_domain_ai_vision_mtd(self):
        return [("ai_vision_results", "!=", False), ("create_date", ">=", self._kpi_periods().month_start)]

    @api.model
    def _kpi_domain_ai_hot_auto_mtd(self):
        return [
            ("decision", "=", "hot"),
            ("state", "=", "intake_created"),
            ("create_date", ">=", self._kpi_periods().month_start),
        ]

    @api.model
    def _kpi_domain_ai_error_mtd(self):
        return [("state", "=", "error"), ("create_date", ">=", self._kpi_periods().month_start)]

    @api.model
    def _kpi_domain_ai_intakes_auto_created(self):
        return [("source_lead_id", "!=", False), ("create_date", ">=", self._kpi_periods().month_start)]

    @api.model
    def _kpi_domain_ai_manual_override_mtd(self):
        return [
            ("decision", "=", "hot"),
            ("triage_log", "ilike", _MANUAL_OVERRIDE_MARKER),
            ("create_date", ">=", self._kpi_periods().month_start),
        ]

    @api.model
    def _kpi_domain_ai_pending_review(self):
        return [
            ("source_lead_id", "!=", False),
            ("partner_id", "=", False),
            ("status", "not in", _INTAKE_CLOSED_STATUSES),
        ]

    @api.model
    def _kpi_domain_funnel_transaction(self):
        return [("state", "in", _TX_PRE_SHIPPING_STATES)]

    @api.model
    def _kpi_domain_funnel_shipping(self):
        return [("state", "in", _TX_SHIPPING_STATES)]

    @api.model
    def _kpi_domain_funnel_documents(self):
        return [("state", "in", _TX_DELIVERED_STATES), ("compliance_status", "=", "missing")]

    @api.model
    def _kpi_domain_funnel_invoicing(self):
        return [
            ("state", "in", _TX_DELIVERED_STATES),
            ("compliance_status", "!=", "missing"),
            "|",
            ("customer_invoice_id", "=", False),
            ("customer_invoice_id.state", "!=", "posted"),
        ]

    @api.model
    def _kpi_domain_funnel_payment(self):
        return [
            ("state", "in", _TX_DELIVERED_STATES),
            ("compliance_status", "!=", "missing"),
            ("customer_invoice_id.state", "=", "posted"),
            ("customer_invoice_id.payment_state", "not in", _INVOICE_SETTLED_PAYMENT_STATES),
        ]

    @api.model
    def _exception_type_ids(self):
        types = self.env["mail.activity.type"]
        for xmlid in EXCEPTION_ACTIVITY_TYPES:
            types |= self.env.ref(xmlid, raise_if_not_found=False) or types.browse()
        return types.ids

    @api.model
    def _exceptions_routed_to(self, role):
        return [("activity_type_id", "in", self._exception_type_ids()), ("note", "ilike", f"Routed to {role}:")]

    @api.model
    def _kpi_domain_exceptions_operations(self):
        return self._exceptions_routed_to("operations")

    @api.model
    def _kpi_domain_exceptions_logistics(self):
        return self._exceptions_routed_to("logistics")

    @api.model
    def _kpi_domain_documents_verified_mtd(self):
        return [("verified", "=", True), ("verified_at", ">=", self._kpi_periods().month_start)]

    @api.model
    def _kpi_domain_documents_backlog(self):
        return [("association_state", "in", ["pending", "review"])]

    @api.model
    def _kpi_domain_linda_held_mtd(self):
        return [("edge_case", "!=", "refusal"), ("requested_at", ">=", self._kpi_periods().month_start)]

    @api.model
    def _kpi_domain_linda_pending(self):
        return [("state", "=", "pending")]

    @api.model
    def _live_closed_domain(self, extra):
        """Closed, live (non-historical) transactions; historical ERP trades are excluded the
        same two ways the commission payouts exclude them (flag and legacy sale import)."""
        domain = [("state", "=", "closed"), ("legacy_erp_history", "=", False), *extra]
        return domain + self._legacy_sale_exclusion(domain)

    @api.model
    def _legacy_sale_exclusion(self, domain):
        orders = self.env[PLASTICOS_TRANSACTION].search(domain).sale_order_id
        if not orders:
            return []
        legacy_rows = (
            self.env["ir.model.data"]
            .sudo()  # sudo: core grants ir.model.data to group_erp_manager; reads legacy sale markers only
            .search(
                [
                    ("module", "=", "plasticos_transaction"),
                    ("model", "=", "sale.order"),
                    ("res_id", "in", orders.ids),
                    ("name", "=like", f"{_LEGACY_SALE_XMLID_PREFIX}%"),
                ]
            )
        )
        legacy_order_ids = sorted({row.res_id for row in legacy_rows if row.name.startswith(_LEGACY_SALE_XMLID_PREFIX)})
        return [("sale_order_id", "not in", legacy_order_ids)] if legacy_order_ids else []

    @api.model
    def _urgency_domain_negative_margin(self):
        return [("gross_margin", "<", 0), ("state", "not in", _TX_TERMINAL_STATES)]

    @api.model
    def _urgency_domain_delivered_uninvoiced(self):
        return [
            ("state", "=", "delivered"),
            "|",
            ("customer_invoice_id", "=", False),
            ("customer_invoice_id.state", "=", "draft"),
        ]

    @api.model
    def _urgency_domain_missing_docs(self):
        return [("compliance_status", "=", "missing"), ("state", "not in", ["draft", "cancelled"])]

    @api.model
    def _urgency_domain_supplier_not_ready(self):
        return [("state", "=", "supplier_not_ready")]

    @api.model
    def _urgency_domain_stalled_followup(self):
        return [
            ("supplier_confirmation_followup_count", ">=", 3),
            ("supplier_confirmation_received", "=", False),
            ("state", "not in", _TX_TERMINAL_STATES),
        ]

    @api.model
    def _urgency_domain_expiring_offers(self):
        horizon = fields.Date.context_today(self) + timedelta(days=3)
        return [
            ("state", "in", _OFFER_OPEN_STATES),
            ("valid_until", "!=", False),
            ("valid_until", "<=", horizon),
        ]

    @api.model
    def _urgency_domain_lead_errors(self):
        return [("state", "=", "error")]

    @api.model
    def _urgency_domain_commission_unlocked(self):
        """Closed, live (non-historical) transactions whose commission is not locked."""
        return self._live_closed_domain([("commission_locked", "=", False)])

    # ── Drill actions ────────────────────────────────────────────────────────

    def action_open_sales_dashboard(self):
        """Jump to Sales Pipeline Dashboard with its "Active" deals filter applied."""
        return {
            "type": "ir.actions.act_window",
            "name": "Sales Pipeline",
            "res_model": "plasticos.sales.dashboard",
            "view_mode": "list,kanban",
            "context": {"search_default_active_deals": 1},
        }

    def action_open_logistics_dashboard(self):
        """Jump to Logistics Dashboard."""
        return {
            "type": "ir.actions.act_window",
            "name": "Logistics Dashboard",
            "res_model": "plasticos.load.dashboard",
            "view_mode": "list",
        }

    def action_open_negative_margin(self):
        return self._kpi_drill("tx_negative_margin")

    def action_open_supplier_not_ready(self):
        return self._kpi_drill("tx_sup_not_ready")

    def action_open_stalled_followup(self):
        return self._kpi_drill("tx_stalled_followup")

    def action_open_delivered_uninvoiced(self):
        return self._kpi_drill("tx_delivered_uninvoiced")

    def action_open_missing_docs(self):
        return self._kpi_drill("tx_missing_docs")

    def action_open_expiring_offers(self):
        return self._kpi_drill("offer_expiring_soon")

    def action_open_commission_unlocked(self):
        return self._kpi_drill("commission_unlocked")

    def action_open_lead_errors(self):
        return self._kpi_drill("lead_error_open")

    def action_open_ai_pending_review(self):
        return self._kpi_drill("ai_pending_review")

    @api.model
    def action_open_admin_dashboard(self):
        """Main entry point: open the current company's KPI record, creating it if missing."""
        rec = self._get_or_create()
        return {
            "type": "ir.actions.act_window",
            "name": "RevOps Command Center",
            "res_model": "plasticos.admin.kpi",
            "res_id": rec.id,
            "view_mode": "form",
            "target": "current",
            "context": {"form_view_initial_mode": "readonly"},
        }

    def action_view_rep_performance(self):
        """Navigate to the standalone rep performance list (WTD/MTD/YTD)."""
        return {
            "type": "ir.actions.act_window",
            "name": "Rep Performance",
            "res_model": "plasticos.rep.performance",
            "view_mode": "list",
            "context": {"search_default_filter_mtd": 1},
        }


# ─────────────────────────────────────────────────────────────────────────────
# REP PERFORMANCE — SQL VIEW (one row per rep × period)
# ─────────────────────────────────────────────────────────────────────────────


class PlasticosRepPerformance(models.Model):
    """Rep performance SQL VIEW: one row per salesperson per period.

    Three rows per rep: WTD, MTD, YTD.
    Used in embedded list sub-view inside admin form.
    Sorted by period DESC, revenue DESC.
    """

    _name = "plasticos.rep.performance"
    _description = "Sales Rep Performance (SQL VIEW)"
    _auto = False
    _rec_name = "rep_name"
    _order = "period_sort asc, revenue_closed desc"

    rep_name = fields.Char(string="Rep", readonly=True)
    salesperson_id = fields.Many2one("res.users", readonly=True, ondelete="restrict")
    period = fields.Char(string="Period", readonly=True)
    period_sort = fields.Integer(string="_psort", readonly=True)

    deals_closed = fields.Integer(string="Closed (earned date)", readonly=True, help=_CLOSED_DEAL_HELP)
    revenue_closed = fields.Float(string="Closed-Deal Revenue", readonly=True, digits=(16, 2), help=_CLOSED_DEAL_HELP)
    gm_closed = fields.Float(string="Closed-Deal GM $", readonly=True, digits=(16, 2), help=_CLOSED_DEAL_HELP)
    gm_pct = fields.Float(string="GM %", readonly=True, digits=(5, 1))
    net_margin = fields.Float(string="Closed-Deal Net $", readonly=True, digits=(16, 2), help=_CLOSED_DEAL_HELP)
    commission = fields.Float(string="Earned Commission", readonly=True, digits=(16, 2), help=_CLOSED_DEAL_HELP)

    deals_open = fields.Integer(
        string="Open Deals (snapshot)",
        readonly=True,
        help="Open transactions right now; a point-in-time snapshot, the same in every period row.",
    )
    pipeline_val = fields.Float(
        string="Open Pipeline (snapshot)",
        readonly=True,
        digits=(16, 2),
        help="Revenue of open transactions right now; a point-in-time snapshot, not a period total.",
    )
    intakes_created = fields.Integer(string="Intakes", readonly=True)
    offers_sent = fields.Integer(string="Offers Sent", readonly=True)
    offers_accepted = fields.Integer(string="Acc'd", readonly=True)
    offer_acc_rate = fields.Float(string="Acc Rate %", readonly=True, digits=(5, 1))
    avg_gm_pct = fields.Float(string="Avg GM %", readonly=True, digits=(5, 1))

    def init(self):
        """One CTE per measure, each pre-aggregated per (user, period) before the join.

        Joining raw closed, open, intake and offer rows multiplies money by the
        join cardinality (F-002); aggregating first keeps every measure exact.
        Historical ERP trades are excluded exactly as in the Admin KPI SQL
        (DEC-009). Open pipeline is a point-in-time snapshot, identical in every
        period row.
        """
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE VIEW plasticos_rep_performance AS
            WITH periods AS (
                SELECT 'WTD' AS period_label, 1 AS period_sort,
                       date_trunc('week', NOW()) AS period_start
                UNION ALL
                SELECT 'MTD', 2, date_trunc('month', NOW())
                UNION ALL
                SELECT 'YTD', 3, date_trunc('year', NOW())
            ),
            reps AS (
                SELECT DISTINCT user_id FROM plasticos_transaction WHERE user_id IS NOT NULL
            ),
            closed_tx AS (
                SELECT t.id, t.user_id, t.revenue_total, t.gross_margin, t.net_margin,
                       t.commission_amount, t.commission_earned_date
                FROM plasticos_transaction t
                WHERE t.state = 'closed'
                  AND t.user_id IS NOT NULL
                  AND t.legacy_erp_history = FALSE
                  AND NOT EXISTS (
                      SELECT 1 FROM ir_model_data import_id
                      WHERE import_id.model = 'sale.order'
                        AND import_id.module = 'plasticos_transaction'
                        AND import_id.res_id = t.sale_order_id
                        AND import_id.name LIKE 'legacy_erp_so_%%'
                  )
            ),
            closed_agg AS (
                SELECT ct.user_id, p.period_label,
                       COUNT(ct.id)                              AS deals_closed,
                       COALESCE(SUM(ct.revenue_total), 0)        AS revenue_closed,
                       COALESCE(SUM(ct.gross_margin), 0)         AS gm_closed,
                       COALESCE(SUM(ct.net_margin), 0)           AS net_margin,
                       COALESCE(SUM(ct.commission_amount), 0)    AS commission
                FROM closed_tx ct
                JOIN periods p ON ct.commission_earned_date >= p.period_start
                GROUP BY ct.user_id, p.period_label
            ),
            open_agg AS (
                SELECT t.user_id,
                       COUNT(DISTINCT t.id)                      AS deals_open,
                       COALESCE(SUM(t.revenue_total), 0)         AS pipeline_val
                FROM plasticos_transaction t
                WHERE t.state NOT IN ('closed','cancelled')
                  AND t.user_id IS NOT NULL
                GROUP BY t.user_id
            ),
            intake_agg AS (
                SELECT i.assigned_user_id AS user_id, p.period_label,
                       COUNT(i.id)                               AS intakes_created
                FROM plasticos_intake i
                JOIN periods p ON i.create_date >= p.period_start
                WHERE i.assigned_user_id IS NOT NULL
                GROUP BY i.assigned_user_id, p.period_label
            ),
            offer_agg AS (
                SELECT i.assigned_user_id AS user_id, p.period_label,
                       COUNT(o.id) FILTER (WHERE o.state != 'draft')                  AS offers_sent,
                       COUNT(o.id) FILTER (WHERE o.state = 'accepted')                AS offers_accepted,
                       COUNT(o.id) FILTER (WHERE o.state IN ('accepted','rejected'))  AS offers_decided
                FROM plasticos_offer o
                JOIN plasticos_intake i ON i.id = o.intake_id
                JOIN periods p ON o.create_date >= p.period_start
                WHERE i.assigned_user_id IS NOT NULL
                GROUP BY i.assigned_user_id, p.period_label
            )
            SELECT
                ROW_NUMBER() OVER (ORDER BY r.user_id, p.period_sort) AS id,
                rp.name                                 AS rep_name,
                r.user_id                               AS salesperson_id,
                p.period_label                          AS period,
                p.period_sort                           AS period_sort,

                COALESCE(ca.deals_closed, 0)            AS deals_closed,
                COALESCE(ca.revenue_closed, 0)          AS revenue_closed,
                COALESCE(ca.gm_closed, 0)               AS gm_closed,
                CASE WHEN COALESCE(ca.revenue_closed, 0) = 0 THEN 0
                     ELSE ROUND((ca.gm_closed / ca.revenue_closed * 100)::numeric, 1)
                END                                     AS gm_pct,
                COALESCE(ca.net_margin, 0)              AS net_margin,
                COALESCE(ca.commission, 0)              AS commission,

                COALESCE(oa.deals_open, 0)              AS deals_open,
                COALESCE(oa.pipeline_val, 0)            AS pipeline_val,

                COALESCE(ia.intakes_created, 0)         AS intakes_created,
                COALESCE(fa.offers_sent, 0)             AS offers_sent,
                COALESCE(fa.offers_accepted, 0)         AS offers_accepted,
                CASE WHEN COALESCE(fa.offers_decided, 0) = 0 THEN 0
                     ELSE ROUND((fa.offers_accepted::numeric / fa.offers_decided * 100)::numeric, 1)
                END                                     AS offer_acc_rate,
                CASE WHEN COALESCE(ca.revenue_closed, 0) = 0 THEN 0
                     ELSE ROUND((ca.gm_closed / ca.revenue_closed * 100)::numeric, 1)
                END                                     AS avg_gm_pct

            FROM reps r
            CROSS JOIN periods p
            LEFT JOIN res_users u    ON u.id = r.user_id
            LEFT JOIN res_partner rp ON rp.id = u.partner_id
            LEFT JOIN closed_agg ca  ON ca.user_id = r.user_id AND ca.period_label = p.period_label
            LEFT JOIN open_agg oa    ON oa.user_id = r.user_id
            LEFT JOIN intake_agg ia  ON ia.user_id = r.user_id AND ia.period_label = p.period_label
            LEFT JOIN offer_agg fa   ON fa.user_id = r.user_id AND fa.period_label = p.period_label
        """)
