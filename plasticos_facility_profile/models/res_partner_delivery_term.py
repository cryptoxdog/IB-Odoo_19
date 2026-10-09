from odoo import fields, models


class ResPartnerDeliveryTerm(models.Model):
    """Add default delivery term to all partners (suppliers AND buyers)."""

    _inherit = "res.partner"

    default_delivery_term = fields.Selection(
        [("fcfs", "FCFS"), ("appointment", "Appointment")],
        string="Dock Rule",
        default="appointment",
        help="Dock rule for this company. Appointment or first come, first served. Same rule for pickup and delivery.",
    )
