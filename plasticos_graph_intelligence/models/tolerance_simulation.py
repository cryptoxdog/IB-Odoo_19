from odoo import fields, models


class ToleranceSimulation(models.Model):
    _name = "plasticos.tolerance.simulation"
    _description = "Capability Tolerance Simulation"
    _order = "create_date desc"

    facility_id = fields.Many2one(
        "res.partner",
        required=True,
        index=True,
    )

    capability_id = fields.Char(required=True)

    parameter = fields.Selection(
        [
            ("contamination", "Contamination"),
            ("filler", "Filler"),
            ("mfi", "MFI"),
        ],
        required=True,
    )

    multiplier = fields.Float(required=True)

    unlocked_match_count = fields.Integer(required=True)
    unlocked_volume = fields.Float(required=True)

    created_by = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
    )
