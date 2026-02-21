from datetime import timedelta

from odoo import fields


def get_recent_lane_rate(env, carrier_id, lane_key):
    cutoff = fields.Date.today() - timedelta(days=30)

    rec = env["plasticos.rate.memory"].search(
        [
            ("carrier_id", "=", carrier_id),
            ("lane_key", "=", lane_key),
            ("rate_date", ">=", cutoff),
        ],
        order="rate_date desc",
        limit=1,
    )

    if rec:
        return rec.rate_amount
    return None
