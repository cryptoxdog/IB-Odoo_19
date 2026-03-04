import logging
import uuid

from odoo import fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def new_correlation_id():
    """Generate correlation ID (stub for l9_trace)"""
    return str(uuid.uuid4())


# Valid state transitions for dispatch workflow
ALLOWED_TRANSITIONS = {
    "quoted": ["dispatched"],
    "dispatched": ["picked_up"],
    "picked_up": ["delivered"],
    "delivered": ["closed"],
    "closed": [],  # Terminal state — no transitions allowed
}


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
        """Transition dispatch to a new state with validation.

        Only allows forward transitions per ALLOWED_TRANSITIONS map.
        Prevents skipping states or going backwards.
        """
        for rec in self:
            allowed = ALLOWED_TRANSITIONS.get(rec.state, [])
            if new_state not in allowed:
                if not allowed:
                    raise UserError(f"Dispatch is in terminal state '{rec.state}' and cannot be transitioned.")
                raise UserError(
                    f"Cannot transition from '{rec.state}' to '{new_state}'. "
                    f"Allowed transitions: {', '.join(allowed)}."
                )

            correlation_id = new_correlation_id()
            old_state = rec.state
            rec.state = new_state
            _logger.info(
                "Dispatch %s state transition: %s -> %s (correlation: %s)",
                rec.id,
                old_state,
                new_state,
                correlation_id,
            )
