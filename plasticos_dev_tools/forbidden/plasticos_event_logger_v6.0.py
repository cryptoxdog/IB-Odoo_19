# ============================================
# Canonical Header (v4.0 Production Baseline)
# ============================================
# File Name: plasticos_event_logger_v4.5.py
# Version: 4.6
# Created: 2025-10-17
# Author: Igor Beylin
# Domain: Plastic Recycling / AI-Augmented ERP
# Purpose: Unified Python service for event logging and CRM synchronization
# Related Files: ../configs/event_sync_policy_v4.5.yaml, ../models/audit_log.py, governance_audit_hooks_v4.0C.py
# ============================================

import json

from odoo import api, fields, models


class PlastOSEventLogger(models.Model):
    _name = "plasticos.event_logger"
    _description = "Unified Event Logger v4.3"

    name = fields.Char()
    event_key = fields.Char(required=True)
    reference_model = fields.Char()
    reference_id = fields.Integer()
    actor = fields.Char(default="PlasticOS-Agent")
    timestamp = fields.Datetime(default=fields.Datetime.now)

    @api.model
    def log_event(self, event_key, model, record_id, message=None, user=None):
        policy_str = self.env["ir.config_parameter"].sudo().get_param("event_sync_policy") or "{}"
        try:
            policy = json.loads(policy_str)
        except (json.JSONDecodeError, TypeError):
            policy = {}
        ledger = self.env["plasticos.decision_ledger"].create(
            {
                "event": event_key,
                "reference_model": model,
                "reference_id": record_id,
                "summary": message or "",
                "actor": user or "PlasticOS-Agent",
            }
        )
        target = self.env[model].browse(record_id)
        cfg = policy.get(event_key, {})
        if cfg.get("chatter"):
            target.message_post(body=message or f"{event_key} logged.")
        if cfg.get("activity"):
            self.env["mail.activity"].create(
                {
                    "res_model": model,
                    "res_id": record_id,
                    "summary": f"{event_key} requires attention",
                    "user_id": getattr(target, "user_id", False) and target.user_id.id or False,
                }
            )
        return ledger.id
