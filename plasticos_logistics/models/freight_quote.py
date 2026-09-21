"""Odoo-owned RFQ episode, delivery ledger, and immutable quote evidence."""

from __future__ import annotations

import hashlib
import json

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

_RFQ_INTERNAL_WRITE = "plasticos_logistics_internal_rfq_write"
_RFQ_INTERNAL_SELECTION = "plasticos_logistics_internal_rfq_selection"
_RFQ_INTERNAL_WRITE_TOKEN = object()
_RFQ_INTERNAL_SELECTION_TOKEN = object()

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


def recipient_idempotency_key(request_id, carrier_id, channel):
    """Deterministic recipient identity: one logical recipient per request, carrier, and channel."""
    return hashlib.sha256(f"recipient:{request_id}:{carrier_id}:{channel}".encode()).hexdigest()


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
        from odoo.addons.plasticos_logistics.services.freight_context import (
            FREIGHT_CONTEXT_VERSION,
            build_freight_context,
        )

        load_ids = [values["load_id"] for values in vals_list if values.get("load_id")]
        loads = self.env["plasticos.load"].browse(load_ids).exists()
        loads._require_freight_operator()
        for vals in vals_list:
            load = loads.filtered(lambda candidate, values=vals: candidate.id == values.get("load_id"))
            if not load or load.state != "ready_confirmed" or load.sal_decision not in ("miss", "not_eligible"):
                raise UserError(
                    "A current SAL miss or not-eligible decision is required before creating an RFQ episode."
                )
            context = build_freight_context(load)
            if not context or load.freight_context_fingerprint != context.fingerprint:
                raise UserError("A complete current freight context is required before creating an RFQ episode.")
            company = _company_for_load(load)
            if not company or not load.transaction_id:
                raise UserError("Load company and transaction are required before creating an RFQ episode.")
            idempotency_key = hashlib.sha256(f"rfq:{load.id}:{context.fingerprint}".encode()).hexdigest()
            vals.update(
                {
                    "company_id": company.id,
                    "transaction_id": load.transaction_id.id,
                    "origin_partner_id": load.pickup_partner_id.id,
                    "destination_partner_id": load.delivery_partner_id.id,
                    "context_fingerprint": context.fingerprint,
                    "fingerprint_version": FREIGHT_CONTEXT_VERSION,
                    "idempotency_key": idempotency_key,
                    "sal_decision": load.sal_decision,
                    "sal_miss_reason": load.sal_miss_reason or "not_eligible",
                }
            )
            if self.search([("idempotency_key", "=", idempotency_key)], limit=1):
                raise UserError("A freight quote request already exists for the current load context.")
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("plasticos.freight.quote.request") or "New"
        return super().create(vals_list)

    def _rfq_write(self, values):
        return self.with_context(**{_RFQ_INTERNAL_WRITE: _RFQ_INTERNAL_WRITE_TOKEN}).write(values)

    def _require_operator(self):
        self.mapped("load_id")._require_freight_operator()

    def _lock_decision(self):
        for rec in self:
            # Advisory lock justification: serializes RFQ ranking and selection across workers.
            rec.env.cr.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))", [f"plasticos_logistics.rfq-decision:{rec.id}"]
            )

    def _ensure_active_for_child_evidence(self):
        self._lock_decision()
        for rec in self:
            rec.invalidate_recordset()
            if rec.state in ("resolved", "cancelled", "failed"):
                raise UserError("Terminal freight quote requests cannot accept new evidence.")
            rec._ensure_current_context()

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
        """Refuse a request whose freight context no longer matches its load.

        This guard performs no write. A ``UserError`` rolls the transaction back,
        so a cancellation written here could never persist and every retry would
        repeat the failure. The durable cancellation (plus its audit event) is
        recorded by ``plasticos.load.action_resolve_freight``, which runs in a
        transaction that succeeds.
        """
        from odoo.addons.plasticos_logistics.services.freight_context import build_freight_context

        for rec in self:
            current_context = build_freight_context(rec.load_id)
            if not current_context or current_context.fingerprint != rec.context_fingerprint:
                raise UserError(
                    "Freight context changed; this quote request is stale and cannot be used. "
                    "Re-run Resolve Freight on the load to cancel it."
                )

    @api.constrains("recommended_quote_id", "selected_quote_id")
    def _check_recommended_quote_relationship(self):
        for rec in self:
            if rec.recommended_quote_id and rec.recommended_quote_id.request_id != rec:
                raise ValidationError("A recommended quote must belong to its freight quote request.")
            if rec.selected_quote_id and (
                rec.selected_quote_id.request_id != rec
                or rec.selected_quote_id.company_id != rec.company_id
                or not rec.selected_quote_id.selected
            ):
                raise ValidationError("A resolved freight quote request must reference its own selected quote.")

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
        from odoo.addons.plasticos_logistics.services.state_machine import new_correlation_id

        for rec in self:
            rec._require_operator()
            correlation_id = new_correlation_id()
            rec._lock_decision()
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
                quote.with_context(**{_RFQ_INTERNAL_WRITE: _RFQ_INTERNAL_WRITE_TOKEN}).write(
                    {
                        "ranking_status": status,
                        "ranking_score": ranking.score if ranking.eligible else False,
                        "ranking_rank": rank_by_id.get(quote.id, False),
                        "ranking_policy_version": RANKING_POLICY_VERSION,
                        "ranking_reasoning": ranking.as_dict(),
                        "ranked_at": fields.Datetime.now(),
                    }
                )
            rec._rfq_write(
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
                correlation_id=correlation_id,
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
        internal = self.env.context.get(_RFQ_INTERNAL_WRITE) is _RFQ_INTERNAL_WRITE_TOKEN
        if "state" in vals:
            for rec in self:
                if not internal:
                    raise UserError("Freight quote request state changes require a validated freight command.")
                if vals["state"] != rec.state and vals["state"] not in self._REQUEST_TRANSITIONS[rec.state]:
                    raise UserError("Freight quote request transition is not permitted.")
        # ``readonly=True`` is a UI hint only; lifecycle and selection evidence
        # must be guarded server-side against direct ORM/RPC writes.
        lifecycle_evidence = {
            "sent_at",
            "resolved_at",
            "cancelled_at",
            "cancellation_reason",
            "failure_code",
            "selected_quote_id",
        }
        if lifecycle_evidence.intersection(vals) and not internal:
            raise UserError("Freight quote request lifecycle evidence may only change through a validated workflow.")
        if {"recommended_quote_id", "ranking_policy_version", "ranked_at"}.intersection(vals) and not internal:
            raise UserError("Freight ranking provenance may only change through the ranking workflow.")
        return super().write(vals)

    def unlink(self):
        raise UserError("Freight quote requests are audit evidence and cannot be deleted.")

    def action_select_quote(self):
        for rec in self:
            rec._require_operator()
            rec._lock_decision()
            rec.invalidate_recordset()
            if rec.state not in ("draft", "sent", "collecting"):
                raise UserError("Only an active freight quote request can be resolved.")
            # Validate the context before any write so a stale request leaves no partial state.
            rec._ensure_current_context()
            if rec.state == "draft":
                rec._rfq_write({"state": "collecting"})
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
                resolving_request=rec,
            )
            rec._rfq_write(
                {"selected_quote_id": selected.id, "resolved_at": fields.Datetime.now(), "state": "resolved"}
            )
            rec.load_id._freight_write({"selected_freight_quote_id": selected.id})
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

    @api.model_create_multi
    def create(self, vals_list):
        request_ids = [values["request_id"] for values in vals_list if values.get("request_id")]
        requests = self.env["plasticos.freight.quote.request"].browse(request_ids).exists()
        requests._require_operator()
        requests._ensure_active_for_child_evidence()
        for vals in vals_list:
            # The request form collects carrier, channel and destination only;
            # derive the required identity key so operators can add recipients.
            if not vals.get("idempotency_key"):
                vals["idempotency_key"] = recipient_idempotency_key(
                    vals.get("request_id"), vals.get("carrier_id"), vals.get("channel")
                )
        return super().create(vals_list)

    def _rfq_write(self, values):
        """Workflow-owned evidence write; only validated freight commands hold the token."""
        return self.with_context(**{_RFQ_INTERNAL_WRITE: _RFQ_INTERNAL_WRITE_TOKEN}).write(values)

    @api.constrains("company_id", "request_id")
    def _check_recipient_company(self):
        for rec in self:
            if rec.request_id.company_id != rec.company_id:
                raise ValidationError("Recipient company must match its freight quote request.")

    @api.constrains(
        "state",
        "attempt_count",
        "last_attempt_at",
        "sent_at",
        "response_at",
        "delivery_error_class",
        "outbound_message_ref",
    )
    def _check_recipient_state_evidence(self):
        """Keep send evidence truthful.

        Outbound delivery is not available in this slice; a carrier response is
        manual/inbound evidence and must never imply that PlasticOS sent an RFQ.
        Send facts are required only when an actual outbound attempt was recorded.
        """
        for rec in self:
            if rec.state == "sent" and (rec.attempt_count < 1 or not rec.sent_at):
                raise ValidationError("Sent recipients require a successful delivery attempt and sent time.")
            if rec.state == "responded" and not rec.response_at:
                raise ValidationError("Responded recipients require a response timestamp.")
            if rec.state == "delivery_failed" and (rec.attempt_count < 1 or not rec.delivery_error_class):
                raise ValidationError("Delivery failures require an attempt and error classification.")
            has_send_evidence = bool(rec.sent_at or rec.last_attempt_at or rec.outbound_message_ref)
            if has_send_evidence and rec.attempt_count < 1:
                raise ValidationError("Send evidence cannot exist without a recorded outbound attempt.")
            if rec.attempt_count >= 1 and not rec.last_attempt_at:
                raise ValidationError("A recorded outbound attempt requires an attempt timestamp.")
            if rec.state == "pending" and has_send_evidence:
                raise ValidationError("Pending recipients cannot carry send evidence.")

    def write(self, vals):
        protected = {"company_id", "request_id", "carrier_id", "channel", "idempotency_key"}
        if protected.intersection(vals):
            raise UserError("Freight quote recipient identity is immutable after creation.")
        internal = self.env.context.get(_RFQ_INTERNAL_WRITE) is _RFQ_INTERNAL_WRITE_TOKEN
        if "state" in vals and not internal:
            raise UserError("Recipient lifecycle changes require the validated freight response workflow.")
        # Delivery/response evidence is workflow-owned; ``readonly=True`` alone
        # does not stop direct ORM/RPC writes.
        delivery_evidence = {
            "attempt_count",
            "last_attempt_at",
            "sent_at",
            "response_at",
            "delivery_error_class",
            "outbound_message_ref",
        }
        if delivery_evidence.intersection(vals) and not internal:
            raise UserError("Recipient delivery and response evidence may only change through a validated workflow.")
        if "destination_snapshot" in vals:
            for rec in self:
                if rec.sent_at or rec.attempt_count:
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

    def init(self):
        """Enforce one selected quote per RFQ even under concurrent ORM commands."""
        # Atomic partial-index creation is required; ORM constraints cannot express `WHERE selected`.
        self.env.cr.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS plasticos_freight_quote_one_selected_per_request_idx
            ON plasticos_freight_quote (request_id)
            WHERE selected
            """
        )

    @api.model_create_multi
    def create(self, vals_list):
        if any(values.get("selected") for values in vals_list):
            raise UserError("Quote selection is only permitted through the locked selection workflow.")
        request_ids = [values["request_id"] for values in vals_list if values.get("request_id")]
        requests = self.env["plasticos.freight.quote.request"].browse(request_ids).exists()
        requests._require_operator()
        requests._ensure_active_for_child_evidence()
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
            recipient = rec.recipient_id
            if recipient.state not in ("cancelled", "responded"):
                # Record response provenance only. attempt_count, sent_at,
                # last_attempt_at and outbound_message_ref stay as the outbound
                # workflow left them (zero/unset while delivery is manual-only).
                recipient._rfq_write({"response_at": rec.responded_at, "state": "responded"})
            if rec.supersedes_quote_id:
                rec.supersedes_quote_id.with_context(**{_RFQ_INTERNAL_WRITE: _RFQ_INTERNAL_WRITE_TOKEN}).write(
                    {"lifecycle_state": "superseded"}
                )
        return records

    @api.constrains("company_id", "request_id", "recipient_id", "carrier_id")
    def _check_quote_relationships(self):
        for rec in self:
            if rec.request_id.company_id != rec.company_id or rec.recipient_id.company_id != rec.company_id:
                raise ValidationError("Quote evidence must remain within its request company.")
            if rec.recipient_id.request_id != rec.request_id or rec.recipient_id.carrier_id != rec.carrier_id:
                raise ValidationError("Quote recipient and carrier must match the quote request.")

    @api.constrains("supersedes_quote_id", "request_id", "carrier_id", "company_id")
    def _check_supersession_lineage(self):
        for rec in self:
            prior = rec.supersedes_quote_id
            if not prior:
                continue
            if prior == rec:
                raise ValidationError("A carrier response cannot supersede itself.")
            if (
                prior.request_id != rec.request_id
                or prior.carrier_id != rec.carrier_id
                or prior.company_id != rec.company_id
            ):
                raise ValidationError("A superseding response must belong to the same request, carrier, and company.")
            if prior.selected:
                raise ValidationError("A selected quote cannot be superseded; the request is already resolved.")
            if self.search_count([("supersedes_quote_id", "=", prior.id), ("id", "!=", rec.id)]):
                raise ValidationError("A carrier response may be superseded only once.")

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
            # Ranking input: mutable timeliness would silently change scores.
            "timeliness",
        }
        if protected.intersection(vals):
            raise UserError("Carrier response evidence is immutable; create a superseding quote instead.")
        if "selected" in vals and self.env.context.get(_RFQ_INTERNAL_SELECTION) is not _RFQ_INTERNAL_SELECTION_TOKEN:
            raise UserError("Quote selection is only permitted through the locked selection workflow.")
        if "lifecycle_state" in vals and self.env.context.get(_RFQ_INTERNAL_WRITE) is not _RFQ_INTERNAL_WRITE_TOKEN:
            raise UserError("Quote lifecycle changes require a validated supersession workflow.")
        ranking_fields = {
            "ranking_status",
            "ranking_score",
            "ranking_rank",
            "ranking_policy_version",
            "ranking_reasoning",
            "ranked_at",
        }
        if (
            ranking_fields.intersection(vals)
            and self.env.context.get(_RFQ_INTERNAL_WRITE) is not _RFQ_INTERNAL_WRITE_TOKEN
        ):
            raise UserError("Quote ranking provenance may only change through the ranking workflow.")
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
        from odoo.addons.plasticos_logistics.models.freight_governance import record_freight_event
        from odoo.addons.plasticos_logistics.services.state_machine import new_correlation_id

        for rec in self:
            rec.request_id._require_operator()
            correlation_id = new_correlation_id()
            rec.request_id._ensure_active_for_child_evidence()
            rec.invalidate_recordset()
            rec._check_selectable()
            (rec.request_id.quote_ids - rec).filtered("selected").with_context(
                **{_RFQ_INTERNAL_SELECTION: _RFQ_INTERNAL_SELECTION_TOKEN}
            ).write({"selected": False})
            rec.with_context(**{_RFQ_INTERNAL_SELECTION: _RFQ_INTERNAL_SELECTION_TOKEN}).write({"selected": True})
            record_freight_event(
                rec.env,
                event_type="freight_quote_selected",
                outcome_code="selected",
                load=rec.request_id.load_id,
                facts={"request_id": rec.request_id.id, "quote_id": rec.id},
                correlation_id=correlation_id,
            )
        return True
