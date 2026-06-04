from odoo import fields, models


class PlasticosRateMemory(models.Model):
    _name = "plasticos.rate.memory"
    _description = "Plasticos Rate Memory"

    carrier_id = fields.Many2one("res.partner", required=True, index=True, ondelete="restrict")
    lane_key = fields.Char(required=True, index=True)
    rate_amount = fields.Float(required=True, default=0.0)
    rate_date = fields.Date(required=True, index=True, default=fields.Date.today)

    # ── Constraints ──────────────────────────────────────────
    _unique_carrier_lane_date = models.Constraint(
        "unique(carrier_id, lane_key, rate_date)",
        "Only one rate per carrier + lane + date is allowed.",
    )
