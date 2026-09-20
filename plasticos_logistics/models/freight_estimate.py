"""Immutable nonbinding freight-estimate observations owned by Odoo."""

from __future__ import annotations

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class PlasticosFreightEstimate(models.Model):
    _name = "plasticos.freight.estimate"
    _description = "Plasticos Freight Estimate"
    _order = "generated_at desc, id desc"

    name = fields.Char(required=True, default="New", copy=False, readonly=True, index=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True, ondelete="restrict"
    )
    origin_partner_id = fields.Many2one("res.partner", required=True, ondelete="restrict")
    destination_partner_id = fields.Many2one("res.partner", required=True, ondelete="restrict")
    source_model = fields.Char(required=True, index=True, readonly=True)
    source_record_id = fields.Integer(required=True, index=True, readonly=True)
    context_fingerprint = fields.Char(required=True, index=True, readonly=True)
    request_fingerprint = fields.Char(required=True, index=True, readonly=True)
    fingerprint_version = fields.Char(required=True, readonly=True)
    expected_weight_lbs = fields.Float()
    haversine_miles = fields.Float(readonly=True)
    geometry_status = fields.Selection(
        [("available", "Available"), ("missing_or_invalid", "Missing or Invalid")],
        required=True,
        default="missing_or_invalid",
        readonly=True,
    )
    estimate_floor = fields.Monetary(currency_field="currency_id", readonly=True)
    estimate_target = fields.Monetary(currency_field="currency_id", readonly=True)
    estimate_ceiling = fields.Monetary(currency_field="currency_id", readonly=True)
    pricing_assumption = fields.Monetary(currency_field="currency_id", readonly=True)
    currency_id = fields.Many2one("res.currency", ondelete="restrict", readonly=True)
    confidence = fields.Float(readonly=True)
    method = fields.Selection(
        [
            ("exact_lane", "Exact Lane"),
            ("similar_lane", "Similar Lane"),
            ("hybrid", "Hybrid"),
            ("model_prior", "Model Prior"),
        ],
        readonly=True,
    )
    model_version = fields.Char(readonly=True)
    policy_version = fields.Char(readonly=True)
    evidence_summary = fields.Json(readonly=True)
    reasoning_summary = fields.Json(readonly=True)
    # Retained only for non-destructive compatibility with earlier observations.
    # Linda's current deterministic path neither reads nor writes this provenance.
    gate_packet_id = fields.Char(readonly=True)
    gate_correlation_id = fields.Char(readonly=True)
    gate_operation_id = fields.Char(readonly=True)
    logical_request_id = fields.Char(readonly=True)
    attempt = fields.Integer(default=1, readonly=True)
    status = fields.Selection(
        [
            ("pending", "Pending"),
            ("succeeded", "Succeeded"),
            ("insufficient_evidence", "Insufficient Evidence"),
            ("failed", "Failed"),
        ],
        required=True,
        default="pending",
        tracking=True,
    )
    failure_code = fields.Char(readonly=True)
    generated_at = fields.Datetime(required=True, default=fields.Datetime.now, readonly=True)
    valid_until = fields.Datetime(readonly=True)
    supersedes_estimate_id = fields.Many2one("plasticos.freight.estimate", ondelete="restrict", readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("plasticos.freight.estimate") or "New"
        return super().create(vals_list)

    @api.constrains(
        "confidence",
        "estimate_floor",
        "estimate_target",
        "estimate_ceiling",
        "pricing_assumption",
        "currency_id",
        "status",
        "model_version",
        "source_model",
        "source_record_id",
    )
    def _check_estimate_contract(self):
        for rec in self:
            if not rec.source_model or not rec.source_record_id:
                raise ValidationError("Estimate source model and record identity are required.")
            if rec.confidence and not 0 <= rec.confidence <= 1:
                raise ValidationError("Estimate confidence must be between zero and one.")
            amounts = [rec.estimate_floor, rec.estimate_target, rec.estimate_ceiling, rec.pricing_assumption]
            if any(amount is not None and amount < 0 for amount in amounts):
                raise ValidationError("Estimate amounts cannot be negative.")
            if rec.status == "succeeded":
                if not rec.currency_id or not rec.model_version or rec.estimate_target is None:
                    raise ValidationError("Succeeded estimates require currency, target, and model provenance.")
                if not rec.estimate_floor <= rec.estimate_target <= rec.estimate_ceiling:
                    raise ValidationError("Estimate range must be floor <= target <= ceiling.")
                if not rec.estimate_target <= rec.pricing_assumption <= rec.estimate_ceiling:
                    raise ValidationError("Pricing assumption must be within the estimate range.")

    def write(self, vals):
        immutable = {
            "context_fingerprint",
            "request_fingerprint",
            "fingerprint_version",
            "source_model",
            "source_record_id",
            "origin_partner_id",
            "destination_partner_id",
            "expected_weight_lbs",
            "haversine_miles",
            "geometry_status",
            "estimate_floor",
            "estimate_target",
            "estimate_ceiling",
            "pricing_assumption",
            "currency_id",
            "confidence",
            "method",
            "model_version",
            "policy_version",
            "evidence_summary",
            "reasoning_summary",
            "gate_packet_id",
            "gate_correlation_id",
            "gate_operation_id",
            "logical_request_id",
            "attempt",
            "status",
            "failure_code",
            "generated_at",
            "valid_until",
            "supersedes_estimate_id",
        }
        if immutable.intersection(vals):
            raise UserError("Freight estimates are immutable observations; create a superseding estimate instead.")
        return super().write(vals)
