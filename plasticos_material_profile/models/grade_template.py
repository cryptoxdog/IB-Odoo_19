"""
Material Grade Template - Pre-defined material specifications for quick selection.

Reps can select from common grades like "LDPE Film - Grade A" and have
all material specification fields auto-populated.
"""

from odoo import api, fields, models


class PlasticosGradeTemplate(models.Model):
    _name = "plasticos.grade.template"
    _description = "Material Grade Template"
    _order = "sequence, name"

    name = fields.Char(
        required=True,
        index=True,
        help="Display name for the grade (e.g., 'LDPE Film - Grade A').",
    )
    code = fields.Char(
        index=True,
        help="Short code for quick reference (e.g., 'LDPE_FILM_A').",
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    polymer_id = fields.Many2one(
        "plasticos.polymer",
        string="Polymer",
        required=True,
        index=True,
        ondelete="restrict",
    )
    form_id = fields.Many2one(
        "plasticos.material.form",
        string="Form",
        index=True,
        ondelete="restrict",
    )
    color_id = fields.Many2one(
        "plasticos.material.color",
        string="Color",
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

    quality_tier = fields.Selection(
        [
            ("prime", "Prime"),
            ("grade_a", "Grade A"),
            ("grade_b", "Grade B"),
            ("standard", "Standard"),
            ("economy", "Economy"),
        ],
        default="standard",
    )

    has_metal = fields.Boolean(default=False)
    no_metal = fields.Boolean(default=False)
    is_clean = fields.Boolean(default=False)
    no_liners = fields.Boolean(default=False)

    description = fields.Text()
    condition_notes = fields.Char()
    usage_count = fields.Integer(default=0, readonly=True)

    @api.model
    def _name_search(self, name, domain=None, operator="ilike", limit=None, order=None):
        domain = domain or []
        if name:
            domain = [
                "|",
                "|",
                ("name", operator, name),
                ("code", operator, name),
                ("polymer_id.name", operator, name),
            ] + domain
        return self._search(domain, limit=limit, order=order)

    def get_template_values(self):
        """Return dict of values to copy to target record."""
        self.ensure_one()
        self.usage_count += 1
        return {
            "polymer_id": self.polymer_id.id,
            "form_id": self.form_id.id if self.form_id else False,
            "color_id": self.color_id.id if self.color_id else False,
            "packaging_type_id": self.packaging_type_id.id if self.packaging_type_id else False,
            "source_type_id": self.source_type_id.id if self.source_type_id else False,
            "quality_tier": self.quality_tier,
            "has_metal": self.has_metal,
        }
