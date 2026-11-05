"""Capacity observation — attributed facility capacity measurements (TASK-025)."""

from __future__ import annotations

import uuid

from odoo import api, fields, models
from odoo.exceptions import UserError


class PlasticosCapacityObservation(models.Model):
    _name = "plasticos.capacity.observation"
    _description = "Capacity Observation"
    _order = "observed_at desc, id desc"
    _rec_name = "capacity_kind"

    canonical_uuid = fields.Char(
        required=True,
        index=True,
        copy=False,
        default=lambda self: str(uuid.uuid4()),
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        index=True,
        ondelete="restrict",
        default=lambda self: self.env.company,
    )
    active = fields.Boolean(default=True)
    facility_profile_id = fields.Many2one(
        "plasticos.facility.profile",
        required=True,
        index=True,
        ondelete="cascade",
    )
    capacity_kind = fields.Selection(
        [
            ("installed_nominal", "Installed Nominal"),
            ("typical_throughput", "Typical Throughput"),
            ("available", "Available"),
            ("committed", "Committed"),
            ("reserved", "Reserved"),
            ("estimated", "Estimated"),
        ],
        required=True,
        index=True,
    )
    value = fields.Float(required=True)
    unit_code = fields.Selection(
        [
            ("lb_per_month", "lb/month"),
            ("lb_per_week", "lb/week"),
            ("lb_per_hour", "lb/hour"),
            ("ton_per_month", "ton/month"),
        ],
        required=True,
    )
    period_start = fields.Date()
    period_end = fields.Date()
    value_state = fields.Selection(
        [
            ("observed", "Observed"),
            ("reported", "Reported"),
            ("inferred", "Inferred"),
            ("unknown", "Unknown"),
            ("stale", "Stale"),
            ("conflicting", "Conflicting"),
        ],
        required=True,
        index=True,
    )
    confidence = fields.Float()
    observed_at = fields.Datetime(required=True, index=True)
    valid_until = fields.Datetime(index=True)
    source_system = fields.Char(required=True)
    source_record_ref = fields.Char()
    method = fields.Char()
    supersedes_id = fields.Many2one(
        "plasticos.capacity.observation",
        ondelete="restrict",
        index=True,
    )
    migration_batch_id = fields.Char(index=True)
    contract_version = fields.Char(required=True, default="1.0")

    _canonical_uuid_uniq = models.Constraint(
        "unique(canonical_uuid)",
        "canonical_uuid must be unique and immutable.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("canonical_uuid"):
                vals["canonical_uuid"] = str(uuid.uuid4())
        return super().create(vals_list)

    def write(self, vals):
        if "canonical_uuid" in vals:
            raise UserError("canonical_uuid is immutable once issued.")
        return super().write(vals)
