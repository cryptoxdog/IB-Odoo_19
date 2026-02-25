import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


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

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for record in records:
            if record.res_model == "plasticos.load":
                # Look up transaction via reverse relation (transaction.load_id -> load)
                tx = self.env["plasticos.transaction"].search([("load_id", "=", record.res_id)], limit=1)
                if tx:
                    self.env["plasticos.compliance.service"].get_missing_documents("plasticos.transaction", tx.id)

        return records

    def action_verify(self):
        for rec in self:
            rec.verified = True
            rec.verified_by = self.env.user.id
            rec.verified_at = fields.Datetime.now()

    def action_override(self, reason=None):
        """Override document verification.

        Args:
            reason: Optional override reason string.  When called from a
                    button action (no positional args), the reason can be
                    set later via the ``override_reason`` field.
        """
        if not self.env.user.has_group("plasticos_documents.group_documents_manager"):
            raise UserError("Not authorized to override.")
        for rec in self:
            rec.override = True
            if reason:
                rec.override_reason = reason

    # ── Cron ────────────────────────────────────────────────
    @api.model
    def _cron_compliance_audit(self):
        """Batch compliance audit: flag verified documents that have expired.

        Called by the scheduled action ``cron_document_compliance_check``.
        Resets ``verified`` on any document whose ``x_is_expired`` is True
        so that the compliance service no longer considers them valid.
        """
        expired = self.search(
            [
                ("verified", "=", True),
                ("x_is_expired", "=", True),
                ("active", "=", True),
            ]
        )
        if expired:
            expired.write({"verified": False})
            _logger.info("Compliance audit: reset verified flag on %d expired documents.", len(expired))
        else:
            _logger.info("Compliance audit: no expired verified documents found.")
