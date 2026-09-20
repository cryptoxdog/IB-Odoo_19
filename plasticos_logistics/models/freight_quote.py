"""Odoo-owned RFQ episode, delivery ledger, and immutable quote evidence."""

from __future__ import annotations

import hashlib
import json

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

RANKING_STATUS = [
    ("not_evaluated", "Not Evaluated"),
    ("eligible", "Eligible"),
    ("recommended", "Recommended"),
    ("ineligible", "Ineligible"),
]


def _company_for_load(load):
    return getattr(load, "company_id", False) or (
        load.sale_order_id.company_id if load.sale_order_id and load.sale_order_id.company_id else None
    )


def _source_fingerprint(values):
    payload = json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class PlasticosFreightQuoteRequest(models.Model):
    _name = "plasticos.freight.quote.request"
    _description = "Plasticos Freight Quote Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(required=True, default="New", copy=False, readonly=True, index=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True, ondelete="restrict"
    )
    load_id = fields.Many2one("plasticos.load", required=True, index=True, ondelete="restrict")
    transaction_id = fields.Many2one("plasticos.transaction", required=True, index=True, ondelete="restrict")
    origin_partner_id = fields.Many2one("res.partner", required=True, ondelete="restrict")
    destination_partner_id = fields.Many2one("res.partner", required=True, ondelete="restrict")
    context_fingerprint = fields.Char(required=True, index=True, readonly=True)
    fingerprint_version = fields.Char(required=True, readonly=True)
    idempotency_key = fields.Char(required=True, index=True, readonly=True)
    sal_decision = fields.Selection([("miss", "Miss"), ("not_eligible", "Not Eligible")], required=True, readonly=True)
    sal_miss_reason = fields.Char(required=True, readonly=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("sent", "Sent"),
            ("collecting", "Collecting"),
            ("resolved", "Resolved"),
            ("cancelled", "Cancelled"),
            ("failed", "Failed"),
        ],
        required=True,
        default="draft",
        tracking=True,
    )
    response_deadline = fields.Datetime()
    sent_at = fields.Datetime(readonly=True)
    resolved_at = fields.Datetime(readonly=True)
    cancelled_at = fields.Datetime(readonly=True)
    cancellation_reason = fields.Text(readonly=True)
    failure_code = fields.Char(readonly=True)
    selected_quote_id = fields.Many2one("plasticos.freight.quote", readonly=True, ondelete="restrict")
    recommended_quote_id = fields.Many2one("plasticos.freight.quote", readonly=True, ondelete="restrict")
    ranking_policy_version = fields.Char(readonly=True)
    ranked_at = fields.Datetime(readonly=True)
    recipient_ids = fields.One2many("plasticos.freight.quote.recipient", "request_id", string="Recipients")
    quote_ids = fields.One2many("plasticos.freight.quote", "request_id", string="Carrier Responses")

    _logical_request_unique = models.Constraint(
        "unique(load_id, context_fingerprint, idempotency_key)",
        "Only one logical request may exist for a load and freight context.",
    )

    _REQUEST_TRANSITIONS = {
        "draft": {"sent", "collecting", "cancelled"},
        "sent": {"collecting", "failed", "cancelled"},
        "collecting": {"resolved", "failed", "cancelled"},
        "resolved": set(),
        "cancelled": set(),
        "failed": set(),
    }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("plasticos.freight.quote.request") or "New"
        return super().create(vals_list)

    @api.constrains("company_id", "load_id", "transaction_id", "origin_partner_id", "destination_partner_id")
    def _check_request_company_and_lane(self):
        for rec in self:
            company = _company_for_load(rec.load_id)
            if not company or company != rec.company_id:
                raise ValidationError("Freight quote request company must match the load company.")
            if rec.load_id.transaction_id != rec.transaction_id:
                raise ValidationError("Freight quote request transaction must match the load transaction.")
            if (
                rec.load_id.pickup_partner_id != rec.origin_partner_id
                or rec.load_id.delivery_partner_id != rec.destination_partner_id
            ):
                raise ValidationError("Freight quote request lane must match the load lane at creation.")

    def _ensure_current_context(self):
        from odoo.addons.plasticos_logistics.services.freight_context import build_freight_context

        for rec in self:
            current_context = build_freight_context(rec.load_id)
            if not current_context or current_context.fingerprint != rec.context_fingerprint:
                if rec.state not in ("resolved", "cancelled", "failed"):
                    rec.write(
                        {
                            "state": "cancelled",
                            "cancelled_at": fields.Datetime.now(),
                            "cancellation_reason": "context_changed",
                        }
                    )
                raise UserError("Freight context changed; the quote request was cancelled and cannot be used.")

    @api.constrains("recommended_quote_id")
    def _check_recommended_quote_relationship(self):
        for rec in self:
            if rec.recommended_quote_id and rec.recommended_quote_id.request_id != rec:
                raise ValidationError("A recommended quote must belong to its freight quote request.")

    def action_rank_quotes(self):
        """Rank current eligible quotes for operator review; this never selects or awards a quote."""
        from odoo.addons.plasticos_logistics.models.freight_governance import record_freight_event
        from odoo.addons.plasticos_logistics.services.freight_history import (
            local_estimation_evidence,
            recent_comparable_executed_evidence,
            recent_executed_lane_evidence,
        )
        from odoo.addons.plasticos_logistics.services.freight_quote_ranking import (
            RANKING_POLICY_VERSION,
            LaneOutcome,
            QuoteCandidate,
            rank_quotes,
        )

        for rec in self:
            rec.env.cr.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))", [f"plasticos_logistics.rfq-decision:{rec.id}"]
            )
            rec.invalidate_recordset()
            if rec.state in ("resolved", "cancelled", "failed"):
                raise UserError("Terminal freight quote requests cannot be ranked.")
            rec._ensure_current_context()
            if not rec.load_id.rate_currency_id:
                raise UserError("An explicit load freight currency is required before quote ranking.")
            exact_history = recent_executed_lane_evidence(rec.env, rec.load_id)
            exact_ids = exact_history.ids
            comparable_history = recent_comparable_executed_evidence(rec.env, rec.load_id).filtered(
                lambda candidate, exact_ids=exact_ids: candidate.id not in exact_ids
            )
            evidence = local_estimation_evidence(exact_history + comparable_history)
            outcomes = [
                LaneOutcome(
                    carrier_id=item.carrier_id,
                    amount=item.amount,
                    currency_id=item.currency_id,
                    occurred_at=item.occurred_at,
                )
                for item in evidence
            ]
            rankings = rank_quotes(
                quotes=[
                    QuoteCandidate(
                        quote_id=quote.id,
                        carrier_id=quote.carrier_id.id,
                        amount=quote.quoted_amount,
                        currency_id=quote.currency_id.id if quote.currency_id else None,
                        response_kind=quote.response_kind,
                        lifecycle_state=quote.lifecycle_state,
                        valid_until=quote.valid_until,
                        responded_at=quote.responded_at,
                        timeliness=quote.timeliness,
                        context_current=True,
                        carrier_active=quote.carrier_id.active,
                        carrier_blocked=getattr(quote.carrier_id, "entity_status", None) == "blocked",
                    )
                    for quote in rec.quote_ids
                ],
                lane_outcomes=outcomes,
                required_currency_id=rec.load_id.rate_currency_id.id,
            )
            recommended_id = next((ranking.quote_id for ranking in rankings if ranking.eligible), False)
            by_id = {ranking.quote_id: ranking for ranking in rankings}
            rank_by_id = {
                ranking.quote_id: ordinal
                for ordinal, ranking in enumerate((item for item in rankings if item.eligible), start=1)
            }
            for quote in rec.quote_ids:
                ranking = by_id[quote.id]
                if ranking.eligible:
                    status = "recommended" if quote.id == recommended_id else "eligible"
                else:
                    status = "ineligible"
                quote.write(
                    {
                        "ranking_status": status,
                        "ranking_score": ranking.score if ranking.eligible else False,
                        "ranking_rank": rank_by_id.get(quote.id, False),
                        "ranking_policy_version": RANKING_POLICY_VERSION,
                        "ranking_reasoning": ranking.as_dict(),
                        "ranked_at": fields.Datetime.now(),
                    }
                )
            rec.write(
                {
                    "recommended_quote_id": recommended_id,
                    "ranking_policy_version": RANKING_POLICY_VERSION,
                    "ranked_at": fields.Datetime.now(),
                }
            )
            record_freight_event(
                rec.env,
                event_type="freight_quote_ranked",
                outcome_code="recommended" if recommended_id else "no_eligible_quote",
                load=rec.load_id,
                facts={"request_id": rec.id, "recommended_quote_id": recommended_id, "policy": RANKING_POLICY_VERSION},
            )
        return True

    def write(self, vals):
        protected = {
            "company_id",
            "load_id",
            "transaction_id",
            "origin_partner_id",
            "destination_partner_id",
            "context_fingerprint",
            "fingerprint_version",
            "idempotency_key",
            "sal_decision",
            "sal_miss_reason",
        }
        if protected.intersection(vals):
            raise UserError("Freight quote request identity is immutable after creation.")
        if "state" in vals:
            for rec in self:
                if vals["state"] != rec.state and vals["state"] not in self._REQUEST_TRANSITIONS[rec.state]:
                    raise UserError("Freight quote request transition is not permitted.")
        return super().write(vals)

    def unlink(self):
        raise UserError("Freight quote requests are audit evidence and cannot be deleted.")

    def action_select_quote(self):
        for rec in self:
            rec.env.cr.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))", [f"plasticos_logistics.rfq-decision:{rec.id}"]
            )
            rec.invalidate_recordset()
            if rec.state not in ("draft", "sent", "collecting"):
                raise UserError("Only an active freight quote request can be resolved.")
            if rec.state == "draft":
                rec.write({"state": "collecting"})
            rec._ensure_current_context()
            quote = rec.quote_ids.filtered(lambda item: item.selected)
            if len(quote) != 1:
                raise UserError("Select exactly one active, valid carrier quote before confirming freight.")
            selected = quote[0]
            selected._check_selectable()
            rec.load_id._confirm_freight_rate(
                rate=selected.quoted_amount,
                carrier=selected.carrier_id,
                currency=selected.currency_id,
                resolution_method="live_quote",
                context_fingerprint=rec.context_fingerprint,
            )
            rec.write({"selected_quote_id": selected.id, "resolved_at": fields.Datetime.now(), "state": "resolved"})
            rec.load_id.write({"selected_freight_quote_id": selected.id})
            rec.message_post(
                body=f"Freight quote {selected.name} selected and confirmed through the canonical load rate path."
            )
        return True


class PlasticosFreightQuoteRecipient(models.Model):
    _name = "plasticos.freight.quote.recipient"
    _description = "Plasticos Freight Quote Recipient"
    _order = "id asc"

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True, ondelete="restrict"
    )
    request_id = fields.Many2one("plasticos.freight.quote.request", required=True, index=True, ondelete="cascade")
    carrier_id = fields.Many2one("res.partner", required=True, index=True, ondelete="restrict")
    channel = fields.Selection(
        [("email", "Email"), ("sms", "SMS"), ("api", "API"), ("manual", "Manual")], required=True
    )
    destination_snapshot = fields.Char(required=True)
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("sent", "Sent"),
            ("delivery_failed", "Delivery Failed"),
            ("responded", "Responded"),
            ("no_response", "No Response"),
            ("cancelled", "Cancelled"),
        ],
        required=True,
        default="pending",
    )
    attempt_count = fields.Integer(required=True, default=0)
    idempotency_key = fields.Char(required=True, index=True)
    last_attempt_at = fields.Datetime(readonly=True)
    sent_at = fields.Datetime(readonly=True)
    response_at = fields.Datetime(readonly=True)
    delivery_error_class = fields.Char(readonly=True)
    outbound_message_ref = fields.Char(readonly=True)

    _recipient_unique = models.Constraint(
        "unique(request_id, carrier_id, channel)",
        "Only one logical recipient may exist for each request, carrier, and channel.",
    )

    @api.constrains("company_id", "request_id")
    def _check_recipient_company(self):
        for rec in self:
            if rec.request_id.company_id != rec.company_id:
                raise ValidationError("Recipient company must match its freight quote request.")

    @api.constrains("state", "attempt_count", "sent_at", "response_at", "delivery_error_class")
    def _check_recipient_state_evidence(self):
        for rec in self:
            if rec.state in ("sent", "responded") and (rec.attempt_count < 1 or not rec.sent_at):
                raise ValidationError(
                    "Sent or responded recipients require a successful delivery attempt and sent time."
                )
            if rec.state == "responded" and not rec.response_at:
                raise ValidationError("Responded recipients require a response timestamp.")
            if rec.state == "delivery_failed" and (rec.attempt_count < 1 or not rec.delivery_error_class):
                raise ValidationError("Delivery failures require an attempt and error classification.")

    def write(self, vals):
        protected = {"company_id", "request_id", "carrier_id", "channel", "idempotency_key"}
        if protected.intersection(vals):
            raise UserError("Freight quote recipient identity is immutable after creation.")
        if "destination_snapshot" in vals:
            for rec in self:
                if rec.sent_at:
                    raise UserError("Recipient destination evidence cannot change after a send attempt.")
        return super().write(vals)

    def unlink(self):
        raise UserError("Freight quote recipients are audit evidence and cannot be deleted.")


class PlasticosFreightQuote(models.Model):
    _name = "plasticos.freight.quote"
    _description = "Plasticos Freight Quote Evidence"
    _order = "responded_at desc, id desc"

    name = fields.Char(required=True, default="New", copy=False, readonly=True, index=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True, ondelete="restrict"
    )
    request_id = fields.Many2one("plasticos.freight.quote.request", required=True, index=True, ondelete="cascade")
    recipient_id = fields.Many2one("plasticos.freight.quote.recipient", required=True, index=True, ondelete="restrict")
    carrier_id = fields.Many2one("res.partner", required=True, index=True, ondelete="restrict")
    response_kind = fields.Selection(
        [("quote", "Quote"), ("declined", "Declined"), ("no_capacity", "No Capacity"), ("invalid", "Invalid")],
        required=True,
    )
    timeliness = fields.Selection(
        [("in_window", "In Window"), ("late", "Late"), ("unknown", "Unknown")], required=True, default="unknown"
    )
    lifecycle_state = fields.Selection(
        [("active", "Active"), ("withdrawn", "Withdrawn"), ("superseded", "Superseded")],
        required=True,
        default="active",
    )
    responded_at = fields.Datetime(required=True, default=fields.Datetime.now)
    source_channel = fields.Selection(
        [("email", "Email"), ("sms", "SMS"), ("api", "API"), ("manual", "Manual")], required=True, default="manual"
    )
    source_message_id = fields.Char(required=True)
    source_fingerprint = fields.Char(required=True, index=True, readonly=True)
    quoted_amount = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", ondelete="restrict")
    valid_until = fields.Datetime()
    conditions = fields.Text()
    selected = fields.Boolean(default=False, tracking=True)
    supersedes_quote_id = fields.Many2one("plasticos.freight.quote", ondelete="restrict")
    ranking_status = fields.Selection(RANKING_STATUS, required=True, default="not_evaluated", readonly=True)
    ranking_score = fields.Float(readonly=True)
    ranking_rank = fields.Integer(readonly=True)
    ranking_policy_version = fields.Char(readonly=True)
    ranking_reasoning = fields.Json(readonly=True)
    ranked_at = fields.Datetime(readonly=True)

    _source_unique = models.Constraint(
        "unique(request_id, source_fingerprint)", "Carrier response source is already recorded for this request."
    )

    @api.model_create_multi
    def create(self, vals_list):
        recipient_ids = [vals["recipient_id"] for vals in vals_list if vals.get("recipient_id")]
        recipients = self.env["plasticos.freight.quote.recipient"].browse(recipient_ids).exists()
        recipients_by_id = {recipient.id: recipient for recipient in recipients}
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("plasticos.freight.quote") or "New"
            recipient = recipients_by_id.get(vals.get("recipient_id"))
            if recipient and not vals.get("carrier_id"):
                vals["carrier_id"] = recipient.carrier_id.id
            if not vals.get("source_fingerprint"):
                vals["source_fingerprint"] = _source_fingerprint(
                    {
                        "carrier_id": vals.get("carrier_id"),
                        "message_id": vals.get("source_message_id") or "",
                        "request_id": vals.get("request_id"),
                        "source_channel": vals.get("source_channel", "manual"),
                    }
                )
        records = super().create(vals_list)
        for rec in records:
            if rec.recipient_id.state not in ("cancelled", "responded"):
                rec.recipient_id.write(
                    {
                        "attempt_count": max(1, rec.recipient_id.attempt_count),
                        "last_attempt_at": rec.responded_at,
                        "response_at": rec.responded_at,
                        "sent_at": rec.recipient_id.sent_at or rec.responded_at,
                        "state": "responded",
                    }
                )
        return records

    @api.constrains("company_id", "request_id", "recipient_id", "carrier_id")
    def _check_quote_relationships(self):
        for rec in self:
            if rec.request_id.company_id != rec.company_id or rec.recipient_id.company_id != rec.company_id:
                raise ValidationError("Quote evidence must remain within its request company.")
            if rec.recipient_id.request_id != rec.request_id or rec.recipient_id.carrier_id != rec.carrier_id:
                raise ValidationError("Quote recipient and carrier must match the quote request.")

    @api.constrains("response_kind", "quoted_amount", "currency_id", "selected", "lifecycle_state")
    def _check_amount_semantics(self):
        for rec in self:
            if rec.response_kind == "quote":
                if not rec.quoted_amount or rec.quoted_amount <= 0 or not rec.currency_id:
                    raise ValidationError("A quote response requires a positive amount and currency.")
            elif rec.quoted_amount or rec.currency_id or rec.selected:
                raise ValidationError("Declines, no-capacity, and invalid responses cannot carry a price or selection.")
            if rec.selected and rec.lifecycle_state != "active":
                raise ValidationError("Only active quote evidence may be selected.")

    def write(self, vals):
        protected = {
            "company_id",
            "request_id",
            "recipient_id",
            "carrier_id",
            "response_kind",
            "responded_at",
            "source_channel",
            "source_message_id",
            "source_fingerprint",
            "quoted_amount",
            "currency_id",
            "conditions",
            "valid_until",
            "supersedes_quote_id",
        }
        if protected.intersection(vals):
            raise UserError("Carrier response evidence is immutable; create a superseding quote instead.")
        return super().write(vals)

    def unlink(self):
        raise UserError("Carrier response evidence cannot be deleted.")

    def _check_selectable(self):
        for rec in self:
            if (
                rec.response_kind != "quote"
                or rec.lifecycle_state != "active"
                or not rec.quoted_amount
                or not rec.currency_id
            ):
                raise UserError("Only an active priced quote may be selected.")
            if rec.valid_until and rec.valid_until < fields.Datetime.now():
                raise UserError("An expired quote cannot be selected.")

    def action_select(self):
        for rec in self:
            rec.env.cr.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                [f"plasticos_logistics.rfq-decision:{rec.request_id.id}"],
            )
            rec.invalidate_recordset()
            if rec.request_id.state in ("resolved", "cancelled", "failed"):
                raise UserError("Quotes cannot be changed after the request is terminal.")
            rec._check_selectable()
            rec.request_id._ensure_current_context()
            (rec.request_id.quote_ids - rec).filtered("selected").write({"selected": False})
            rec.write({"selected": True})
        return True
