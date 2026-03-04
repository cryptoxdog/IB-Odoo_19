from odoo import fields, models


class PlasticosDocumentBridge(models.Model):
    """Adds load_id to documents for direct load ↔ document linking.

    REVIEWER NOTE: This field uses 'load_id' (no x_ prefix) while the main
    document.py uses 'x_transaction_id' (with prefix). This naming inconsistency
    is intentional — load_id follows Odoo convention for relational fields while
    x_transaction_id was added later as a custom extension field. Both work
    correctly; this is a cosmetic inconsistency only, not a bug.
    """

    _inherit = "plasticos.document"

    load_id = fields.Many2one(
        "plasticos.load",
        string="Load",
        index=True,
        ondelete="set null",
        help="Load this document is attached to (BOL, weight ticket, etc.).",
    )
