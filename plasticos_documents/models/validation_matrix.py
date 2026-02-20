from odoo import models, fields, api
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)


class PlasticosDocumentValidationMatrix(models.Model):
    _name = "plasticos.document.validation.matrix"
    _description = "Document Validation Matrix"
    _order = "sequence, id"

    name = fields.Char(
        required=True,
        help="Descriptive name for this validation matrix entry.",
    )
    sequence = fields.Integer(
        default=10,
        help="Order in which matrix entries are evaluated.",
    )
    doc_category = fields.Selection(
        [
            ("supplier", "Supplier Document"),
            ("carrier", "Carrier Document"),
            ("buyer", "Buyer Document"),
        ],
        string="Document Category",
        required=True,
        help="The party category this matrix entry applies to.",
    )
    tag_id = fields.Many2one(
        "plasticos.document.tag",
        string="Required Document Tag",
        required=True,
        help="The document tag that must be present for compliance.",
    )
    required_for_close = fields.Boolean(
        string="Required for Close",
        default=True,
        help="Whether this document is required to close the transaction.",
    )
    required_for_invoice = fields.Boolean(
        string="Required for Invoice",
        default=False,
        help="Whether this document is required before invoicing.",
    )
    required_for_dispatch = fields.Boolean(
        string="Required for Dispatch",
        default=False,
        help="Whether this document is required before load dispatch.",
    )
    active = fields.Boolean(default=True)

    @api.constrains("doc_category", "tag_id")
    def _check_unique_category_tag(self):
        """Prevent duplicate category+tag combinations."""
        for rec in self:
            existing = self.search([
                ("doc_category", "=", rec.doc_category),
                ("tag_id", "=", rec.tag_id.id),
                ("id", "!=", rec.id),
                ("active", "=", True),
            ])
            if existing:
                raise ValidationError(
                    "A validation matrix entry for category '%s' with tag '%s' "
                    "already exists." % (rec.doc_category, rec.tag_id.name)
                )
