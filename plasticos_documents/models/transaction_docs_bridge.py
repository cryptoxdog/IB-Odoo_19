from odoo import api, fields, models
from odoo.fields import Domain


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
    )
    def _compute_compliance(self):
        """Override to add document_ids dependencies for auto-recompute."""
        return super()._compute_compliance()

    def _search(self, domain, offset=0, limit=None, order=None, *, active_test=True, bypass_access=False):
        if self._domain_mentions_compliance(domain):
            self._refresh_elapsed_expiry_compliance()
        return super()._search(
            domain,
            offset=offset,
            limit=limit,
            order=order,
            active_test=active_test,
            bypass_access=bypass_access,
        )

    def _domain_mentions_compliance(self, domain):
        try:
            parsed = Domain(domain)
        except (TypeError, ValueError):
            return False
        return any(condition.field_expr == "compliance_status" for condition in parsed.iter_conditions())

    def _refresh_elapsed_expiry_compliance(self):
        """Stored compliance follows expiry without waiting for a document write."""
        if self.env.context.get("plasticos_compliance_quiet"):
            return
        document_model = self.env["plasticos.document"]
        documents = document_model.search(
            [
                ("res_model", "=", "plasticos.transaction"),
                ("association_state", "=", "accepted"),
                *document_model._elapsed_expiry_domain(),
                "|",
                ("verified", "=", True),
                ("override", "=", True),
            ]
        )
        if not documents:
            return
        transactions = self.browse(list({doc.res_id for doc in documents})).exists()
        if transactions:
            transactions.with_context(plasticos_compliance_quiet=True)._compute_compliance()

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
