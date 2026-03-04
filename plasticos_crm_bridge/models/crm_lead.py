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

    # ── Intake Link ────────────────────────────────────────
    intake_ids = fields.One2many(
        "plasticos.intake",
        "crm_lead_id",
        string="Intakes",
    )
    intake_count = fields.Integer(
        compute="_compute_intake_count",
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

    def _compute_intake_count(self):
        for rec in self:
            rec.intake_count = len(rec.intake_ids)

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

    # ── Phase 5: Convert CRM Lead to Intake ──────────────────

    def action_convert_to_intake(self):
        """Convert CRM lead into a PlastOS material intake.

        Flow:
        1. Create or find res.partner from lead data
        2. Create plasticos.intake linked to partner + this lead
        3. Move CRM lead to Active Supplier stage
        4. Open the new intake form
        """
        self.ensure_one()

        # 1. Ensure partner exists
        if not self.partner_id:
            partner = self._find_or_create_partner_from_lead()
            self.partner_id = partner
        else:
            partner = self.partner_id

        # 2. Create intake
        intake_vals = {
            "partner_id": partner.id,
            "crm_lead_id": self.id,
            "intake_notes": self.description or "",
        }

        # Set lead source from CRM source_id if available
        if self.source_id:
            intake_vals["lead_source_id"] = self.source_id.id

        intake = self.env["plasticos.intake"].create(intake_vals)

        # 3. Move lead to Active Supplier stage
        won_stage = self.env.ref(
            "plasticos_crm_bridge.stage_active_supplier",
            raise_if_not_found=False,
        )
        if won_stage:
            self.stage_id = won_stage

        self.message_post(
            body=f"Intake created: <a href=\"#\" "
            f"data-oe-model=\"plasticos.intake\" "
            f"data-oe-id=\"{intake.id}\">{intake.name or 'New Intake'}</a>"
        )

        # 4. Open intake form
        return {
            "type": "ir.actions.act_window",
            "name": f"Intake — {partner.name}",
            "res_model": "plasticos.intake",
            "res_id": intake.id,
            "view_mode": "form",
            "target": "current",
        }

    def _find_or_create_partner_from_lead(self):
        """Find existing partner by name or create new one from lead data."""
        Partner = self.env["res.partner"]
        name = self.partner_name or self.contact_name or self.name

        # Try exact match first
        existing = Partner.search(
            [
                ("name", "=ilike", name),
                ("is_company", "=", True),
                ("parent_id", "=", False),
            ],
            limit=1,
        )
        if existing:
            self.message_post(body=f"Linked to existing partner: {existing.name}")
            return existing

        # Create new partner
        vals = {
            "name": name,
            "is_company": True,
            "email": self.email_from,
            "phone": self.phone,
            "street": self.street,
            "city": self.city,
            "state_id": self.state_id.id if self.state_id else False,
            "zip": self.zip,
            "country_id": self.country_id.id if self.country_id else False,
            "supplier_rank": 1,
        }

        # Set lead source from CRM source_id
        if self.source_id:
            vals["lead_source_id"] = self.source_id.id

        partner = Partner.create(vals)
        self.message_post(body=f"Created new partner: {partner.name} (ID: {partner.id})")
        return partner

    def action_view_intakes(self):
        """Navigate to intakes linked to this CRM lead."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Intakes — {self.partner_name or self.name}",
            "res_model": "plasticos.intake",
            "view_mode": "list,form",
            "domain": [("crm_lead_id", "=", self.id)],
            "context": {"default_crm_lead_id": self.id},
        }

    # ── Navigation Actions (for smart buttons) ───────────────

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
