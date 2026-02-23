from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    material_profile_id = fields.Many2one(
        "plasticos.material.profile",
        string="Material Profile",
        help="Link this product to a canonical material profile (polymer, form, grade)",
    )

    # Convenience fields (related for quick access)
    material_polymer = fields.Char(related="material_profile_id.polymer", string="Polymer", readonly=True, store=True)

    material_form = fields.Selection(related="material_profile_id.form", string="Form", readonly=True, store=True)

    material_resin_grade = fields.Char(
        related="material_profile_id.sub_grade", string="Resin Grade", readonly=True, store=True
    )
