from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    """
    Extend purchase.order.line with full material specification.

    Product = Polymer only (required).
    All other fields describe the specific material variation for this line.
    Pre-filled from material_profile_id but editable by user.

    Full description format: "HDPE Blue Regrind - Gaylords - Post-Industrial - Clean"
    Order: Polymer + Color + Form + Packaging + Source + Attributes
    """

    _inherit = "purchase.order.line"

    # ── Material Profile Link (hidden, for traceability) ──────────
    material_profile_id = fields.Many2one(
        "plasticos.material.profile",
        string="Material Profile",
        index=True,
        ondelete="set null",
        help="Source material profile. Fields pre-filled from here but editable.",
    )

    # ── Material Specification Fields ─────────────────────────────
    color_id = fields.Many2one(
        "plasticos.material.color",
        string="Color",
        index=True,
        ondelete="restrict",
    )
    form_id = fields.Many2one(
        "plasticos.material.form",
        string="Form",
        index=True,
        ondelete="restrict",
    )
    packaging_type_id = fields.Many2one(
        "plasticos.packaging.type",
        string="Packaging",
        index=True,
        ondelete="restrict",
    )
    source_type_id = fields.Many2one(
        "plasticos.source.type",
        string="Source Type",
        index=True,
        ondelete="restrict",
    )
    filler_type_id = fields.Many2one(
        "plasticos.filler.type",
        string="Filler Type",
        index=True,
        ondelete="restrict",
    )
    material_attribute_ids = fields.Many2many(
        "plasticos.material.attribute",
        "purchase_line_material_attribute_rel",
        "line_id",
        "attribute_id",
        string="Attributes",
    )

    # ── Computed Full Description ─────────────────────────────────
    material_description = fields.Char(
        string="Material Description",
        compute="_compute_material_description",
        store=True,
        help="Full material description: Polymer Color Form - Packaging - Source - Attributes",
    )

    def _build_main_description_part(self, line):
        """Build space-separated main part: Polymer Color Filler Form."""
        parts = []
        if line.product_id and line.product_id.polymer_id:
            parts.append(line.product_id.polymer_id.name)
        if line.color_id:
            parts.append(line.color_id.name)
        if line.filler_type_id:
            parts.append(line.filler_type_id.name)
        if line.form_id:
            parts.append(line.form_id.name)
        return " ".join(parts)

    def _build_extras_parts(self, line):
        """Build dash-separated extras list: Packaging, Source, Attributes."""
        extras = []
        if line.packaging_type_id:
            extras.append(line.packaging_type_id.name)
        if line.source_type_id:
            extras.append(line.source_type_id.name)
        if line.material_attribute_ids:
            extras.append(", ".join(line.material_attribute_ids.mapped("name")))
        return extras

    @api.depends(
        "product_id",
        "product_id.polymer_id",
        "color_id",
        "form_id",
        "packaging_type_id",
        "source_type_id",
        "filler_type_id",
        "material_attribute_ids",
    )
    def _compute_material_description(self):
        """
        Build full description: HDPE Blue Glass Filled Regrind - Gaylords - Post-Industrial - Clean

        Order: Polymer + Color + Filler + Form - Packaging - Source - Attributes
        Main part (space-separated): Polymer Color Filler Form
        Extras (dash-separated): Packaging - Source - Attributes
        """
        for line in self:
            main_part = self._build_main_description_part(line)
            extras = self._build_extras_parts(line)
            if extras:
                line.material_description = f"{main_part} - {' - '.join(extras)}"
            else:
                line.material_description = main_part

    @api.onchange("material_profile_id")
    def _onchange_material_profile_id(self):
        """Pre-fill fields from material profile (editable by user)."""
        if not self.material_profile_id:
            return

        profile = self.material_profile_id

        # Set product from polymer
        if profile.polymer_id and profile.polymer_id.product_id:
            self.product_id = profile.polymer_id.product_id.id

        # Pre-fill material fields
        self.color_id = profile.color_id.id if profile.color_id else False
        self.form_id = profile.form_id.id if profile.form_id else False
        self.packaging_type_id = profile.packaging_type_id.id if profile.packaging_type_id else False
        self.source_type_id = profile.source_type_id.id if profile.source_type_id else False
        self.filler_type_id = profile.filler_type_id.id if profile.filler_type_id else False
        self.material_attribute_ids = (
            [(6, 0, profile.material_attribute_ids.ids)] if profile.material_attribute_ids else [(5,)]
        )

    # ── Navigation Actions (Jump To) ────────────────────────────
    def action_view_material_profile(self):
        """Navigate to the linked material profile."""
        self.ensure_one()
        if not self.material_profile_id:
            return
        return {
            "type": "ir.actions.act_window",
            "name": "Material Profile",
            "res_model": "plasticos.material.profile",
            "view_mode": "form",
            "res_id": self.material_profile_id.id,
        }
