"""Immutable local provenance for Linda events, calibration, and cache retirement."""

from __future__ import annotations

from odoo import SUPERUSER_ID, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

# ADR-129: reconciliation dispositions that carry no company and no canonical load.
UNOWNED_RECONCILIATION_DISPOSITIONS = (
    "invalid_lane_key",
    "no_candidate_match",
    "multiple_candidate_matches",
    "candidate_scan_truncated",
)

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
    ("actual_pickup_recorded", "Actual Pickup Recorded"),
    ("actual_delivery_recorded", "Actual Delivery Recorded"),
    ("actual_event_corrected", "Actual Event Corrected"),
]

# Workflow audit of a state change may still be written for a legacy load that
# has no proven company. It is marked as such. Every other freight evidence row
# requires the load's own company (no env.company fallback).
_UNPROVEN_COMPANY_AUDIT_EVENTS = frozenset({"freight_state_transition"})


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
    # Not required: Odoo stores an empty Json value ({} / []) as SQL NULL, so a NOT NULL
    # column rejects every event that records no facts or no unknowns.
    facts = fields.Json(default=dict)
    unknowns = fields.Json(default=list)
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
            # plasticos.transaction has no company_id; its company is its sale order's.
            tx_company = record.transaction_id.sale_order_id.company_id
            if tx_company and tx_company != record.company_id:
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
        initial_load_ids = [
            vals.get("load_id")
            for vals in vals_list
            if not vals.get("supersedes_observation_id") and vals.get("load_id")
        ]
        existing_load_ids = set()
        if initial_load_ids:
            existing_load_ids = set(
                self.search([("load_id", "in", initial_load_ids), ("supersedes_observation_id", "=", False)])
                .mapped("load_id")
                .ids
            )
        seen_initial = set()
        for vals in vals_list:
            prior_id = vals.get("supersedes_observation_id")
            if prior_id and not vals.get("correction_reason"):
                raise ValidationError("A calibration correction requires an attributed reason.")
            load_id = vals.get("load_id")
            if not prior_id and load_id and (load_id in existing_load_ids or load_id in seen_initial):
                raise ValidationError("A later calibration must supersede the existing immutable observation.")
            if not prior_id and load_id:
                seen_initial.add(load_id)
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
        "res.company",
        required=False,
        ondelete="restrict",
        help=(
            "Company of the matched canonical load. Empty for a non-exact disposition "
            "so the operator's company is not stored as ownership. See ADR-129."
        ),
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

    @api.constrains("disposition", "company_id", "canonical_load_id")
    def _check_canonical_load_company(self):
        """ADR-129: ownership follows the historical evidence.

        An exact match carries its canonical load and that load's company. The
        four unowned dispositions carry neither. ``rate_mismatch`` and
        ``missing_canonical_rate`` have no producer and no ADR-129 ownership
        rule, so they are refused rather than given an ownership shape here.
        """
        for record in self:
            disposition = record.disposition
            if disposition == "exact_single_match":
                load = record.canonical_load_id
                if not load:
                    raise ValidationError("An exact rate-memory match requires its canonical load.")
                # sudo() justification: reads only the company that owns the
                # load this row already links, so the check does not depend on
                # whether the creating actor can see that company.
                load_sudo = load.sudo()  # sudo: reads only the linked load's company (ADR-129)
                load_company = getattr(load_sudo, "company_id", False) or (
                    load_sudo.sale_order_id.company_id if load_sudo.sale_order_id else False
                )
                if not load_company:
                    raise ValidationError("An exact rate-memory match requires the canonical load's company.")
                if load_company != record.company_id:
                    raise ValidationError("Canonical load must belong to the reconciliation company.")
            elif disposition in UNOWNED_RECONCILIATION_DISPOSITIONS:
                if record.company_id or record.canonical_load_id:
                    raise ValidationError(
                        "A non-exact rate-memory reconciliation has no company and no canonical load (ADR-129)."
                    )
            else:
                raise ValidationError(f"Rate-memory disposition {disposition!r} has no ADR-129 ownership rule.")

    def write(self, vals):
        raise UserError("Rate-memory reconciliation evidence is immutable.")

    def unlink(self):
        raise UserError("Rate-memory reconciliation evidence cannot be deleted.")


def _load_company(load):
    """The load's own source company. Never the acting user's company."""
    if not load:
        return False
    return getattr(load, "company_id", False) or (load.sale_order_id.company_id if load.sale_order_id else False)


def _require_freight_evidence_authority(env, load, *, allow_unproven_company_audit=False):
    """Validate actor and source access before narrowly elevating immutable writes.

    Authoritative evidence takes the company of its source load. A load without a
    proven company cannot produce rates, estimates, calibration or actual-event
    evidence. Only a workflow state audit of such a legacy load may fall back to
    the acting company, and that event says so in its facts.
    """
    if not load:
        raise AccessError("Immutable freight evidence requires a source load.")
    company = _load_company(load)
    if not company:
        if not allow_unproven_company_audit:
            raise UserError(
                f"Load {load.display_name} has no proven company. "
                "Freight evidence takes the load's own company, never the user's."
            )
        company = env.company
    if company not in env.companies:
        raise AccessError("Freight evidence cannot be created outside an allowed company.")
    # The elevated create below is limited to immutable evidence rows. Source
    # access is always checked first so sudo never becomes a cross-company or
    # cross-role authorization bypass.
    load.check_access_rights("read")
    load.check_access_rule("read")
    if env.uid != SUPERUSER_ID and not env.user.has_group("plasticos_security_base.group_logistics"):
        raise AccessError("Only Logistics users may create immutable freight evidence.")
    return company


def create_freight_evidence_rows(env, model_name, pairs, *, unproven_company_audit=()):
    """Create one command's evidence rows after checking every source load.

    Evidence models are intentionally read-only in ACLs. Each pair is checked
    before the single elevated create that preserves append-only evidence.
    ``unproven_company_audit`` names the pair indexes that are workflow audit
    events allowed to fall back for a load with no proven company.
    """
    prepared = []
    for index, (load, values) in enumerate(pairs):
        company = _require_freight_evidence_authority(
            env, load, allow_unproven_company_audit=index in unproven_company_audit
        )
        prepared.append({**values, "company_id": company.id})
    if not prepared:
        return env[model_name]
    return env[model_name].sudo().create(prepared)  # sudo: evidence ACL is read-only; caller checked above


def create_freight_evidence(env, model_name, values, *, load):
    """Create exactly one validated immutable evidence row with explained elevation.

    Evidence models are intentionally read-only in ACLs. The helper verifies the
    acting user, source-load rule, and allowed company before the narrow sudo
    create required to preserve append-only evidence semantics.
    """
    return create_freight_evidence_rows(env, model_name, [(load, values)])


def _freight_event_values(*, event_type, outcome_code, load=None, facts=None, unknowns=None, correlation_id=None):
    return {
        "load_id": load.id if load else False,
        "transaction_id": load.transaction_id.id if load and load.transaction_id else False,
        "event_type": event_type,
        "outcome_code": outcome_code,
        "correlation_id": correlation_id or False,
        "facts": facts or {},
        "unknowns": unknowns or [],
    }


def record_freight_events(env, events):
    """Persist one command's freight events in a single evidence create."""
    pairs = []
    unproven = set()
    for index, event in enumerate(events):
        load = event.get("load")
        facts = dict(event.get("facts") or {})
        unknowns = list(event.get("unknowns") or [])
        if event["event_type"] in _UNPROVEN_COMPANY_AUDIT_EVENTS and load and not _load_company(load):
            unproven.add(index)
            facts["company_basis"] = "acting_company_unproven_load"
            unknowns.append("load_company_unproven")
        pairs.append(
            (
                load,
                _freight_event_values(
                    event_type=event["event_type"],
                    outcome_code=event["outcome_code"],
                    load=load,
                    facts=facts,
                    unknowns=unknowns,
                    correlation_id=event.get("correlation_id"),
                ),
            )
        )
    return create_freight_evidence_rows(env, "plasticos.freight.event", pairs, unproven_company_audit=unproven)


def record_freight_event(env, *, event_type, outcome_code, load=None, facts=None, unknowns=None, correlation_id=None):
    """Persist structured, correlated event evidence without raw carrier content."""
    return record_freight_events(
        env,
        [
            {
                "event_type": event_type,
                "outcome_code": outcome_code,
                "load": load,
                "facts": facts,
                "unknowns": unknowns,
                "correlation_id": correlation_id,
            }
        ],
    )
