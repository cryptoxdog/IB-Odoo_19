from odoo import api, fields, models


class PlasticosLoadDocsBridge(models.Model):
    """Adds document_ids reverse + smart-button nav to load."""

    _inherit = "plasticos.load"

    document_ids = fields.One2many(
        "plasticos.document",
        "load_id",
        string="Documents",
        help="BOLs, weight tickets, and other documents for this load.",
    )
    document_count = fields.Integer(
        compute="_compute_document_count",
        string="Document Count",
    )

    @api.depends("document_ids")
    def _compute_document_count(self):
        for rec in self:
            rec.document_count = len(rec.document_ids)

    def _protected_parent_loads(self):
        """An accepted document on a load is parent-link evidence."""
        protected = super()._protected_parent_loads()
        if not self:
            return protected
        accepted = self.env["plasticos.document"].search(
            [("load_id", "in", self.ids), ("association_state", "=", "accepted")]
        )
        return protected | accepted.load_id

    def _physical_release_errors(self, operation_kind):
        """Documents evidence policy on the Logistics release guard.

        Logistics does not import Documents; this owner appends its reasons by
        inheritance. Only accepted operation-scoped evidence on this exact load
        can withhold a NEW physical instruction: evidence from another company,
        or a current accepted decision that is no longer eligible (expired or
        its original replaced) with no eligible row for the same scope. A
        superseded row is history: its successor decides. Only obligations that
        ``plasticos.document._release_obligations(operation_kind)`` names apply.
        Recording an actual event that already happened is not routed here.
        """
        errors = super()._physical_release_errors(operation_kind)
        errors.extend(self._scoped_evidence_release_errors(operation_kind))
        return errors

    def _scoped_evidence_release_errors(self, operation_kind):
        self.ensure_one()
        relevant = self.env["plasticos.document"]._release_obligations(operation_kind)
        if not relevant:
            return []
        rows = (
            self.env["plasticos.document"]
            .sudo()  # sudo: the guard must see every accepted scope row on this load; it only reads
            .search(
                [
                    ("association_state", "=", "accepted"),
                    *self.env["plasticos.document"]._operation_obligation_domain(),
                    "|",
                    ("load_id", "=", self.id),
                    "&",
                    ("res_model", "=", "plasticos.load"),
                    ("res_id", "=", self.id),
                ],
                order="id ASC",
            )
        ).filtered(lambda row: row.obligation_kind in relevant and row.is_current and not row.superseded_by)
        errors = []
        foreign = rows.filtered(
            lambda row: row.subject_company_id and self.company_id and row.subject_company_id != self.company_id
        )
        if foreign:
            errors.append(f"Load {self.name} carries evidence from another company. Review it before release.")
        scopes = {}
        for row in rows - foreign:
            scopes.setdefault((row.obligation_kind, row.operation_revision_key, row.coverage_key), []).append(row)
        for (kind, revision, coverage), scope_rows in sorted(scopes.items()):
            decided = [row for row in scope_rows if row.verified or row.override]
            if decided and not any(row._currently_eligible() for row in scope_rows):
                errors.append(
                    f"Load {self.name}: the accepted {kind} evidence for revision {revision} ({coverage}) "
                    "is no longer current."
                )
        return errors

    def action_view_documents(self):
        """View documents linked to this load."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Documents — {self.name}",
            "res_model": "plasticos.document",
            "view_mode": "list,form",
            "domain": [("load_id", "=", self.id)],
            "context": {"default_load_id": self.id},
        }
