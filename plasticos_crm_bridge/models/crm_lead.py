import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class CrmLeadCrmBridge(models.Model):
    _inherit = "crm.lead"

    web_lead_ids = fields.One2many(
        "plasticos.web.lead",
        "crm_lead_id",
        string="Web Leads",
    )
    web_lead_count = fields.Integer(
        string="Web Leads",
        compute="_compute_web_lead_count",
        store=False,
    )

    # ── Summary Rollup Fields (from partner's material profiles) ──
    material_profile_count = fields.Integer(
        string="Material Profiles",
        compute="_compute_partner_stats",
        store=False,
    )
    total_match_count = fields.Integer(
        string="Total Matches",
        compute="_compute_partner_stats",
        store=False,
    )
    total_transaction_count = fields.Integer(
        string="Total Transactions",
        compute="_compute_partner_stats",
        store=False,
    )
    partner_total_revenue = fields.Float(
        string="Partner Total Revenue",
        digits=(16, 2),
        compute="_compute_partner_stats",
        store=False,
    )
    partner_last_pickup = fields.Datetime(
        string="Last Pickup Date",
        compute="_compute_partner_stats",
        store=False,
    )

    @api.depends("web_lead_ids")
    def _compute_web_lead_count(self):
        for rec in self:
            rec.web_lead_count = len(rec.web_lead_ids)

    @api.depends("partner_id")
    def _compute_partner_stats(self):
        Profile = self.env["plasticos.material.profile"]
        Intake = self.env["plasticos.intake"]
        MatchResult = self.env["plasticos.match.result"]
        Transaction = self.env["plasticos.transaction"]

        for rec in self:
            if not rec.partner_id:
                rec.material_profile_count = 0
                rec.total_match_count = 0
                rec.total_transaction_count = 0
                rec.partner_total_revenue = 0.0
                rec.partner_last_pickup = False
                continue

            # Include both the partner and its children
            partner_ids = (rec.partner_id | rec.partner_id.child_ids).ids

            profiles = Profile.search([("partner_id", "in", partner_ids)])
            rec.material_profile_count = len(profiles)

            # Match stats: find all intakes for these partners then all match results
            intakes = Intake.search([("partner_id", "in", partner_ids)])
            if intakes:
                match_results = MatchResult.search(
                    [("intake_id", "in", intakes.ids)]
                )
                rec.total_match_count = len(match_results)
            else:
                rec.total_match_count = 0

            # Transaction stats
            profile_ids = profiles.ids
            if profile_ids:
                txs = Transaction.search(
                    [
                        "|",
                        ("supplier_profile_id", "in", profile_ids),
                        ("buyer_profile_id", "in", profile_ids),
                    ]
                )
            else:
                txs = Transaction.browse()

            rec.total_transaction_count = len(txs)
            rec.partner_total_revenue = sum(txs.mapped("revenue_total"))

            # Last pickup from linked loads
            loads = txs.mapped("load_id").filtered(
                lambda ld: ld.pickup_datetime
                and ld.state in ("picked_up", "delivered", "closed")
            )
            pickup_dates = loads.mapped("pickup_datetime")
            rec.partner_last_pickup = max(pickup_dates) if pickup_dates else False
