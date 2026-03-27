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

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# KPI SINGLETON
# ─────────────────────────────────────────────────────────────────────────────


class PlasticosAdminKpi(models.Model):
    """Singleton record holding all RevOps KPIs for the admin command center.

    One record per company. Refreshed by action_refresh() (button or cron).
    All fields are stored=False computed fields reading live from the DB.
    """

    _name = "plasticos.admin.kpi"
    _description = "Admin RevOps KPI Snapshot"
    _rec_name = "id"

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
    tx_closed_mtd = fields.Integer(string="Closed (MTD)", compute="_compute_kpis", store=False)

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

    revenue_mtd = fields.Float(string="Revenue MTD", compute="_compute_kpis", store=False)
    revenue_ytd = fields.Float(string="Revenue YTD", compute="_compute_kpis", store=False)
    gm_mtd = fields.Float(string="Gross Margin MTD", compute="_compute_kpis", store=False)
    gm_ytd = fields.Float(string="Gross Margin YTD", compute="_compute_kpis", store=False)
    gm_pct_mtd = fields.Float(string="GM % MTD", compute="_compute_kpis", store=False, digits=(5, 1))
    gm_pct_ytd = fields.Float(string="GM % YTD", compute="_compute_kpis", store=False, digits=(5, 1))
    net_margin_mtd = fields.Float(string="Net Margin MTD", compute="_compute_kpis", store=False)
    net_margin_ytd = fields.Float(string="Net Margin YTD", compute="_compute_kpis", store=False)
    commission_mtd = fields.Float(string="Commission MTD", compute="_compute_kpis", store=False)
    commission_ytd = fields.Float(string="Commission YTD", compute="_compute_kpis", store=False)
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
    # COMPUTE
    # ══════════════════════════════════════════════════════════════════════════

    @api.depends()
    def _compute_kpis(self):
        for rec in self:
            cr = self.env.cr

            # ── Date helpers ──────────────────────────────────────────────────
            cr.execute("""
                SELECT
                    date_trunc('month', NOW())::date  AS mtd_start,
                    date_trunc('year',  NOW())::date  AS ytd_start,
                    date_trunc('week',  NOW())::date  AS wtd_start,
                    NOW()::date                       AS today,
                    (NOW() + INTERVAL '3 days')::date AS in_3_days
            """)
            row = cr.dictfetchone()
            mtd = row["mtd_start"]
            ytd = row["ytd_start"]
            wtd = row["wtd_start"]
            today = row["today"]
            in_3d = row["in_3_days"]

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
                                     AND create_date >= %s)               AS expired_mtd,
                    COUNT(*) FILTER (WHERE state IN ('draft','sent','responded')
                                     AND valid_until IS NOT NULL
                                     AND valid_until <= %s)               AS expiring_soon
                FROM plasticos_offer
            """,
                (mtd, mtd, mtd, in_3d),
            )
            r = cr.dictfetchone()
            rec.offer_draft = r["draft"] or 0
            rec.offer_sent = r["sent"] or 0
            rec.offer_responded = r["responded"] or 0
            rec.offer_accepted_mtd = r["accepted_mtd"] or 0
            rec.offer_rejected_mtd = r["rejected_mtd"] or 0
            rec.offer_expired_mtd = r["expired_mtd"] or 0
            rec.offer_expiring_soon = r["expiring_soon"] or 0

            acc = rec.offer_accepted_mtd
            rej = rec.offer_rejected_mtd
            rec.offer_accept_rate_mtd = round(acc / (acc + rej) * 100, 1) if (acc + rej) else 0.0

            # ── TRANSACTIONS ──────────────────────────────────────────────────
            cr.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE state NOT IN ('closed','cancelled'))         AS tx_open,
                    COUNT(*) FILTER (WHERE state IN ('dispatched','in_progress','in_transit')) AS in_motion,
                    COUNT(*) FILTER (WHERE state='delivered'
                                     AND (customer_invoice_id IS NULL
                                          OR EXISTS(
                                            SELECT 1 FROM account_move am
                                            WHERE am.id=customer_invoice_id
                                            AND am.state='draft')))                    AS delivered_uninv,
                    COUNT(*) FILTER (WHERE compliance_status='missing'
                                     AND state NOT IN ('draft','cancelled'))            AS missing_docs,
                    COUNT(*) FILTER (WHERE gross_margin < 0
                                     AND state NOT IN ('closed','cancelled'))           AS neg_margin,
                    COUNT(*) FILTER (WHERE state='supplier_not_ready')                 AS sup_not_ready,
                    COUNT(*) FILTER (WHERE supplier_confirmation_followup_count >= 3
                                     AND supplier_confirmation_received IS NULL
                                     AND state NOT IN ('closed','cancelled'))           AS stalled_fu,
                    COUNT(*) FILTER (WHERE state='closed'
                                     AND write_date >= %s)                             AS closed_mtd,
                    SUM(revenue_total) FILTER (WHERE state NOT IN ('closed','cancelled')
                                              AND revenue_total > 0)                   AS pipeline_val
                FROM plasticos_transaction
            """,
                (mtd,),
            )
            r = cr.dictfetchone()
            rec.tx_open = r["tx_open"] or 0
            rec.tx_in_motion = r["in_motion"] or 0
            rec.tx_delivered_uninvoiced = r["delivered_uninv"] or 0
            rec.tx_missing_docs = r["missing_docs"] or 0
            rec.tx_negative_margin = r["neg_margin"] or 0
            rec.tx_sup_not_ready = r["sup_not_ready"] or 0
            rec.tx_stalled_followup = r["stalled_fu"] or 0
            rec.tx_closed_mtd = r["closed_mtd"] or 0
            rec.pipeline_value_open = r["pipeline_val"] or 0.0

            # ── FINANCIALS ────────────────────────────────────────────────────
            cr.execute(
                """
                SELECT
                    SUM(revenue_total)   FILTER (WHERE write_date >= %s)  AS rev_mtd,
                    SUM(revenue_total)   FILTER (WHERE write_date >= %s)  AS rev_ytd,
                    SUM(gross_margin)    FILTER (WHERE write_date >= %s)  AS gm_mtd,
                    SUM(gross_margin)    FILTER (WHERE write_date >= %s)  AS gm_ytd,
                    SUM(net_margin)      FILTER (WHERE write_date >= %s)  AS nm_mtd,
                    SUM(net_margin)      FILTER (WHERE write_date >= %s)  AS nm_ytd,
                    SUM(commission_amount) FILTER (WHERE write_date >= %s) AS comm_mtd,
                    SUM(commission_amount) FILTER (WHERE write_date >= %s) AS comm_ytd,
                    COUNT(*) FILTER (WHERE state='closed'
                                     AND commission_locked=FALSE)         AS comm_unlocked
                FROM plasticos_transaction
                WHERE state='closed'
            """,
                (mtd, ytd, mtd, ytd, mtd, ytd, mtd, ytd),
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
            rec.commission_unlocked = r["comm_unlocked"] or 0

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
                                     AND create_date >= %s)               AS cold_mtd,
                    COUNT(*) FILTER (WHERE state='error')                 AS err_open
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
            rec.lead_error_open = r["err_open"] or 0

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

            rec.last_refresh = fields.Datetime.now()

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
                config = self.env[config_model].sudo().get_config()
                rec.ai_normalized_enabled = bool(getattr(config, "ai_enabled", False))
                rec.ai_vision_enabled = bool(getattr(config, "vision_enabled", False))
                rec.ai_openai_key_set = bool(getattr(config, "openai_api_key", ""))
            except Exception:
                rec.ai_normalized_enabled = False
                rec.ai_vision_enabled = False
                rec.ai_openai_key_set = False

    # ── Singleton helper ──────────────────────────────────────────────────────

    @api.model
    def _get_or_create(self):
        """Return singleton record, creating if missing."""
        rec = self.search([], limit=1)
        if not rec:
            rec = self.create({})
        return rec

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_refresh(self):
        """Force re-compute all KPIs."""
        self._compute_kpis()
        self._compute_ai_config()
        return True

    def action_open_sales_dashboard(self):
        """Jump to Sales Pipeline Dashboard (filtered to open deals)."""
        return {
            "type": "ir.actions.act_window",
            "name": "Sales Pipeline",
            "res_model": "plasticos.sales.dashboard",
            "view_mode": "list,kanban",
            "context": {"search_default_filter_open": 1},
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
        return {
            "type": "ir.actions.act_window",
            "name": "⚠ Negative Margin Deals",
            "res_model": "plasticos.sales.dashboard",
            "view_mode": "list",
            "domain": [("has_negative_margin", "=", True)],
        }

    def action_open_supplier_not_ready(self):
        return {
            "type": "ir.actions.act_window",
            "name": "⚠ Supplier Not Ready",
            "res_model": "plasticos.sales.dashboard",
            "view_mode": "list",
            "domain": [("state", "=", "supplier_not_ready")],
        }

    def action_open_stalled_followup(self):
        return {
            "type": "ir.actions.act_window",
            "name": "⚠ 3+ Followups No Response",
            "res_model": "plasticos.sales.dashboard",
            "view_mode": "list",
            "domain": [
                ("supplier_followup_count", ">=", 3),
                ("is_supplier_confirmed", "=", False),
            ],
        }

    def action_open_delivered_uninvoiced(self):
        return {
            "type": "ir.actions.act_window",
            "name": "⚠ Delivered — No Posted Invoice",
            "res_model": "plasticos.sales.dashboard",
            "view_mode": "list",
            "domain": [("state", "=", "delivered"), ("invoice_state", "in", ["draft", "-"])],
        }

    def action_open_missing_docs(self):
        return {
            "type": "ir.actions.act_window",
            "name": "⚠ Missing Docs",
            "res_model": "plasticos.sales.dashboard",
            "view_mode": "list",
            "domain": [("compliance_status", "=", "missing")],
        }

    def action_open_expiring_offers(self):
        return {
            "type": "ir.actions.act_window",
            "name": "⏰ Offers Expiring ≤3 Days",
            "res_model": "plasticos.offer",
            "view_mode": "list,form",
            "domain": [
                ("state", "in", ["draft", "sent", "responded"]),
                ("valid_until", "<=", fields.Date.today() + __import__("datetime").timedelta(days=3)),
            ],
        }

    def action_open_commission_unlocked(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Commission Unlocked on Closed TXs",
            "res_model": "plasticos.sales.dashboard",
            "view_mode": "list",
            "domain": [("state", "=", "closed"), ("commission_locked", "=", False)],
        }

    def action_open_lead_errors(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Lead Triage Errors",
            "res_model": "plasticos.web.lead",
            "view_mode": "list,form",
            "domain": [("state", "=", "error")],
        }

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
        """Main entry point: ensure singleton exists and open form."""
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
    salesperson_id = fields.Many2one("res.users", readonly=True)
    period = fields.Char(string="Period", readonly=True)
    period_sort = fields.Integer(string="_psort", readonly=True)

    deals_closed = fields.Integer(string="Closed", readonly=True)
    revenue_closed = fields.Float(string="Revenue", readonly=True, digits=(16, 2))
    gm_closed = fields.Float(string="GM $", readonly=True, digits=(16, 2))
    gm_pct = fields.Float(string="GM %", readonly=True, digits=(5, 1))
    net_margin = fields.Float(string="Net $", readonly=True, digits=(16, 2))
    commission = fields.Float(string="Commission", readonly=True, digits=(16, 2))

    deals_open = fields.Integer(string="Open Deals", readonly=True)
    pipeline_val = fields.Float(string="Pipeline", readonly=True, digits=(16, 2))
    intakes_created = fields.Integer(string="Intakes", readonly=True)
    offers_sent = fields.Integer(string="Offers Sent", readonly=True)
    offers_accepted = fields.Integer(string="Acc'd", readonly=True)
    offer_acc_rate = fields.Float(string="Acc Rate %", readonly=True, digits=(5, 1))
    avg_gm_pct = fields.Float(string="Avg GM %", readonly=True, digits=(5, 1))

    def init(self):
        self.env.cr.execute("DROP VIEW IF EXISTS plasticos_rep_performance")
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
            closed_tx AS (
                SELECT
                    t.id,
                    t.user_id,
                    rp.name AS rep_name,
                    t.revenue_total,
                    t.gross_margin,
                    t.net_margin,
                    t.commission_amount,
                    t.write_date
                FROM plasticos_transaction t
                LEFT JOIN res_users u ON u.id = t.user_id
                LEFT JOIN res_partner rp ON rp.id = u.partner_id
                WHERE t.state = 'closed'
            ),
            open_tx AS (
                SELECT
                    t.user_id,
                    t.revenue_total
                FROM plasticos_transaction t
                WHERE t.state NOT IN ('closed','cancelled')
            )
            SELECT
                ROW_NUMBER() OVER () AS id,
                rp.name             AS rep_name,
                t.user_id           AS salesperson_id,
                p.period_label      AS period,
                p.period_sort       AS period_sort,

                COUNT(DISTINCT ct.id) FILTER (WHERE ct.write_date >= p.period_start) AS deals_closed,
                COALESCE(SUM(ct.revenue_total)  FILTER (WHERE ct.write_date >= p.period_start), 0) AS revenue_closed,
                COALESCE(SUM(ct.gross_margin)   FILTER (WHERE ct.write_date >= p.period_start), 0) AS gm_closed,
                CASE WHEN COALESCE(SUM(ct.revenue_total) FILTER (WHERE ct.write_date >= p.period_start),0) = 0 THEN 0
                     ELSE ROUND((COALESCE(SUM(ct.gross_margin) FILTER (WHERE ct.write_date >= p.period_start),0)
                          / SUM(ct.revenue_total) FILTER (WHERE ct.write_date >= p.period_start) * 100)::numeric, 1)
                END                             AS gm_pct,
                COALESCE(SUM(ct.net_margin)     FILTER (WHERE ct.write_date >= p.period_start), 0) AS net_margin,
                COALESCE(SUM(ct.commission_amount) FILTER (WHERE ct.write_date >= p.period_start), 0) AS commission,

                COUNT(DISTINCT ot.user_id)                                         AS deals_open,
                COALESCE(SUM(ot.revenue_total), 0)                                 AS pipeline_val,

                COUNT(DISTINCT i.id) FILTER (WHERE i.create_date >= p.period_start) AS intakes_created,

                COUNT(DISTINCT o.id) FILTER (WHERE o.create_date >= p.period_start
                                              AND o.state != 'draft')              AS offers_sent,
                COUNT(DISTINCT o.id) FILTER (WHERE o.create_date >= p.period_start
                                              AND o.state = 'accepted')            AS offers_accepted,

                CASE WHEN COUNT(o.id) FILTER (WHERE o.create_date >= p.period_start
                                              AND o.state IN ('accepted','rejected')) = 0 THEN 0
                     ELSE ROUND((
                         COUNT(o.id) FILTER (WHERE o.create_date >= p.period_start AND o.state='accepted')::numeric
                         / COUNT(o.id) FILTER (WHERE o.create_date >= p.period_start
                                               AND o.state IN ('accepted','rejected'))
                         * 100
                     )::numeric, 1)
                END                             AS offer_acc_rate,

                CASE WHEN COALESCE(SUM(ct.revenue_total) FILTER (WHERE ct.write_date >= p.period_start),0) = 0 THEN 0
                     ELSE ROUND((
                         COALESCE(SUM(ct.gross_margin) FILTER (WHERE ct.write_date >= p.period_start),0)
                         / COALESCE(SUM(ct.revenue_total) FILTER (WHERE ct.write_date >= p.period_start),1)
                         * 100
                     )::numeric, 1)
                END                             AS avg_gm_pct

            FROM (SELECT DISTINCT user_id FROM plasticos_transaction WHERE user_id IS NOT NULL) t
            CROSS JOIN periods p
            LEFT JOIN res_users u   ON u.id = t.user_id
            LEFT JOIN res_partner rp ON rp.id = u.partner_id
            LEFT JOIN closed_tx ct  ON ct.user_id = t.user_id
            LEFT JOIN open_tx ot    ON ot.user_id = t.user_id
            LEFT JOIN plasticos_intake i    ON i.assigned_user_id = t.user_id
            LEFT JOIN plasticos_offer  o    ON o.supplier_id IN (
                SELECT DISTINCT supplier_id FROM plasticos_transaction WHERE user_id = t.user_id
            )
            GROUP BY t.user_id, rp.name, p.period_label, p.period_sort
        """)
