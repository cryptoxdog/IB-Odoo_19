from odoo import api, fields, models

MATERIAL_PROFILE = "plasticos.material.profile"


def _material_chip(profile):
    """One material as polymer · form · grade · rate. Empty parts are left out."""
    parts = [
        profile.polymer_id.name or "",
        profile.form_id.name or "",
        profile.material_grade_id.name or "",
    ]
    label = " · ".join(part for part in parts if part)
    if profile.rate_lb_hr:
        rate = f"{profile.rate_lb_hr:g} lb/hr"
        label = f"{label} · {rate}" if label else rate
    return label


def _join_chips(profiles):
    return " | ".join(chip for chip in (_material_chip(profile) for profile in profiles) if chip)


class _KeyProperties(fields.Properties):
    """A selection detail reads back as its stored key.

    Odoo otherwise returns the selection label (``HRB``) from ``details[name]``.
    The migration and the form both identify the baler by the key ``hrb``.
    """

    def __get__(self, record, owner):
        if record is not None and not record.env.context.get("property_selection_get_key"):
            record = record.with_context(property_selection_get_key=True)
        return super().__get__(record, owner)


class PlasticosCapability(models.Model):
    """One machine or one line on a site. Three shredders are three rows."""

    _name = "plasticos.capability"
    _description = "Site Capability"
    _order = "sequence, id"

    facility_profile_id = fields.Many2one(
        "plasticos.facility.profile",
        string="Facility profile",
        required=True,
        ondelete="cascade",
        index=True,
        help="The site profile this line belongs to.",
    )
    sequence = fields.Integer(default=10, help="Drag order. The order shows the flow.")
    capability_type_id = fields.Many2one(
        "plasticos.capability.type",
        string="Type",
        required=True,
        ondelete="restrict",
        index=True,
        help="What this line does. Changing the type drops this row's detail values.",
    )
    model = fields.Char(
        string="Model",
        help="Free-text model, for example V60. Blank when it is not known. There is no model catalog.",
    )
    rated_capacity_lb_hr = fields.Float(
        string="Rated lb/hr",
        help="The machine's rated throughput in pounds per hour.",
    )
    details = _KeyProperties(
        string="Details",
        definition="capability_type_id.details_definition",
        help="Only this type's detail fields. A type change drops the values.",
    )
    in_material_ids = fields.One2many(
        MATERIAL_PROFILE,
        "capability_id",
        string="In materials",
        domain=[("direction", "=", "in")],
        help="Material profiles that enter this line.",
    )
    out_material_ids = fields.One2many(
        MATERIAL_PROFILE,
        "capability_id",
        string="Out materials",
        domain=[("direction", "=", "out")],
        help="Material profiles that leave this line.",
    )
    in_material_chips = fields.Char(
        string="In",
        compute="_compute_material_chips",
        help="In materials as polymer · form · grade · rate.",
    )
    out_material_chips = fields.Char(
        string="Out",
        compute="_compute_material_chips",
        help="Out materials as polymer · form · grade · rate.",
    )
    notes = fields.Text()

    @api.depends(
        "in_material_ids.polymer_id",
        "in_material_ids.form_id",
        "in_material_ids.material_grade_id",
        "in_material_ids.rate_lb_hr",
        "out_material_ids.polymer_id",
        "out_material_ids.form_id",
        "out_material_ids.material_grade_id",
        "out_material_ids.rate_lb_hr",
    )
    def _compute_material_chips(self):
        for rec in self:
            rec.in_material_chips = _join_chips(rec.in_material_ids)
            rec.out_material_chips = _join_chips(rec.out_material_ids)

    @api.onchange("capability_type_id")
    def _onchange_capability_type_id(self):
        """Warn before a saved row's type change, which drops its detail values."""
        origin = self._origin
        if origin.capability_type_id and origin.capability_type_id != self.capability_type_id:
            self.details = False
            return {
                "warning": {
                    "title": "Capability type change",
                    "message": "Changing the type drops this row's detail values.",
                }
            }
        return None

    def write(self, vals):
        if (
            "capability_type_id" in vals
            and "details" not in vals
            and self._type_is_changing(vals["capability_type_id"])
        ):
            vals = dict(vals, details=False)
        return super().write(vals)

    def _type_is_changing(self, type_id):
        return any(rec.capability_type_id.id != type_id for rec in self)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.facility_profile_id._autolink_when_sole_capability()
        return records

    def unlink(self):
        facilities = self.facility_profile_id
        result = super().unlink()
        facilities.exists()._autolink_when_sole_capability()
        return result


class PlasticosFacilityProfileCapability(models.Model):
    _inherit = "plasticos.facility.profile"

    capability_ids = fields.One2many(
        "plasticos.capability",
        "facility_profile_id",
        string="Capabilities",
        help="Machines and lines at this site, in flow order. One row is one line.",
    )

    def _autolink_when_sole_capability(self):
        """Link a site's unlinked material profiles when the site has exactly one capability.

        The profiles are read once. Each site's only line is a different record, so
        each link is its own write, done one site at a time rather than as a query
        inside a loop.
        """
        sole = self.filtered(lambda facility: len(facility.capability_ids) == 1 and facility.partner_id)
        if not sole:
            return
        unlinked = self.env[MATERIAL_PROFILE].search(
            [
                ("partner_id", "in", sole.partner_id.ids),
                ("capability_id", "=", False),
            ]
        )
        if unlinked:
            self._link_sole_capability(sole, unlinked)

    def _link_sole_capability(self, facilities, unlinked):
        facility = facilities[:1]
        rows = unlinked.filtered(lambda profile: profile.partner_id == facility.partner_id)
        if rows:
            rows.write({"capability_id": facility.capability_ids.id})
        remaining = facilities - facility
        if remaining:
            self._link_sole_capability(remaining, unlinked - rows)
