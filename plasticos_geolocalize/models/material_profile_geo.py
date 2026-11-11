"""Material profile coordinates follow the location.

The location is the facility partner (``partner_id``). Latitude and longitude
on the profile are a stored copy of that partner's geocoded coordinates.
"""

from odoo import fields, models


class PlasticosMaterialProfileGeo(models.Model):
    _inherit = "plasticos.material.profile"

    lat = fields.Float(
        string="Latitude",
        related="partner_id.partner_latitude",
        store=True,
        readonly=True,
        digits=(10, 7),
        help="Latitude of this profile's location. It follows the facility partner.",
    )
    lon = fields.Float(
        string="Longitude",
        related="partner_id.partner_longitude",
        store=True,
        readonly=True,
        digits=(10, 7),
        help="Longitude of this profile's location. It follows the facility partner.",
    )
