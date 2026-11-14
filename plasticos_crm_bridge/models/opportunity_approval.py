"""Immutable approved lot behind the one native Opportunity matching command.

``plasticos.opportunity.approval`` freezes the Partner, Material Profile and
optional Facility a broker approved for one ``crm.lead`` opportunity. The
material values in the frozen ``snapshot`` come from the opportunity's own
material sheet (``plasticos.opportunity.material``), the same row manual offers
and the release sell; the Material Profile is used only when the opportunity
has no sheet. The Gate request is built from the frozen ``snapshot``; a later
sheet or profile edit never rewrites an approved lot, a retry reuses the lot,
and a new command mints a new lot from the sheet as it stands then. Rows are
server-minted (``mint``) and immutable afterwards.
"""

from __future__ import annotations

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

# Server-owned create door. ``mint`` is the only caller that opens it; a form,
# RPC, import or ``sudo()`` create without it is refused at the ORM boundary.
APPROVAL_MINT_CONTEXT = "plasticos_opportunity_approval_mint"

APPROVAL_SOURCES = [
    ("hot", "HOT web lead"),
    ("manual", "Manual"),
    ("vanillasoft", "VanillaSoft"),
]

# Material Profile relations frozen into the lot as their master-data code.
# Keys use the Gate query vocabulary already spoken by ``build_match_request``.
SNAPSHOT_RELATION_FIELDS = (
    ("polymer_id", "polymer_type"),
    ("form_id", "form"),
    ("source_type_id", "source_type"),
    ("material_grade_id", "material_grade"),
    ("packaging_type_id", "packaging_type"),
    ("filler_type_id", "filler_type"),
)
SNAPSHOT_SCALAR_FIELDS = (
    ("melt_flow_index", "mfi"),
    ("density", "density"),
    ("moisture_percent", "moisture_pct"),
    ("contamination_percent", "contamination_pct"),
    ("filler_pct", "filler_pct"),
    ("quantity_per_load_lbs", "quantity_per_load_lbs"),
    ("loads_per_month", "loads_per_month"),
    ("lat", "lat"),
    ("lon", "lon"),
    ("origin_process_type", "origin_process_type"),
)

# Every business field is frozen once the lot exists. Only mail.thread
# bookkeeping may still be written.
FROZEN_FIELDS = (
    "opportunity_id",
    "partner_id",
    "material_profile_id",
    "facility_profile_id",
    "source_intake_id",
    "source",
    "snapshot",
    "snapshot_digest",
    "approved_by",
    "approved_at",
)


class PlasticosOpportunityApproval(models.Model):
    _name = "plasticos.opportunity.approval"
    _description = "Opportunity Approved Lot"
    _inherit = ["mail.thread"]
    _order = "create_date desc, id desc"
    _rec_name = "display_name"

    display_name = fields.Char(compute="_compute_display_name", store=True)
    opportunity_id = fields.Many2one(
        "crm.lead",
        string="Opportunity",
        required=True,
        index=True,
        ondelete="restrict",
        domain=[("type", "=", "opportunity")],
        help="Native CRM opportunity that owns this approved lot.",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
        required=True,
        index=True,
        ondelete="restrict",
        help="Verified supplier partner approved for this lot.",
    )
    material_profile_id = fields.Many2one(
        "plasticos.material.profile",
        string="Material Profile",
        required=True,
        index=True,
        ondelete="restrict",
        help="Material profile approved for this lot. Its values are frozen in the snapshot.",
    )
    facility_profile_id = fields.Many2one(
        "plasticos.facility.profile",
        string="Facility Profile",
        index=True,
        ondelete="set null",
        help="Optional facility. When absent, no facility evidence is sent to Gate.",
    )
    source_intake_id = fields.Many2one(
        "plasticos.intake",
        string="Source Intake",
        index=True,
        ondelete="restrict",
        help="Optional originating intake (HOT web submission). Manual lots have none.",
    )
    source = fields.Selection(
        APPROVAL_SOURCES,
        required=True,
        index=True,
        help="Ingress that produced this lot.",
    )
    snapshot = fields.Json(
        readonly=True,
        help=(
            "Frozen material, partner and optional facility values the Gate request is built from. "
            "Material values come from the opportunity's material sheet, or from the profile when it has none."
        ),
    )
    snapshot_digest = fields.Char(
        readonly=True,
        index=True,
        copy=False,
        help="SHA-256 of the canonical snapshot; identity of the frozen lot.",
    )
    approved_by = fields.Many2one(
        "res.users",
        string="Approved By",
        readonly=True,
        ondelete="restrict",
    )
    approved_at = fields.Datetime(readonly=True)
    company_id = fields.Many2one(
        related="opportunity_id.company_id",
        store=True,
        readonly=True,
    )
    match_run_ids = fields.One2many(
        "plasticos.match.run",
        "approval_id",
        string="Match Runs",
    )

    @api.depends("opportunity_id", "material_profile_id", "source")
    def _compute_display_name(self):
        for rec in self:
            opportunity = rec.opportunity_id.name or "?"
            profile = rec.material_profile_id.display_name or "?"
            rec.display_name = f"Lot {rec.id or 'new'} [{rec.source or '?'}] {opportunity} / {profile}"

    # ── Verification ─────────────────────────────────────────

    @api.model
    def _allowed_profile_owners(self, partner):
        """Partners that may own the approved material: the partner, its sites, and its company."""
        owners = partner | partner.child_ids
        if partner.parent_id:
            owners |= partner.parent_id
        return owners

    @api.constrains("opportunity_id", "partner_id", "material_profile_id", "facility_profile_id")
    def _check_lot_identity(self):
        for rec in self:
            if rec.opportunity_id.type != "opportunity":
                raise ValidationError(_("An approved lot belongs to a native CRM opportunity, not a lead."))
            if not rec.partner_id.is_company and not rec.partner_id.parent_id:
                raise ValidationError(_("The approved partner must be a verified company or one of its sites."))
            owners = self._allowed_profile_owners(rec.partner_id)
            profile_owner = rec.material_profile_id.partner_id
            if profile_owner and profile_owner not in owners:
                raise ValidationError(
                    _("Material profile belongs to a different supplier and cannot be approved for this partner.")
                )
            facility_owner = rec.facility_profile_id.partner_id
            if facility_owner and facility_owner not in owners:
                raise ValidationError(_("Facility profile belongs to a different partner."))

    # ── Snapshot ─────────────────────────────────────────────

    @api.model
    def _material_snapshot(self, partner, material_profile, facility_profile=None, source_intake=None, material=None):
        """Freeze the lot. Absent optional evidence is omitted, never fabricated.

        ``material`` is the opportunity's material sheet. When given, every
        material value is read from it and its id is recorded as lineage;
        ``material_profile`` then only names the approved profile. Without a
        sheet the profile supplies the values. The sheet's supplier price is
        never frozen: a Gate match carries no price authority.
        """
        source = material or material_profile
        snapshot = {
            "supplier_partner_id": partner.id,
            "material_profile_id": material_profile.id,
        }
        if material:
            snapshot["opportunity_material_id"] = material.id
        for field_name, key in SNAPSHOT_RELATION_FIELDS:
            related = source[field_name]
            if related:
                snapshot[key] = related.code or related.name
        colors = source.color_ids
        named = [color.code or color.name for color in colors]
        if len(named) == 1:
            snapshot["color"] = named[0]
        elif named:
            snapshot["color"] = named
        for field_name, key in SNAPSHOT_SCALAR_FIELDS:
            value = source[field_name]
            if value not in (None, False, "", 0, 0.0):
                snapshot[key] = value
        if facility_profile:
            snapshot["facility_profile_id"] = facility_profile.id
            if facility_profile.partner_id:
                snapshot["facility_partner_id"] = facility_profile.partner_id.id
        if source_intake:
            snapshot["intake_id"] = source_intake.id
            from odoo.addons.plasticos_intake.source_origin import downstream_coordinates

            lat, lon = downstream_coordinates(
                snapshot.get("lat") or 0.0,
                snapshot.get("lon") or 0.0,
                source_intake.lat,
                source_intake.lon,
            )
            if lat:
                snapshot["lat"] = lat
            if lon:
                snapshot["lon"] = lon
        return snapshot

    @api.model
    def _plasticos_refuse_incomplete_material(self, opportunity, values):
        """Raise when ``values`` (Gate query vocabulary) lack a fact matching and offers need."""
        from odoo.addons.plasticos_intake.match_material import missing_match_material  # noqa: PLC0415

        missing = missing_match_material(values)
        if missing:
            raise UserError(
                _(
                    "Opportunity '%(opportunity)s' cannot be matched or offered: %(missing)s not set "
                    "on its material. Fill it on the opportunity material, then run Match via Gate again.",
                    opportunity=opportunity.name,
                    missing=" and ".join(missing),
                )
            )

    @api.model
    def _plasticos_require_source_material(self, opportunity, material_profile):
        """Refuse before a lot is minted: read the material ``mint`` would freeze (the sheet, else the profile)."""
        source = opportunity.opportunity_material_ids[:1] or material_profile
        self._plasticos_refuse_incomplete_material(
            opportunity, {"polymer_type": source.polymer_id, "form": source.form_id}
        )

    def _plasticos_require_match_material(self):
        """Refuse matching and offer creation while the frozen material lacks a required fact."""
        for rec in self:
            snapshot = rec.snapshot if isinstance(rec.snapshot, dict) else {}
            self._plasticos_refuse_incomplete_material(rec.opportunity_id, snapshot)

    @api.model
    def mint(self, opportunity, *, source, partner, material_profile, facility_profile=None, source_intake=None):
        """Server-mint one immutable lot for ``opportunity``.

        Every call is a new lot: two commands on one partner and profile are two
        independent snapshots and are never collapsed. The material values are
        the opportunity's material sheet as it stands now; the profile supplies
        them only when the opportunity has no sheet. When the sheet names the
        profile it was copied from, the lot records that profile, not
        ``material_profile``, so the lot never pairs one profile's id with
        another profile's values.
        """
        from odoo.addons.plasticos_matching.canonical_digest import _canonical_digest  # noqa: PLC0415

        opportunity.ensure_one()
        partner.ensure_one()
        material_profile.ensure_one()
        if source not in dict(APPROVAL_SOURCES):
            raise ValidationError(_("Unknown approval source %s.") % source)
        material = opportunity.opportunity_material_ids[:1] or None
        if material and material.source_profile_id:
            # The sheet is copied once; a later profile change on the opportunity
            # does not recopy it. The lot names the profile its frozen values came
            # from, so values and provenance never describe two different profiles.
            material_profile = material.source_profile_id
        snapshot = self._material_snapshot(
            partner, material_profile, facility_profile, source_intake, material=material
        )
        vals = {
            "opportunity_id": opportunity.id,
            "partner_id": partner.id,
            "material_profile_id": material_profile.id,
            "facility_profile_id": facility_profile.id if facility_profile else False,
            "source_intake_id": source_intake.id if source_intake else False,
            "source": source,
            "snapshot": snapshot,
            "snapshot_digest": _canonical_digest(snapshot),
        }
        return self.with_context(**{APPROVAL_MINT_CONTEXT: True}).create(vals)

    # ── Immutability guards ──────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get(APPROVAL_MINT_CONTEXT):
            raise AccessError(_("Approved lots are server-minted from the Opportunity and cannot be created directly."))
        now = fields.Datetime.now()
        for vals in vals_list:
            vals["approved_by"] = self.env.uid
            vals["approved_at"] = now
        return super().create(vals_list)

    def write(self, vals):
        frozen = sorted(set(vals) & set(FROZEN_FIELDS))
        if frozen:
            raise AccessError(
                _("Approved lot %(lot)s is immutable; %(fields)s cannot change. Approve a new lot instead.")
                % {"lot": ", ".join(str(rec.id) for rec in self), "fields": ", ".join(frozen)}
            )
        return super().write(vals)

    def unlink(self):
        raise AccessError(_("Approved lots are audit evidence and cannot be deleted."))
