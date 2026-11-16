import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Only action_transition may move a dispatch. A direct create or write of a later
# state would skip the transition graph and the load's physical-release guard.
_DISPATCH_TRANSITION = "plasticos_dispatch_transition"
_DISPATCH_TRANSITION_TOKEN = object()
# Entering these states issues a new physical instruction for the load.
_RELEASE_STATES = {"dispatched": "dispatch"}


class PlasticosDispatch(models.Model):
    _name = "plasticos.dispatch"
    _description = "Plasticos Dispatch"

    name = fields.Char(required=True, default="New Dispatch")
    load_id = fields.Many2one("plasticos.load", string="Load", ondelete="restrict", index=True)
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

    def _transition_authorized(self):
        return self.env.context.get(_DISPATCH_TRANSITION) is _DISPATCH_TRANSITION_TOKEN

    @api.model_create_multi
    def create(self, vals_list):
        if not self._transition_authorized():
            for vals in vals_list:
                if vals.get("state") not in (None, False, "quoted"):
                    raise UserError("A dispatch is created as Quoted and moves only through its transition workflow.")
        return super().create(vals_list)

    def write(self, vals):
        if "state" in vals and not self._transition_authorized():
            raise UserError("Dispatch state may only change through the validated transition workflow.")
        return super().write(vals)

    def action_transition(self, new_state):
        """Transition dispatch to a new state with validation.

        Only allows forward transitions per ALLOWED_TRANSITIONS map.
        Prevents skipping states or going backwards. Entering ``dispatched``
        issues a new physical instruction, so the load's release guard must
        allow it first. Later states record movement that already happened and
        are never rewound or blocked by that guard.
        """
        from odoo.addons.plasticos_logistics.services.state_machine import (
            ALLOWED_TRANSITIONS,
            new_correlation_id,
        )

        for rec in self:
            allowed = ALLOWED_TRANSITIONS.get(rec.state, [])
            if new_state not in allowed:
                if not allowed:
                    raise UserError(f"Dispatch is in terminal state '{rec.state}' and cannot be transitioned.")
                raise UserError(
                    f"Cannot transition from '{rec.state}' to '{new_state}'. Allowed transitions: {', '.join(allowed)}."
                )
            release = _RELEASE_STATES.get(new_state)
            if release and rec.load_id:
                rec.load_id._require_physical_release(release)

            correlation_id = new_correlation_id()
            old_state = rec.state
            rec.with_context(**{_DISPATCH_TRANSITION: _DISPATCH_TRANSITION_TOKEN}).write({"state": new_state})
            _logger.info(
                "Dispatch %s state transition: %s -> %s (correlation: %s)",
                rec.id,
                old_state,
                new_state,
                correlation_id,
            )
