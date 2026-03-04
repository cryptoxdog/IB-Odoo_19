from odoo import api, fields, models


class MaterialProfileCRMBridge(models.Model):
    _inherit = "plasticos.material.profile"

    # ── Match Stats (per-profile, NOT per-partner) ──────────
    match_count = fields.Integer(
        string="Match Count",
        compute="_compute_match_stats",
        store=True,
    )
    best_match_score = fields.Float(
        string="Best Match Score",
        digits=(5, 2),
        compute="_compute_match_stats",
        store=True,
    )
    pending_match_count = fields.Integer(
        string="Pending Matches",
        compute="_compute_match_stats",
        store=True,
    )

    # ── Transaction Stats (per-profile) ─────────────────────
    transaction_count = fields.Integer(
        string="Transactions",
        compute="_compute_tx_stats",
        store=True,
    )
    total_revenue = fields.Float(
        string="Total Revenue",
        compute="_compute_tx_stats",
        store=True,
    )

    # ── Logistics: Last Load Shipped ────────────────────────
    last_pickup_date = fields.Datetime(
        string="Last Load Shipped",
        compute="_compute_tx_stats",
        store=True,
        help="Most recent pickup_datetime from linked loads.",
    )

    @api.depends("partner_id", "polymer_id")
    def _compute_match_stats(self):
        """Match results link through intake → intake.partner_id + polymer.

        A match is 'for this profile' when the intake's supplier and
        polymer match this material profile's partner + polymer.
        """
        MatchResult = self.env["plasticos.match.result"]
        Intake = self.env["plasticos.intake"]
        for rec in self:
            if not rec.partner_id or not rec.polymer_id:
                rec.match_count = 0
                rec.best_match_score = 0.0
                rec.pending_match_count = 0
                continue

            # Find intakes for this facility + polymer
            intakes = Intake.search(
                [
                    ("partner_id", "=", rec.partner_id.id),
                    ("polymer_id", "=", rec.polymer_id.id),
                ]
            )
            if not intakes:
                rec.match_count = 0
                rec.best_match_score = 0.0
                rec.pending_match_count = 0
                continue

            matches = MatchResult.search(
                [
                    ("intake_id", "in", intakes.ids),
                ]
            )
            rec.match_count = len(matches)
            rec.best_match_score = max(matches.mapped("score"), default=0.0)
            rec.pending_match_count = len(matches.filtered(lambda m: m.state == "pending"))

    @api.depends("partner_id", "polymer_id")
    def _compute_tx_stats(self):
        """Transactions already store supplier_profile_id / buyer_profile_id.

        Also reaches into plasticos.load for last_pickup_date.
        """
        Transaction = self.env["plasticos.transaction"]
        for rec in self:
            # Transactions where this is the supplier's profile
            txs = Transaction.search(
                [
                    "|",
                    ("supplier_profile_id", "=", rec.id),
                    ("buyer_profile_id", "=", rec.id),
                ]
            )
            rec.transaction_count = len(txs)
            rec.total_revenue = sum(txs.mapped("revenue_total"))

            # Last load shipped — traverse tx → load_id → pickup_datetime
            loads = txs.mapped("load_id").filtered(
                lambda load: load.pickup_datetime and load.state in ("picked_up", "delivered", "closed")
            )
            if loads:
                rec.last_pickup_date = max(loads.mapped("pickup_datetime"))
            else:
                rec.last_pickup_date = False

    # ── Navigation Actions (for smart buttons + views) ──────
    # FIXED: These were previously defined OUTSIDE the class as
    # standalone functions (dead code). Now properly indented as methods.

    def action_view_match_results(self):
        """Navigate to match results for this material profile."""
        self.ensure_one()
        intakes = self.env["plasticos.intake"].search(
            [
                ("partner_id", "=", self.partner_id.id),
                ("polymer_id", "=", self.polymer_id.id),
            ]
        )
        return {
            "type": "ir.actions.act_window",
            "name": f"Matches — {self.polymer_id.name} @ {self.partner_id.name}",
            "res_model": "plasticos.match.result",
            "view_mode": "list,form",
            "domain": [("intake_id", "in", intakes.ids)],
        }

    def action_view_transactions(self):
        """Navigate to transactions for this material profile."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Transactions — {self.polymer_id.name}",
            "res_model": "plasticos.transaction",
            "view_mode": "list,form",
            "domain": [
                "|",
                ("supplier_profile_id", "=", self.id),
                ("buyer_profile_id", "=", self.id),
            ],
        }
