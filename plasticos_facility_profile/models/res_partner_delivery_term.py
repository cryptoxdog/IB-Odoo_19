from odoo import fields, models


class ResPartnerDeliveryTerm(models.Model):
    """Add default delivery term to all partners (suppliers AND buyers)."""

    _inherit = "res.partner"

    default_delivery_term = fields.Selection(
        [("fcfs", "FCFS"), ("appointment", "Appointment")],
        string="Default Delivery Term",
        help="Default delivery term for transactions with this partner. Used when this partner is supplier or buyer.",
    )
