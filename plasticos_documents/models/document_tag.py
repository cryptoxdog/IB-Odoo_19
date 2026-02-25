from odoo import fields, models


class PlasticosDocumentTag(models.Model):
    _name = "plasticos.document.tag"
    _description = "Document Tag"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)

    _unique_code = models.Constraint(
        "UNIQUE(code)",
        "Document tag code must be unique.",
    )
