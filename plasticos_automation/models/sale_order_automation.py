import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class SaleOrderAutomation(models.Model):
    _inherit = "sale.order"

    # ── Delivery Term Management ───────────────────────────────────
    delivery_term = fields.Selection(
        [
            ("fcfs", "FCFS (First Come, First Served)"),
            ("appointment", "Appointment Required"),
        ],
        string="Delivery Term",
        default="fcfs",
        help="Delivery method: FCFS or appointment-based.",
    )
    appt_requested = fields.Boolean(
        string="Dock Appointment Requested",
        default=False,
        help="Flag indicating dock appointment has been requested.",
    )
    appt_requested_on = fields.Datetime(
        string="Dock Appointment Requested On",
        help="Timestamp when dock appointment was requested.",
    )

    def action_request_dock_appointment(self):
        """Mark the order as having a dock appointment requested."""
        for rec in self:
            rec.appt_requested = True
            rec.appt_requested_on = fields.Datetime.now()
            rec.message_post(
                body=f"Dock appointment requested for SO {rec.name}.",
                message_type="notification",
            )
            _logger.info(
                "Logistics automation: dock appointment requested for SO %s",
                rec.name,
            )
