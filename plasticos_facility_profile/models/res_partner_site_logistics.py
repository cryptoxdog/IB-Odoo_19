from odoo import fields, models


class ResPartnerSiteLogistics(models.Model):
    """Site logistics facts. Nothing selected means unknown. No defaults."""

    _inherit = "res.partner"

    loading_docks = fields.Selection(
        [
            ("none", "None (ground level)"),
            ("1", "1"),
            ("2", "2"),
            ("3_5", "3–5"),
            ("6_plus", "6+"),
        ],
        string="Loading Docks",
        help="How many loading docks the site has. Blank means unknown.",
    )
    export_container_loading = fields.Selection(
        [
            ("yes", "Yes"),
            ("cant", "Can't"),
            ("wont", "Won't"),
        ],
        string="Export Container Loading",
        help="Whether the site loads an export container. Blank means unknown.",
    )
    truck_scale = fields.Selection(
        [
            ("yes", "Yes"),
            ("no", "No"),
        ],
        string="Truck Scale",
        help="Whether the site has a truck scale. Blank means unknown.",
    )
    dock_rule_confirmed_on = fields.Date(
        string="Dock Rule Confirmed On",
        help="When a person got the site's dock-rule answer. Blank means the Appointment default is unverified.",
    )
    shipping_hours = fields.Char(
        string="Shipping Hours",
        help="Free-text hours in the site's local time. Blank means unknown.",
    )
