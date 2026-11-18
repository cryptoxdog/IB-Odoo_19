from odoo import api, fields, models  # pyright: ignore[reportMissingImports]
from odoo.exceptions import ValidationError  # pyright: ignore[reportMissingImports]


class PlasticosFacilityProfile(models.Model):
    _name = "plasticos.facility.profile"
    _description = "Facility Capability Profile"
    _inherit = ["mail.thread"]
    _order = "partner_id"

    # Not ``required`` at the field level: an installed module may add another
    # owner (plasticos_crm_bridge adds ``crm_lead_id``), and a column that claims
    # NOT NULL in the base module cannot hold those rows. The owner rule is
    # enforced by ``_check_profile_owner`` over ``_plasticos_owner_fields``.
    partner_id = fields.Many2one(
        "res.partner",
        index=True,
        ondelete="cascade",
        domain="[('parent_id','!=',False)]",
        tracking=True,
        help="Facility partner that owns this capability profile.",
    )

    active = fields.Boolean(default=True)

    # ── Throughput ───────────────────────────────────────────
    avg_truckload_lbs = fields.Float()

    # ── Certification ────────────────────────────────────────
    iso_certified = fields.Boolean()
    food_grade_certified = fields.Boolean()
    medical_grade_capable = fields.Boolean()

    # ── Operational Constraints ──────────────────────────────
    min_lot_size_lbs = fields.Float()
    max_lot_size_lbs = fields.Float()
    accepts_spot = fields.Boolean(help="Accepts spot deals. NULL = unknown (assume True in matching).")
    prefers_contract = fields.Boolean()

    # ── AI Enrichment ────────────────────────────────────────
    freeform_notes = fields.Text()

    # ── Feedstock Type ───────────────────────────────────────
    feedstock_type = fields.Selection(
        [
            ("post_industrial", "Post Industrial"),
            ("post_consumer", "Post Consumer"),
            ("mixed", "Mixed"),
            ("virgin", "Virgin"),
            ("unknown", "Unknown"),
        ],
        help="Primary feedstock classification this facility purchases.",
    )

    # ── Technical Tolerances ─────────────────────────────────
    contamination_tolerance_pct = fields.Float(
        help="Maximum acceptable contamination percentage.",
    )
    moisture_tolerance_pct = fields.Float(
        help="Maximum acceptable moisture percentage.",
    )

    # ── Capacity ─────────────────────────────────────────────
    capacity_lbs_month = fields.Integer(
        string="Capacity (lbs/month)",
        help="Total purchasing or processing capacity in lbs per month.",
    )

    # ── PCR / Blend ──────────────────────────────────────────
    pcr_pct_min = fields.Float(
        help="Minimum post-consumer recycled content percentage required.",
    )
    pcr_pct_max = fields.Float(
        help="Maximum post-consumer recycled content percentage accepted.",
    )

    # ── Application Context ──────────────────────────────────
    application_class = fields.Selection(
        [
            ("food", "Food Contact"),
            ("medical", "Medical"),
            ("automotive", "Automotive"),
            ("packaging", "Packaging"),
            ("agricultural", "Agricultural"),
            ("construction", "Construction"),
        ],
        string="Application Class",
        help="End-use application class. Determines contamination tolerance thresholds for buyer matching.",
    )
    application_notes = fields.Text(
        help="Additional notes about the facility's end-use applications.",
    )

    # ── Filler Acceptance (45-step framework Layer 4) ──────
    accepts_filled_materials = fields.Boolean(
        string="Accepts Filled Materials",
        help="Facility can process glass-filled, talc-filled, or other filled materials. "
        "Required for materials with filler_pct > 0.",
    )

    # ── Embedding Readiness (Data Sparsity Control) ────────
    embedding_ready = fields.Boolean(
        string="Embedding Ready",
        compute="_compute_embedding_ready",
        store=True,
        index=True,
        help="True when the site has a capability, a material profile, and a state.",
    )

    # ═════════════════════════════════════════════════════════
    # Constraints
    # ═════════════════════════════════════════════════════════

    _unique_partner = models.Constraint(
        "unique(partner_id)",
        "Each facility may only have one capability profile.",
    )

    # ═════════════════════════════════════════════════════════
    # Validation
    # ═════════════════════════════════════════════════════════

    @api.constrains("partner_id")
    def _check_partner_is_facility(self):
        for rec in self:
            if not rec.partner_id:
                continue
            if not rec.partner_id.is_facility:
                raise ValidationError(
                    "Capability profile can only be attached to facility-level partners (locations or standalone companies)."
                )

    @api.model
    def _plasticos_owner_fields(self):
        """Fields of which at least one must be set: the profile's owner.

        An inheriting module that adds another owner extends this tuple and
        re-declares ``_check_profile_owner`` with its field in ``@api.constrains``.
        """
        return ("partner_id",)

    def _plasticos_owner_error(self):
        return "A facility profile needs a facility partner."

    @api.constrains("partner_id")
    def _check_profile_owner(self):
        owner_fields = self._plasticos_owner_fields()
        for rec in self:
            if not any(rec[name] for name in owner_fields):
                raise ValidationError(rec._plasticos_owner_error())

    @api.depends("capability_ids", "partner_id.state_id", "partner_id.material_profile_ids")
    def _compute_embedding_ready(self):
        """A site is ready to embed when it has a line, a material, and a state."""
        for rec in self:
            rec.embedding_ready = bool(
                rec.capability_ids and rec.partner_id.material_profile_ids and rec.partner_id.state_id
            )

    # ═════════════════════════════════════════════════════════
    # CRUD
    # ═════════════════════════════════════════════════════════

    def _reject_duplicate_facility_partners(self, partner_ids):
        """Reject partner assignments that would violate one profile per facility.

        ``partner_ids`` is the intended partner of every record in the operation.
        The database unique constraint remains the concurrency authority.
        """
        requested = [partner_id for partner_id in partner_ids if partner_id]
        if not requested:
            return
        seen = set()
        conflict_ids = set()
        for partner_id in requested:
            if partner_id in seen:
                conflict_ids.add(partner_id)
            seen.add(partner_id)
        domain = [("partner_id", "in", list(seen))]
        if self.ids:
            domain.append(("id", "not in", list(self.ids)))
        persisted = self.search(domain)
        conflict_ids.update(persisted.mapped("partner_id").ids)
        if not conflict_ids:
            return
        partners = self.env["res.partner"].browse(sorted(conflict_ids))
        partner = partners[:1]
        raise ValidationError(f"A capability profile for facility '{partner.name}' already exists.")

    @api.model_create_multi
    def create(self, vals_list):
        self._reject_duplicate_facility_partners([vals.get("partner_id") for vals in vals_list])
        records = super().create(vals_list)
        # @api.constrains runs only for fields present in the create values, so a
        # create that names no owner field would otherwise skip the owner rule.
        records._check_profile_owner()
        return records

    def write(self, vals):
        if vals.get("partner_id"):
            self._reject_duplicate_facility_partners([vals["partner_id"]] * len(self))
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if not rec.partner_id:
                continue
            if (
                rec.env["sale.order"].search_count(
                    [
                        ("partner_id", "=", rec.partner_id.id),
                        ("state", "!=", "cancel"),
                    ]
                )
                > 0
            ):
                raise ValidationError("Cannot delete capability profile linked to active transaction.")
        return super().unlink()

    # ═════════════════════════════════════════════════════════
    # Action Methods (for UX smart buttons)
    # ═════════════════════════════════════════════════════════

    def action_view_partner(self):
        """Open the linked partner (facility) form."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "res.partner",
            "res_id": self.partner_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_profile_form(self):
        """Open this facility profile in a full form view."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "plasticos.facility.profile",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_remove_profile(self):
        """Delete this profile from its line's trash button.

        ``unlink`` still refuses a profile whose partner has a live sale order.
        """
        self.ensure_one()
        self.check_access("read")
        self.partner_id.check_access("read")
        self.unlink()
        return True
