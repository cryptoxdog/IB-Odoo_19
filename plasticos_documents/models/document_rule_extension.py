import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class PlasticosDocumentRuleExtension(models.Model):
    _inherit = "plasticos.document.rule"

    # ── Extended Rule Conditions ───────────────────────────────────
    x_doc_category = fields.Selection(
        [
            ("supplier", "Supplier Document"),
            ("carrier", "Carrier Document"),
            ("buyer", "Buyer Document"),
            ("internal", "Internal Document"),
        ],
        string="Document Category",
        help="Category of document this rule applies to.",
    )
    x_overdue_business_days = fields.Integer(
        string="Overdue After (Business Days)",
        default=1,
        help="Number of business days after which a missing document " "is considered overdue.",
    )
    x_escalation_business_days = fields.Integer(
        string="Escalate After (Business Days)",
        default=5,
        help="Number of business days after which a missing document " "triggers escalation.",
    )
    x_required_for_dispatch = fields.Boolean(
        string="Required for Dispatch",
        default=False,
        help="Whether this document is required before load dispatch.",
    )
