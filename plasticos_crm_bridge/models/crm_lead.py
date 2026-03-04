from odoo import fields, models


class CrmLeadPlastOS(models.Model):
    _inherit = "crm.lead"

    # ── Web Lead Link ──────────────────────────────────────
    web_lead_ids = fields.One2many(
        "plasticos.web.lead",
        "crm_lead_id",
        string="Web Leads",
    )
    web_lead_count = fields.Integer(
        compute="_compute_web_lead_count",
    )

    # ── Material Profile Summary (rolled up from partner) ──
    material_profile_count = fields.Integer(
        compute="_compute_profile_summary",
    )
    total_match_count = fields.Integer(
        string="Total Matches (All Profiles)",
        compute="_compute_profile_summary",
    )
    total_transaction_count = fields.Integer(
        string="Total Transactions",
        compute="_compute_profile_summary",
    )
    partner_total_revenue = fields.Float(
        string="Total Revenue (All Profiles)",
        compute="_compute_profile_summary",
    )
    partner_last_pickup = fields.Datetime(
        string="Last Load Shipped",
        compute="_compute_profile_summary",
    )

    def _compute_web_lead_count(self):
        for rec in self:
            rec.web_lead_count = len(rec.web_lead_ids)

    def _compute_profile_summary(self):
        Profile = self.env["plasticos.material.profile"]
        for rec in self:
            if not rec.partner_id:
                rec.material_profile_count = 0
                rec.total_match_count = 0
                rec.total_transaction_count = 0
                rec.partner_total_revenue = 0.0
                rec.partner_last_pickup = False
                continue

            # All profiles for this partner's facilities
            facilities = rec.partner_id.child_ids
            profiles = Profile.search(
                [
                    ("partner_id", "in", facilities.ids),
                ]
            )
            rec.material_profile_count = len(profiles)
            rec.total_match_count = sum(profiles.mapped("match_count"))
            rec.total_transaction_count = sum(profiles.mapped("transaction_count"))
            rec.partner_total_revenue = sum(profiles.mapped("total_revenue"))
            pickups = profiles.mapped("last_pickup_date")
            pickups = [d for d in pickups if d]
            rec.partner_last_pickup = max(pickups) if pickups else False


# In crm_lead.py — add these action methods


def action_view_web_leads(self):
    self.ensure_one()
    return {
        "type": "ir.actions.act_window",
        "name": f"Web Leads — {self.partner_name or self.name}",
        "res_model": "plasticos.web.lead",
        "view_mode": "list,form",
        "domain": [("crm_lead_id", "=", self.id)],
    }


def action_view_material_profiles(self):
    self.ensure_one()
    facilities = self.partner_id.child_ids if self.partner_id else self.env["res.partner"]
    return {
        "type": "ir.actions.act_window",
        "name": f"Material Profiles — {self.partner_id.name or ''}",
        "res_model": "plasticos.material.profile",
        "view_mode": "list,form",
        "domain": [("partner_id", "in", facilities.ids)],
    }


def action_view_match_results(self):
    self.ensure_one()
    facilities = self.partner_id.child_ids if self.partner_id else self.env["res.partner"]
    intakes = self.env["plasticos.intake"].search(
        [
            ("partner_id", "in", facilities.ids),
        ]
    )
    return {
        "type": "ir.actions.act_window",
        "name": f"Match Results — {self.partner_id.name or ''}",
        "res_model": "plasticos.match.result",
        "view_mode": "list,form",
        "domain": [("intake_id", "in", intakes.ids)],
    }


def action_view_transactions(self):
    self.ensure_one()
    facilities = self.partner_id.child_ids if self.partner_id else self.env["res.partner"]
    profiles = self.env["plasticos.material.profile"].search(
        [
            ("partner_id", "in", facilities.ids),
        ]
    )
    return {
        "type": "ir.actions.act_window",
        "name": f"Transactions — {self.partner_id.name or ''}",
        "res_model": "plasticos.transaction",
        "view_mode": "list,form",
        "domain": [
            "|",
            ("supplier_profile_id", "in", profiles.ids),
            ("buyer_profile_id", "in", profiles.ids),
        ],
    }
