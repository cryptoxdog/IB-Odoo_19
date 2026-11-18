"""Load dock appointments (ADR-135 §5).

One accepted appointment per load and side. A new acceptance cancels the previous
one; it never overwrites it (BRS-03-R018). Accepting a different delivery slot
cancels the dependent pickup and opens a rebook flag (BRS-03-R022). Linda's
acceptance is held on the S11 gate. A person accepts directly. Archiving Linda
stops her command and writes nothing.
"""

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..schedule_window import R018_CANCEL_REASON, R022_CANCEL_REASON, acceptance_effects, may_open_pickup_appointment

LOAD = "plasticos.load"
MAIL_MESSAGE = "mail.message"

_APPOINTMENT_REPLACE = "plasticos_load_appointment_replace"
_APPOINTMENT_REPLACE_TOKEN = object()


class PlasticosLoadAppointment(models.Model):
    _name = "plasticos.load.appointment"
    _description = "Plasticos Load Appointment"
    _inherit = ["mail.thread"]
    _order = "load_id, side, id"

    load_id = fields.Many2one(
        LOAD,
        string="Load",
        required=True,
        index=True,
        ondelete="cascade",
        help="Load this dock appointment belongs to.",
    )
    company_id = fields.Many2one(
        "res.company",
        related="load_id.company_id",
        store=True,
        index=True,
        ondelete="restrict",
        help="Company of the load. Kept for company rules.",
    )
    side = fields.Selection(
        [("pickup", "Pickup"), ("delivery", "Delivery")],
        required=True,
        index=True,
        tracking=True,
        help="Which dock this appointment is for.",
    )
    state = fields.Selection(
        [
            ("requested", "Requested"),
            ("proposed", "Proposed"),
            ("accepted", "Accepted"),
            ("canceled", "Canceled"),
            ("missed", "Missed"),
        ],
        required=True,
        default="requested",
        index=True,
        tracking=True,
        help="Requested until a verified proposal exists. Accepted is one per load and side.",
    )
    slot_start = fields.Datetime(
        string="Slot Start",
        tracking=True,
        help="Slot start in UTC. Shown in the site's time zone.",
    )
    slot_end = fields.Datetime(
        string="Slot End",
        tracking=True,
        help="Slot end in UTC. Shown in the site's time zone.",
    )
    reference = fields.Char(help="The facility's appointment number.")
    arranged_by = fields.Selection(
        [("us", "Us"), ("buyer", "Buyer"), ("supplier", "Supplier")],
        string="Arranged By",
        help="Who arranged the appointment.",
    )
    proposed_by = fields.Selection(
        [("us", "Us"), ("counterparty", "Counterparty")],
        string="Proposed By",
        help="Who proposed this slot.",
    )
    source_message_id = fields.Many2one(
        MAIL_MESSAGE,
        string="Source Message",
        ondelete="set null",
        help="Message this proposal was read from. Empty until a person records it.",
    )
    note = fields.Text(help="Free note. A cancellation writes its reason here.")

    _one_accepted_per_side = models.UniqueIndex(
        "(load_id, side) WHERE state = 'accepted'",
        "A load already has an accepted appointment on this side.",
    )

    def _slot_key(self):
        self.ensure_one()
        return (self.slot_start, self.slot_end)

    def _replace_context(self):
        return self.with_context(**{_APPOINTMENT_REPLACE: _APPOINTMENT_REPLACE_TOKEN})

    def _replacing(self):
        return self.env.context.get(_APPOINTMENT_REPLACE) is _APPOINTMENT_REPLACE_TOKEN

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("state") in ("accepted", "canceled", "missed") and not self._replacing():
                raise UserError("Accept or cancel an appointment through its command.")
            if vals.get("side") == "pickup":
                load = self.env[LOAD].browse(vals.get("load_id")).exists()
                ready = bool(load.ready_confirmed_at) if load else False
                if load and not may_open_pickup_appointment(load.pickup_dock_rule, ready):
                    raise UserError(
                        "A pickup appointment is opened only when the pickup dock rule is appointment (BRS-03-R019)."
                    )
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("state") == "canceled" and not self._replacing():
            if self.filtered(lambda appointment: appointment.state == "accepted"):
                raise UserError("An accepted appointment is canceled only when its replacement is accepted.")
        if vals.get("state") == "accepted" and not self._replacing():
            raise UserError("Accept an appointment through its command.")
        return super().write(vals)

    def action_accept_appointment(self):
        """Accept this slot. Linda is held on the S11 gate. A person accepts directly."""
        self.ensure_one()
        from .linda_approval import linda_acting, linda_stop

        stop = linda_stop(self.env)
        if stop:
            return stop
        if linda_acting(self.env):
            return self._linda_accept_gate()
        return self._apply_accept()

    def _linda_accept_gate(self):
        from .linda_approval import hold_for_approval, prior_refusal

        self.check_access("read")
        load = self.load_id
        if not load.company_id:
            return {"status": "blocked", "record_id": self.id, "reason": f"Load {load.name} needs its proven company"}
        if self.state == "accepted":
            return {"status": "already_applied", "record_id": self.id}
        subject_key = f"appointment:{self.id}"
        retry = prior_refusal(self.env, "accept_appointment", subject_key, load.company_id)
        return hold_for_approval(
            self.env,
            "accept_appointment",
            "refusal_retry" if retry else "acceptance",
            f"Linda accepts the {self.side} appointment on load {load.name}",
            {"appointment_id": self.id},
            f"accept_appointment:{self.id}",
            load.company_id,
            self,
            subject_key=subject_key,
        )

    def _apply_accept(self):
        """Accept this row, then cancel the slot it replaces. Pickup follows a changed delivery."""
        self.ensure_one()
        if self.state == "accepted":
            return {"status": "already_applied", "record_id": self.id}
        if self.state in ("canceled", "missed"):
            raise UserError("A canceled or missed appointment cannot be accepted.")
        load = self.load_id
        current = {}
        accepted = load.appointment_ids.filtered(lambda appointment: appointment.state == "accepted")
        for appointment in accepted:
            current[appointment.side] = appointment._slot_key()
        effects = acceptance_effects(self.side, self._slot_key(), True, current)
        if not effects or effects[0][0] != "accept":
            raise UserError("This appointment cannot be accepted before its replacement is the accepted slot.")
        previous = accepted.filtered(lambda appointment: appointment.side == self.side and appointment.id != self.id)
        replacing = self._replace_context()
        if previous:
            self._swap_accept(previous[:1])
        else:
            replacing.write({"state": "accepted"})
        if any(effect[0] == "cancel" and effect[1] == "pickup" for effect in effects):
            pickup = accepted.filtered(lambda appointment: appointment.side == "pickup")
            if pickup:
                pickup._replace_context().write({"state": "canceled", "note": R022_CANCEL_REASON})
                load.pickup_rebook_required = True
                load._open_rebook_activity()
        elif self.side == "pickup" and load.pickup_rebook_required:
            load.pickup_rebook_required = False
        return {"status": "applied", "record_id": self.id}

    def _swap_accept(self, previous):
        """One statement: this row becomes accepted and the previous accepted row is canceled.

        PostgreSQL checks the one-accepted index at the end of the statement, so the
        replacement is accepted in the same write that cancels the slot it replaces.
        """
        self.ensure_one()
        previous.ensure_one()
        # atomic: the one-accepted index is checked at the end of this statement
        self.env.cr.execute(
            """
            UPDATE plasticos_load_appointment
               SET state = CASE id WHEN %s THEN 'accepted' ELSE 'canceled' END,
                   note = CASE id WHEN %s THEN note ELSE %s END,
                   write_uid = %s,
                   write_date = (NOW() AT TIME ZONE 'UTC')
             WHERE id IN (%s, %s)
            """,
            (self.id, self.id, R018_CANCEL_REASON, self.env.uid, self.id, previous.id),
        )
        self.invalidate_recordset()
        previous.invalidate_recordset()
