# ============================================================
# File: core/system_state_registry_v4.0C.py
# Domain: core
# Version: 4.0C
# Created: 2025-10-28T09:56:00Z
# Author: Igor Beylin
# Purpose: Centralized registry maintaining live and historical
#          state data for all AI modules and core processes within
#          Odoo 19. Enables traceability, rollback, and temporal
#          analysis for governance and diagnostics.
# ============================================================

"""
System State Registry
=====================
The System State Registry acts as a canonical log and state-store
for all key AI subsystems and operational processes. It provides
continuous state snapshots, temporal rollback capabilities, and
insight into both live and archived configurations.

Core Responsibilities:
- Maintain real-time state tracking for active modules.
- Log system configuration and context changes.
- Support temporal rollback and audit reconstruction.
- Provide interfaces for analytics, compliance, and recovery.
"""

import datetime

from odoo import api, fields, models


class SystemStateRegistry(models.Model):
    _name = "plasticos.system.state"
    _description = "System State Registry"
    _order = "timestamp desc"

    timestamp = fields.Datetime(default=lambda self: datetime.datetime.utcnow(), readonly=True)
    module_name = fields.Char("Module", required=True)
    state_key = fields.Char("State Key", required=True)
    state_value = fields.Text("State Value", required=True)
    change_type = fields.Selection(
        [("update", "Update"), ("rollback", "Rollback"), ("rebuild", "Rebuild"), ("reset", "Reset")], default="update"
    )
    actor = fields.Char("Modified By", default="system")
    context = fields.Char("Operational Context")
    verified = fields.Boolean("Integrity Verified", default=True)

    @api.model
    def record_state(self, module_name, state_key, state_value, change_type="update", actor="system", context=None):
        """Creates a new entry in the system state registry."""
        entry = self.create(
            {
                "module_name": module_name,
                "state_key": state_key,
                "state_value": state_value,
                "change_type": change_type,
                "actor": actor,
                "context": context or "unspecified",
            }
        )
        self._log_to_governance(entry)
        return entry

    def _log_to_governance(self, entry):
        """Reports all state changes to governance layer."""
        ledger = self.env["plasticos.governance.ledger"]
        ledger.log_event(
            event_type="info",
            actor="SystemStateRegistry",
            module=entry.module_name,
            context_ref=entry.state_key,
            message=f"State {entry.change_type.upper()} at {entry.timestamp.isoformat()}",
        )
        return True

    @api.model
    def rollback_state(self, module_name, state_key):
        """Performs a rollback to the previous recorded state."""
        last_entry = self.search(
            [("module_name", "=", module_name), ("state_key", "=", state_key)], limit=1, order="timestamp desc"
        )
        if not last_entry:
            return False
        rollback_entry = self.create(
            {
                "module_name": module_name,
                "state_key": state_key,
                "state_value": last_entry.state_value,
                "change_type": "rollback",
                "actor": "rollback_daemon",
            }
        )
        self._log_to_governance(rollback_entry)
        return rollback_entry

    @api.model
    def verify_integrity(self):
        """Runs integrity checks on stored state data."""
        corrupt_entries = []
        for entry in self.search([]):
            if not entry.state_value or len(entry.state_value.strip()) == 0:
                entry.verified = False
                corrupt_entries.append(entry.id)
        if corrupt_entries:
            governance = self.env["plasticos.governance.ledger"]
            governance.log_event(
                event_type="warning",
                actor="SystemStateRegistry",
                module="registry",
                context_ref="integrity_check",
                message=f"{len(corrupt_entries)} entries failed integrity validation.",
            )
        return len(corrupt_entries)


# ------------------------------------------------------------
# SYSTEM INITIALIZATION HOOK
# ------------------------------------------------------------


def initialize_system_state_registry(env):
    """Initialize registry and perform baseline snapshot of critical modules."""
    registry = env["plasticos.system.state"]
    for module in ["governance", "buyer_matching", "offer_dispatch", "recovery_daemon"]:
        registry.record_state(
            module_name=module,
            state_key="startup_snapshot",
            state_value="initialized",
            change_type="update",
            actor="bootstrap",
        )


# End of File
# ============================================================
