from odoo import fields

ESCALATION_HOURS = {
    "awaiting_ready": 48,
    "ready_confirmed": 24,
    "rate_confirmed": 24,
    "scheduled": 24,
    "dispatched": 72,
}


def check_escalations(env):
    now = fields.Datetime.now()
    loads = env["plasticos.load"].search(
        [("state", "in", list(ESCALATION_HOURS.keys()))],
        order="id asc",
        limit=500,
    )
    for load in loads:
        if not load.entered_state_at:
            continue
        limit = ESCALATION_HOURS.get(load.state)
        if not limit:
            continue
        delta = (now - load.entered_state_at).total_seconds() / 3600
        if delta > limit and not load.sla_breached:
            load.sla_breached = True
            load.message_post(body=f"SLA breach: stuck in {load.state} > {limit}h")
