"""Central, bounded historical evidence queries for Linda freight workflows."""

from __future__ import annotations

from datetime import timedelta

from odoo import fields

PLASTICOS_LOAD = "plasticos.load"


def recent_executed_lane_evidence(env, load, *, limit=20, days=365):
    """Return current-company executed records on the exact physical lane.

    The result is evidence only.  It never computes a freight price or selects
    a carrier, preserving Gate as the sole intelligence authority.
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


def bounded_evidence_payload(records):
    """Serialize non-sensitive, deterministic payload fields for Gate admission."""
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
