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
        existing_legacy_ids = set(
            reconciliation_model.search([("legacy_rate_memory_id", "in", self.ids)]).mapped("legacy_rate_memory_id").ids
        )
        empty_loads = self.env["plasticos.load"].browse()
        for record in self:
            if record.id in existing_legacy_ids:
                continue
            if not record.lane_key or "-" not in record.lane_key:
                disposition = "invalid_lane_key"
                candidates = empty_loads
            else:
                candidates, candidate_scan_truncated = legacy_lane_candidates(self.env, record)
                if candidate_scan_truncated:
                    disposition = "candidate_scan_truncated"
                elif len(candidates) == 1:
                    disposition = "exact_single_match"
                elif len(candidates) > 1:
                    disposition = "multiple_candidate_matches"
                else:
                    disposition = "no_candidate_match"
            canonical_load = candidates if disposition == "exact_single_match" else empty_loads
            company = getattr(canonical_load, "company_id", False) or (
                canonical_load.sale_order_id.company_id if canonical_load and canonical_load.sale_order_id else False
            )
            if not company:
                # Legacy rows have no durable company ownership.  Retain an
                # ambiguous/no-match classification without creating an
                # incorrectly company-scoped immutable record.
                continue
            reconciliation_model.create(
                {
                    "company_id": company.id,
                    "legacy_rate_memory_id": record.id,
                    "carrier_id": record.carrier_id.id,
                    "lane_key": record.lane_key,
                    "legacy_rate_amount": record.rate_amount,
                    "legacy_rate_date": record.rate_date,
                    "disposition": disposition,
                    "canonical_load_id": canonical_load.id,
                    "candidate_count": len(candidates),
                }
            )
        return True

    def unlink(self):
        raise UserError("Legacy rate-memory rows are retained until retirement is approved by reconciliation evidence.")
