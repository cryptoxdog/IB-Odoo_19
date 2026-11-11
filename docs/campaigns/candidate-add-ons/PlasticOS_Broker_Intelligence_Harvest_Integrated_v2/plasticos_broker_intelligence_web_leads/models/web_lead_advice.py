"""Optional qualification-signals seam: only in non-routing shadow mode."""

import logging

from odoo import models

from ..services.shadow import can_inject, context_from_advice

_logger = logging.getLogger(__name__)
_SETTING = "plasticos_broker_intelligence_web_leads.mode"


class BrokerWebLeadAdvice(models.Model):
    _inherit = "plasticos.web.lead"

    def action_broker_advice(self):
        self.ensure_one()
        self.check_access("read")
        return {
            "type": "ir.actions.act_window",
            "name": "Broker Advice: Web Lead",
            "res_model": "plasticos.broker.advice.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_source_model": self._name, "default_source_id": self.id},
        }

    def _qualification_signals(self, merged, evidence_bundle, eligibility, config):
        """Off = byte-equivalent parent dict. Shadow cannot alter any live final routing."""
        base = super()._qualification_signals(merged, evidence_bundle, eligibility, config)
        mode = self.env["ir.config_parameter"].sudo().get_param(_SETTING, "off")
        if not can_inject(mode, config.get_qualification_mode()):
            return base
        try:
            # If an optional knowledge query fails at the database layer, its
            # failed statement must not poison the containing web-lead transaction.
            with self.env.cr.savepoint():
                advisory = self.env["plasticos.broker.advice.service"].advise_v2(
                    self._name, self.id, "What facts must be verified before qualifying this lead?"
                )
                value = dict(base)
                value["broker_advisory_shadow"] = context_from_advice(advisory)
            return value
        except Exception as exc:  # Optional advice must not become qualification authority.
            _logger.info(
                "Optional broker advisory was unavailable; original qualification retained: %s", type(exc).__name__
            )
            return base
