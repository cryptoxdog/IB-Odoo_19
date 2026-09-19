from odoo import fields, models
from odoo.exceptions import UserError


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

    def action_reconcile_to_canonical_history(self):
        """Create one immutable classification per legacy cache row without moving data."""
        from odoo.addons.plasticos_logistics.services.freight_history import legacy_lane_candidates

        reconciliation_model = self.env["plasticos.rate.memory.reconciliation"]
        for record in self:
            if reconciliation_model.search_count([("legacy_rate_memory_id", "=", record.id)]):
                continue
            if not record.lane_key or "-" not in record.lane_key:
                disposition = "invalid_lane_key"
                candidates = self.env["plasticos.load"].browse()
            else:
                candidates = legacy_lane_candidates(self.env, record)
                if len(candidates) == 1:
                    disposition = "exact_single_match"
                elif len(candidates) > 1:
                    disposition = "multiple_candidate_matches"
                else:
                    disposition = "no_candidate_match"
            reconciliation_model.create(
                {
                    "company_id": self.env.company.id,
                    "legacy_rate_memory_id": record.id,
                    "carrier_id": record.carrier_id.id,
                    "lane_key": record.lane_key,
                    "legacy_rate_amount": record.rate_amount,
                    "legacy_rate_date": record.rate_date,
                    "disposition": disposition,
                    "canonical_load_id": candidates.id if len(candidates) == 1 else False,
                    "candidate_count": len(candidates),
                }
            )
        return True

    def unlink(self):
        raise UserError("Legacy rate-memory rows are retained until retirement is approved by reconciliation evidence.")
