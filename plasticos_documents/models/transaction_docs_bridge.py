from odoo import api, fields, models


class AccountMoveDocumentsCompliance(models.Model):
    """Invoice posting checks documents before the native post."""

    _inherit = "account.move"

    def _missing_invoice_documents(self, transaction):
        service = self.env["plasticos.compliance.service"]
        return not service.is_compliant("plasticos.transaction", transaction.id, purpose="invoice")


class PlasticosTransactionDocsBridge(models.Model):
    """Adds document_ids reverse + smart-button nav to transaction."""

    _inherit = "plasticos.transaction"

    document_ids = fields.One2many(
        "plasticos.document",
        "transaction_id",
        string="Documents",
    )
    document_count = fields.Integer(
        compute="_compute_document_count",
        string="Document Count",
    )

    @api.depends("document_ids")
    def _compute_document_count(self):
        for rec in self:
            rec.document_count = len(rec.document_ids)

    @api.depends(
        "document_ids",
        "document_ids.verified",
        "document_ids.override",
        "document_ids.active",
        "document_ids.tag_id",
        "document_ids.association_state",
        "document_ids.is_current",
        "document_ids.superseded_by",
        "document_ids.obligation_kind",
    )
    def _compute_compliance(self):
        """Document-aware compliance. Base stays compliant when this addon is absent.

        The service reads exact legacy rows only, so an unrelated operation-scoped
        row never sets this transaction compliant. Expiry is applied by the
        midnight recompute, not at search time.
        """
        service = self.env["plasticos.compliance.service"]
        for rec in self:
            if service.is_compliant("plasticos.transaction", rec.id):
                rec.compliance_status = "compliant"
            else:
                rec.compliance_status = "missing"

    def _missing_close_documents(self, rec):
        service = self.env["plasticos.compliance.service"]
        return not service.is_compliant("plasticos.transaction", rec.id, purpose="close")

    def action_view_documents(self):
        """Open documents linked to this transaction."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Documents — {self.name}",
            "res_model": "plasticos.document",
            "view_mode": "list,form",
            "domain": [("transaction_id", "=", self.id)],
            "context": {"default_transaction_id": self.id},
        }
