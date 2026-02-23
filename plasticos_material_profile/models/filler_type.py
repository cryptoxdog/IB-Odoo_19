from odoo import fields, models


class PlasticosFillerType(models.Model):
    _name = "plasticos.filler.type"
    _description = "Filler Type"
    _order = "sequence, name"

    name = fields.Char(required=True, index=True)
    code = fields.Char(required=True, index=True)
    description = fields.Text()
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
