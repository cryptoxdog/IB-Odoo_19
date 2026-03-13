import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

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
            ("internal", "Internal Document"),
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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._check_unique_category_tag_before_save(
                vals.get("doc_category"),
                vals.get("tag_id"),
                vals.get("active", True),
            )
        return super().create(vals_list)

    def write(self, vals):
        for record in self:
            doc_category = vals.get("doc_category", record.doc_category)
            tag_id = vals.get("tag_id", record.tag_id.id)
            active = vals.get("active", record.active)
            if "doc_category" in vals or "tag_id" in vals or "active" in vals:
                self._check_unique_category_tag_before_save(doc_category, tag_id, active, exclude_id=record.id)
        return super().write(vals)

    def _check_unique_category_tag_before_save(self, doc_category, tag_id, active, exclude_id=None):
        """Check for duplicate category+tag combinations before SQL insert."""
        if not active:
            return
        if doc_category and tag_id:
            domain = [
                ("doc_category", "=", doc_category),
                ("tag_id", "=", tag_id),
                ("active", "=", True),
            ]
            if exclude_id:
                domain.append(("id", "!=", exclude_id))
            if self.search(domain, limit=1):
                tag = self.env["plasticos.document.tag"].browse(tag_id)
                raise ValidationError(
                    f"A validation matrix entry for category '{doc_category}' with tag '{tag.name}' already exists."
                )
