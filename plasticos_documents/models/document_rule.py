from odoo import fields, models


class PlasticosDocumentRule(models.Model):
    _name = "plasticos.document.rule"
    _description = "Document Compliance Rule"

    name = fields.Char(required=True)
    tag_id = fields.Many2one("plasticos.document.tag", required=True, index=True)
    res_model = fields.Char(required=True, index=True)
    client_id = fields.Many2one("res.partner", index=True)
    required_for_invoice = fields.Boolean(default=False)
    required_for_close = fields.Boolean(default=True)
    active = fields.Boolean(default=True)

    # ── Constraints (Odoo 19 models.Constraint) ──────────────
    _check_unique_rule = models.Constraint(
        "unique(tag_id, res_model, client_id)",
        "Only one rule per tag + model + client combination is allowed.",
    )
