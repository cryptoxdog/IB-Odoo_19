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

    The latest immutable calibration observation is preferred over mutable load
    display fields. A confirmed booked rate remains usable when calibration
    evidence does not exist.
    """
    from odoo.addons.plasticos_logistics.services.freight_estimation import FreightEvidence

    observations = records.env["plasticos.freight.calibration.observation"].search(
        [("load_id", "in", records.ids)], order="observed_at desc, id desc"
    )
    latest_observation_by_load = {}
    for observation in observations:
        latest_observation_by_load.setdefault(observation.load_id.id, observation)
    output = []
    for record in records:
        observation = latest_observation_by_load.get(record.id)
        if observation:
            amount = observation.actual_cost_amount
            currency = observation.currency_id
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


def legacy_lane_candidates(env, legacy_row, *, scan_limit=200):
    """Return ``(candidates, truncated, complete)`` for one legacy cache row.

    A legacy cache row has no company, and its reconciliation is one global,
    immutable row (ADR-129). The classification must therefore come from every
    load in the database, not from the actor's companies, or the first
    operator to run it would decide the answer for everyone.

    The scan runs over the whole load table, bounded at ``scan_limit``. A
    truncated scan is never classified as an exact historical match.

    ``complete`` is True only when the actor can read every load the scan
    found. When it is False the caller must not record a classification, and
    ``candidates`` is empty, so no load outside the actor's access leaves this
    function. ``candidates`` is bound to the actor's environment.
    """
    loads = env[PLASTICOS_LOAD]
    if not legacy_row.rate_date:
        return loads.browse(), False, True
    start = fields.Datetime.to_datetime(legacy_row.rate_date)
    end = start + timedelta(days=1)
    # sudo() justification: existence check only. Company isolation on
    # plasticos.load would hide another company's matching load, and a global
    # reconciliation recorded from that partial view would be permanently
    # wrong. The search is pinned to this legacy row's carrier, amount and
    # date; the elevated records are compared by id below and never returned.
    scanned = loads.sudo().search(  # sudo: bounded existence scan; records never returned (ADR-129)
        [
            ("carrier_id", "=", legacy_row.carrier_id.id),
            ("rate_amount", "=", legacy_row.rate_amount),
            ("rate_confirmed_at", ">=", start),
            ("rate_confirmed_at", "<", end),
            ("state", "in", ("rate_confirmed", "scheduled", "dispatched", "picked_up", "delivered", "closed")),
        ],
        order="rate_confirmed_at desc, id desc",
        limit=scan_limit + 1,
    )
    truncated = len(scanned) > scan_limit
    matches = scanned[:scan_limit].filtered(
        lambda load: (
            load.carrier_id.id == legacy_row.carrier_id.id
            and load.rate_amount == legacy_row.rate_amount
            and load.rate_confirmed_at
            and fields.Date.to_date(load.rate_confirmed_at) == legacy_row.rate_date
            and _legacy_lane_key(load) == legacy_row.lane_key
        )
    )
    # A truncated outcome is decided by every scanned load; any other outcome
    # by the lane matches. The actor must be able to read all of them.
    decisive = scanned if truncated else matches
    readable = loads.search([("id", "in", decisive.ids)]) if decisive else loads.browse()
    if len(readable) != len(decisive):
        return loads.browse(), truncated, False
    return loads.browse(matches.ids), truncated, True


def _legacy_lane_key(load):
    sale_order = load.sale_order_id
    if not sale_order or not sale_order.partner_shipping_id or not sale_order.partner_invoice_id:
        return None
    return f"{sale_order.partner_shipping_id.id}-{sale_order.partner_invoice_id.id}"
