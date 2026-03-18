"""Status Cascade Service for cross-model status updates.

This service handles cascading status changes across related records
(Transaction -> DO, Transaction -> PO, DO -> Transaction) with audit
logging via mail.thread chatter messages.
"""

import logging

from odoo import fields

_logger = logging.getLogger(__name__)

VALID_CASCADES = {
    "plasticos.transaction": {
        "delivered": [
            ("stock.picking", "delivery_order_id", "done"),
        ],
        "cancelled": [
            ("purchase.order", "purchase_order_ids", "cancel"),
            ("stock.picking", "delivery_order_id", "cancel"),
        ],
    },
    "stock.picking": {
        "done": [
            ("plasticos.transaction", "_reverse_tx", "delivered"),
        ],
    },
}


class StatusCascadeService:
    """Service to cascade status changes across related records.

    Audit logging is handled via mail.thread tracking (native Odoo)
    plus structured chatter messages for cascade events.
    """

    def __init__(self, env):
        self.env = env

    def cascade_status(self, model_name, record_id, new_status, reason=None):
        """Cascade status change to related records with audit trail.

        Args:
            model_name: Source model (e.g., 'plasticos.transaction')
            record_id: Source record ID
            new_status: New status value
            reason: Optional reason for the change (for audit)

        Returns:
            dict with 'updated' list and optional 'error'
        """
        record = self.env[model_name].browse(record_id)
        if not record.exists():
            return {"error": f"{model_name} {record_id} not found"}

        old_status = record.state if hasattr(record, "state") else None
        cascades = VALID_CASCADES.get(model_name, {}).get(new_status, [])
        updated = [(model_name, record_id)]

        self._log_cascade_start(record, old_status, new_status, reason)

        for target_model, field_name, target_status in cascades:
            try:
                if field_name == "_reverse_tx":
                    tx = self.env["plasticos.transaction"].search([("delivery_order_id", "=", record_id)], limit=1)
                    if tx:
                        tx_old = tx.state
                        tx.with_context(bypass_state_guard=True).write({"state": target_status})
                        self._log_cascade_effect(tx, tx_old, target_status, record)
                        updated.append((target_model, tx.id))
                elif hasattr(record, field_name):
                    related = getattr(record, field_name)
                    if related:
                        for rec in related:
                            if hasattr(rec, "state") and rec.state != target_status:
                                rec_old = rec.state
                                rec.state = target_status
                                self._log_cascade_effect(rec, rec_old, target_status, record)
                                updated.append((target_model, rec.id))
            except Exception as e:
                _logger.error(
                    "Cascade failed: %s.%s -> %s: %s",
                    model_name,
                    field_name,
                    target_status,
                    str(e),
                )

        return {"updated": updated}

    def _log_cascade_start(self, record, old_status, new_status, reason):
        """Post audit message to source record chatter."""
        if not hasattr(record, "message_post"):
            return

        body = "<b>Status Cascade Initiated</b><br/>"
        body += f"State: {old_status} → {new_status}<br/>"
        if reason:
            body += f"Reason: {reason}<br/>"
        body += f"Timestamp: {fields.Datetime.now()}"

        record.message_post(body=body, message_type="notification")

    def _log_cascade_effect(self, target_record, old_status, new_status, source_record):
        """Post audit message to cascaded record chatter."""
        if not hasattr(target_record, "message_post"):
            return

        body = "<b>Status Updated via Cascade</b><br/>"
        body += f"State: {old_status} → {new_status}<br/>"
        body += f"Triggered by: {source_record._name} {source_record.display_name}<br/>"
        body += f"Timestamp: {fields.Datetime.now()}"

        target_record.message_post(body=body, message_type="notification")
