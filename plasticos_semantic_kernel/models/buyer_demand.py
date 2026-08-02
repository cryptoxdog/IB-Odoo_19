"""Buyer demand — qualified buyer requirements (TASK-024)."""

from __future__ import annotations

import uuid

from odoo import api, fields, models
from odoo.exceptions import UserError


class PlasticosBuyerDemand(models.Model):
    _name = "plasticos.buyer.demand"
    _description = "Buyer Demand"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name, id desc"
    _rec_name = "name"

    name = fields.Char(required=True, index=True, tracking=True)
    canonical_uuid = fields.Char(
        required=True,
        index=True,
        copy=False,
        default=lambda self: str(uuid.uuid4()),
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        index=True,
        ondelete="restrict",
        default=lambda self: self.env.company,
    )
    active = fields.Boolean(default=True)
    buyer_partner_id = fields.Many2one(
        "res.partner",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    buyer_facility_id = fields.Many2one("res.partner", ondelete="restrict", index=True)
    specification_id = fields.Many2one(
        "plasticos.material.specification",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("qualified", "Qualified"),
            ("open", "Open"),
            ("partially_filled", "Partially Filled"),
            ("filled", "Filled"),
            ("closed", "Closed"),
            ("cancelled", "Cancelled"),
            ("expired", "Expired"),
        ],
        required=True,
        default="draft",
        index=True,
        tracking=True,
    )
    quantity_lbs = fields.Float()
    quantity_state = fields.Selection(
        [
            ("exact", "Exact"),
            ("estimated", "Estimated"),
            ("range", "Range"),
            ("unknown", "Unknown"),
        ],
        required=True,
        default="unknown",
        index=True,
    )
    min_lot_size_lbs = fields.Float()
    max_lot_size_lbs = fields.Float()
    cadence = fields.Selection(
        [
            ("one_time", "One Time"),
            ("weekly", "Weekly"),
            ("biweekly", "Biweekly"),
            ("monthly", "Monthly"),
            ("contract", "Contract"),
            ("unknown", "Unknown"),
        ],
    )
    needed_from = fields.Date()
    needed_until = fields.Date()
    currency_id = fields.Many2one(
        "res.currency",
        ondelete="restrict",
        default=lambda self: self.env.company.currency_id,
    )
    target_price_per_lb = fields.Monetary(currency_field="currency_id")
    delivery_state_id = fields.Many2one("res.country.state", ondelete="restrict")
    delivery_zip = fields.Char()
    required_evidence_ids = fields.Many2many(
        "plasticos.material.attribute",
        "plasticos_buyer_demand_attribute_rel",
        "demand_id",
        "attribute_id",
        string="Required Evidence Attributes",
    )
    source_system = fields.Char()
    source_record_ref = fields.Char()
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
