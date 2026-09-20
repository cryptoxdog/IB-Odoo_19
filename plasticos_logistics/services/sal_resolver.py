"""Pure-ish Same As Last qualification against canonical executed-load history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from odoo import fields

from .freight_context import build_freight_context

SAL_WINDOW = timedelta(days=30)
QUALIFYING_STATES = ("picked_up", "delivered", "closed")
# Deterministic bound on the candidate history scan. The query is ordered by
# most recent movement first, so the newest same-lane records are always
# considered; anything beyond the bound is older than the SAL window in any
# realistic lane and is intentionally never scanned.
SAL_HISTORY_LIMIT = 200


@dataclass(frozen=True)
class SalDecision:
    """A non-mutating SAL evaluation result."""

    decision: str
    reason: str | None = None
    source_load_id: int | None = None
    context_fingerprint: str | None = None
    movement_age_seconds: float | None = None


def _company_for(load):
    """Use the existing sale-order company; never infer cross-company ownership."""
    return load.sale_order_id.company_id if load.sale_order_id and load.sale_order_id.company_id else None


def _movement_at(load):
    if load.state in ("delivered", "closed") and load.delivered_at:
        return load.delivered_at
    if load.state == "picked_up" and load.dispatched_at:
        return load.dispatched_at
    return None


def resolve_sal(load) -> SalDecision:
    """Evaluate a load deterministically without mutating it or creating RFQs."""
    if load.state != "ready_confirmed":
        return SalDecision("not_eligible", "not_ready_confirmed")
    if load.rate_amount or load.carrier_id:
        return SalDecision("not_eligible", "already_rate_confirmed")

    company = _company_for(load)
    context = build_freight_context(load)
    if not company or not context:
        return SalDecision("not_eligible", "missing_lane_identity")

    cutoff = fields.Datetime.now() - SAL_WINDOW
    # Company scope is enforced at query level (the load company is the
    # sale-order company) and re-checked per candidate below, so cross-company
    # history is never scanned, let alone reused.
    candidates = load.env["plasticos.load"].search(
        [
            ("id", "!=", load.id),
            ("sale_order_id.company_id", "=", company.id),
            ("pickup_partner_id", "=", load.pickup_partner_id.id),
            ("delivery_partner_id", "=", load.delivery_partner_id.id),
            ("state", "in", QUALIFYING_STATES),
            ("carrier_id", "!=", False),
            ("rate_amount", ">", 0),
        ],
        order="delivered_at desc, dispatched_at desc, id desc",
        limit=SAL_HISTORY_LIMIT,
    )
    saw_movement = False
    saw_old_movement = False
    saw_missing_rate = False
    saw_inactive_carrier = False
    for candidate in candidates:
        if _company_for(candidate) != company:
            continue
        # Compare scalar intake IDs: ``intake_id`` is a recordset while
        # ``repeat_stream_id`` is the intake's integer ID.
        candidate_intake_id = candidate.transaction_id.intake_id.id if candidate.transaction_id else None
        if not candidate_intake_id or candidate_intake_id != context.repeat_stream_id:
            continue
        candidate_context = build_freight_context(candidate)
        if not candidate_context or candidate_context.fingerprint != context.fingerprint:
            continue
        moved_at = _movement_at(candidate)
        if not moved_at:
            continue
        saw_movement = True
        if moved_at < cutoff:
            saw_old_movement = True
            continue
        if not candidate.rate_amount or not candidate.rate_currency_id:
            saw_missing_rate = True
            continue
        if not candidate.carrier_id.active:
            saw_inactive_carrier = True
            continue
        age = (fields.Datetime.now() - moved_at).total_seconds()
        return SalDecision(
            "hit",
            source_load_id=candidate.id,
            context_fingerprint=context.fingerprint,
            movement_age_seconds=age,
        )
    if saw_inactive_carrier:
        return SalDecision("miss", "prior_carrier_inactive", context_fingerprint=context.fingerprint)
    if saw_missing_rate:
        return SalDecision("miss", "prior_rate_missing", context_fingerprint=context.fingerprint)
    if saw_old_movement:
        return SalDecision("miss", "prior_movement_too_old", context_fingerprint=context.fingerprint)
    if saw_movement:
        return SalDecision("miss", "prior_record_ambiguous", context_fingerprint=context.fingerprint)
    return SalDecision("miss", "no_prior_movement", context_fingerprint=context.fingerprint)
