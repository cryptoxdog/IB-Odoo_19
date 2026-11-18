"""Scheduled enrichment sweep: settings parsing and buyer selection (pure, no Odoo).

Odoo owns WHICH buyers are swept; EIE owns the run and enforces the budget as
min(daily_budget_usd, an EIE ceiling) per tenant per UTC day (ADR-012
amendment 2026-11-15). Settings are system parameters only (operator-approved:
no stored field on any business model). Every value is validated on read; a
malformed value fails closed (the sweep does not run) instead of widening the
selection.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta

ICP_PREFIX = "plasticos.gate.sweep_"
ICP_ENABLED = "plasticos.gate.sweep_enabled"
ICP_DAILY_BUDGET_USD = "plasticos.gate.sweep_daily_budget_usd"
ICP_MAX_CANDIDATES = "plasticos.gate.sweep_max_candidates"
ICP_COOLDOWN_DAYS = "plasticos.gate.sweep_cooldown_days"
ICP_CAPABILITY_TYPE_CODES = "plasticos.gate.sweep_process_types"
ICP_APPLICATION_CLASSES = "plasticos.gate.sweep_application_classes"
ICP_FEEDSTOCK_TYPES = "plasticos.gate.sweep_feedstock_types"
ICP_CAPABILITY_TYPE_IDS = "plasticos.gate.sweep_capability_type_ids"
ICP_POLYMER_IDS = "plasticos.gate.sweep_accepted_polymer_ids"
ICP_MIN_CAPACITY_LBS_MONTH = "plasticos.gate.sweep_min_capacity_lbs_month"

DEFAULT_DAILY_BUDGET_USD = 5.0
# 50: at the $5 starting cap that leaves ~$0.10 per facility of headroom, keeps
# one send packet well inside the 30 s caller budget, and is a day's review
# load an operator can actually clear. EIE stops at its budget regardless.
DEFAULT_MAX_CANDIDATES = 50
MAX_CANDIDATES_CEILING = 500
DEFAULT_COOLDOWN_DAYS = 30
MAX_COOLDOWN_DAYS = 3650

_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"", "0", "false", "no", "off"}


class SweepSettingsError(ValueError):
    """A sweep system parameter is malformed; the sweep must not run on it."""


@dataclass(frozen=True, slots=True)
class SweepSettings:
    enabled: bool = False
    daily_budget_usd: float = DEFAULT_DAILY_BUDGET_USD
    max_candidates: int = DEFAULT_MAX_CANDIDATES
    cooldown_days: int = DEFAULT_COOLDOWN_DAYS
    capability_type_codes: tuple[str, ...] = ()
    application_classes: tuple[str, ...] = ()
    feedstock_types: tuple[str, ...] = ()
    capability_type_ids: tuple[int, ...] = ()
    polymer_ids: tuple[int, ...] = ()
    min_capacity_lbs_month: int = 0


@dataclass(frozen=True, slots=True)
class SelectionKeys:
    """The selection keys the facility-profile fields accept (read from the live model)."""

    capability_type_codes: frozenset[str] = field(default_factory=frozenset)
    application_classes: frozenset[str] = field(default_factory=frozenset)
    feedstock_types: frozenset[str] = field(default_factory=frozenset)


def parse_bool(raw: str | None, key: str) -> bool:
    value = (raw or "").strip().lower()
    if value in _TRUTHY:
        return True
    if value in _FALSY:
        return False
    raise SweepSettingsError(f"{key} must be a boolean, got {raw!r}")


def parse_float(raw: str | None, key: str, default: float, *, minimum: float, exclusive_min: bool = False) -> float:
    value = (raw or "").strip()
    if not value:
        return default
    try:
        number = float(value)
    except ValueError as exc:
        raise SweepSettingsError(f"{key} is not a number: {raw!r}") from exc
    too_low = number <= minimum if exclusive_min else number < minimum
    if not math.isfinite(number) or too_low:
        raise SweepSettingsError(f"{key} is out of range: {raw!r}")
    return number


def parse_int(raw: str | None, key: str, default: int, *, minimum: int, maximum: int) -> int:
    value = (raw or "").strip()
    if not value:
        return default
    try:
        number = int(value)
    except ValueError as exc:
        raise SweepSettingsError(f"{key} is not an integer: {raw!r}") from exc
    if number < minimum or number > maximum:
        raise SweepSettingsError(f"{key} must be between {minimum} and {maximum}, got {number}")
    return number


def parse_list(raw: str | None, key: str, *, allowed: Iterable[str] | None = None, ints: bool = False) -> tuple:
    """A JSON list or a comma list; empty means "no filter". Unknown keys fail closed."""
    value = (raw or "").strip()
    if not value:
        return ()
    if value.startswith("["):
        try:
            items = json.loads(value)
        except json.JSONDecodeError as exc:
            raise SweepSettingsError(f"{key} is not a JSON list: {raw!r}") from exc
        if not isinstance(items, list):
            raise SweepSettingsError(f"{key} is not a list: {raw!r}")
    else:
        items = [part.strip() for part in value.split(",") if part.strip()]
    out: list = []
    for item in items:
        if ints:
            if isinstance(item, bool):
                raise SweepSettingsError(f"{key} holds a non-id {item!r}")
            try:
                number = int(item)
            except (TypeError, ValueError) as exc:
                raise SweepSettingsError(f"{key} holds a non-id {item!r}") from exc
            if number <= 0 or str(number) != str(item).strip():
                raise SweepSettingsError(f"{key} holds a non-id {item!r}")
            out.append(number)
            continue
        if not isinstance(item, str) or not item.strip():
            raise SweepSettingsError(f"{key} holds a non-key {item!r}")
        out.append(item.strip())
    if allowed is not None:
        unknown = sorted(set(out) - set(allowed))
        if unknown:
            raise SweepSettingsError(f"{key} names unknown key(s) {unknown}")
    return tuple(sorted(set(out)))


def dump_list(values: Iterable) -> str:
    """The canonical stored form (a sorted JSON list; empty string when empty)."""
    items = sorted(set(values))
    return json.dumps(items) if items else ""


def read_settings(get_param: Callable[[str], str | None], keys: SelectionKeys) -> SweepSettings:
    return SweepSettings(
        enabled=parse_bool(get_param(ICP_ENABLED), ICP_ENABLED),
        daily_budget_usd=parse_float(
            get_param(ICP_DAILY_BUDGET_USD),
            ICP_DAILY_BUDGET_USD,
            DEFAULT_DAILY_BUDGET_USD,
            minimum=0.0,
            exclusive_min=True,
        ),
        max_candidates=parse_int(
            get_param(ICP_MAX_CANDIDATES),
            ICP_MAX_CANDIDATES,
            DEFAULT_MAX_CANDIDATES,
            minimum=1,
            maximum=MAX_CANDIDATES_CEILING,
        ),
        cooldown_days=parse_int(
            get_param(ICP_COOLDOWN_DAYS), ICP_COOLDOWN_DAYS, DEFAULT_COOLDOWN_DAYS, minimum=0, maximum=MAX_COOLDOWN_DAYS
        ),
        capability_type_codes=parse_list(
            get_param(ICP_CAPABILITY_TYPE_CODES), ICP_CAPABILITY_TYPE_CODES, allowed=keys.capability_type_codes
        ),
        application_classes=parse_list(
            get_param(ICP_APPLICATION_CLASSES), ICP_APPLICATION_CLASSES, allowed=keys.application_classes
        ),
        feedstock_types=parse_list(get_param(ICP_FEEDSTOCK_TYPES), ICP_FEEDSTOCK_TYPES, allowed=keys.feedstock_types),
        capability_type_ids=parse_list(get_param(ICP_CAPABILITY_TYPE_IDS), ICP_CAPABILITY_TYPE_IDS, ints=True),
        polymer_ids=parse_list(get_param(ICP_POLYMER_IDS), ICP_POLYMER_IDS, ints=True),
        min_capacity_lbs_month=parse_int(
            get_param(ICP_MIN_CAPACITY_LBS_MONTH), ICP_MIN_CAPACITY_LBS_MONTH, 0, minimum=0, maximum=2**31 - 1
        ),
    )


def facility_domain(settings: SweepSettings) -> list:
    """The Odoo domain over plasticos.facility.profile for sweep-eligible BUYER facilities.

    A buyer is a partner with customer_rank > 0. The rank may sit on the site,
    on its commercial partner, or on the parent company when the site is its
    own commercial partner (a company child with is_company set). Lead-owned
    profiles (no partner) are never candidates. Empty filters do not narrow.
    Capability and inbound-polymer filters replace the retired equipment,
    process and accepted-polymer fields (ADR-134).
    """
    domain: list = [
        ("active", "=", True),
        ("partner_id", "!=", False),
        ("partner_id.active", "=", True),
        "|",
        "|",
        ("partner_id.customer_rank", ">", 0),
        ("partner_id.commercial_partner_id.customer_rank", ">", 0),
        ("partner_id.parent_id.commercial_partner_id.customer_rank", ">", 0),
    ]
    if settings.capability_type_codes:
        domain.append(("capability_ids.capability_type_id.code", "in", list(settings.capability_type_codes)))
    if settings.application_classes:
        domain.append(("application_class", "in", list(settings.application_classes)))
    if settings.feedstock_types:
        domain.append(("feedstock_type", "in", list(settings.feedstock_types)))
    if settings.capability_type_ids:
        domain.append(("capability_ids.capability_type_id", "in", list(settings.capability_type_ids)))
    if settings.polymer_ids:
        domain.append(
            (
                "partner_id.material_profile_ids",
                "any",
                [("polymer_id", "in", list(settings.polymer_ids)), ("direction", "=", "in")],
            )
        )
    if settings.min_capacity_lbs_month:
        domain.append(("capacity_lbs_month", ">=", settings.min_capacity_lbs_month))
    return domain


@dataclass(frozen=True, slots=True)
class FacilityHistory:
    """One eligible facility and its converge v2 enrichment history."""

    facility_id: int
    last_enriched_at: datetime | None = None
    in_review: bool = False
    # Already sent in a sweep whose results are not yet collected.
    pending_in_sweep: bool = False


def order_candidates(history: Sequence[FacilityHistory], *, now: datetime, cooldown_days: int, cap: int) -> list[int]:
    """Drop facilities in review, pending in an open sweep, or enriched inside the cooldown.

    Order: oldest enrichment first, then id; then cap.

    Never-enriched facilities sort before every enriched one.
    """
    cutoff = now - timedelta(days=cooldown_days)
    eligible = [
        h
        for h in history
        if not h.in_review
        and not h.pending_in_sweep
        and (h.last_enriched_at is None or cooldown_days == 0 or h.last_enriched_at < cutoff)
    ]
    eligible.sort(key=lambda h: (h.last_enriched_at is not None, h.last_enriched_at or datetime.min, h.facility_id))
    return [h.facility_id for h in eligible[: max(cap, 0)]]
