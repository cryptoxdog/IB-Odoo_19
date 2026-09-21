"""Immutable local provenance for Linda events, calibration, and cache retirement."""

from __future__ import annotations

from odoo import SUPERUSER_ID, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

EVENT_TYPES = [
    ("freight_resolution_started", "Freight Resolution Started"),
    ("sal_hit", "SAL Hit"),
    ("sal_miss", "SAL Miss"),
    ("sal_not_eligible", "SAL Not Eligible"),
    ("sal_execution_failed", "SAL Execution Failed"),
    ("rfq_request_created", "RFQ Request Created"),
    ("rfq_request_cancelled_context_change", "RFQ Request Cancelled: Context Change"),
    ("rfq_request_cancelled_rate_confirmed", "RFQ Request Cancelled: Load Rate Confirmed"),
    ("carrier_response_recorded", "Carrier Response Recorded"),
    ("freight_quote_ranked", "Freight Quote Ranked"),
    ("freight_quote_selected", "Freight Quote Selected"),
    ("freight_rate_confirmed", "Freight Rate Confirmed"),
    ("freight_estimate_requested", "Freight Estimate Requested"),
    ("freight_estimate_persisted", "Freight Estimate Persisted"),
    ("freight_estimate_rejected", "Freight Estimate Rejected"),
    ("freight_actual_recorded", "Freight Actual Recorded"),
    ("freight_actual_corrected", "Freight Actual Corrected"),
    ("freight_state_transition", "Freight State Transition"),
]


class PlasticosFreightEvent(models.Model):
    _name = "plasticos.freight.event"
    _description = "Plasticos Freight Event"
    _order = "occurred_at desc, id desc"

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, ondelete="restrict"
    )
    load_id = fields.Many2one("plasticos.load", index=True, ondelete="restrict")
    transaction_id = fields.Many2one("plasticos.transaction", index=True, ondelete="restrict")
    event_type = fields.Selection(EVENT_TYPES, required=True, index=True)
    outcome_code = fields.Char(required=True, index=True)
    correlation_id = fields.Char(index=True)
    policy_version = fields.Char()
    facts = fields.Json(required=True, default=dict)
    unknowns = fields.Json(required=True, default=list)
    occurred_at = fields.Datetime(required=True, default=fields.Datetime.now, index=True)

    @api.constrains("load_id", "transaction_id", "company_id")
    def _check_company_identity(self):
        for record in self:
            if record.load_id:
                load_company = getattr(record.load_id, "company_id", False) or (
                    record.load_id.sale_order_id.company_id if record.load_id.sale_order_id else False
                )
                if load_company and load_company != record.company_id:
                    raise ValidationError("Freight event company must match its load company.")
            if record.transaction_id and record.transaction_id.company_id != record.company_id:
                raise ValidationError("Freight event company must match its transaction company.")

    def write(self, vals):
        raise UserError("Freight events are immutable audit evidence.")

    def unlink(self):
        raise UserError("Freight events cannot be deleted.")


class PlasticosFreightCalibrationObservation(models.Model):
    _name = "plasticos.freight.calibration.observation"
    _description = "Plasticos Freight Calibration Observation"
    _order = "observed_at desc, id desc"

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, ondelete="restrict"
    )
    load_id = fields.Many2one("plasticos.load", required=True, index=True, ondelete="restrict")
    estimate_id = fields.Many2one("plasticos.freight.estimate", ondelete="restrict")
    selected_quote_id = fields.Many2one("plasticos.freight.quote", ondelete="restrict")
    currency_id = fields.Many2one("res.currency", required=True, ondelete="restrict")
    estimate_amount = fields.Monetary(currency_field="currency_id", readonly=True)
    booked_rate_amount = fields.Monetary(currency_field="currency_id", readonly=True)
    actual_cost_amount = fields.Monetary(currency_field="currency_id", required=True, readonly=True)
    estimate_to_actual_variance = fields.Monetary(currency_field="currency_id", readonly=True)
    booked_to_actual_variance = fields.Monetary(currency_field="currency_id", readonly=True)
    context_fingerprint = fields.Char(required=True, readonly=True, index=True)
    observed_at = fields.Datetime(required=True, default=fields.Datetime.now, readonly=True)
    supersedes_observation_id = fields.Many2one(
        "plasticos.freight.calibration.observation", readonly=True, ondelete="restrict", index=True
    )
    correction_reason = fields.Text(readonly=True)
    recorded_by_id = fields.Many2one("res.users", required=True, readonly=True, ondelete="restrict")

    def init(self):
        """Preserve one initial observation and one direct successor per observation."""
        # Atomic partial-index creation is required; ORM constraints cannot express this lifecycle invariant.
        self.env.cr.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS plasticos_freight_calibration_initial_per_load_idx
            ON plasticos_freight_calibration_observation (load_id)
            WHERE supersedes_observation_id IS NULL
            """
        )
        # Atomic partial-index creation prevents two corrections from superseding one immutable observation.
        self.env.cr.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS plasticos_freight_calibration_one_successor_idx
            ON plasticos_freight_calibration_observation (supersedes_observation_id)
            WHERE supersedes_observation_id IS NOT NULL
            """
        )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            prior_id = vals.get("supersedes_observation_id")
            if prior_id and not vals.get("correction_reason"):
                raise ValidationError("A calibration correction requires an attributed reason.")
            if not prior_id and self.search([("load_id", "=", vals.get("load_id"))], limit=1):
                raise ValidationError("A later calibration must supersede the existing immutable observation.")
            if not vals.get("recorded_by_id"):
                vals["recorded_by_id"] = self.env.user.id
        return super().create(vals_list)

    @api.constrains("actual_cost_amount", "estimate_amount", "booked_rate_amount")
    def _check_amounts(self):
        for record in self:
            if record.actual_cost_amount < 0:
                raise ValidationError("Actual freight cost cannot be negative.")

    @api.constrains("company_id", "load_id", "estimate_id", "selected_quote_id")
    def _check_provenance_company(self):
        for record in self:
            load_company = getattr(record.load_id, "company_id", False) or (
                record.load_id.sale_order_id.company_id if record.load_id.sale_order_id else False
            )
            if load_company != record.company_id:
                raise ValidationError("Calibration evidence company must match its load company.")
            if record.estimate_id and record.estimate_id.company_id != record.company_id:
                raise ValidationError("Calibration estimate must belong to the load company.")
            if record.selected_quote_id and record.selected_quote_id.company_id != record.company_id:
                raise ValidationError("Calibration quote must belong to the load company.")

    def write(self, vals):
        raise UserError("Freight calibration observations are immutable evidence.")

    def unlink(self):
        raise UserError("Freight calibration observations cannot be deleted.")


class PlasticosRateMemoryReconciliation(models.Model):
    _name = "plasticos.rate.memory.reconciliation"
    _description = "Plasticos Rate Memory Reconciliation"
    _order = "legacy_rate_date desc, id desc"

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, ondelete="restrict"
    )
    legacy_rate_memory_id = fields.Many2one("plasticos.rate.memory", required=True, index=True, ondelete="restrict")
    carrier_id = fields.Many2one("res.partner", required=True, ondelete="restrict")
    lane_key = fields.Char(required=True, readonly=True)
    legacy_rate_amount = fields.Float(required=True, readonly=True)
    legacy_rate_date = fields.Date(required=True, readonly=True)
    disposition = fields.Selection(
        [
            ("exact_single_match", "Exact Single Match"),
            ("multiple_candidate_matches", "Multiple Candidate Matches"),
            ("no_candidate_match", "No Candidate Match"),
            ("invalid_lane_key", "Invalid Lane Key"),
            ("rate_mismatch", "Rate Mismatch"),
            ("missing_canonical_rate", "Missing Canonical Rate"),
            ("candidate_scan_truncated", "Candidate Scan Truncated"),
        ],
        required=True,
        index=True,
    )
    canonical_load_id = fields.Many2one("plasticos.load", ondelete="restrict")
    candidate_count = fields.Integer(required=True, readonly=True)
    reconciled_at = fields.Datetime(required=True, default=fields.Datetime.now, readonly=True)

    _legacy_row_unique = models.Constraint(
        "unique(legacy_rate_memory_id)", "A legacy rate-memory row may be reconciled only once."
    )

    @api.constrains("legacy_rate_memory_id", "carrier_id", "lane_key", "legacy_rate_amount", "legacy_rate_date")
    def _check_snapshot(self):
        for record in self:
            legacy = record.legacy_rate_memory_id
            if (
                legacy.carrier_id != record.carrier_id
                or legacy.lane_key != record.lane_key
                or legacy.rate_amount != record.legacy_rate_amount
                or legacy.rate_date != record.legacy_rate_date
            ):
                raise ValidationError("Reconciliation snapshot must exactly preserve the legacy row.")

    @api.constrains("company_id", "canonical_load_id")
    def _check_canonical_load_company(self):
        for record in self:
            if not record.canonical_load_id:
                continue
            load_company = getattr(record.canonical_load_id, "company_id", False) or (
                record.canonical_load_id.sale_order_id.company_id if record.canonical_load_id.sale_order_id else False
            )
            if load_company != record.company_id:
                raise ValidationError("Canonical load must belong to the reconciliation company.")

    def write(self, vals):
        raise UserError("Rate-memory reconciliation evidence is immutable.")

    def unlink(self):
        raise UserError("Rate-memory reconciliation evidence cannot be deleted.")


def _load_company(load, fallback_company):
    return getattr(load, "company_id", False) or (
        load.sale_order_id.company_id if load and load.sale_order_id else fallback_company
    )


def _require_freight_evidence_authority(env, load):
    """Validate actor and source access before narrowly elevating immutable writes."""
    if not load:
        raise AccessError("Immutable freight evidence requires a source load.")
    company = _load_company(load, env.company)
    if not company or company not in env.companies:
        raise AccessError("Freight evidence cannot be created outside an allowed company.")
    # The elevated create below is limited to immutable evidence rows. Source
    # access is always checked first so sudo never becomes a cross-company or
    # cross-role authorization bypass.
    load.check_access_rights("read")
    load.check_access_rule("read")
    if env.uid != SUPERUSER_ID and not env.user.has_group("plasticos_security_base.group_logistics"):
        raise AccessError("Only Logistics users may create immutable freight evidence.")
    return company


def create_freight_evidence(env, model_name, values, *, load):
    """Create exactly one validated immutable evidence row with explained elevation.

    Evidence models are intentionally read-only in ACLs. The helper verifies the
    acting user, source-load rule, and allowed company before the narrow sudo
    create required to preserve append-only evidence semantics.
    """
    company = _require_freight_evidence_authority(env, load)
    values = {**values, "company_id": company.id}
    return env[model_name].sudo().create(values)


def record_freight_event(env, *, event_type, outcome_code, load=None, facts=None, unknowns=None, correlation_id=None):
    """Persist structured, correlated event evidence without raw carrier content."""
    return create_freight_evidence(
        env,
        "plasticos.freight.event",
        {
            "load_id": load.id if load else False,
            "transaction_id": load.transaction_id.id if load and load.transaction_id else False,
            "event_type": event_type,
            "outcome_code": outcome_code,
            "correlation_id": correlation_id or False,
            "facts": facts or {},
            "unknowns": unknowns or [],
        },
        load=load,
    )
