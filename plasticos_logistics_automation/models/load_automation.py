from odoo import models, fields, api

import logging

_logger = logging.getLogger(__name__)

# SLA thresholds in hours per state.
# Loads stuck beyond these limits are flagged as SLA-breached.
_SLA_HOURS = {
    "awaiting_ready": 48,
    "ready_confirmed": 24,
    "rate_confirmed": 24,
    "scheduled": 24,
    "dispatched": 72,
}


class PlasticosLoadAutomation(models.Model):
    _inherit = "plasticos.load"

    # ── Computed Automation Flags ──────────────────────────────────
    x_awaiting_ready_flag = fields.Boolean(
        string="Awaiting Ready Flag",
        compute="_compute_awaiting_ready_flag",
        store=True,
        help="True when load is stuck in awaiting_ready state.",
    )
    x_escalation_level = fields.Selection(
        [
            ("none", "None"),
            ("warning", "Warning"),
            ("critical", "Critical"),
        ],
        string="Escalation Level",
        default="none",
        help="Current escalation level based on SLA breach duration.",
    )

    @api.depends("state")
    def _compute_awaiting_ready_flag(self):
        for rec in self:
            rec.x_awaiting_ready_flag = rec.state == "awaiting_ready"

    @api.model
    def cron_load_sla_check(self):
        """Check all active loads for SLA breaches and escalate.

        This method replaces the inline escalation logic with a proper
        model method that logs to plasticos.automation.log.
        Does NOT mutate load state — only flags, notifies, and logs.
        """
        now = fields.Datetime.now()
        monitored_states = list(_SLA_HOURS.keys())

        loads = self.search([
            ("state", "in", monitored_states),
        ])

        log_model = self.env.get("plasticos.automation.log")

        for load in loads:
            if not load.entered_state_at:
                continue

            limit_hours = _SLA_HOURS.get(load.state)
            if not limit_hours:
                continue

            delta_hours = (now - load.entered_state_at).total_seconds() / 3600

            if delta_hours <= limit_hours:
                # Within SLA — reset escalation if previously set
                if load.x_escalation_level != "none":
                    load.x_escalation_level = "none"
                continue

            # SLA breached
            if not load.sla_breached:
                load.sla_breached = True

            # Determine escalation level
            if delta_hours > limit_hours * 2:
                new_level = "critical"
            else:
                new_level = "warning"

            if load.x_escalation_level != new_level:
                load.x_escalation_level = new_level

                load.message_post(
                    body="SLA breach [%s]: load stuck in '%s' for %.1f hours "
                         "(limit: %d hours)."
                         % (new_level.upper(), load.state,
                            delta_hours, limit_hours),
                    message_type="notification",
                )

                # Log to automation log
                if log_model is not None:
                    log_model.create({
                        "name": "SLA breach [%s] for %s"
                                % (new_level, load.name),
                        "model_name": "plasticos.load",
                        "res_id": load.id,
                        "action_type": "logistics_escalation",
                    })

                _logger.info(
                    "Logistics automation: SLA breach [%s] for load %s "
                    "(state=%s, hours=%.1f, limit=%d)",
                    new_level,
                    load.name,
                    load.state,
                    delta_hours,
                    limit_hours,
                )
