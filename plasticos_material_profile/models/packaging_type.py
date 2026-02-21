from odoo import models, fields


class PlasticosPackagingType(models.Model):
    """
    Packaging types for how material is shipped/stored.
    
    Distinct from Form (what the material IS) - this is how it's packaged.
    Examples: Gaylords, Super Sacks, Bales, Loose, Palletized
    """

    _name = "plasticos.packaging.type"
    _description = "Packaging Type"
    _order = "sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    description = fields.Text()
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("unique_code", "unique(code)", "Packaging type code must be unique."),
    ]
