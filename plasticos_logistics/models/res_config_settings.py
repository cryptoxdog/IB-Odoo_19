"""Schedule-window settings (ADR-135 §7). Values live in ir.config_parameter."""

from odoo import fields, models

from ..schedule_window import (
    PARAM_BUFFER_DAYS,
    PARAM_FAR_GAP_DAYS,
    PARAM_LEAD_DAYS,
    PARAM_MILES_PER_DAY,
    PARAM_NEAR_WINDOW_DAYS,
)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    plasticos_schedule_miles_per_day = fields.Integer(
        string="Miles per Transit Day",
        default=500,
        config_parameter=PARAM_MILES_PER_DAY,
        help="Transit days are the accepted carrier quote, otherwise the miles divided by this.",
    )
    plasticos_schedule_lead_days = fields.Integer(
        string="Carrier Lead Time (business days)",
        default=2,
        config_parameter=PARAM_LEAD_DAYS,
        help="Business days of carrier lead time added before the earliest pickup.",
    )
    plasticos_schedule_buffer_days = fields.Integer(
        string="Schedule Buffer (business days)",
        default=1,
        config_parameter=PARAM_BUFFER_DAYS,
        help="Business days of buffer subtracted when dating the staging deadline.",
    )
    plasticos_schedule_far_gap_days = fields.Integer(
        string="Far Gap (business days)",
        default=3,
        config_parameter=PARAM_FAR_GAP_DAYS,
        help="A later slot more than this many business days out is far enough to ask about.",
    )
    plasticos_schedule_near_window_days = fields.Integer(
        string="Near Window (business days)",
        default=7,
        config_parameter=PARAM_NEAR_WINDOW_DAYS,
        help="An earlier delivery option is asked only when that slot is inside this window.",
    )
