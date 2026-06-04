from odoo import fields, models


class PlasticosDocumentRule(models.Model):
    _name = "plasticos.document.rule"
    _description = "Document Compliance Rule"

    name = fields.Char(required=True)
    tag_id = fields.Many2one("plasticos.document.tag", required=True, index=True, ondelete="restrict")
    res_model = fields.Char(required=True, index=True)
    client_id = fields.Many2one("res.partner", index=True, ondelete="restrict")
    required_for_invoice = fields.Boolean(default=False)
    required_for_close = fields.Boolean(default=True)
    active = fields.Boolean(default=True)

    # ── Extended Rule Conditions ───────────────────────────────────
    doc_category = fields.Selection(
        [
            ("supplier", "Supplier Document"),
            ("carrier", "Carrier Document"),
            ("buyer", "Buyer Document"),
            ("internal", "Internal Document"),
        ],
        string="Document Category",
        help="Category of document this rule applies to.",
    )
    overdue_business_days = fields.Integer(
        string="Overdue After (Business Days)",
        default=1,
        help="Number of business days after which a missing document is considered overdue.",
    )
    escalation_business_days = fields.Integer(
        string="Escalate After (Business Days)",
        default=5,
        help="Number of business days after which a missing document triggers escalation.",
    )
    required_for_dispatch = fields.Boolean(
        string="Required for Dispatch",
        default=False,
        help="Whether this document is required before load dispatch.",
    )

    # ── Constraints ──────────────────────────────────────────
    _unique_rule_per_tag_model_client = models.Constraint(
        "unique(tag_id, res_model, client_id)",
        "Only one rule per tag + model + client combination is allowed.",
    )
