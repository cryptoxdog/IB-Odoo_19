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
from datetime import timedelta

from psycopg2 import errors as pg_errors

from odoo import api, fields, models, tools
from odoo.exceptions import ConcurrencyError

_logger = logging.getLogger(__name__)

PLASTICOS_TRANSACTION = "plasticos.transaction"
PLASTICOS_OFFER = "plasticos.offer"
PLASTICOS_WEB_LEAD = "plasticos.web.lead"

_TX_TERMINAL_STATES = ["closed", "cancelled"]

# Intakes, offers and web leads carry no company, so their KPIs cannot be scoped to the
# record's company (DEC-008). They are shown as all-company figures, never faked per company.
_ALL_COMPANIES_HELP = (
    "All companies (not company-scoped): intakes, offers and web leads carry no company, "
    "so this figure counts every company's records."
)
_OFFER_OPEN_STATES = ["draft", "sent", "responded"]
_LEGACY_SALE_XMLID_PREFIX = "legacy_erp_so_"

# DEC-002: closed-deal and earned-commission periods use commission_earned_date,
# never write_date. These are operational figures, not accounting revenue.
_CLOSED_DEAL_HELP = (
    "Operational closed-deal figure: live (non-historical) closed transactions of this company, "
    "attributed to the period of their commission_earned_date. Not accounting-recognized revenue; "
    "posted invoices, invoice aging and cash are separate figures with their own dates."
)

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
    intake_draft = fields.Integer(
        string="Intakes: Draft", compute="_compute_kpis", store=False, help=_ALL_COMPANIES_HELP
    )
    intake_matched = fields.Integer(
        string="Intakes: Matched", compute="_compute_kpis", store=False, help=_ALL_COMPANIES_HELP
    )
    intake_offer_sent = fields.Integer(
        string="Intakes: Offer Sent", compute="_compute_kpis", store=False, help=_ALL_COMPANIES_HELP
    )
    intake_processing = fields.Integer(
        string="Intakes: Processing", compute="_compute_kpis", store=False, help=_ALL_COMPANIES_HELP
    )
    intake_won_mtd = fields.Integer(
        string="Intakes Won (MTD)", compute="_compute_kpis", store=False, help=_ALL_COMPANIES_HELP
    )
    intake_lost_mtd = fields.Integer(
        string="Intakes Lost (MTD)", compute="_compute_kpis", store=False, help=_ALL_COMPANIES_HELP
    )
    intake_total_open = fields.Integer(
        string="Open Intakes", compute="_compute_kpis", store=False, help=_ALL_COMPANIES_HELP
    )

    # Offers
    offer_draft = fields.Integer(string="Offers: Draft", compute="_compute_kpis", store=False, help=_ALL_COMPANIES_HELP)
    offer_sent = fields.Integer(string="Offers: Sent", compute="_compute_kpis", store=False, help=_ALL_COMPANIES_HELP)
    offer_responded = fields.Integer(
        string="Offers: Responded", compute="_compute_kpis", store=False, help=_ALL_COMPANIES_HELP
    )
    offer_accepted_mtd = fields.Integer(
        string="Offers Accepted (MTD)", compute="_compute_kpis", store=False, help=_ALL_COMPANIES_HELP
    )
    offer_rejected_mtd = fields.Integer(
        string="Offers Rejected (MTD)", compute="_compute_kpis", store=False, help=_ALL_COMPANIES_HELP
    )
    offer_expired_mtd = fields.Integer(
        string="Offers Expired (MTD)", compute="_compute_kpis", store=False, help=_ALL_COMPANIES_HELP
    )
    offer_expiring_soon = fields.Integer(
        string="Expiring ≤3 Days", compute="_compute_kpis", store=False, help=_ALL_COMPANIES_HELP
    )

    # Deal Conversion
    offer_accept_rate_mtd = fields.Float(
        string="Offer Accept Rate %",
        compute="_compute_kpis",
        store=False,
        digits=(5, 1),
        help="Accepted / (Accepted+Rejected) × 100 MTD. " + _ALL_COMPANIES_HELP,
    )
    intake_win_rate_mtd = fields.Float(
        string="Intake Win Rate %",
        compute="_compute_kpis",
        store=False,
        digits=(5, 1),
        help="Won / (Won+Lost) × 100 MTD. " + _ALL_COMPANIES_HELP,
    )
    avg_intake_age_days = fields.Float(
        string="Avg Intake Age (days)", compute="_compute_kpis", store=False, digits=(5, 1), help=_ALL_COMPANIES_HELP
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
    lead_received_today = fields.Integer(
        string="Leads Today", compute="_compute_kpis", store=False, help=_ALL_COMPANIES_HELP
    )
    lead_received_wtd = fields.Integer(
        string="Leads WTD", compute="_compute_kpis", store=False, help=_ALL_COMPANIES_HELP
    )
    lead_received_mtd = fields.Integer(
        string="Leads MTD", compute="_compute_kpis", store=False, help=_ALL_COMPANIES_HELP
    )
    lead_hot_mtd = fields.Integer(
        string="HOT Leads MTD", compute="_compute_kpis", store=False, help=_ALL_COMPANIES_HELP
    )
    lead_cold_mtd = fields.Integer(
        string="COLD Leads MTD", compute="_compute_kpis", store=False, help=_ALL_COMPANIES_HELP
    )
    lead_error_open = fields.Integer(
        string="Lead Errors (open)", compute="_compute_kpis", store=False, help=_ALL_COMPANIES_HELP
    )
    lead_hot_rate_mtd = fields.Float(
        string="Lead→HOT Rate %", compute="_compute_kpis", store=False, digits=(5, 1), help=_ALL_COMPANIES_HELP
    )

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
        help="Leads processed with ai_normalized != null MTD" + " " + _ALL_COMPANIES_HELP,
    )
    ai_leads_vision_mtd = fields.Integer(
        string="Vision Analyzed MTD",
        compute="_compute_kpis",
        store=False,
        help="Leads with ai_vision_results != null MTD" + " " + _ALL_COMPANIES_HELP,
    )
    ai_hot_auto_mtd = fields.Integer(
        string="Auto-HOT MTD",
        compute="_compute_kpis",
        store=False,
        help="HOT leads auto-classified by AI (not manually overridden)" + " " + _ALL_COMPANIES_HELP,
    )
    ai_cold_auto_mtd = fields.Integer(
        string="Auto-COLD MTD", compute="_compute_kpis", store=False, help=_ALL_COMPANIES_HELP
    )
    ai_error_mtd = fields.Integer(
        string="AI Errors MTD",
        compute="_compute_kpis",
        store=False,
        help="Leads that hit state=error during triage MTD" + " " + _ALL_COMPANIES_HELP,
    )
    ai_hot_rate_mtd = fields.Float(
        string="AI HOT Rate %", compute="_compute_kpis", store=False, digits=(5, 1), help=_ALL_COMPANIES_HELP
    )
    ai_intakes_auto_created = fields.Integer(
        string="Auto-Intakes MTD",
        compute="_compute_kpis",
        store=False,
        help="Intakes created automatically from HOT web leads MTD" + " " + _ALL_COMPANIES_HELP,
    )
    ai_manual_override_mtd = fields.Integer(
        string="Manual Overrides MTD",
        compute="_compute_kpis",
        store=False,
        help="Cold leads manually forced to HOT by admin MTD" + " " + _ALL_COMPANIES_HELP,
    )
    ai_pending_review = fields.Integer(
        string="Pending Review",
        compute="_compute_kpis",
        store=False,
        help="HOT intakes from web leads with no partner yet (need buyer-match action)" + " " + _ALL_COMPANIES_HELP,
    )
    ai_normalized_enabled = fields.Boolean(string="AI Normalizer Active", compute="_compute_ai_config", store=False)
    ai_vision_enabled = fields.Boolean(string="Vision Active", compute="_compute_ai_config", store=False)
    ai_openai_key_set = fields.Boolean(string="OpenAI Key Set", compute="_compute_ai_config", store=False)

    # ══════════════════════════════════════════════════════════════════════════
    # COMPUTE
    # ══════════════════════════════════════════════════════════════════════════

    @api.depends()
    def _compute_kpis(self):
        for rec in self:
            cr = self.env.cr
            company_id = rec.company_id.id
            for name in URGENCY_KPIS:
                rec[name] = rec._urgency_count(name)

            # ── Date helpers ──────────────────────────────────────────────────
            cr.execute("""
                SELECT
                    date_trunc('month', NOW())::date  AS mtd_start,
                    date_trunc('year',  NOW())::date  AS ytd_start,
                    date_trunc('week',  NOW())::date  AS wtd_start,
                    NOW()::date                       AS today
            """)
            row = cr.dictfetchone()
            mtd = row["mtd_start"]
            ytd = row["ytd_start"]
            wtd = row["wtd_start"]
            today = row["today"]

            # ── INTAKES ───────────────────────────────────────────────────────
            cr.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE status='draft')                AS draft,
                    COUNT(*) FILTER (WHERE status='matched')              AS matched,
                    COUNT(*) FILTER (WHERE status='offer_sent')           AS offer_sent,
                    COUNT(*) FILTER (WHERE status='processing')           AS processing,
                    COUNT(*) FILTER (WHERE status='won'
                                     AND create_date >= %s)               AS won_mtd,
                    COUNT(*) FILTER (WHERE status='lost'
                                     AND create_date >= %s)               AS lost_mtd,
                    COUNT(*) FILTER (WHERE status NOT IN ('won','lost','expired')) AS total_open,
                    AVG(EXTRACT(EPOCH FROM NOW()-create_date)/86400)
                        FILTER (WHERE status NOT IN ('won','lost','expired','draft')) AS avg_age
                FROM plasticos_intake
            """,
                (mtd, mtd),
            )
            r = cr.dictfetchone()
            rec.intake_draft = r["draft"] or 0
            rec.intake_matched = r["matched"] or 0
            rec.intake_offer_sent = r["offer_sent"] or 0
            rec.intake_processing = r["processing"] or 0
            rec.intake_won_mtd = r["won_mtd"] or 0
            rec.intake_lost_mtd = r["lost_mtd"] or 0
            rec.intake_total_open = r["total_open"] or 0
            rec.avg_intake_age_days = round(r["avg_age"] or 0, 1)

            won = rec.intake_won_mtd
            lost = rec.intake_lost_mtd
            rec.intake_win_rate_mtd = round(won / (won + lost) * 100, 1) if (won + lost) else 0.0

            # ── OFFERS ────────────────────────────────────────────────────────
            cr.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE state='draft')                 AS draft,
                    COUNT(*) FILTER (WHERE state='sent')                  AS sent,
                    COUNT(*) FILTER (WHERE state='responded')             AS responded,
                    COUNT(*) FILTER (WHERE state='accepted'
                                     AND create_date >= %s)               AS accepted_mtd,
                    COUNT(*) FILTER (WHERE state='rejected'
                                     AND create_date >= %s)               AS rejected_mtd,
                    COUNT(*) FILTER (WHERE state='expired'
                                     AND create_date >= %s)               AS expired_mtd
                FROM plasticos_offer
            """,
                (mtd, mtd, mtd),
            )
            r = cr.dictfetchone()
            rec.offer_draft = r["draft"] or 0
            rec.offer_sent = r["sent"] or 0
            rec.offer_responded = r["responded"] or 0
            rec.offer_accepted_mtd = r["accepted_mtd"] or 0
            rec.offer_rejected_mtd = r["rejected_mtd"] or 0
            rec.offer_expired_mtd = r["expired_mtd"] or 0

            acc = rec.offer_accepted_mtd
            rej = rec.offer_rejected_mtd
            rec.offer_accept_rate_mtd = round(acc / (acc + rej) * 100, 1) if (acc + rej) else 0.0

            # ── TRANSACTIONS ──────────────────────────────────────────────────
            cr.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE state NOT IN ('closed','cancelled'))         AS tx_open,
                    COUNT(*) FILTER (WHERE state IN ('dispatched','in_progress','in_transit')) AS in_motion,
                    COUNT(*) FILTER (WHERE state='closed' AND legacy_erp_history = FALSE
                                     AND commission_earned_date >= %s
                                     AND NOT EXISTS (
                                         SELECT 1 FROM ir_model_data import_id
                                         WHERE import_id.model = 'sale.order'
                                           AND import_id.module = 'plasticos_transaction'
                                           AND import_id.res_id = plasticos_transaction.sale_order_id
                                           AND import_id.name LIKE 'legacy_erp_so_%%'
                                     ))                                                AS closed_mtd,
                    SUM(revenue_total) FILTER (WHERE state NOT IN ('closed','cancelled')
                                              AND revenue_total > 0)                   AS pipeline_val
                FROM plasticos_transaction
                WHERE sale_order_id IN (SELECT so.id FROM sale_order so WHERE so.company_id = %s)
            """,
                (mtd, company_id),
            )
            r = cr.dictfetchone()
            rec.tx_open = r["tx_open"] or 0
            rec.tx_in_motion = r["in_motion"] or 0
            rec.tx_closed_mtd = r["closed_mtd"] or 0
            rec.pipeline_value_open = r["pipeline_val"] or 0.0

            # ── FINANCIALS ────────────────────────────────────────────────────
            cr.execute(
                """
                SELECT
                    SUM(revenue_total)   FILTER (WHERE commission_earned_date >= %s)  AS rev_mtd,
                    SUM(revenue_total)   FILTER (WHERE commission_earned_date >= %s)  AS rev_ytd,
                    SUM(gross_margin)    FILTER (WHERE commission_earned_date >= %s)  AS gm_mtd,
                    SUM(gross_margin)    FILTER (WHERE commission_earned_date >= %s)  AS gm_ytd,
                    SUM(net_margin)      FILTER (WHERE commission_earned_date >= %s)  AS nm_mtd,
                    SUM(net_margin)      FILTER (WHERE commission_earned_date >= %s)  AS nm_ytd,
                    SUM(commission_amount) FILTER (WHERE commission_earned_date >= %s) AS comm_mtd,
                    SUM(commission_amount) FILTER (WHERE commission_earned_date >= %s) AS comm_ytd
                FROM plasticos_transaction
                WHERE state='closed' AND legacy_erp_history = FALSE
                  AND sale_order_id IN (SELECT so.id FROM sale_order so WHERE so.company_id = %s)
                  AND NOT EXISTS (
                    SELECT 1 FROM ir_model_data import_id
                    WHERE import_id.model = 'sale.order'
                      AND import_id.module = 'plasticos_transaction'
                      AND import_id.res_id = plasticos_transaction.sale_order_id
                      AND import_id.name LIKE 'legacy_erp_so_%%'
                  )
            """,
                (mtd, ytd, mtd, ytd, mtd, ytd, mtd, ytd, company_id),
            )
            r = cr.dictfetchone()
            rec.revenue_mtd = r["rev_mtd"] or 0.0
            rec.revenue_ytd = r["rev_ytd"] or 0.0
            rec.gm_mtd = r["gm_mtd"] or 0.0
            rec.gm_ytd = r["gm_ytd"] or 0.0
            rec.net_margin_mtd = r["nm_mtd"] or 0.0
            rec.net_margin_ytd = r["nm_ytd"] or 0.0
            rec.commission_mtd = r["comm_mtd"] or 0.0
            rec.commission_ytd = r["comm_ytd"] or 0.0

            rev_mtd = rec.revenue_mtd
            rev_ytd = rec.revenue_ytd
            rec.gm_pct_mtd = round(rec.gm_mtd / rev_mtd * 100, 1) if rev_mtd else 0.0
            rec.gm_pct_ytd = round(rec.gm_ytd / rev_ytd * 100, 1) if rev_ytd else 0.0

            # ── WEB LEADS ─────────────────────────────────────────────────────
            cr.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE create_date::date = %s)        AS today,
                    COUNT(*) FILTER (WHERE create_date >= %s)             AS wtd,
                    COUNT(*) FILTER (WHERE create_date >= %s)             AS mtd,
                    COUNT(*) FILTER (WHERE decision='hot'
                                     AND create_date >= %s)               AS hot_mtd,
                    COUNT(*) FILTER (WHERE decision='cold'
                                     AND create_date >= %s)               AS cold_mtd
                FROM plasticos_web_lead
            """,
                (today, wtd, mtd, mtd, mtd),
            )
            r = cr.dictfetchone()
            rec.lead_received_today = r["today"] or 0
            rec.lead_received_wtd = r["wtd"] or 0
            rec.lead_received_mtd = r["mtd"] or 0
            rec.lead_hot_mtd = r["hot_mtd"] or 0
            rec.lead_cold_mtd = r["cold_mtd"] or 0

            total_leads = rec.lead_hot_mtd + rec.lead_cold_mtd
            rec.lead_hot_rate_mtd = round(rec.lead_hot_mtd / total_leads * 100, 1) if total_leads else 0.0

            # ── AI STATS ──────────────────────────────────────────────────────
            cr.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE ai_normalized IS NOT NULL
                                     AND create_date >= %s)               AS normalized_mtd,
                    COUNT(*) FILTER (WHERE ai_vision_results IS NOT NULL
                                     AND create_date >= %s)               AS vision_mtd,
                    COUNT(*) FILTER (WHERE decision='hot'
                                     AND state='intake_created'
                                     AND create_date >= %s)               AS hot_auto_mtd,
                    COUNT(*) FILTER (WHERE decision='cold'
                                     AND create_date >= %s)               AS cold_auto_mtd,
                    COUNT(*) FILTER (WHERE state='error'
                                     AND create_date >= %s)               AS err_mtd
                FROM plasticos_web_lead
            """,
                (mtd, mtd, mtd, mtd, mtd),
            )
            r = cr.dictfetchone()
            rec.ai_leads_normalized_mtd = r["normalized_mtd"] or 0
            rec.ai_leads_vision_mtd = r["vision_mtd"] or 0
            rec.ai_hot_auto_mtd = r["hot_auto_mtd"] or 0
            rec.ai_cold_auto_mtd = r["cold_auto_mtd"] or 0
            rec.ai_error_mtd = r["err_mtd"] or 0

            hot = rec.ai_hot_auto_mtd
            cold = rec.ai_cold_auto_mtd
            rec.ai_hot_rate_mtd = round(hot / (hot + cold) * 100, 1) if (hot + cold) else 0.0

            # Auto-intakes: HOT leads that created intakes MTD
            cr.execute(
                """
                SELECT COUNT(*) FROM plasticos_intake i
                WHERE i.source_lead_id IS NOT NULL
                AND i.create_date >= %s
            """,
                (mtd,),
            )
            rec.ai_intakes_auto_created = cr.fetchone()[0] or 0

            # Manual overrides: COLD leads forced to HOT
            cr.execute(
                """
                SELECT COUNT(*) FROM plasticos_web_lead
                WHERE decision='hot'
                AND triage_log ILIKE '%%Manual override%%'
                AND create_date >= %s
            """,
                (mtd,),
            )
            rec.ai_manual_override_mtd = cr.fetchone()[0] or 0

            # Pending review: HOT intakes from web leads with no partner
            cr.execute("""
                SELECT COUNT(*) FROM plasticos_intake
                WHERE source_lead_id IS NOT NULL
                AND partner_id IS NULL
                AND status NOT IN ('won','lost','expired')
            """)
            rec.ai_pending_review = cr.fetchone()[0] or 0

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
        if rec:
            return rec
        try:
            with self.env.cr.savepoint():
                return self.create({"company_id": company.id})
        except pg_errors.UniqueViolation as exc:
            # A concurrent request created this company's record first. Under REPEATABLE READ
            # this transaction cannot see it, so Odoo's request retry (service.model.retrying)
            # re-runs the request, which then finds the committed record.
            raise ConcurrencyError(f"Admin KPI record for company {company.id} was created concurrently") from exc

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

    # ── DEC-007 urgency declarations ─────────────────────────────────────────

    def _kpi_company(self):
        """The company a KPI record counts for; the current company outside a single record."""
        if len(self) == 1 and self.company_id:
            return self.company_id
        return self.env.company

    def _urgency_domain(self, kpi_name):
        """Return the one domain that both counts and drills the urgency KPI.

        Transaction KPIs are scoped to the record's company through the sale
        order (DEC-008). Offers and web leads carry no company.
        """
        _title, model_name, builder = URGENCY_KPIS[kpi_name]
        domain = getattr(self, builder)()
        if model_name == PLASTICOS_TRANSACTION:
            domain = [("sale_order_id.company_id", "=", self._kpi_company().id), *domain]
        return domain

    def _urgency_count(self, kpi_name):
        _title, model_name, _builder = URGENCY_KPIS[kpi_name]
        return self.env[model_name].search_count(self._urgency_domain(kpi_name))

    def _urgency_drill(self, kpi_name):
        title, model_name, _builder = URGENCY_KPIS[kpi_name]
        return {
            "type": "ir.actions.act_window",
            "name": title,
            "res_model": model_name,
            "view_mode": "list,form",
            "domain": self._urgency_domain(kpi_name),
            "target": "current",
        }

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
        """Closed, live (non-historical) transactions whose commission is not locked.

        Historical ERP trades are excluded the same two ways the financial KPIs
        and commission payouts exclude them: the legacy_erp_history flag, and a
        sale order imported under a legacy_erp_so_* external id.
        """
        domain = [
            ("state", "=", "closed"),
            ("legacy_erp_history", "=", False),
            ("commission_locked", "=", False),
        ]
        orders = self.env[PLASTICOS_TRANSACTION].search(domain).sale_order_id
        if not orders:
            return domain
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
        if legacy_order_ids:
            domain.append(("sale_order_id", "not in", legacy_order_ids))
        return domain

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
        return self._urgency_drill("tx_negative_margin")

    def action_open_supplier_not_ready(self):
        return self._urgency_drill("tx_sup_not_ready")

    def action_open_stalled_followup(self):
        return self._urgency_drill("tx_stalled_followup")

    def action_open_delivered_uninvoiced(self):
        return self._urgency_drill("tx_delivered_uninvoiced")

    def action_open_missing_docs(self):
        return self._urgency_drill("tx_missing_docs")

    def action_open_expiring_offers(self):
        return self._urgency_drill("offer_expiring_soon")

    def action_open_commission_unlocked(self):
        return self._urgency_drill("commission_unlocked")

    def action_open_lead_errors(self):
        return self._urgency_drill("lead_error_open")

    def action_open_ai_pending_review(self):
        return {
            "type": "ir.actions.act_window",
            "name": "HOT Intakes Pending Buyer Match",
            "res_model": "plasticos.intake",
            "view_mode": "list,form",
            "domain": [
                ("source_lead_id", "!=", False),
                ("partner_id", "=", False),
                ("status", "not in", ["won", "lost", "expired"]),
            ],
        }

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
