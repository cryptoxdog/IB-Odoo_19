from odoo import api, fields, models
from odoo.exceptions import UserError


class PlasticosDocument(models.Model):
    _name = "plasticos.document"
    _description = "Plasticos Document"
    _inherit = ["mail.thread"]

    name = fields.Char(required=True)
    res_model = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)

    attachment_id = fields.Many2one("ir.attachment", required=True)
    tag_id = fields.Many2one("plasticos.document.tag", required=True)

    verified = fields.Boolean(default=False)
    verified_by = fields.Many2one("res.users")
    verified_at = fields.Datetime()

    override = fields.Boolean(default=False)
    override_reason = fields.Text()

    active = fields.Boolean(default=True)

    @api.model
    def create(self, vals):
        record = super().create(vals)

        if record.res_model == "plasticos.load":
            # Look up transaction via reverse relation (transaction.load_id -> load)
            tx = self.env["plasticos.transaction"].search([("load_id", "=", record.res_id)], limit=1)
            if tx:
                self.env["plasticos.compliance.service"].get_missing_documents("plasticos.transaction", tx.id)

        return record

    def action_verify(self):
        for rec in self:
            rec.verified = True
            rec.verified_by = self.env.user.id
            rec.verified_at = fields.Datetime.now()

    def action_override(self, reason):
        if not self.env.user.has_group("plasticos_documents.group_documents_manager"):
            raise UserError("Not authorized to override.")
        for rec in self:
            rec.override = True
            rec.override_reason = reason
