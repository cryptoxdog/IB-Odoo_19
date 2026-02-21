import logging
import uuid

from odoo import fields, models

_logger = logging.getLogger(__name__)

# Stub for l9_trace (enable when module available)
# from odoo.addons.l9_trace.services.trace_kernel import TraceKernel
# from odoo.addons.l9_trace.services.correlation import new_correlation_id


def new_correlation_id():
    """Generate correlation ID (stub for l9_trace)"""
    return str(uuid.uuid4())


class PlasticosDispatch(models.Model):
    _name = "plasticos.dispatch"
    _description = "Plasticos Dispatch"

    name = fields.Char(required=True)
    state = fields.Selection(
        [
            ("quoted", "Quoted"),
            ("dispatched", "Dispatched"),
            ("picked_up", "Picked Up"),
            ("delivered", "Delivered"),
            ("closed", "Closed"),
        ],
        default="quoted",
    )

    def action_transition(self, new_state):
        for rec in self:
            correlation_id = new_correlation_id()
            old_state = rec.state
            rec.state = new_state
            # Log state transition (l9_trace integration disabled)
            _logger.info(
                "Dispatch %s state transition: %s -> %s (correlation: %s)", rec.id, old_state, new_state, correlation_id
            )
