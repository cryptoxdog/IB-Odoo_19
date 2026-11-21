"""Schedule window, appointment rules and shadow-draft wording (ADR-135 §5–§8).

Pure: no Odoo import. Business days are Monday–Friday. No holiday calendar is
applied, because ADR-135 names none. An unknown transit, weight or export fact
stays unknown and does not become a date, a zero or a send.

Projection: l9.projection/coding-agent-execution@1 bundle f8e44d1536cb,
source l9.source/invariants@1 (L9-UNKNOWN-001, L9-AUTH-001).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TypeGuard

PARAM_MILES_PER_DAY = "plasticos_logistics.schedule_miles_per_day"
PARAM_LEAD_DAYS = "plasticos_logistics.schedule_lead_days"
PARAM_BUFFER_DAYS = "plasticos_logistics.schedule_buffer_days"
PARAM_FAR_GAP_DAYS = "plasticos_logistics.schedule_far_gap_days"
PARAM_NEAR_WINDOW_DAYS = "plasticos_logistics.schedule_near_window_days"

PARAMETER_DEFAULTS: tuple[tuple[str, str], ...] = (
    (PARAM_MILES_PER_DAY, "500"),
    (PARAM_LEAD_DAYS, "2"),
    (PARAM_BUFFER_DAYS, "1"),
    (PARAM_FAR_GAP_DAYS, "3"),
    (PARAM_NEAR_WINDOW_DAYS, "7"),
)

FLAG_EARLIER = "earlier_option_available"
FLAG_READY_FAR = "ready_slot_far"
FLAG_NEEDS_SLOT = "needs_delivery_slot"
FLAG_DOCK_UNVERIFIED = "dock_rule_unverified"
FLAG_HOURS_UNKNOWN = "site_hours_unknown"
FLAG_WEIGHT_UNKNOWN = "weight_unknown"
FLAG_EXPORT_CUTOFF = "export_cutoff_notice"
FLAG_BOOKING_ROLL = "booking_roll_request"

AUDIENCE_SHIPPER = "shipper"
AUDIENCE_BUYER = "buyer"
AUDIENCE_PICKUP_SITE = "pickup_site"
AUDIENCE_DELIVERY_SITE = "delivery_site"

SCHEDULE_PURPOSES: tuple[str, ...] = (
    FLAG_EARLIER,
    FLAG_READY_FAR,
    FLAG_NEEDS_SLOT,
    FLAG_DOCK_UNVERIFIED,
    FLAG_HOURS_UNKNOWN,
    FLAG_WEIGHT_UNKNOWN,
    FLAG_EXPORT_CUTOFF,
    FLAG_BOOKING_ROLL,
)

PROPOSAL_FLAGS = frozenset({FLAG_EARLIER, FLAG_READY_FAR, FLAG_NEEDS_SLOT})

R022_CANCEL_REASON = "Delivery slot changed; rebook the pickup (BRS-03-R022)."
R018_CANCEL_REASON = "Replaced when a different appointment on this side was accepted (BRS-03-R018)."

BOOK_X = "book_x"
BOOK_Y_ACCEPT = "book_y_accept"
WAIT = "wait"
UNANSWERED = "unanswered"
ALLOW = "allow"
REFUSE = "refuse"
NEED_REASON = "need_reason"
OVERRIDE = "override"


@dataclass(frozen=True)
class ScheduleSettings:
    miles_per_day: int = 500
    lead_days: int = 2
    buffer_days: int = 1
    far_gap_days: int = 3
    near_window_days: int = 7


@dataclass(frozen=True)
class ScheduleFacts:
    today: date
    expected_ready_date: date | None = None
    ready_confirmed: bool = False
    ready_net_weight_lbs: float | None = None
    minimum_net_weight: float | None = None
    miles: float | None = None
    quote_transit_days: int | None = None
    delivery_rule: str | None = None
    pickup_rule: str | None = None
    accepted_delivery: date | None = None
    available_slots: tuple[date, ...] = ()
    pickup_site: bool = False
    delivery_site: bool = False
    pickup_confirmed_on: date | None = None
    delivery_confirmed_on: date | None = None
    pickup_hours: str | None = None
    delivery_hours: str | None = None
    pickup_tz: str | None = None
    delivery_tz: str | None = None
    buyer_po_ref: str = ""
    settings: ScheduleSettings = ScheduleSettings()


@dataclass(frozen=True)
class ScheduleWindow:
    transit_days: int | None
    earliest_pickup: date | None
    earliest_delivery: date | None


@dataclass(frozen=True)
class ScheduleFlag:
    code: str
    audience: str
    body: str
    detail: str


@dataclass(frozen=True)
class ExportWindow:
    cutoff: date | None
    staging_deadline: date | None
    next_cutoff: date | None
    next_vessel: str | None
    known_gap: str | None
    buyer_provided: bool | None
    ready_date: date | None


def add_business_days(start: date, days: int) -> date:
    """Move ``days`` Monday–Friday steps. Zero leaves ``start`` where it is."""
    if days == 0:
        return start
    step = 1 if days > 0 else -1
    remaining = abs(days)
    cursor = start
    while remaining:
        cursor += timedelta(days=step)
        if cursor.weekday() < 5:
            remaining -= 1
    return cursor


def business_days_after(start: date, end: date) -> int:
    """Monday–Friday days strictly after ``start`` through ``end``."""
    if end <= start:
        return 0
    count = 0
    cursor = start
    while cursor < end:
        cursor += timedelta(days=1)
        if cursor.weekday() < 5:
            count += 1
    return count


def on_or_before_business_day(day: date) -> date:
    cursor = day
    while cursor.weekday() >= 5:
        cursor -= timedelta(days=1)
    return cursor


def weight_is_known(weight: float | None) -> TypeGuard[float]:
    """A full net weight is known only when it is a positive number. Zero is unset."""
    return weight is not None and weight > 0


def minimum_exists(minimum: float | None) -> TypeGuard[float]:
    return minimum is not None and minimum > 0


def weight_blocks_proposals(weight: float | None, minimum: float | None) -> bool:
    """ADR-135 §8: ask for the full weight before proposing any slot."""
    return minimum_exists(minimum) and not weight_is_known(weight)


def transit_day_count(quote_days: int | None, miles: float | None, miles_per_day: int) -> int | None:
    """Accepted quote transit, otherwise ceil(miles / miles per day). Unknown stays unknown."""
    if quote_days is not None:
        return max(0, int(quote_days))
    if miles is None or miles_per_day <= 0:
        return None
    return math.ceil(miles / miles_per_day)


def compute_window(facts: ScheduleFacts) -> ScheduleWindow:
    settings = facts.settings
    transit = transit_day_count(facts.quote_transit_days, facts.miles, settings.miles_per_day)
    earliest_pickup = add_business_days(facts.today, settings.lead_days)
    if facts.expected_ready_date is not None:
        earliest_pickup = max(facts.expected_ready_date, earliest_pickup)
    earliest_delivery = None if transit is None else add_business_days(earliest_pickup, transit)
    return ScheduleWindow(transit, earliest_pickup, earliest_delivery)


def staging_deadline(slot: date, transit: int, settings: ScheduleSettings) -> date:
    """Slot minus transit, buffer and lead, on a business day."""
    return on_or_before_business_day(add_business_days(slot, -(transit + settings.buffer_days + settings.lead_days)))


def decision_date_for(slot: date, transit: int, settings: ScheduleSettings) -> date:
    """Last business day Linda can still accept the slot. After it, she falls back."""
    return staging_deadline(slot, transit, settings)


def earlier_slot_outcome(answer: str | None, today: date, decision: date) -> str:
    """Yes books X. No, or no answer after the decision date, books Y and accepts it.

    An unknown answer is not a yes. On the decision date itself the ask is still open.
    """
    normalized = (answer or "").strip().lower()
    if normalized == "yes":
        return BOOK_X
    if normalized == "no":
        return BOOK_Y_ACCEPT
    if (not normalized or normalized == UNANSWERED) and today > decision:
        return BOOK_Y_ACCEPT
    return WAIT


def light_load_decision(
    actor_is_linda: bool,
    weight: float | None,
    minimum: float | None,
    override_reason: str | None,
) -> str:
    """Linda is refused a light load. A person may override only with a recorded reason."""
    if not weight_is_known(weight) or not minimum_exists(minimum) or weight >= minimum:
        return ALLOW
    if actor_is_linda:
        return REFUSE
    if not (override_reason or "").strip():
        return NEED_REASON
    return OVERRIDE


def may_open_pickup_appointment(pickup_rule: str | None, ready_confirmed: bool) -> bool:
    """FCFS pickup never gets a pickup appointment, including once the load is ready.

    ``ready_confirmed`` is part of the call so the BRS-03-R019 case is visible:
    readiness does not turn FCFS into an appointment.
    """
    del ready_confirmed
    return pickup_rule == "appointment"


def appointments_to_open(pickup_rule: str | None, delivery_rule: str | None, ready_confirmed: bool) -> list[str]:
    opened: list[str] = []
    if delivery_rule == "appointment":
        opened.append("delivery")
    if may_open_pickup_appointment(pickup_rule, ready_confirmed):
        opened.append("pickup")
    return opened


def hours_default(site_hours: str | None, config_default: str) -> str:
    text = (site_hours or "").strip()
    return text or config_default


def _earlier_pair(facts: ScheduleFacts, earliest_delivery: date) -> tuple[date, date] | None:
    settings = facts.settings
    candidates = sorted({slot for slot in facts.available_slots if slot >= facts.today})
    for slot_x in candidates:
        if slot_x >= earliest_delivery:
            continue
        if business_days_after(facts.today, slot_x) > settings.near_window_days:
            continue
        later = [slot for slot in candidates if slot > slot_x]
        if not later:
            continue
        slot_y = later[0]
        if business_days_after(slot_x, slot_y) > settings.far_gap_days:
            return slot_x, slot_y
    return None


def _earlier_body(slot_x: date, slot_y: date, deadline: date) -> str:
    return (
        f"The buyer has an open delivery slot on {slot_x.isoformat()}, and the next one is "
        f"{slot_y.isoformat()}. To make {slot_x.isoformat()}, the full load must be staged by "
        f"{deadline.isoformat()}. Can you have it ready at full weight by then?"
    )


def _ready_far_body(po_ref: str, earliest: date, slot: date) -> str:
    label = po_ref.strip() or "the order"
    return (
        f"Material for your PO {label} is ready. We can deliver as early as {earliest.isoformat()}. "
        f"Is there any chance of a slot sooner than {slot.isoformat()}?"
    )


def _needs_slot_body(earliest: date) -> str:
    return f"Ready now. Can we book delivery for {earliest.isoformat()} or later?"


def _dock_body() -> str:
    return "Do you require an appointment, or is it first come, first served?"


def _hours_body() -> str:
    return "What are your shipping hours, and what time zone are they in?"


def _weight_body() -> str:
    return (
        "What date will the full load be ready, and what full net weight in pounds will be staged? "
        "A delivery slot is not proposed until that weight is known."
    )


def _proposal_flags(facts: ScheduleFacts, window: ScheduleWindow) -> list[ScheduleFlag]:
    if weight_blocks_proposals(facts.ready_net_weight_lbs, facts.minimum_net_weight):
        return [ScheduleFlag(FLAG_WEIGHT_UNKNOWN, "shipper", _weight_body(), "weight")]
    if window.earliest_delivery is None or window.transit_days is None:
        return []
    flags: list[ScheduleFlag] = []
    pair = _earlier_pair(facts, window.earliest_delivery)
    if pair is not None:
        slot_x, slot_y = pair
        deadline = staging_deadline(slot_x, window.transit_days, facts.settings)
        flags.append(
            ScheduleFlag(
                FLAG_EARLIER,
                "shipper",
                _earlier_body(slot_x, slot_y, deadline),
                f"{slot_x.isoformat()}:{slot_y.isoformat()}",
            )
        )
    if (
        facts.ready_confirmed
        and facts.accepted_delivery is not None
        and business_days_after(window.earliest_delivery, facts.accepted_delivery) > facts.settings.far_gap_days
    ):
        flags.append(
            ScheduleFlag(
                FLAG_READY_FAR,
                "buyer",
                _ready_far_body(facts.buyer_po_ref, window.earliest_delivery, facts.accepted_delivery),
                facts.accepted_delivery.isoformat(),
            )
        )
    if facts.ready_confirmed and facts.delivery_rule == "appointment" and facts.accepted_delivery is None:
        flags.append(
            ScheduleFlag(
                FLAG_NEEDS_SLOT,
                "buyer",
                _needs_slot_body(window.earliest_delivery),
                window.earliest_delivery.isoformat(),
            )
        )
    return flags


def _site_flags(facts: ScheduleFacts) -> list[ScheduleFlag]:
    flags: list[ScheduleFlag] = []
    dock_body = _dock_body()
    hours_body = _hours_body()
    if facts.pickup_site and facts.pickup_confirmed_on is None:
        flags.append(ScheduleFlag(FLAG_DOCK_UNVERIFIED, "pickup_site", dock_body, "pickup"))
    if facts.delivery_site and facts.delivery_confirmed_on is None:
        flags.append(ScheduleFlag(FLAG_DOCK_UNVERIFIED, "delivery_site", dock_body, "delivery"))
    if facts.pickup_site and (not (facts.pickup_hours or "").strip() or not (facts.pickup_tz or "").strip()):
        flags.append(ScheduleFlag(FLAG_HOURS_UNKNOWN, "pickup_site", hours_body, "pickup"))
    if facts.delivery_site and (not (facts.delivery_hours or "").strip() or not (facts.delivery_tz or "").strip()):
        flags.append(ScheduleFlag(FLAG_HOURS_UNKNOWN, "delivery_site", hours_body, "delivery"))
    return flags


def evaluate_flags(facts: ScheduleFacts) -> list[ScheduleFlag]:
    """The five ADR-135 §7 flags, plus the §8 weight ask that blocks slot proposals."""
    return [*_proposal_flags(facts, compute_window(facts)), *_site_flags(facts)]


def export_notices(installed: bool, window: ExportWindow | None) -> list[ScheduleFlag]:
    """Early cutoff notice and the buyer roll request. Nothing while Export is uninstalled.

    ``booking_amend`` is not produced here. It stays the announcement of an accepted revision.
    A buyer who did not provide the booking, or whose role is unknown, is not emailed.
    """
    if not installed or window is None:
        return []
    if window.ready_date is None or window.cutoff is None or window.ready_date <= window.cutoff:
        return []
    if window.next_cutoff is None and not (window.next_vessel or "").strip():
        follow = "The next cutoff or vessel is not on record."
    else:
        vessel = (window.next_vessel or "").strip() or "not on record"
        nxt = window.next_cutoff.isoformat() if window.next_cutoff else "not on record"
        follow = f"The next cutoff is {nxt} on vessel {vessel}."
    staged = window.staging_deadline.isoformat() if window.staging_deadline else "not on record"
    known_gap = (window.known_gap or "").strip()
    gap = f"{known_gap} " if known_gap else ""
    notice = (
        f"{gap}The booking cutoff is {window.cutoff.isoformat()}. To make it, the full load must be "
        f"staged by {staged}. {follow}"
    )
    flags = [ScheduleFlag(FLAG_EXPORT_CUTOFF, "shipper", notice.strip(), window.cutoff.isoformat())]
    if window.buyer_provided is True:
        flags.append(
            ScheduleFlag(
                FLAG_BOOKING_ROLL,
                "buyer",
                f"The shipper cannot make the cutoff of {window.cutoff.isoformat()}. Please roll the booking.",
                window.cutoff.isoformat(),
            )
        )
    return flags


def acceptance_effects(
    side: str,
    new_slot: tuple,
    new_will_be_accepted: bool,
    current_accepted: dict[str, tuple],
) -> list[tuple]:
    """Accept the replacement first. Cancel an accepted slot only in that same plan.

    A different accepted delivery slot then cancels the dependent pickup (BRS-03-R022).
    The plan reads only this load's accepted slots (BRS-03-R021).
    """
    if not new_will_be_accepted:
        return []
    effects: list[tuple] = [("accept", side, new_slot)]
    current = current_accepted.get(side)
    if current is None or current == new_slot:
        return effects
    effects.append(("cancel", side, current, R018_CANCEL_REASON))
    if side == "delivery":
        pickup = current_accepted.get("pickup")
        if pickup is not None:
            effects.append(("cancel", "pickup", pickup, R022_CANCEL_REASON))
            effects.append(("rebook", "pickup"))
    return effects


def plan_appointment_backfill(orders: list[dict]) -> tuple[list[dict], dict[str, int]]:
    """One requested delivery appointment per sale order that already asked.

    A second pass, once those load ids are in ``existing_delivery_load_ids``, creates nothing.
    """
    plans: list[dict] = []
    seen = already = skipped = 0
    for order in orders:
        seen += 1
        loads = list(order.get("load_ids") or [])
        existing = set(order.get("existing_delivery_load_ids") or [])
        if any(load_id in existing for load_id in loads):
            already += 1
            continue
        if not loads:
            skipped += 1
            continue
        plans.append({"sale_order_id": order["sale_order_id"], "load_id": min(loads)})
    counts = {
        "rows_seen": seen,
        "rows_created": len(plans),
        "already_present": already,
        "skipped_no_load": skipped,
    }
    return plans, counts
