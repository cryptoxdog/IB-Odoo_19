import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

_SLA_HOURS = {
    "awaiting_ready": 48,
    "ready_confirmed": 24,
    "rate_confirmed": 24,
    "scheduled": 24,
    "dispatched": 72,
}


class PlasticosLoadAutomation(models.Model):
    _inherit = "plasticos.load"

    awaiting_ready_flag = fields.Boolean(compute="_compute_awaiting_ready_flag", store=True)
    escalation_level = fields.Selection(
        [("none", "None"), ("warning", "Warning"), ("critical", "Critical")],
        default="none",
    )

    @api.depends("state")
    def _compute_awaiting_ready_flag(self):
        for rec in self:
            rec.awaiting_ready_flag = rec.state == "awaiting_ready"

    @api.model
    def cron_load_sla_check(self):
        self.env.cr.execute("SELECT pg_try_advisory_lock(hashtext(%s))", ["plasticos_automation.cron_load_sla_check"])
        if not self.env.cr.fetchone()[0]:
            _logger.info("Skipping load SLA cron: lock is already held.")
            return

        try:
            now = fields.Datetime.now()
            loads = self.search(
                [("state", "in", list(_SLA_HOURS.keys()))],
                order="entered_state_at ASC, id ASC",
                limit=500,
            )
            log_model = self.env["plasticos.automation.log"]

            for load in loads:
                if not load.entered_state_at:
                    continue
                limit_hours = _SLA_HOURS.get(load.state)
                if not limit_hours:
                    continue

                delta_hours = (now - load.entered_state_at).total_seconds() / 3600
                if delta_hours <= limit_hours:
                    if load.escalation_level != "none":
                        load.escalation_level = "none"
                    continue

                if not load.sla_breached:
                    load.sla_breached = True

                new_level = "critical" if delta_hours > limit_hours * 2 else "warning"
                if load.escalation_level != new_level:
                    load.escalation_level = new_level
                    load.message_post(
                        body=(
                            f"SLA breach [{new_level.upper()}]: load stuck in '{load.state}' "
                            f"for {delta_hours:.1f} hours (limit: {limit_hours} hours)."
                        ),
                        message_type="notification",
                    )
                    log_model.create(
                        {
                            "name": f"SLA breach [{new_level}] for {load.name}",
                            "model_name": "plasticos.load",
                            "res_id": load.id,
                            "action_type": "logistics_escalation",
                        }
                    )
        finally:
            self.env.cr.execute("SELECT pg_advisory_unlock(hashtext(%s))", ["plasticos_automation.cron_load_sla_check"])
