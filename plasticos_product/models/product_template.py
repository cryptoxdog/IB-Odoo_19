from odoo import models, fields


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
    material_form_id = fields.Many2one(
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
    packaging_type_id = fields.Many2one(
        "plasticos.packaging.type",
        string="Packaging",
        help="How the material is packaged/shipped (Gaylords, Super Sacks, Bales). Optional.",
    )
    material_color_id = fields.Many2one(
        "plasticos.material.color",
        string="Color",
        help="Color of the material. Optional.",
    )
    source_type_id = fields.Many2one(
        "plasticos.source.type",
        string="Source Type",
        help="Source/origin type (Post-Consumer, Post-Industrial, etc.). Optional.",
    )
    material_attribute_ids = fields.Many2many(
        "plasticos.material.attribute",
        string="Attributes",
        help="Material condition attributes (Clean, With Metal, Printed, etc.). Optional.",
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
