from odoo import fields, models


class PlasticosFormType(models.Model):
    """Physical form of plastic material (pellet, regrind, flake, etc.)."""

    _name = "plasticos.form.type"
    _description = "Form Type"
    _order = "sequence, name"

    name = fields.Char(required=True, index=True)
    code = fields.Char(
        required=True,
        index=True,
        help="Canonical lowercase code (e.g. pellet, regrind).",
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    _sql_constraints = [
        ("code_uniq", "unique(code)", "Form type code must be unique."),
    ]


class PlasticosColorType(models.Model):
    """Color classification for plastic materials."""

    _name = "plasticos.color.type"
    _description = "Color Type"
    _order = "sequence, name"

    name = fields.Char(required=True, index=True)
    code = fields.Char(
        required=True,
        index=True,
        help="Canonical lowercase code (e.g. natural, white, black).",
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    _sql_constraints = [
        ("code_uniq", "unique(code)", "Color type code must be unique."),
    ]


class PlasticosSourceType(models.Model):
    """Source classification (post-industrial, post-consumer, etc.)."""

    _name = "plasticos.source.type"
    _description = "Source Type"
    _order = "sequence, name"

    name = fields.Char(required=True, index=True)
    code = fields.Char(
        required=True,
        index=True,
        help="Canonical lowercase code (e.g. post_industrial, post_consumer).",
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    _sql_constraints = [
        ("code_uniq", "unique(code)", "Source type code must be unique."),
    ]


class PlasticosProcessType(models.Model):
    """Processing method (injection, extrusion, blow_mold, etc.)."""

    _name = "plasticos.process.type"
    _description = "Process Type"
    _order = "sequence, name"

    name = fields.Char(required=True, index=True)
    code = fields.Char(
        required=True,
        index=True,
        help="Canonical lowercase code (e.g. injection, extrusion).",
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    _sql_constraints = [
        ("code_uniq", "unique(code)", "Process type code must be unique."),
    ]


class PlasticosDealType(models.Model):
    """Deal type classification (spot, recurring, contract, trial)."""

    _name = "plasticos.deal.type"
    _description = "Deal Type"
    _order = "sequence, name"

    name = fields.Char(required=True, index=True)
    code = fields.Char(
        required=True,
        index=True,
        help="Canonical lowercase code (e.g. spot, recurring).",
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    _sql_constraints = [
        ("code_uniq", "unique(code)", "Deal type code must be unique."),
    ]
