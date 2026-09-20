"""Central, bounded historical evidence queries for Linda freight workflows."""

from __future__ import annotations

from datetime import timedelta

from odoo import fields

PLASTICOS_LOAD = "plasticos.load"


def recent_executed_lane_evidence(env, load, *, limit=20, days=365):
    """Return current-company executed records on the exact physical lane.

    The result is evidence only. It never selects or awards a carrier.
    """
    company = getattr(load, "company_id", False) or (load.sale_order_id.company_id if load.sale_order_id else False)
    if not company or not load.pickup_partner_id or not load.delivery_partner_id:
        return env[PLASTICOS_LOAD].browse()
    cutoff = fields.Datetime.now() - timedelta(days=days)
    return (
        env[PLASTICOS_LOAD]
        .search(
            [
                ("id", "!=", load.id),
                ("company_id", "=", company.id),
                ("pickup_partner_id", "=", load.pickup_partner_id.id),
                ("delivery_partner_id", "=", load.delivery_partner_id.id),
                ("state", "in", ("delivered", "closed")),
                ("rate_amount", ">", 0),
                ("rate_currency_id", "!=", False),
                ("rate_confirmed_at", ">=", cutoff),
            ],
            order="rate_confirmed_at desc, id desc",
            limit=limit,
        )
        .filtered(lambda candidate: _load_company(candidate) == company)
    )


def recent_comparable_executed_evidence(env, load, *, candidate_limit=200, result_limit=20, days=365):
    """Return a deterministic, bounded company-local comparable-lane evidence set."""
    from odoo.addons.plasticos_logistics.services.freight_geometry import FreightCoordinateError, haversine_miles

    company = getattr(load, "company_id", False) or (load.sale_order_id.company_id if load.sale_order_id else False)
    if not company or not load.pickup_partner_id or not load.delivery_partner_id:
        return env[PLASTICOS_LOAD].browse()
    cutoff = fields.Datetime.now() - timedelta(days=days)
    candidates = (
        env[PLASTICOS_LOAD]
        .search(
            [
                ("id", "!=", load.id),
                ("company_id", "=", company.id),
                ("state", "in", ("delivered", "closed")),
                ("rate_amount", ">", 0),
                ("rate_currency_id", "!=", False),
                ("rate_confirmed_at", ">=", cutoff),
            ],
            order="rate_confirmed_at desc, id desc",
            limit=candidate_limit,
        )
        .filtered(lambda candidate: _load_company(candidate) == company)
    )
    try:
        current_lane = haversine_miles(
            load.pickup_partner_id.partner_latitude,
            load.pickup_partner_id.partner_longitude,
            load.delivery_partner_id.partner_latitude,
            load.delivery_partner_id.partner_longitude,
        )
    except FreightCoordinateError:
        return env[PLASTICOS_LOAD].browse()
    ranked = []
    for recency_index, candidate in enumerate(candidates):
        try:
            origin_delta = haversine_miles(
                load.pickup_partner_id.partner_latitude,
                load.pickup_partner_id.partner_longitude,
                candidate.pickup_partner_id.partner_latitude,
                candidate.pickup_partner_id.partner_longitude,
            )
            destination_delta = haversine_miles(
                load.delivery_partner_id.partner_latitude,
                load.delivery_partner_id.partner_longitude,
                candidate.delivery_partner_id.partner_latitude,
                candidate.delivery_partner_id.partner_longitude,
            )
            candidate_lane = haversine_miles(
                candidate.pickup_partner_id.partner_latitude,
                candidate.pickup_partner_id.partner_longitude,
                candidate.delivery_partner_id.partner_latitude,
                candidate.delivery_partner_id.partner_longitude,
            )
        except FreightCoordinateError:
            continue
        exact = origin_delta == 0 and destination_delta == 0
        lane_distance = origin_delta + destination_delta + abs(candidate_lane - current_lane)
        ranked.append((not exact, lane_distance, recency_index, candidate.id, candidate))
    ranked.sort(key=lambda row: (row[0], row[1], row[2], row[3]), reverse=False)
    return env[PLASTICOS_LOAD].browse([row[4].id for row in ranked[:result_limit]])


def bounded_evidence_payload(records):
    """Serialize non-sensitive, deterministic freight evidence fields."""
    return [
        {
            "load_id": record.id,
            "carrier_id": record.carrier_id.id if record.carrier_id else None,
            "rate_amount": record.rate_amount,
            "currency_id": record.rate_currency_id.id if record.rate_currency_id else None,
            "rate_confirmed_at": fields.Datetime.to_string(record.rate_confirmed_at)
            if record.rate_confirmed_at
            else None,
            "resolution_method": record.rate_resolution_method,
        }
        for record in records
    ]


def local_estimation_evidence(records):
    """Normalize executed outcomes for local Haversine-curve estimation.

    Actual freight cost is preferred when it is currency-bearing. A confirmed
    booked rate remains usable where actual cost has not yet been recorded.
    """
    from odoo.addons.plasticos_logistics.services.freight_estimation import FreightEvidence

    output = []
    for record in records:
        actual_currency = record.actual_freight_currency_id
        if record.actual_freight_recorded_at and actual_currency:
            amount = record.actual_freight_cost
            currency = actual_currency
            source_type = "executed_actual"
        elif record.rate_amount and record.rate_currency_id:
            amount = record.rate_amount
            currency = record.rate_currency_id
            source_type = "executed_booked_rate"
        else:
            continue
        output.append(
            FreightEvidence(
                source_load_id=record.id,
                carrier_id=record.carrier_id.id if record.carrier_id else None,
                amount=amount,
                currency_id=currency.id,
                origin_latitude=record.pickup_partner_id.partner_latitude,
                origin_longitude=record.pickup_partner_id.partner_longitude,
                destination_latitude=record.delivery_partner_id.partner_latitude,
                destination_longitude=record.delivery_partner_id.partner_longitude,
                occurred_at=record.delivered_at or record.rate_confirmed_at,
                evidence_kind=source_type,
            )
        )
    return output


def _load_company(load):
    return getattr(load, "company_id", False) or (load.sale_order_id.company_id if load.sale_order_id else False)


def legacy_lane_candidates(env, legacy_row):
    """Return only candidate loads whose historical lane key exactly matches a cache row."""
    candidates = env[PLASTICOS_LOAD].search(
        [("state", "in", ("rate_confirmed", "scheduled", "dispatched", "picked_up", "delivered", "closed"))],
        order="rate_confirmed_at desc, id desc",
    )
    return candidates.filtered(
        lambda load: (
            load.carrier_id == legacy_row.carrier_id
            and load.rate_amount == legacy_row.rate_amount
            and load.rate_confirmed_at
            and fields.Date.to_date(load.rate_confirmed_at) == legacy_row.rate_date
            and _legacy_lane_key(load) == legacy_row.lane_key
        )
    )


def _legacy_lane_key(load):
    sale_order = load.sale_order_id
    if not sale_order or not sale_order.partner_shipping_id or not sale_order.partner_invoice_id:
        return None
    return f"{sale_order.partner_shipping_id.id}-{sale_order.partner_invoice_id.id}"
