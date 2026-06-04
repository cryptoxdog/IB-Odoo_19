"""
Facility Profile Template - Pre-defined facility capability profiles for quick selection.

Reps can select from common facility types like "Recycler - Full Line" and have
all capability fields auto-populated.
"""

from odoo import api, fields, models


class PlasticosFacilityTemplate(models.Model):
    _name = "plasticos.facility.template"
    _description = "Facility Profile Template"
    _order = "sequence, name"

    name = fields.Char(
        required=True,
        index=True,
        help="Display name for the facility type (e.g., 'Recycler - Full Line').",
    )
    code = fields.Char(
        index=True,
        help="Short code for quick reference.",
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    # ── Equipment ──────────────────────────────────────────────
    equipment_type_ids = fields.Many2many(
        "plasticos.equipment.type",
        "facility_template_equipment_rel",
        "template_id",
        "equipment_type_id",
        string="Equipment Types",
    )

    # ── Material Handling ──────────────────────────────────────
    handles_bales = fields.Boolean()
    handles_regrind = fields.Boolean()
    handles_pellet = fields.Boolean()
    handles_flake = fields.Boolean()
    handles_rollstock = fields.Boolean()

    # ── Quality Processing ─────────────────────────────────────
    can_remove_metal = fields.Boolean()
    can_reduce_moisture = fields.Boolean()
    can_filter_fr = fields.Boolean()
    can_screen_fines = fields.Boolean()

    # ── Certification ──────────────────────────────────────────
    iso_certified = fields.Boolean()
    food_grade_certified = fields.Boolean()
    medical_grade_capable = fields.Boolean()

    # ── Operational ────────────────────────────────────────────
    accepts_spot = fields.Boolean(default=True)
    prefers_contract = fields.Boolean()
    accepts_filled_materials = fields.Boolean()

    # ── Feedstock & Application ────────────────────────────────
    feedstock_type = fields.Selection(
        [
            ("post_industrial", "Post Industrial"),
            ("post_consumer", "Post Consumer"),
            ("mixed", "Mixed"),
            ("virgin", "Virgin"),
        ],
    )
    application_class = fields.Selection(
        [
            ("food", "Food Contact"),
            ("medical", "Medical"),
            ("automotive", "Automotive"),
            ("packaging", "Packaging"),
            ("agricultural", "Agricultural"),
            ("construction", "Construction"),
        ],
    )

    # ── Form Preference ────────────────────────────────────────
    form_preference_id = fields.Many2one(
        "plasticos.material.form",
        string="Form Preference",
        ondelete="restrict",
    )

    # ── Notes ──────────────────────────────────────────────────
    description = fields.Text()
    usage_count = fields.Integer(default=0, readonly=True)

    @api.model
    def _name_search(self, name, domain=None, operator="ilike", limit=None, order=None):
        domain = domain or []
        if name:
            domain = ["|", ("name", operator, name), ("code", operator, name)] + domain
        return self._search(domain, limit=limit, order=order)

    def get_template_values(self):
        """Return dict of values to copy to facility profile."""
        self.ensure_one()
        self.usage_count += 1
        return {
            "equipment_type_ids": [(6, 0, self.equipment_type_ids.ids)],
            "handles_bales": self.handles_bales,
            "handles_regrind": self.handles_regrind,
            "handles_pellet": self.handles_pellet,
            "handles_flake": self.handles_flake,
            "handles_rollstock": self.handles_rollstock,
            "can_remove_metal": self.can_remove_metal,
            "can_reduce_moisture": self.can_reduce_moisture,
            "can_filter_fr": self.can_filter_fr,
            "can_screen_fines": self.can_screen_fines,
            "iso_certified": self.iso_certified,
            "food_grade_certified": self.food_grade_certified,
            "medical_grade_capable": self.medical_grade_capable,
            "accepts_spot": self.accepts_spot,
            "prefers_contract": self.prefers_contract,
            "accepts_filled_materials": self.accepts_filled_materials,
            "feedstock_type": self.feedstock_type,
            "application_class": self.application_class,
            "form_preference_id": self.form_preference_id.id if self.form_preference_id else False,
        }
