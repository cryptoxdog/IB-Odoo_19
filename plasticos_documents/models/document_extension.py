import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class PlasticosDocumentExtension(models.Model):
    _inherit = "plasticos.document"

    # ── Expiry Tracking ────────────────────────────────────────────
    x_expiry_date = fields.Date(
        string="Expiry Date",
        help="Date after which this document is no longer valid.",
    )
    x_is_expired = fields.Boolean(
        string="Expired",
        compute="_compute_is_expired",
        store=True,
        help="Computed flag indicating whether the document has expired.",
    )

    # ── Versioning ─────────────────────────────────────────────────
    x_version = fields.Integer(
        string="Version",
        default=1,
        help="Document version number. Incremented on re-upload.",
    )
    x_superseded_by = fields.Many2one(
        "plasticos.document",
        string="Superseded By",
        help="Reference to the newer version of this document.",
    )
    x_is_current = fields.Boolean(
        string="Current Version",
        default=True,
        help="Whether this is the current (latest) version of the document.",
    )

    # ── Transaction Link ───────────────────────────────────────────
    x_transaction_id = fields.Many2one(
        "plasticos.transaction",
        string="Transaction",
        index=True,
        help="Link this document to a specific transaction.",
    )

    # ── Document Category ──────────────────────────────────────────
    x_doc_category = fields.Selection(
        [
            ("supplier", "Supplier Document"),
            ("carrier", "Carrier Document"),
            ("buyer", "Buyer Document"),
            ("internal", "Internal Document"),
        ],
        string="Document Category",
        help="Classification of the document by party responsible.",
    )

    @api.depends("x_expiry_date")
    def _compute_is_expired(self):
        today = fields.Date.today()
        for rec in self:
            if rec.x_expiry_date:
                rec.x_is_expired = rec.x_expiry_date < today
            else:
                rec.x_is_expired = False

    def action_supersede(self, new_doc_id):
        """Mark this document as superseded by a newer version."""
        for rec in self:
            rec.x_is_current = False
            rec.x_superseded_by = new_doc_id
            _logger.info(
                "Document %s (v%d) superseded by document %s",
                rec.name,
                rec.x_version,
                new_doc_id,
            )
