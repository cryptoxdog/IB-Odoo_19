"""Opportunity-owned material copy.

Copied once from the linked material profile. Later edits stay on this row.
They never write ``plasticos.material.profile`` or its image attachments.
The approved lot stays frozen; this copy is the broker's working sheet.
"""

from __future__ import annotations

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

SUPPLIER_OFFER_OPTIONAL = "plasticos_supplier_offer_optional"

PROFILE_MODEL = "plasticos.material.profile"
RELATION_FIELDS = (
    "polymer_id",
    "material_grade_id",
    "form_id",
    "color_id",
    "packaging_type_id",
    "source_type_id",
    "filler_type_id",
)
SCALAR_FIELDS = (
    "melt_flow_index",
    "density",
    "moisture_percent",
    "contamination_percent",
    "filler_pct",
    "quantity_per_load_lbs",
    "loads_per_month",
    "lat",
    "lon",
    "origin_process_type",
)
LINE_SPEC_FIELDS = (
    "material_grade_id",
    "color_id",
    "form_id",
    "packaging_type_id",
    "source_type_id",
    "filler_type_id",
)
ORIGIN_PROCESS_SELECTION = [
    ("blow_mold", "Blow Molding"),
    ("compounding", "Compounding"),
    ("compression_mold", "Compression Molding"),
    ("extrusion", "Extrusion"),
    ("film_blown", "Film Blown"),
    ("film_cast", "Film Cast"),
    ("injection", "Injection Molding"),
    ("other", "Other"),
    ("rotomold", "Rotational Molding"),
    ("thermoform", "Thermoforming"),
]


class PlasticosOpportunityMaterial(models.Model):
    _name = "plasticos.opportunity.material"
    _description = "Opportunity Material Copy"
    _order = "id desc"
    _rec_name = "display_name"

    _unique_opportunity_material = models.UniqueIndex("(opportunity_id)")
    _check_buy_price_non_negative = models.Constraint(
        "check(buy_price_per_lb >= 0)",
        "Offer price cannot be negative.",
    )

    display_name = fields.Char(compute="_compute_display_name", store=True)
    opportunity_id = fields.Many2one(
        "crm.lead",
        string="Opportunity",
        required=True,
        index=True,
        ondelete="cascade",
        help="Native opportunity that owns this material copy.",
    )
    source_profile_id = fields.Many2one(
        PROFILE_MODEL,
        string="Source Profile",
        readonly=True,
        ondelete="set null",
        help="Profile this copy was taken from. Edits here do not write that profile.",
    )
    polymer_id = fields.Many2one(
        "plasticos.polymer",
        string="Polymer",
        index=True,
        ondelete="restrict",
        help="Polymer on this opportunity's own material copy.",
    )
    material_grade_id = fields.Many2one(
        "plasticos.material.grade",
        string="Material Type",
        index=True,
        ondelete="restrict",
        help="Material type on this opportunity's own material copy.",
    )
    form_id = fields.Many2one(
        "plasticos.material.form",
        string="Form",
        index=True,
        ondelete="restrict",
        help="Form on this opportunity's own material copy.",
    )
    color_id = fields.Many2one(
        "plasticos.material.color",
        string="Color",
        index=True,
        ondelete="restrict",
        help="Color on this opportunity's own material copy.",
    )
    packaging_type_id = fields.Many2one(
        "plasticos.packaging.type",
        string="Packaging",
        ondelete="restrict",
        help="Packaging on this opportunity's own material copy.",
    )
    source_type_id = fields.Many2one(
        "plasticos.source.type",
        string="Source",
        ondelete="restrict",
        help="Source on this opportunity's own material copy.",
    )
    filler_type_id = fields.Many2one(
        "plasticos.filler.type",
        string="Filler",
        ondelete="restrict",
        help="Filler on this opportunity's own material copy.",
    )
    material_attribute_ids = fields.Many2many(
        "plasticos.material.attribute",
        "plasticos_opportunity_material_attribute_rel",
        "material_id",
        "attribute_id",
        string="Attributes",
        help="Attributes on this opportunity's own material copy.",
    )
    melt_flow_index = fields.Float(string="MFI", help="Melt flow index copied onto the opportunity.")
    density = fields.Float(help="Density copied onto the opportunity.")
    moisture_percent = fields.Float(help="Moisture percent copied onto the opportunity.")
    contamination_percent = fields.Float(help="Contamination percent copied onto the opportunity.")
    filler_pct = fields.Float(string="Filler %", help="Filler percent copied onto the opportunity.")
    quantity_per_load_lbs = fields.Float(
        string="Quantity per Load (lbs)", help="Supply quantity copied onto the opportunity."
    )
    buy_price_per_lb = fields.Float(
        string="Offer Price",
        digits=(10, 4),
        help="Supplier price per pound for this pursuit. The material profile does not store it.",
    )
    loads_per_month = fields.Integer(string="Loads per Month", help="Monthly loads copied onto the opportunity.")
    lat = fields.Float(string="Latitude", digits=(10, 7), help="Latitude copied onto the opportunity.")
    lon = fields.Float(string="Longitude", digits=(10, 7), help="Longitude copied onto the opportunity.")
    origin_process_type = fields.Selection(
        ORIGIN_PROCESS_SELECTION,
        string="Origin Process",
        help="Origin process copied onto the opportunity.",
    )
    freeform_notes = fields.Text(help="Notes copied onto the opportunity. Edits stay on this copy.")
    image_attachment_ids = fields.Many2many(
        "ir.attachment",
        "plasticos_opportunity_material_image_rel",
        "material_id",
        "attachment_id",
        string="Pictures",
        help="Pictures owned by this opportunity. They are copies, not the profile's attachments.",
    )

    @api.depends("polymer_id", "material_grade_id", "form_id")
    def _compute_display_name(self):
        for rec in self:
            parts = [rec.polymer_id.name, rec.material_grade_id.name, rec.form_id.name]
            name = " ".join(part for part in parts if part)
            rec.display_name = name or _("Opportunity material")

    @api.model
    def _vals_from_profile(self, profile, opportunity):
        """Specification and weight for one new line. The profile has no price to copy."""
        profile.ensure_one()
        vals = {
            "source_profile_id": profile.id,
            "freeform_notes": profile.freeform_notes or False,
            "material_attribute_ids": [(6, 0, profile.material_attribute_ids.ids)],
        }
        for name in RELATION_FIELDS:
            related = profile[name]
            vals[name] = related.id if related else False
        for name in SCALAR_FIELDS:
            vals[name] = profile[name]
        intake = opportunity.source_intake_id[:1] if opportunity else self.env["plasticos.intake"]
        from odoo.addons.plasticos_intake.source_origin import downstream_coordinates

        lat, lon = downstream_coordinates(
            profile.lat,
            profile.lon,
            intake.lat if intake else 0.0,
            intake.lon if intake else 0.0,
        )
        vals["lat"] = lat
        vals["lon"] = lon
        return vals

    @api.model
    def copy_from_profile(self, opportunity, profile):
        """Copy ``profile`` onto ``opportunity`` once. Never writes the profile."""
        opportunity.ensure_one()
        profile.ensure_one()
        if opportunity.opportunity_material_ids:
            return opportunity.opportunity_material_ids[:1]
        vals = self._vals_from_profile(profile, opportunity)
        vals["opportunity_id"] = opportunity.id
        material = self.with_context(**{SUPPLIER_OFFER_OPTIONAL: True}).create(vals)
        intake = opportunity.source_intake_id
        if intake:
            address = {}
            if not opportunity.street and intake.source_street:
                address["street"] = intake.source_street
            if not opportunity.city and intake.source_city:
                address["city"] = intake.source_city
            if not opportunity.zip and intake.source_zip:
                address["zip"] = intake.source_zip
            if address:
                opportunity.write(address)
        return material

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record, vals in zip(records, vals_list, strict=True):
            if record.source_profile_id and "image_attachment_ids" not in vals:
                record._copy_profile_images(record.source_profile_id)
        records._plasticos_sync_expected_revenue()
        return records

    def write(self, vals):
        res = super().write(vals)
        if {"buy_price_per_lb", "quantity_per_load_lbs"} & set(vals):
            self._plasticos_sync_expected_revenue()
        return res

    def _plasticos_sync_expected_revenue(self):
        """One load's weight times the supplier price. Monthly volume is not revenue."""
        for material in self:
            opportunity = material.opportunity_id
            if not opportunity:
                continue
            revenue = (material.quantity_per_load_lbs or 0.0) * (material.buy_price_per_lb or 0.0)
            if opportunity.expected_revenue != revenue:
                opportunity.expected_revenue = revenue

    @api.constrains("buy_price_per_lb", "opportunity_id")
    def _require_positive_offer_when_profile_backed(self):
        if self.env.context.get(SUPPLIER_OFFER_OPTIONAL):
            return
        for material in self:
            if material.opportunity_id.material_profile_id and material.buy_price_per_lb <= 0:
                raise ValidationError(_("Enter the supplier offer price before saving this opportunity."))

    def _copy_profile_images(self, profile):
        """Duplicate image attachments. The new rows are not the profile's files."""
        self.ensure_one()
        images = self.env["ir.attachment"].search(
            [
                ("res_model", "=", PROFILE_MODEL),
                ("res_id", "=", profile.id),
                ("mimetype", "like", "image/"),
            ]
        )
        copied = self.env["ir.attachment"]
        for image in images:
            copied |= image.copy(
                {
                    "res_model": self._name,
                    "res_id": self.id,
                    "res_field": False,
                }
            )
        if copied:
            self.image_attachment_ids = [(6, 0, copied.ids)]

    def _sell_product(self):
        """Product variant of this copy's polymer. Does not read the live profile."""
        self.ensure_one()
        polymer = self.polymer_id
        if not polymer:
            raise UserError(_("The opportunity material copy has no polymer to sell."))
        template = polymer._purchase_product()
        product = template.product_variant_id
        if not product:
            raise UserError(_("Polymer %s has no sellable product variant.") % polymer.name)
        return product

    def _line_specification(self, line_model):
        """Order-line specification values. ``material_profile_id`` is left empty."""
        self.ensure_one()
        present = self.env[line_model]._fields
        vals = {}
        for name in LINE_SPEC_FIELDS:
            if name not in present:
                continue
            related = self[name]
            vals[name] = related.id if related else False
        if "material_attribute_ids" in present:
            vals["material_attribute_ids"] = [(6, 0, self.material_attribute_ids.ids)]
        return vals
