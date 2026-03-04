from odoo import fields, models


class PlasticosDocumentBridge(models.Model):
    """Adds load_id to documents for direct load ↔ document linking."""

    _inherit = "plasticos.document"

    load_id = fields.Many2one(
        "plasticos.load",
        string="Load",
        index=True,
        ondelete="set null",
        help="Load this document is attached to (BOL, weight ticket, etc.).",
    )
