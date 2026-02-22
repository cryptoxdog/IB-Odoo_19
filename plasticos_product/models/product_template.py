from odoo import api, fields, models


class ProductTemplate(models.Model):
    """
    Extends product.template with plastics-specific material fields.

    Product Structure:
    - Polymer (required): HDPE, LDPE, PP, PET, etc.
    - Form (required): Current physical form - Regrind, Flake, Pellet, etc.
    - Origin Form (optional): What it was before processing - Drums, Bottles, Film
    - Packaging (optional): How it's shipped - Gaylords, Super Sacks, Bales
    - Color (optional): Blue, Natural, Mixed
    - Attributes (optional): Conditions - Clean, With Metal, Printed

    Example: "HDPE Drum Regrind - Clean Bales"
    - Polymer: HDPE
    - Form: Regrind (current form)
    - Origin Form: Drums (what it was)
    - Packaging: Bales (how shipped)
    - Attributes: Clean
    """

    _inherit = "product.template"

    # ── Required Fields ────────────────────────────────────────
    polymer_id = fields.Many2one(
        "plasticos.polymer",
        string="Polymer",
        help="Primary polymer type (HDPE, LDPE, PP, etc.). Required.",
    )
    form_id = fields.Many2one(
        "plasticos.material.form",
        string="Form",
        help="Current physical form (Regrind, Flake, Pellet, etc.). Required.",
    )

    # ── Optional Fields ────────────────────────────────────────
    origin_form_id = fields.Many2one(
        "plasticos.material.form",
        string="Origin Form",
        help="What the material was before processing (Drums, Bottles, Film). Optional.",
    )
    packaging_id = fields.Many2one(
        "plasticos.packaging.type",
        string="Packaging",
        help="How the material is packaged/shipped (Gaylords, Super Sacks, Bales). Optional.",
    )
    color_id = fields.Many2one(
        "plasticos.material.color",
        string="Color",
        help="Color of the material. Optional.",
    )
    type_id = fields.Many2one(
        "plasticos.source.type",
        string="Source Type",
        help="Source/origin type (Post-Consumer, Post-Industrial, etc.). Optional.",
    )
    attribute_ids = fields.Many2many(
        "plasticos.material.attribute",
        string="Attributes",
        help="Material condition attributes (Clean, With Metal, Printed, etc.). Optional.",
    )

    # ── Product Format (computed combination) ───────────────────
    product_format = fields.Char(
        string="Product Format",
        compute="_compute_product_format",
        store=True,
        help="Read-only combination: polymer + type + form/packaging + attributes (e.g. HDPE PC Regrind Bales - Clean).",
    )

    # ── Short Codes (for display/search) ───────────────────────
    type_code = fields.Char(
        string="Type Code",
        help="Short code for source type (e.g., PC, PI).",
    )
    form_code = fields.Char(
        string="Form Code",
        help="Short code for material form (e.g., BALE, RG, FILM).",
    )
    color_code = fields.Char(
        string="Color Code",
        help="Short code for color (e.g., MIX, NAT, BLK).",
    )

    @api.depends(
        "polymer_id",
        "polymer_id.name",
        "type_id",
        "type_id.name",
        "form_id",
        "form_id.name",
        "packaging_id",
        "packaging_id.name",
        "attribute_ids",
        "attribute_ids.name",
    )
    def _compute_product_format(self):
        """Build format string: polymer + type + form/packaging + attributes."""
        for rec in self:
            parts = []
            if rec.polymer_id:
                parts.append(rec.polymer_id.name or "")
            if rec.type_id:
                parts.append(rec.type_id.name or "")
            if rec.form_id:
                parts.append(rec.form_id.name or "")
            if rec.packaging_id:
                parts.append(rec.packaging_id.name or "")
            attr = rec.attribute_ids.mapped("name") if rec.attribute_ids else []
            if attr:
                parts.append("- " + ", ".join(attr))
            rec.product_format = " ".join(p for p in parts if p) or ""

    # ── Material Profile Link ────────────────────────────────────
    material_profile_id = fields.Many2one(
        "plasticos.material.profile",
        string="Material Profile",
        help="Links this product SKU to a specific material identity profile. "
        "Enables product-level material tracking and buyer matching.",
    )
