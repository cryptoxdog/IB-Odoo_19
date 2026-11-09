from odoo import SUPERUSER_ID, api, fields, models
from odoo.exceptions import AccessError, UserError


class PlasticosRateMemory(models.Model):
    _name = "plasticos.rate.memory"
    _description = "Plasticos Rate Memory"

    carrier_id = fields.Many2one("res.partner", required=True, index=True, ondelete="restrict")
    lane_key = fields.Char(required=True, index=True)
    rate_amount = fields.Float(required=True, default=0.0)
    rate_date = fields.Date(required=True, index=True, default=fields.Date.today)

    # ── Constraints ──────────────────────────────────────────
    _unique_carrier_lane_date = models.Constraint(
        "unique(carrier_id, lane_key, rate_date)",
        "Only one rate per carrier + lane + date is allowed.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("plasticos_logistics_legacy_rate_memory_migration"):
            raise UserError("Legacy rate memory is frozen; canonical freight evidence owns new rates.")
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get("plasticos_logistics_legacy_rate_memory_migration"):
            raise UserError("Legacy rate memory is frozen; canonical freight evidence cannot be changed.")
        return super().write(vals)

    def _require_reconciliation_operator(self):
        if self.env.uid == SUPERUSER_ID:
            return
        if not (
            self.env.user.has_group("plasticos_security_base.group_logistics")
            or self.env.user.has_group("base.group_system")
        ):
            raise AccessError("Only Logistics or system administrators may reconcile legacy rate memory.")

    def action_reconcile_to_canonical_history(self):
        """Create one immutable classification per legacy cache row without moving data."""
        from odoo.addons.plasticos_logistics.services.freight_history import legacy_lane_candidates

        self._require_reconciliation_operator()
        reconciliation_model = self.env["plasticos.rate.memory.reconciliation"]
        # sudo() justification: existence check only. A legacy row is reconciled
        # once for the whole database, and an exact-match row is hidden outside
        # its load's company, so a company-filtered search would miss it and the
        # create below would hit the unique constraint. Only legacy ids the
        # actor already holds are read back; no reconciliation field is returned.
        existing_legacy_ids = set(
            reconciliation_model.sudo()  # sudo: existence check of legacy ids only (ADR-129)
            .search([("legacy_rate_memory_id", "in", self.ids)])
            .mapped("legacy_rate_memory_id")
            .ids
        )
        empty_loads = self.env["plasticos.load"].browse()
        reconciliation_vals = []
        unclassifiable = []
        for record in self:
            if record.id in existing_legacy_ids:
                continue
            if not record.lane_key or "-" not in record.lane_key:
                disposition = "invalid_lane_key"
                candidates = empty_loads
            else:
                candidates, candidate_scan_truncated, complete = legacy_lane_candidates(self.env, record)
                if not complete:
                    # ADR-129 / issue #182: a partial view must not become the
                    # permanent global answer for this legacy row.
                    unclassifiable.append(record.id)
                    continue
                if candidate_scan_truncated:
                    disposition = "candidate_scan_truncated"
                elif len(candidates) == 1:
                    disposition = "exact_single_match"
                elif len(candidates) > 1:
                    disposition = "multiple_candidate_matches"
                else:
                    disposition = "no_candidate_match"
            if disposition == "exact_single_match":
                company = getattr(candidates, "company_id", False) or (
                    candidates.sale_order_id.company_id if candidates.sale_order_id else False
                )
                if not company:
                    raise UserError("An exact rate-memory match requires the canonical load's company.")
                company_id = company.id
                canonical_load_id = candidates.id
            else:
                # ADR-129: a non-exact disposition has no source company. Store
                # False so env.company cannot attribute the row to the operator.
                company_id = False
                canonical_load_id = False
            reconciliation_vals.append(
                {
                    "company_id": company_id,
                    "legacy_rate_memory_id": record.id,
                    "carrier_id": record.carrier_id.id,
                    "lane_key": record.lane_key,
                    "legacy_rate_amount": record.rate_amount,
                    "legacy_rate_date": record.rate_date,
                    "disposition": disposition,
                    "canonical_load_id": canonical_load_id,
                    "candidate_count": len(candidates),
                }
            )
        if unclassifiable:
            # Fail closed for the whole batch: nothing is recorded until an
            # operator who can read every candidate load runs it.
            raise AccessError(
                f"Legacy rate-memory rows {sorted(unclassifiable)} cannot be classified with your access. "
                "Nothing was reconciled; an operator with access to every company must run it."
            )
        if reconciliation_vals:
            # One immutable classification per legacy row, created in one batch.
            reconciliation_model.create(reconciliation_vals)
        return True

    def unlink(self):
        raise UserError("Legacy rate-memory rows are retained until retirement is approved by reconciliation evidence.")
