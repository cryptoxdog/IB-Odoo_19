"""Make intake geo fields related to the partner's coordinates.

Replaces standalone ``lat``/``lon`` Float fields on
``plasticos.intake`` with ``related`` fields that read from
``partner_id.partner_latitude`` / ``partner_id.partner_longitude``.

``store=True`` ensures the values are indexed and searchable
for freight automation queries.
"""

from odoo import fields, models


class PlasticosIntakeGeo(models.Model):
    _inherit = "plasticos.intake"

    # Override standalone Float fields with related fields.
    # store=True persists to DB for indexing / freight queries.
    lat = fields.Float(
        string="Latitude",
        related="partner_id.partner_latitude",
        store=True,
        readonly=True,
    )
    lon = fields.Float(
        string="Longitude",
        related="partner_id.partner_longitude",
        store=True,
        readonly=True,
    )
