from odoo import fields, models


class PlasticosLeadSource(models.Model):
    """Master registry of lead sources for tracking how partners/intakes were acquired."""

    _name = "plasticos.lead.source"
    _description = "Lead Source"
    _order = "sequence, name"

    name = fields.Char(string="Lead Source", required=True, index=True)
    code = fields.Char(
        string="Code",
        required=True,
        index=True,
        help="Internal code for programmatic reference (e.g., 'web_lead', 'magazine').",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text(
        string="Description",
        help="Optional description of this lead source.",
    )

    _unique_code = models.Constraint(
        "unique(code)",
        "Lead source code must be unique.",
    )
