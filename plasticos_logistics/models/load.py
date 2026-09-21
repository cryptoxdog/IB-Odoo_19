import hashlib
import logging
from datetime import timedelta

from odoo import SUPERUSER_ID, api, fields, models
from odoo.addons.plasticos_logistics.services.state_machine import VALID_TRANSITIONS, new_correlation_id
from odoo.exceptions import AccessError, UserError, ValidationError

RES_PARTNER = "res.partner"
PLASTICOS_TRANSACTION = "plasticos.transaction"
PLASTICOS_LOAD = "plasticos.load"
_logger = logging.getLogger(__name__)

_FREIGHT_INTERNAL_WRITE = "plasticos_logistics_internal_freight_write"
_FREIGHT_INTERNAL_WRITE_TOKEN = object()
_FREIGHT_PROVENANCE_FIELDS = {
    "freight_context_fingerprint",
    "freight_context_version",
    "rate_confirmed_at",
    "rate_auto_reused",
    "rate_resolution_method",
    "sal_source_load_id",
    "sal_evaluated_at",
    "sal_decision",
    "sal_miss_reason",
    "sal_execution_failed",
    "sal_execution_failure_reason",
    "selected_freight_quote_id",
    "actual_freight_recorded_at",
}
_FREIGHT_RATE_INPUT_FIELDS = {"carrier_id", "rate_amount", "rate_currency_id"}
_FREIGHT_ACTUAL_INPUT_FIELDS = {"actual_freight_cost", "actual_freight_currency_id"}


class PlasticosLoad(models.Model):
    _name = "plasticos.load"
    _description = "Plasticos Logistics Load"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        required=True, default=lambda self: self.env["ir.sequence"].next_by_code(PLASTICOS_LOAD) or "New"
    )
    sale_order_id = fields.Many2one("sale.order", ondelete="restrict")
    company_id = fields.Many2one(
        "res.company", related="sale_order_id.company_id", store=True, readonly=True, index=True, ondelete="restrict"
    )
    carrier_id = fields.Many2one(RES_PARTNER, string="Carrier", ondelete="restrict")
    rate_amount = fields.Float(string="Rate Amount")
    rate_confirmed_at = fields.Datetime()
    rate_auto_reused = fields.Boolean(default=False)
    rate_currency_id = fields.Many2one(
        "res.currency",
        string="Rate Currency",
        default=lambda self: self.env.company.currency_id,
        ondelete="restrict",
        help="Explicit currency for booked freight; required before a rate can qualify for SAL reuse.",
    )
    rate_resolution_method = fields.Selection(
        [("manual", "Manual"), ("sal", "Same As Last"), ("live_quote", "Live Quote")],
        string="Rate Resolution Method",
        readonly=True,
        tracking=True,
    )
    actual_freight_cost = fields.Monetary(currency_field="actual_freight_currency_id", tracking=True)
    actual_freight_currency_id = fields.Many2one(
        "res.currency", string="Actual Freight Currency", ondelete="restrict", tracking=True
    )
    actual_freight_recorded_at = fields.Datetime(readonly=True, tracking=True)
    freight_context_fingerprint = fields.Char(string="Freight Context Fingerprint", index=True, readonly=True)
    freight_context_version = fields.Char(string="Freight Context Version", readonly=True)
    sal_source_load_id = fields.Many2one(
        "plasticos.load",
        string="SAL Source Load",
        readonly=True,
        ondelete="restrict",
    )
    sal_evaluated_at = fields.Datetime(string="SAL Evaluated At", readonly=True)
    sal_decision = fields.Selection(
        [
            ("not_evaluated", "Not Evaluated"),
            ("hit", "Hit"),
            ("miss", "Miss"),
            ("not_eligible", "Not Eligible"),
        ],
        string="SAL Decision",
        default="not_evaluated",
        readonly=True,
    )
    sal_miss_reason = fields.Selection(
        [
            ("not_ready_confirmed", "Load Not Ready Confirmed"),
            ("missing_lane_identity", "Missing Lane or Repeat Stream"),
            ("already_rate_confirmed", "Rate Already Confirmed"),
            ("no_prior_movement", "No Prior Movement"),
            ("prior_movement_too_old", "Prior Movement Too Old"),
            ("prior_rate_missing", "Prior Rate or Currency Missing"),
            ("prior_carrier_inactive", "Prior Carrier Inactive"),
            ("prior_record_ambiguous", "Prior Record Ambiguous"),
        ],
        string="SAL Miss Reason",
        readonly=True,
    )
    sal_execution_failed = fields.Boolean(readonly=True, default=False)
    sal_execution_failure_reason = fields.Text(readonly=True)
    selected_freight_quote_id = fields.Many2one(
        "plasticos.freight.quote", string="Selected Freight Quote", readonly=True, ondelete="restrict"
    )
    freight_quote_request_ids = fields.One2many(
        "plasticos.freight.quote.request", "load_id", string="Freight Quote Requests"
    )
    freight_quote_request_count = fields.Integer(compute="_compute_freight_evidence_counts")
    freight_estimate_count = fields.Integer(compute="_compute_freight_evidence_counts")

    ready_confirmed_by = fields.Char()
    ready_confirmed_at = fields.Datetime()

    pickup_datetime = fields.Datetime(string="Pickup Date/Time")
    delivery_datetime = fields.Datetime(string="Delivery Date/Time")

    bol_pickup_attached = fields.Boolean(default=False)
    bol_delivery_attached = fields.Boolean(default=False)

    entered_state_at = fields.Datetime(default=fields.Datetime.now, index=True)
    sla_breached = fields.Boolean(default=False, index=True)
    dispatched_at = fields.Datetime()
    delivered_at = fields.Datetime()
    cycle_time_hours = fields.Float(compute="_compute_cycle_time", store=True, index=True)

    # ── Reverse Link to Transaction (for UX) ──────────────────────────
    # Note: This is the inverse of plasticos.transaction.load_id
    # Stored to enable dependency triggers (e.g., delivery_term_overridden)
    transaction_id = fields.Many2one(
        PLASTICOS_TRANSACTION,
        string="Transaction",
        compute="_compute_transaction_id",
        store=True,
        index=True,
        help="Transaction linked to this load (reverse lookup).",
        ondelete="cascade",
    )

    # ── Delivery Term (editable with override tracking) ───────────────
    delivery_term = fields.Selection(
        [
            ("fcfs", "First Come First Served"),
            ("appointment", "Appointment Required"),
        ],
        string="Delivery Term",
        default=lambda self: self._get_default_delivery_term(),
        tracking=True,
        help="Defaults from transaction. Editable by logistics in rare cases (requires reason).",
    )
    delivery_term_override_reason = fields.Text(
        string="Override Reason",
        help="Required when delivery_term differs from transaction. Explain why the change was necessary.",
    )
    delivery_term_overridden = fields.Boolean(
        string="Delivery Term Overridden",
        compute="_compute_delivery_term_overridden",
        store=True,
        help="True if delivery_term differs from linked transaction.",
    )

    # ── Dispatch Tracking ─────────────────────────────────────────────
    dispatch_sent = fields.Datetime(
        string="Dispatch Sent",
        tracking=True,
        help="When dispatch notification was sent to carrier.",
    )
    dispatch_acknowledged = fields.Datetime(
        string="Dispatch Acknowledged",
        tracking=True,
        help="When carrier acknowledged the dispatch.",
    )
    dispatch_method = fields.Selection(
        [
            ("email", "Email"),
            ("sms", "SMS"),
            ("api", "API"),
            ("email_sms", "Email + SMS"),
        ],
        string="Dispatch Method",
        default="email",
        help="Method used to send dispatch notification.",
    )

    # ── Pickup Location Fields ──────────────────────────────────────
    pickup_partner_id = fields.Many2one(
        RES_PARTNER, string="Pickup Location", help="Shipper/pickup location for BOL", ondelete="restrict"
    )
    pickup_contact_name = fields.Char(string="Pickup Contact")
    pickup_contact_phone = fields.Char(string="Pickup Phone")
    pickup_contact_mobile = fields.Char(string="Pickup Mobile")
    pickup_reference = fields.Char(string="Pickup Reference/PO#")
    pickup_hours = fields.Char(
        string="Pickup Hours",
        default=lambda self: (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("plasticos.load.default_pickup_hours", "M-F: 9:00 AM - 3:00 PM")
        ),
    )
    pickup_instructions = fields.Text(string="Pickup Instructions")

    # ── Delivery Location Fields ────────────────────────────────────
    delivery_partner_id = fields.Many2one(
        RES_PARTNER, string="Delivery Location", help="Consignee/delivery location for BOL", ondelete="restrict"
    )
    delivery_contact_name = fields.Char(string="Delivery Contact")
    delivery_contact_phone = fields.Char(string="Delivery Phone")
    delivery_contact_mobile = fields.Char(string="Delivery Mobile")
    delivery_reference = fields.Char(string="Delivery Reference/PO#")
    delivery_hours = fields.Char(
        string="Delivery Hours",
        default=lambda self: (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("plasticos.load.default_delivery_hours", "M-F: 9:00 AM - 3:00 PM")
        ),
    )
    delivery_instructions = fields.Text(string="Delivery Instructions")

    # ── Carrier/Transport Fields ────────────────────────────────────
    carrier_contact_name = fields.Char(string="Carrier Contact")
    carrier_contact_phone = fields.Char(string="Carrier Phone")
    trailer_number = fields.Char(string="Trailer Number")
    seal_number = fields.Char(string="Seal Number")

    # ── Cargo/Product Fields ────────────────────────────────────────
    product_description = fields.Char(string="Product Description")
    quantity = fields.Float(string="Quantity", default=1.0)
    quantity_uom = fields.Char(string="Unit", default="Each")
    reference_weight = fields.Float(string="Reference Weight (lbs)")

    # ── Document Control ────────────────────────────────────────────
    double_blind = fields.Boolean(string="Double Blind", default=True)
    straps_bars_needed = fields.Boolean(string="Straps/Bars Needed", default=True)
    notes = fields.Text(string="Notes/Comments")

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("awaiting_ready", "Awaiting Ready"),
            ("ready_confirmed", "Ready Confirmed"),
            ("rate_confirmed", "Rate Confirmed"),
            ("scheduled", "Scheduled"),
            ("dispatched", "Dispatched"),
            ("picked_up", "Picked Up"),
            ("delivered", "Delivered"),
            ("closed", "Closed"),
            ("exception", "Exception"),
        ],
        default="draft",
        tracking=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Create load and auto-link to transaction via sale_order_id.

        Auto-link only happens if the transaction has both supplier and buyer set.
        This enforces the workflow requirement that loads cannot be assigned until
        the transaction has complete partner information.

        Freight state and provenance are workflow-owned at creation exactly as in
        ``write()``: a caller cannot create a load already past Draft or carrying
        freight provenance, which would bypass operator checks, transitions and
        audit events.
        """
        internal_freight_write = self.env.context.get(_FREIGHT_INTERNAL_WRITE) is _FREIGHT_INTERNAL_WRITE_TOKEN
        if not internal_freight_write:
            for vals in vals_list:
                if vals.get("state") not in (None, False, "draft"):
                    raise UserError(
                        "Loads are created in Draft; state may only change through the validated transition workflow."
                    )
                protected = _FREIGHT_PROVENANCE_FIELDS.intersection(vals)
                if protected:
                    raise UserError(
                        "Freight provenance may only be set through a validated freight command: "
                        f"{', '.join(sorted(protected))}"
                    )
        records = super().create(vals_list)
        for rec in records:
            if rec.sale_order_id:
                tx = self.env[PLASTICOS_TRANSACTION].search([("sale_order_id", "=", rec.sale_order_id.id)], limit=1)
                if tx and not tx.load_id and tx.supplier_id and tx.buyer_id:
                    tx.load_id = rec.id
        return records

    def _compute_freight_evidence_counts(self):
        request_model = self.env["plasticos.freight.quote.request"]
        estimate_model = self.env["plasticos.freight.estimate"]
        for rec in self:
            rec.freight_quote_request_count = request_model.search_count([("load_id", "=", rec.id)])
            rec.freight_estimate_count = estimate_model.search_count(
                [("source_model", "=", PLASTICOS_LOAD), ("source_record_id", "=", rec.id)]
            )

    def _require_freight_operator(self):
        """Require the Logistics business role for freight command boundaries."""
        if self.env.uid == SUPERUSER_ID:
            return
        if not self.env.user.has_group("plasticos_security_base.group_logistics"):
            raise AccessError("Only Logistics users may execute freight commands.")
        self.check_access_rights("write")
        self.check_access_rule("write")

    def _freight_write(self, values):
        """Use the narrow internal capability after a canonical freight command validates."""
        return self.with_context(**{_FREIGHT_INTERNAL_WRITE: _FREIGHT_INTERNAL_WRITE_TOKEN}).write(values)

    def write(self, vals):
        """Guard against unauthorized modifications after dispatch.

        After dispatch, only specific fields can be modified:
        - BOL attachments (pickup/delivery confirmation)
        - State transitions (via action methods)
        - Timestamps (entered_state_at, dispatched_at, delivered_at)
        - Computed fields (cycle_time_hours)
        - Cron-managed fields (sla_breached)
        - Chatter fields (message_ids, message_follower_ids)
        """
        freight_fields = set(vals)
        internal_freight_write = self.env.context.get(_FREIGHT_INTERNAL_WRITE) is _FREIGHT_INTERNAL_WRITE_TOKEN
        if not internal_freight_write:
            if "state" in freight_fields:
                raise UserError("Load state may only change through the validated transition workflow.")
            protected = _FREIGHT_PROVENANCE_FIELDS.intersection(freight_fields)
            if protected:
                raise UserError(
                    "Freight provenance may only change through a validated freight command: "
                    f"{', '.join(sorted(protected))}"
                )
            if _FREIGHT_RATE_INPUT_FIELDS.intersection(freight_fields) or _FREIGHT_ACTUAL_INPUT_FIELDS.intersection(
                freight_fields
            ):
                self._require_freight_operator()
            for rec in self:
                if _FREIGHT_RATE_INPUT_FIELDS.intersection(freight_fields) and rec.rate_confirmed_at:
                    raise UserError(
                        "Confirmed freight rate inputs are immutable; create a new freight resolution instead."
                    )
                if _FREIGHT_ACTUAL_INPUT_FIELDS.intersection(freight_fields) and rec.actual_freight_recorded_at:
                    raise UserError(
                        "Recorded actual freight is immutable; use the attributed calibration correction workflow."
                    )

        for rec in self:
            if rec.state in ["dispatched", "picked_up", "delivered", "closed"]:
                allowed = {
                    "bol_pickup_attached",
                    "bol_delivery_attached",
                    "state",
                    "entered_state_at",
                    "dispatched_at",
                    "delivered_at",
                    "cycle_time_hours",
                    "sla_breached",
                    "message_ids",
                    "message_follower_ids",
                    # Dispatch tracking fields (added for logistics enhancement)
                    "dispatch_sent",
                    "dispatch_acknowledged",
                    "dispatch_method",
                    # Delivery term override (rare but allowed)
                    "delivery_term",
                    "delivery_term_override_reason",
                    "delivery_term_overridden",
                }
                if internal_freight_write:
                    allowed.update(_FREIGHT_ACTUAL_INPUT_FIELDS | {"actual_freight_recorded_at"})
                blocked = set(vals.keys()) - allowed
                if blocked:
                    raise UserError(f"Load locked after dispatch. Cannot modify: {', '.join(sorted(blocked))}")

        res = super().write(vals)

        if "state" in vals and vals["state"] == "closed":
            for rec in self:
                tx = self.env[PLASTICOS_TRANSACTION].search([("load_id", "=", rec.id)], limit=1)
                if tx:
                    tx.message_post(body="Logistics closed.")

        return res

    @api.depends("dispatched_at", "delivered_at")
    def _compute_cycle_time(self):
        for rec in self:
            if rec.dispatched_at and rec.delivered_at:
                delta = (rec.delivered_at - rec.dispatched_at).total_seconds() / 3600
                rec.cycle_time_hours = delta
            else:
                rec.cycle_time_hours = 0

    @api.depends_context("force_recompute_transaction_id")
    def _compute_transaction_id(self):
        """Reverse lookup: find transaction that references this load.

        Batched query to avoid N+1 problem on list views.
        Stored for searchability and dependency triggers.
        Recomputation is triggered by transaction_inherit.py when load_id changes.
        """
        txs = self.env[PLASTICOS_TRANSACTION].search([("load_id", "in", self.ids)])
        tx_map = {tx.load_id.id: tx.id for tx in txs}
        for rec in self:
            rec.transaction_id = tx_map.get(rec.id, False)

    def _get_default_delivery_term(self):
        """Get delivery term from linked transaction if available."""
        tx_id = self.env.context.get("default_transaction_id")
        if tx_id:
            tx = self.env[PLASTICOS_TRANSACTION].browse(tx_id)
            if tx.delivery_term:
                return tx.delivery_term
        return "appointment"

    @api.depends("delivery_term", "transaction_id.delivery_term")
    def _compute_delivery_term_overridden(self):
        """Check if delivery_term differs from transaction."""
        for rec in self:
            # Use reverse lookup to get transaction
            tx = self.env[PLASTICOS_TRANSACTION].search([("load_id", "=", rec.id)], limit=1)
            if tx and tx.delivery_term:
                rec.delivery_term_overridden = rec.delivery_term != tx.delivery_term
            else:
                rec.delivery_term_overridden = False

    @api.constrains("delivery_term", "delivery_term_override_reason")
    def _check_override_reason_required(self):
        """Require reason when delivery_term is overridden."""
        for rec in self:
            if rec.delivery_term_overridden and not rec.delivery_term_override_reason:
                raise ValidationError(
                    "Override reason is required when changing delivery term from transaction default."
                )

    def action_confirm_ready(self):
        """Confirm load is ready for pickup. Captures authenticated user."""
        for rec in self:
            rec._require_freight_operator()
            rec.ready_confirmed_by = self.env.user.name
            rec.ready_confirmed_at = fields.Datetime.now()
            rec._transition("ready_confirmed")

    def action_create_freight_quote_request(self):
        """Create one manual-only RFQ episode after a current SAL miss.

        This persists a recipient/evidence workflow but deliberately performs no
        outbound delivery until an approved channel and RFQ terms exist.
        """
        from odoo.addons.plasticos_logistics.services.freight_context import (
            FREIGHT_CONTEXT_VERSION,
            build_freight_context,
        )

        request_model = self.env["plasticos.freight.quote.request"]
        for rec in self:
            rec._require_freight_operator()
            correlation_id = new_correlation_id()
            if rec.state != "ready_confirmed" or rec.sal_decision not in ("miss", "not_eligible"):
                raise UserError(
                    "A current SAL miss or not-eligible decision is required before creating an RFQ episode."
                )
            context = build_freight_context(rec)
            if not context:
                raise UserError("A complete freight context is required before creating an RFQ episode.")
            if rec.freight_context_fingerprint != context.fingerprint:
                raise UserError("Freight context changed. Re-run freight resolution before creating an RFQ episode.")
            rec.env.cr.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [f"plasticos_logistics.rfq:{rec.id}"])
            key = hashlib.sha256(f"rfq:{rec.id}:{context.fingerprint}".encode()).hexdigest()
            existing = request_model.search([("idempotency_key", "=", key)], limit=1)
            if existing:
                continue
            company = rec.sale_order_id.company_id if rec.sale_order_id else False
            if not company or not rec.transaction_id:
                raise UserError("Load company and transaction are required before creating an RFQ episode.")
            request = request_model.create(
                {
                    "company_id": company.id,
                    "context_fingerprint": context.fingerprint,
                    "fingerprint_version": FREIGHT_CONTEXT_VERSION,
                    "idempotency_key": key,
                    "load_id": rec.id,
                    "origin_partner_id": rec.pickup_partner_id.id,
                    "destination_partner_id": rec.delivery_partner_id.id,
                    "sal_decision": rec.sal_decision,
                    "sal_miss_reason": rec.sal_miss_reason or "not_eligible",
                    "transaction_id": rec.transaction_id.id,
                }
            )
            rec.message_post(
                body=f"Manual-only freight RFQ episode {request.name} created; no outbound carrier send was performed."
            )
            from odoo.addons.plasticos_logistics.models.freight_governance import record_freight_event

            record_freight_event(
                rec.env,
                event_type="rfq_request_created",
                outcome_code="manual_only",
                load=rec,
                facts={"request_id": request.id},
                unknowns=["recipient_policy_unapproved", "outbound_delivery_unavailable"],
                correlation_id=correlation_id,
            )
        return True

    def action_request_freight_estimate(self):
        """Persist a nonbinding local Haversine-curve estimate from canonical evidence."""
        from odoo.addons.plasticos_logistics.services.freight_context import (
            FREIGHT_CONTEXT_VERSION,
            build_freight_context,
        )
        from odoo.addons.plasticos_logistics.services.freight_estimation import (
            ESTIMATOR_MODEL_VERSION,
            ESTIMATOR_POLICY_VERSION,
            estimate_haversine_curve,
        )
        from odoo.addons.plasticos_logistics.services.freight_geometry import FreightCoordinateError
        from odoo.addons.plasticos_logistics.services.freight_history import (
            bounded_evidence_payload,
            local_estimation_evidence,
            recent_comparable_executed_evidence,
            recent_executed_lane_evidence,
        )

        estimate_model = self.env["plasticos.freight.estimate"]
        for rec in self:
            rec._require_freight_operator()
            correlation_id = new_correlation_id()
            rec.env.cr.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [f"plasticos_logistics.estimate:{rec.id}"])
            rec.invalidate_recordset()
            context = build_freight_context(rec)
            if not context:
                raise UserError("A complete freight context is required before an estimate can be requested.")
            currency = rec.rate_currency_id
            if not currency:
                raise UserError("An explicit freight currency is required before an estimate can be requested.")
            if not (
                getattr(rec, "company_id", False) or (rec.sale_order_id.company_id if rec.sale_order_id else False)
            ):
                raise UserError("Load company is required before an estimate can be recorded.")
            exact_history = recent_executed_lane_evidence(rec.env, rec)
            exact_ids = exact_history.ids
            comparable_history = recent_comparable_executed_evidence(rec.env, rec).filtered(
                lambda candidate, exact_ids=exact_ids: candidate.id not in exact_ids
            )
            history_records = exact_history + comparable_history
            try:
                proposal = estimate_haversine_curve(
                    origin_latitude=rec.pickup_partner_id.partner_latitude,
                    origin_longitude=rec.pickup_partner_id.partner_longitude,
                    destination_latitude=rec.delivery_partner_id.partner_latitude,
                    destination_longitude=rec.delivery_partner_id.partner_longitude,
                    currency_id=currency.id,
                    evidence=local_estimation_evidence(history_records),
                )
            except FreightCoordinateError as exc:
                proposal = None
                failure_code = f"coordinate_evidence_gap:{exc}"
            history_count = len(history_records)
            if proposal:
                status = proposal.status
                failure_code = proposal.failure_code
                geometry_status = "available"
                request_fingerprint = proposal.request_fingerprint
                evidence_summary = {
                    **proposal.evidence_summary,
                    "executed_evidence": bounded_evidence_payload(history_records),
                }
                reasoning_summary = proposal.reasoning_summary
            else:
                status = "insufficient_evidence"
                geometry_status = "missing_or_invalid"
                request_fingerprint = hashlib.sha256(
                    f"estimate:{context.fingerprint}:{history_count}:{failure_code}".encode()
                ).hexdigest()
                evidence_summary = {
                    "estimator": ESTIMATOR_MODEL_VERSION,
                    "candidate_evidence_count": history_count,
                    "coordinate_quality": "missing_or_invalid",
                    "exact_lane_executed_count": None,
                    "executed_evidence": bounded_evidence_payload(history_records),
                }
                reasoning_summary = {"formula": "haversine", "reason": failure_code}
            existing = estimate_model.search(
                [
                    ("source_model", "=", PLASTICOS_LOAD),
                    ("source_record_id", "=", rec.id),
                    ("context_fingerprint", "=", context.fingerprint),
                    ("request_fingerprint", "=", request_fingerprint),
                ],
                limit=1,
            )
            if existing:
                continue
            from odoo.addons.plasticos_logistics.models.freight_governance import create_freight_evidence

            estimate = create_freight_evidence(
                rec.env,
                "plasticos.freight.estimate",
                {
                    "context_fingerprint": context.fingerprint,
                    "request_fingerprint": request_fingerprint,
                    "fingerprint_version": FREIGHT_CONTEXT_VERSION,
                    "source_model": PLASTICOS_LOAD,
                    "source_record_id": rec.id,
                    "origin_partner_id": rec.pickup_partner_id.id,
                    "destination_partner_id": rec.delivery_partner_id.id,
                    "expected_weight_lbs": rec.reference_weight,
                    "haversine_miles": proposal.haversine_miles if proposal else False,
                    "geometry_status": geometry_status,
                    "estimate_floor": proposal.estimate_floor if proposal else False,
                    "estimate_target": proposal.estimate_target if proposal else False,
                    "estimate_ceiling": proposal.estimate_ceiling if proposal else False,
                    "pricing_assumption": proposal.pricing_assumption if proposal else False,
                    "currency_id": proposal.currency_id if proposal else False,
                    "confidence": proposal.confidence if proposal else False,
                    "method": proposal.method if proposal else False,
                    "model_version": ESTIMATOR_MODEL_VERSION,
                    "policy_version": ESTIMATOR_POLICY_VERSION,
                    "evidence_summary": evidence_summary,
                    "reasoning_summary": reasoning_summary,
                    "failure_code": failure_code,
                    "status": status,
                },
                load=rec,
            )
            rec.message_post(
                body=(
                    f"Freight estimate {estimate.name} recorded as {status} using the local Haversine-curve policy. "
                    "It is nonbinding and does not assign a carrier or confirm a rate."
                )
            )
            from odoo.addons.plasticos_logistics.models.freight_governance import record_freight_event

            record_freight_event(
                rec.env,
                event_type="freight_estimate_persisted" if status == "succeeded" else "freight_estimate_rejected",
                outcome_code=failure_code or "local_haversine_curve",
                load=rec,
                facts={
                    "estimate_id": estimate.id,
                    "exact_lane_evidence_count": (
                        proposal.evidence_summary["exact_lane_executed_count"] if proposal else None
                    ),
                    "similar_lane_evidence_count": (
                        proposal.evidence_summary["similar_lane_executed_count"] if proposal else None
                    ),
                    "candidate_evidence_count": history_count,
                },
                unknowns=[] if status == "succeeded" else [failure_code],
                correlation_id=correlation_id,
            )
        return True

    def action_view_freight_quote_requests(self):
        action_record = self.env.ref("plasticos_logistics.action_freight_quote_request", raise_if_not_found=False)
        if not action_record:
            raise UserError("Freight quote request action is unavailable; upgrade plasticos_logistics.")
        action = action_record.read()[0]
        action["domain"] = [("load_id", "in", self.ids)]
        action["context"] = {"default_load_id": self.id if len(self) == 1 else False}
        return action

    def action_record_actual_freight_cost(self):
        """Persist a non-mutating calibration observation from a verified actual cost."""
        from odoo.addons.plasticos_logistics.models.freight_governance import record_freight_event
        from odoo.addons.plasticos_logistics.services.freight_context import build_freight_context

        calibration_model = self.env["plasticos.freight.calibration.observation"]
        estimate_model = self.env["plasticos.freight.estimate"]
        for rec in self:
            rec._require_freight_operator()
            correlation_id = new_correlation_id()
            rec.env.cr.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))", [f"plasticos_logistics.actual-cost:{rec.id}"]
            )
            rec.invalidate_recordset()
            context = build_freight_context(rec)
            if not context or rec.actual_freight_cost is None or rec.actual_freight_cost < 0:
                raise UserError("A current freight context and non-negative actual freight cost are required.")
            currency = rec.actual_freight_currency_id or rec.rate_currency_id
            if not currency:
                raise UserError("Actual freight currency is required.")
            existing = calibration_model.search([("load_id", "=", rec.id)], limit=1)
            if existing:
                raise UserError("Actual freight calibration evidence already exists for this load.")
            estimate = estimate_model.search(
                [
                    ("source_model", "=", PLASTICOS_LOAD),
                    ("source_record_id", "=", rec.id),
                    ("context_fingerprint", "=", context.fingerprint),
                    ("status", "=", "succeeded"),
                    ("currency_id", "=", currency.id),
                ],
                order="generated_at desc, id desc",
                limit=1,
            )
            from odoo.addons.plasticos_logistics.models.freight_governance import create_freight_evidence

            create_freight_evidence(
                rec.env,
                "plasticos.freight.calibration.observation",
                {
                    "load_id": rec.id,
                    "estimate_id": estimate.id if estimate else False,
                    "selected_quote_id": rec.selected_freight_quote_id.id if rec.selected_freight_quote_id else False,
                    "currency_id": currency.id,
                    "estimate_amount": estimate.estimate_target if estimate else False,
                    "booked_rate_amount": rec.rate_amount if rec.rate_currency_id == currency else False,
                    "actual_cost_amount": rec.actual_freight_cost,
                    "estimate_to_actual_variance": (
                        rec.actual_freight_cost - estimate.estimate_target if estimate else False
                    ),
                    "booked_to_actual_variance": (
                        rec.actual_freight_cost - rec.rate_amount if rec.rate_currency_id == currency else False
                    ),
                    "context_fingerprint": context.fingerprint,
                },
                load=rec,
            )
            rec._freight_write({"actual_freight_recorded_at": fields.Datetime.now()})
            record_freight_event(
                rec.env,
                event_type="freight_actual_recorded",
                outcome_code="recorded",
                load=rec,
                facts={"currency_id": currency.id},
                correlation_id=correlation_id,
            )
        return True

    def action_correct_actual_freight_cost(self, actual_cost, currency, reason):
        """Append an attributed calibration correction without reopening prior evidence."""
        from odoo.addons.plasticos_logistics.models.freight_governance import (
            create_freight_evidence,
            record_freight_event,
        )
        from odoo.addons.plasticos_logistics.services.freight_context import build_freight_context

        if actual_cost is None or actual_cost < 0 or not currency or not reason:
            raise ValidationError("Actual-cost corrections require a non-negative amount, currency, and reason.")
        calibration_model = self.env["plasticos.freight.calibration.observation"]
        for rec in self:
            rec._require_freight_operator()
            correlation_id = new_correlation_id()
            rec.env.cr.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))", [f"plasticos_logistics.actual-cost:{rec.id}"]
            )
            rec.invalidate_recordset()
            prior = calibration_model.search([("load_id", "=", rec.id)], order="observed_at desc, id desc", limit=1)
            if not prior:
                raise UserError("Record the initial actual freight cost before creating a correction.")
            context = build_freight_context(rec)
            if not context:
                raise UserError("A current freight context is required before correcting actual freight cost.")
            create_freight_evidence(
                rec.env,
                "plasticos.freight.calibration.observation",
                {
                    "load_id": rec.id,
                    "estimate_id": prior.estimate_id.id if prior.estimate_id else False,
                    "selected_quote_id": rec.selected_freight_quote_id.id if rec.selected_freight_quote_id else False,
                    "currency_id": currency.id,
                    "estimate_amount": prior.estimate_amount if prior.currency_id == currency else False,
                    "booked_rate_amount": rec.rate_amount if rec.rate_currency_id == currency else False,
                    "actual_cost_amount": actual_cost,
                    "estimate_to_actual_variance": (
                        actual_cost - prior.estimate_amount
                        if prior.estimate_id and prior.currency_id == currency
                        else False
                    ),
                    "booked_to_actual_variance": (
                        actual_cost - rec.rate_amount if rec.rate_currency_id == currency else False
                    ),
                    "context_fingerprint": context.fingerprint,
                    "supersedes_observation_id": prior.id,
                    "correction_reason": reason,
                },
                load=rec,
            )
            rec._freight_write(
                {
                    "actual_freight_cost": actual_cost,
                    "actual_freight_currency_id": currency.id,
                    "actual_freight_recorded_at": fields.Datetime.now(),
                }
            )
            record_freight_event(
                rec.env,
                event_type="freight_actual_corrected",
                outcome_code="superseded",
                load=rec,
                facts={"currency_id": currency.id, "supersedes_observation_id": prior.id},
                correlation_id=correlation_id,
            )
        return True

    def action_open_actual_freight_correction_wizard(self):
        self.ensure_one()
        self._require_freight_operator()
        return {
            "type": "ir.actions.act_window",
            "name": "Correct Actual Freight",
            "res_model": "plasticos.freight.actual.correction.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_load_id": self.id,
                "default_actual_cost": self.actual_freight_cost,
                "default_currency_id": self.actual_freight_currency_id.id,
            },
        }

    def action_view_freight_estimates(self):
        action_record = self.env.ref("plasticos_logistics.action_freight_estimate", raise_if_not_found=False)
        if not action_record:
            raise UserError("Freight estimate action is unavailable; upgrade plasticos_logistics.")
        action = action_record.read()[0]
        action["domain"] = [("source_model", "=", PLASTICOS_LOAD), ("source_record_id", "in", self.ids)]
        return action

    def action_confirm_rate(self, rate=None):
        """Confirm a manually supplied rate through the canonical rate path."""
        from odoo.addons.plasticos_logistics.services.freight_context import build_freight_context

        for rec in self:
            rec._require_freight_operator()
            context = build_freight_context(rec)
            if not context:
                raise UserError("A complete freight context is required before confirming a manual rate.")
            rec._confirm_freight_rate(
                rate=rate if rate is not None else rec.rate_amount,
                carrier=rec.carrier_id,
                currency=rec.rate_currency_id,
                resolution_method="manual",
                context_fingerprint=context.fingerprint,
            )

    def _cancel_stale_freight_quote_requests(self, current_fingerprint, correlation_id, reason="context_changed"):
        """Cancel active RFQ episodes that can no longer be used for this load.

        With ``current_fingerprint`` set, only episodes whose freight context
        differs are cancelled (``reason="context_changed"``). With ``None`` every
        active episode is cancelled (used when the load is already rate-confirmed
        and the episodes are orphaned). Called from a freight-resolution
        transaction that succeeds, so the cancellation and its audit event
        persist. Request-level guards only refuse stale requests; they never
        write, because their ``UserError`` rolls back.
        """
        from odoo.addons.plasticos_logistics.models.freight_governance import record_freight_event

        request_model = self.env["plasticos.freight.quote.request"]
        for rec in self:
            domain = [("load_id", "=", rec.id), ("state", "in", ("draft", "sent", "collecting"))]
            if current_fingerprint:
                domain.append(("context_fingerprint", "!=", current_fingerprint))
            stale = request_model.search(domain)
            if not stale:
                continue
            stale._rfq_write(
                {
                    "state": "cancelled",
                    "cancelled_at": fields.Datetime.now(),
                    "cancellation_reason": reason,
                }
            )
            for request in stale:
                record_freight_event(
                    rec.env,
                    event_type="rfq_request_cancelled_context_change",
                    outcome_code=reason,
                    load=rec,
                    facts={
                        "request_id": request.id,
                        "stale_fingerprint": request.context_fingerprint,
                        "current_fingerprint": current_fingerprint,
                    },
                    correlation_id=correlation_id,
                )

    def action_resolve_freight(self):
        """Resolve Same As Last deterministically; never creates an RFQ on a miss.

        The live RFQ workflow is intentionally unavailable until its recipient
        policy and delivery contract are accepted. A miss is persisted as a
        useful operator-visible outcome rather than silently falling back.
        """
        from odoo.addons.plasticos_logistics.services.freight_context import FREIGHT_CONTEXT_VERSION
        from odoo.addons.plasticos_logistics.services.sal_resolver import resolve_sal

        for rec in self:
            rec._require_freight_operator()
            correlation_id = new_correlation_id()
            rec.env.cr.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [f"plasticos_logistics.sal:{rec.id}"])
            rec.invalidate_recordset()
            # After the lock, a concurrent Resolve Freight may already have
            # confirmed this load. Keep that first result — do not reevaluate
            # (resolve_sal would return not_eligible and the miss branch would
            # overwrite SAL provenance while leaving the reused rate in place).
            if rec.rate_confirmed_at or rec.state == "rate_confirmed":
                # A confirmed load cannot be re-resolved, so any RFQ episode still
                # active on it is orphaned. Cancel it here, durably, so the
                # request-level guard's advice ("re-run Resolve Freight") always
                # leads to a persisted outcome whatever the load state.
                rec._cancel_stale_freight_quote_requests(None, correlation_id, reason="load_rate_confirmed")
                continue
            decision = resolve_sal(rec)
            # Persist the cancellation of RFQ episodes whose context no longer
            # matches. This transaction succeeds, so unlike the request-level
            # guard (which must raise) the cancellation is durable.
            rec._cancel_stale_freight_quote_requests(decision.context_fingerprint, correlation_id)
            values = {
                "freight_context_fingerprint": decision.context_fingerprint,
                "freight_context_version": FREIGHT_CONTEXT_VERSION if decision.context_fingerprint else False,
                "sal_decision": decision.decision,
                "sal_evaluated_at": fields.Datetime.now(),
                "sal_miss_reason": decision.reason if decision.decision != "hit" else False,
            }
            if decision.decision == "hit":
                source = self.browse(decision.source_load_id).exists()
                rec._confirm_freight_rate(
                    rate=source.rate_amount,
                    carrier=source.carrier_id,
                    currency=source.rate_currency_id,
                    resolution_method="sal",
                    context_fingerprint=decision.context_fingerprint,
                    sal_source_load=source,
                )
                rec.message_post(
                    body=(
                        f"SAL applied from load {source.name}: reused the current eligible carrier and booked rate. "
                        "No carrier RFQ was created."
                    )
                )
            else:
                rec._freight_write(values)
                rec.message_post(body=f"SAL {decision.decision}: {decision.reason or 'no qualifying history'}.")
                from odoo.addons.plasticos_logistics.models.freight_governance import record_freight_event

                record_freight_event(
                    rec.env,
                    event_type="sal_miss" if decision.decision == "miss" else "sal_not_eligible",
                    outcome_code=decision.reason or decision.decision,
                    load=rec,
                    facts={"context_fingerprint": decision.context_fingerprint},
                    correlation_id=correlation_id,
                )
        return True

    def _confirm_freight_rate(
        self,
        rate,
        carrier,
        currency,
        resolution_method,
        context_fingerprint=None,
        sal_source_load=None,
    ):
        """Single serialized state-machine convergence point for all freight rates."""
        from odoo.addons.plasticos_logistics.services.freight_context import (
            FREIGHT_CONTEXT_VERSION,
            build_freight_context,
        )

        for rec in self:
            rec._require_freight_operator()
            correlation_id = new_correlation_id()
            rec.env.cr.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [f"plasticos_logistics.rate:{rec.id}"])
            rec.invalidate_recordset()
            if rec.state != "ready_confirmed":
                raise UserError("Freight rate confirmation requires a Ready Confirmed load.")
            if resolution_method not in {"manual", "sal", "live_quote"}:
                raise ValidationError("Freight resolution method is not supported.")
            if not rate or rate <= 0:
                raise ValidationError("Confirmed freight rate must be positive.")
            if not carrier or not currency:
                raise ValidationError("Confirmed freight requires an eligible carrier and explicit currency.")
            if not carrier.active or getattr(carrier, "entity_status", None) == "blocked":
                raise ValidationError("Confirmed freight carrier is inactive or blocked.")
            company = getattr(rec, "company_id", False) or (
                rec.sale_order_id.company_id if rec.sale_order_id else False
            )
            carrier_company = getattr(carrier, "company_id", False)
            if carrier_company and company and carrier_company != company:
                raise ValidationError("Confirmed freight carrier belongs to a different company.")
            current_context = build_freight_context(rec)
            if not current_context or not context_fingerprint or current_context.fingerprint != context_fingerprint:
                raise ValidationError("Freight context changed or is incomplete; rate confirmation is blocked.")
            if resolution_method == "sal" and not sal_source_load:
                raise ValidationError("SAL confirmation requires a qualifying source load.")
            values = {
                "carrier_id": carrier.id if carrier else False,
                "freight_context_fingerprint": context_fingerprint,
                "freight_context_version": FREIGHT_CONTEXT_VERSION,
                "rate_amount": rate,
                "rate_auto_reused": resolution_method == "sal",
                "rate_confirmed_at": fields.Datetime.now(),
                "rate_currency_id": currency.id if currency else False,
                "rate_resolution_method": resolution_method,
                "sal_decision": "hit" if resolution_method == "sal" else rec.sal_decision,
                "sal_evaluated_at": fields.Datetime.now() if resolution_method == "sal" else rec.sal_evaluated_at,
                "sal_miss_reason": False if resolution_method == "sal" else rec.sal_miss_reason,
                "sal_source_load_id": sal_source_load.id if sal_source_load else False,
            }
            rec._freight_write(values)
            rec._transition("rate_confirmed", correlation_id=correlation_id)
            from odoo.addons.plasticos_logistics.models.freight_governance import record_freight_event

            record_freight_event(
                rec.env,
                event_type="freight_rate_confirmed",
                outcome_code=resolution_method,
                load=rec,
                facts={
                    "carrier_id": carrier.id,
                    "currency_id": currency.id,
                    "sal_source_load_id": sal_source_load.id if sal_source_load else None,
                },
                correlation_id=correlation_id,
            )

    def action_schedule(self, pickup_dt, delivery_dt):
        for rec in self:
            rec._require_freight_operator()
            rec._ensure_sal_context_current()
            rec.pickup_datetime = pickup_dt
            rec.delivery_datetime = delivery_dt
            rec._transition("scheduled")

    def action_dispatch(self):
        """Dispatch load to carrier. Validates required fields before dispatch."""
        for rec in self:
            rec._require_freight_operator()
            rec._ensure_sal_context_current()
            if rec.state != "scheduled":
                raise UserError(f"Load {rec.name} must be in Scheduled state before dispatch.")
            if not rec.carrier_id:
                raise UserError(f"Load {rec.name}: Carrier is required before dispatch.")
            if not rec.pickup_partner_id:
                raise UserError(f"Load {rec.name}: Pickup location is required before dispatch.")
            if not rec.delivery_partner_id:
                raise UserError(f"Load {rec.name}: Delivery location is required before dispatch.")
            if not rec.pickup_datetime:
                raise UserError(f"Load {rec.name}: Pickup date/time is required before dispatch.")
            rec._transition("dispatched")

    def _ensure_sal_context_current(self):
        """Fail closed when any confirmed freight lane has materially changed."""
        from odoo.addons.plasticos_logistics.services.freight_context import build_freight_context

        for rec in self:
            if not rec.rate_resolution_method or not rec.freight_context_fingerprint:
                continue
            current_context = build_freight_context(rec)
            if not current_context or current_context.fingerprint != rec.freight_context_fingerprint:
                raise UserError(
                    "Freight context changed after rate confirmation. Scheduling and dispatch are blocked until an "
                    "approved logistics recovery action resolves the exception."
                )

    def action_close(self):
        for rec in self:
            rec._require_freight_operator()
            if not rec.bol_pickup_attached or not rec.bol_delivery_attached:
                raise UserError("BOL documents required.")
            rec._transition("closed")

    def _transition(self, new_state, *, correlation_id=None):
        """Transition load to new state with validation.

        Enforces forward-only state machine defined in VALID_TRANSITIONS.
        """
        for rec in self:
            allowed = VALID_TRANSITIONS.get(rec.state, [])
            if new_state not in allowed:
                raise UserError(
                    f"Cannot move load '{rec.name}' from '{rec.state}' to '{new_state}'. "
                    f"Allowed: {allowed or ['none — terminal state']}."
                )

            correlation_id = correlation_id or new_correlation_id()
            old = rec.state
            vals = {"state": new_state, "entered_state_at": fields.Datetime.now()}
            if new_state == "dispatched":
                vals["dispatched_at"] = fields.Datetime.now()
            if new_state == "delivered":
                vals["delivered_at"] = fields.Datetime.now()
            rec._freight_write(vals)
            from odoo.addons.plasticos_logistics.models.freight_governance import record_freight_event

            record_freight_event(
                rec.env,
                event_type="freight_state_transition",
                outcome_code=new_state,
                load=rec,
                facts={"from_state": old, "to_state": new_state},
                correlation_id=correlation_id,
            )
            _logger.info("Load %s state transition: %s -> %s (correlation: %s)", rec.id, old, new_state, correlation_id)

    def _store_rate_memory(self):
        """Deprecated compatibility hook; legacy cache writes are permanently frozen."""
        _logger.warning(
            "Legacy rate-memory write skipped for load %s; canonical freight history owns new evidence.", self.id
        )
        return False

    def _lane_key(self):
        so = self.sale_order_id
        return f"{so.partner_shipping_id.id}-{so.partner_invoice_id.id}"

    @api.constrains("pickup_datetime", "delivery_datetime")
    def _check_datetime_order(self):
        """Ensure delivery date/time is not before pickup date/time."""
        for rec in self:
            if rec.pickup_datetime and rec.delivery_datetime:
                if rec.delivery_datetime < rec.pickup_datetime:
                    raise ValidationError(f"Load {rec.name}: Delivery date/time cannot be before pickup date/time.")

    @api.model
    def _cron_escalation_check(self):
        self.env.cr.execute("SELECT pg_try_advisory_lock(hashtext(%s))", ["plasticos_logistics.cron_escalation_check"])
        locked = self.env.cr.fetchone()[0]
        if not locked:
            _logger.info("Skipping escalation cron: lock is already held.")
            return

        try:
            try:
                from odoo.addons.plasticos_logistics.services.escalation_engine import check_escalations

                check_escalations(self.env)
            except ImportError:
                _logger.warning("escalation_engine not found; skipping cron.")
        finally:
            self.env.cr.execute(
                "SELECT pg_advisory_unlock(hashtext(%s))", ["plasticos_logistics.cron_escalation_check"]
            )

    @api.model
    def _cron_check_dispatch_acknowledgments(self):
        """Check for unacknowledged dispatches and escalate.

        Creates escalation activity and resends dispatch email for loads
        where carrier has not acknowledged within threshold.
        """
        threshold_hours = 4
        threshold_dt = fields.Datetime.now() - timedelta(hours=threshold_hours)

        unacknowledged = self.search(
            [
                ("dispatch_sent", "!=", False),
                ("dispatch_sent", "<", threshold_dt),
                ("dispatch_acknowledged", "=", False),
                ("state", "in", ["dispatched", "scheduled"]),
            ],
            order="dispatch_sent asc",
            limit=100,
        )

        for load in unacknowledged:
            has_activity = self.env["mail.activity"].search_count(
                [
                    ("res_model", "=", PLASTICOS_LOAD),
                    ("res_id", "=", load.id),
                    ("summary", "ilike", "URGENT: No carrier acknowledgment"),
                    ("date_deadline", "=", fields.Date.today()),
                ]
            )

            if has_activity:
                continue

            tx = self.env[PLASTICOS_TRANSACTION].search([("load_id", "=", load.id)], order="id asc", limit=1)
            user_id = tx.user_id.id if tx and tx.user_id else self.env.user.id

            load.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=user_id,
                summary=f"URGENT: No carrier acknowledgment for {load.name}",
                note=f"Carrier has not acknowledged dispatch sent {load.dispatch_sent}.",
            )

            try:
                load.action_send_dispatch_direct()
                _logger.info("Resent dispatch for load %s", load.name)
            except Exception as e:
                _logger.error("Failed to resend dispatch for load %s: %s", load.name, str(e))

        return True

    # ── Email Send Actions (Paperless) ──────────────────────────────

    def action_send_delivery_order(self):
        """Open email composer with Delivery Order attached."""
        self.ensure_one()
        template = self._get_email_template("email_template_delivery_order")
        return self._open_mail_composer(template)

    def action_send_bol_pickup(self):
        """Open email composer with BOL Pickup attached."""
        self.ensure_one()
        template = self._get_email_template("email_template_bol_pickup")
        return self._open_mail_composer(template)

    def action_send_bol_delivery(self):
        """Open email composer with BOL Delivery attached."""
        self.ensure_one()
        template = self._get_email_template("email_template_bol_delivery")
        return self._open_mail_composer(template)

    def action_send_dispatch_packet(self):
        """Open email composer with full dispatch packet (all 3 docs)."""
        self.ensure_one()
        template = self._get_email_template("email_template_dispatch_packet")
        return self._open_mail_composer(template)

    def action_send_dispatch_direct(self):
        """Send dispatch packet directly and track timestamp.

        Unlike action_send_dispatch_packet which opens a composer,
        this method sends immediately and sets dispatch_sent timestamp.
        """
        self.ensure_one()
        if not self.carrier_id:
            raise UserError(f"Load {self.name}: Carrier is required to send dispatch.")
        if not self.carrier_id.email:
            raise UserError(f"Carrier {self.carrier_id.name} has no email address.")

        template = self._get_email_template("email_template_dispatch_packet")
        template.send_mail(self.id, force_send=True)
        self.dispatch_sent = fields.Datetime.now()
        self.message_post(body="Dispatch packet sent to carrier.")
        return True

    def _get_email_template(self, template_name):
        """Get email template from plasticos_automation module.

        Raises ValidationError with clear message if template not found
        (plasticos_automation module not installed).
        """
        xml_id = f"plasticos_automation.{template_name}"
        template = self.env.ref(xml_id, raise_if_not_found=False)
        if not template:
            raise ValidationError(
                f"Email template '{template_name}' not found.\n\n"
                "The plasticos_automation module must be installed to use "
                "email send actions. Please install it from Apps."
            )
        return template

    def _open_mail_composer(self, template):
        """Helper to open mail composer wizard with template."""
        ctx = {
            "default_model": PLASTICOS_LOAD,
            "default_res_ids": self.ids,
            "default_template_id": template.id,
            "default_composition_mode": "comment",
            "mark_so_as_sent": True,
            "force_email": True,
        }
        return {
            "type": "ir.actions.act_window",
            "res_model": "mail.compose.message",
            "view_mode": "form",
            "target": "new",
            "context": ctx,
        }

    # ═════════════════════════════════════════════════════════
    # Action Methods (for UX smart buttons)
    # ═════════════════════════════════════════════════════════

    def action_view_transaction(self):
        """Open the linked transaction form."""
        self.ensure_one()
        tx = self.env[PLASTICOS_TRANSACTION].search([("load_id", "=", self.id)], limit=1)
        if not tx:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": PLASTICOS_TRANSACTION,
            "res_id": tx.id,
            "view_mode": "form",
            "target": "current",
        }
