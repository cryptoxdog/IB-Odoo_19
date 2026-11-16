"""Enrichment sweep contract (Odoo side): the ONE module that knows the wire shape.

Contract authority (read-only): the EIE repository (Enrichment Inference Engine,
Quantum-L9) main at ``a606791`` (PR #352), ``docs/contracts/enrichment-sweep.md``. Section numbers
below cite that file. Two Gate actions:

* ``enrichment-sweep``          (section 3) — submit candidates and a daily budget.
* ``enrichment-sweep-results``  (section 6) — page what a sweep produced.

EIE owns the trigger, the targets and the budget (sections 3.4 and 4); Odoo owns
candidate selection and review (ADR-012 amendment 2026-11-15). Every other part
of PlasticOS depends on the frozen types below, never on raw dicts. The parsers
fail closed: a member, type, state or code the contract does not name rejects
the whole reply.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from .gate_contracts import _plain, freeze

# Named without a host-like token: Odoo production code knows no peer address (INV-ODOO-GATE-ONLY-EGRESS).
CONTRACT_REF = "EIE@a606791:docs/contracts/enrichment-sweep.md"

SWEEP_ACTION = "enrichment-sweep"
SWEEP_RESULTS_ACTION = "enrichment-sweep-results"
SWEEP_ACTIONS: tuple[str, ...] = (SWEEP_ACTION, SWEEP_RESULTS_ACTION)

# gate-integration ADR-005: the entity id is LOCKED to res.partner:<id>.
SWEEP_NODE_LABEL = "Facility"
_ENTITY_ID_RE = re.compile(r"^res\.partner:[1-9][0-9]*$")

# Section 6.2: the run state.
SWEEP_STATE_RUNNING = "running"
SWEEP_STATE_COMPLETED = "completed"
SWEEP_STATES = frozenset({SWEEP_STATE_RUNNING, SWEEP_STATE_COMPLETED})

# Section 3.3: rejection reasons of the immediate reply.
REJECT_REASONS = frozenset(
    {
        "invalid_candidate",
        "invalid_entity_id",
        "invalid_entity",
        "invalid_field_confidences",
        "node_label_required",
        "node_not_declared",
        "duplicate_entity_id",
        "candidate_cap_exceeded",
    }
)

# Sections 3.4 and 5: per-candidate skip reasons of a results page.
SKIP_REASONS = frozenset(
    {
        "no_readiness_gaps",
        "no_declared_targets",
        "budget_exhausted",
        "readiness_disabled",
        "readiness_refused",
        "readiness_failed",
        "readiness_malformed",
        "readiness_absent",
        "cartridge_unavailable",
        "budget_ledger_unavailable",
        "converge_failed",
        "sweep_failed",
    }
)

# Section 7: refusal codes. Both actions answer a failure packet whose message begins with one.
REFUSAL_DISABLED = "disabled"
REFUSAL_INVALID_REQUEST = "invalid_request"
REFUSAL_CARTRIDGE_UNAVAILABLE = "cartridge_unavailable"
REFUSAL_STORE_UNAVAILABLE = "sweep_store_unavailable"
REFUSAL_NOT_FOUND = "sweep_not_found"
REFUSAL_CODES = (
    REFUSAL_DISABLED,
    REFUSAL_INVALID_REQUEST,
    REFUSAL_CARTRIDGE_UNAVAILABLE,
    REFUSAL_STORE_UNAVAILABLE,
    REFUSAL_NOT_FOUND,
)
_REFUSAL_RE = re.compile(r"(?:^|[\s:(\[\"'])(" + "|".join(REFUSAL_CODES) + r"):")

_REPLY_KEYS = frozenset({"sweep_id", "accepted", "rejected"})
_PAGE_KEYS = frozenset({"sweep_id", "state", "results", "next_cursor", "budget", "skipped", "stats"})


class SweepContractError(ValueError):
    """A sweep request could not be built, or a reply does not match the contract."""


def _need(condition: bool, detail: str) -> None:
    if not condition:
        raise SweepContractError(detail)


def _is_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _exact_keys(raw: Mapping[str, Any], required: frozenset[str], where: str) -> None:
    keys = set(raw)
    missing = sorted(required - keys)
    unknown = sorted(keys - required)
    _need(not missing, f"{where} is missing {missing}")
    _need(not unknown, f"{where} carries unknown member(s) {unknown}")


def is_sweep_entity_id(value: Any) -> bool:
    return isinstance(value, str) and bool(_ENTITY_ID_RE.match(value))


def partner_id_of(entity_id: str) -> int:
    """The res.partner id an entity id names (ADR-005)."""
    _need(is_sweep_entity_id(entity_id), f"entity_id {entity_id!r} is not res.partner:<id>")
    return int(entity_id.split(":", 1)[1])


def refusal_code(message: str | None) -> str | None:
    """The section 7 code a failure message carries, or None for a transport failure."""
    match = _REFUSAL_RE.search(f" {message or ''}")
    return match.group(1) if match else None


# ── Requests (sections 1.1, 3.1, 6.1) ───────────────────────────────────────


@dataclass(frozen=True, slots=True)
class SweepCandidate:
    entity_id: str
    entity: Mapping[str, Any]
    node_label: str = SWEEP_NODE_LABEL
    field_confidences: Mapping[str, float] | None = None

    def __post_init__(self) -> None:
        _need(is_sweep_entity_id(self.entity_id), f"candidate entity_id {self.entity_id!r} is not res.partner:<id>")
        _need(self.node_label == SWEEP_NODE_LABEL, f"candidate node_label must be {SWEEP_NODE_LABEL!r}")
        _need(isinstance(self.entity, Mapping), "candidate entity is not an object")
        _need(all(_is_str(k) for k in self.entity), "candidate entity keys must be cartridge field names")
        if self.field_confidences is not None:
            for name, value in self.field_confidences.items():
                _need(_is_str(name) and _is_number(value) and 0.0 <= value <= 1.0, f"field_confidences.{name}")

    def to_dict(self) -> dict[str, Any]:
        members: list[tuple[str, Any]] = [
            ("entity_id", self.entity_id),
            ("node_label", self.node_label),
            ("entity", _plain(self.entity)),
        ]
        if self.field_confidences:
            members.append(("field_confidences", dict(self.field_confidences)))
        return dict(members)


@dataclass(frozen=True, slots=True)
class SweepRequest:
    candidates: tuple[SweepCandidate, ...]
    daily_budget_usd: float
    idempotency_key: str

    def __post_init__(self) -> None:
        _need(bool(self.candidates), "a sweep needs at least one candidate")
        ids = [c.entity_id for c in self.candidates]
        _need(len(ids) == len(set(ids)), "a sweep names each entity once")
        # Section 7: non-positive budget is invalid_request. EIE caps it (section 4); Odoo sets no ceiling.
        _need(_is_number(self.daily_budget_usd) and self.daily_budget_usd > 0, "daily_budget_usd must be > 0")
        _need(_is_str(self.idempotency_key), "idempotency_key is required")

    def to_dict(self) -> dict[str, Any]:
        members = (
            ("candidates", [c.to_dict() for c in self.candidates]),
            ("daily_budget_usd", float(self.daily_budget_usd)),
            ("idempotency_key", self.idempotency_key),
        )
        return dict(members)


@dataclass(frozen=True, slots=True)
class SweepResultsRequest:
    sweep_id: str
    cursor: str | None = None

    def __post_init__(self) -> None:
        _need(_is_str(self.sweep_id), "sweep_id is required")
        _need(self.cursor is None or _is_str(self.cursor), "cursor must be a non-empty string or None")

    def to_dict(self) -> dict[str, Any]:
        """Section 6.1: ``cursor`` is sent only with a ``next_cursor`` from the previous page."""
        payload: dict[str, Any] = dict((("sweep_id", self.sweep_id),))
        if self.cursor is not None:
            payload["cursor"] = self.cursor
        return payload


def build_sweep_idempotency_key(tenant: str, utc_date: str, entity_ids) -> str:
    """Deterministic: tenant + UTC date + sorted candidate ids (section 3.3 replays it)."""
    _need(_is_str(tenant), "tenant is required")
    _need(bool(re.match(r"^\d{4}-\d{2}-\d{2}$", utc_date or "")), "utc_date must be YYYY-MM-DD")
    ids = sorted(entity_ids)
    _need(bool(ids), "no candidate ids")
    digest = hashlib.sha256("\n".join(ids).encode("utf-8")).hexdigest()[:32]
    return f"odoo:enrichment-sweep:{tenant}:{utc_date}:{digest}"


# ── Replies (sections 3.2, 6.2) ─────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class SweepRejection:
    entity_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class SweepSendReply:
    sweep_id: str
    accepted: tuple[str, ...]
    rejected: tuple[SweepRejection, ...]

    @property
    def accepted_count(self) -> int:
        return len(self.accepted)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected)


def _entity_reasons(raw: Any, where: str, reasons: frozenset[str]) -> tuple[SweepRejection, ...]:
    _need(isinstance(raw, list), f"{where} is not a list")
    out = []
    for i, item in enumerate(raw):
        _need(isinstance(item, dict), f"{where}[{i}] is not an object")
        _exact_keys(item, frozenset({"entity_id", "reason"}), f"{where}[{i}]")
        _need(_is_str(item["entity_id"]), f"{where}[{i}].entity_id is missing")
        _need(item["reason"] in reasons, f"{where}[{i}].reason {item['reason']!r} is not a contract reason")
        out.append(SweepRejection(item["entity_id"], item["reason"]))
    return tuple(out)


def parse_sweep_send_reply(payload: Any, *, request: SweepRequest) -> SweepSendReply:
    """Parse the ``enrichment-sweep`` reply (section 3.2) or raise SweepContractError.

    ``accepted`` is a list of entity_id strings; ``rejected`` a list of
    ``{entity_id, reason}`` with a section 3.3 reason. Every named entity was
    sent, none twice. A replay returns the original reply (section 3.3).
    """
    _need(isinstance(payload, dict), "sweep reply is not an object")
    _exact_keys(payload, _REPLY_KEYS, "sweep reply")
    _need(_is_str(payload["sweep_id"]), "sweep reply sweep_id is missing")
    raw_acc = payload["accepted"]
    _need(isinstance(raw_acc, list), "sweep reply accepted is not a list")
    _need(all(_is_str(i) for i in raw_acc), "sweep reply accepted holds a non-string entity_id")
    accepted = tuple(raw_acc)
    rejected = _entity_reasons(payload["rejected"], "rejected", REJECT_REASONS)
    named = list(accepted) + [r.entity_id for r in rejected]
    sent = {c.entity_id for c in request.candidates}
    _need(len(named) == len(set(named)), "sweep reply names an entity twice")
    _need(set(named) <= sent, f"sweep reply names entities that were not sent: {sorted(set(named) - sent)}")
    return SweepSendReply(payload["sweep_id"], accepted, rejected)


@dataclass(frozen=True, slots=True)
class SweepResult:
    entity_id: str
    response: Mapping[str, Any]

    def response_dict(self) -> dict[str, Any]:
        return _plain(self.response)


@dataclass(frozen=True, slots=True)
class SweepResultsPage:
    sweep_id: str
    state: str
    results: tuple[SweepResult, ...]
    next_cursor: str | None
    budget: Mapping[str, Any]
    skipped: tuple[SweepRejection, ...]
    stats: Mapping[str, int]

    @property
    def finished(self) -> bool:
        """Section 6.2: ``next_cursor`` is null once completed and the last page was returned."""
        return self.next_cursor is None and self.state == SWEEP_STATE_COMPLETED

    def budget_dict(self) -> dict[str, Any]:
        return _plain(self.budget)

    def stats_dict(self) -> dict[str, int]:
        return dict(self.stats)


def parse_sweep_results_page(payload: Any, *, sweep_id: str) -> SweepResultsPage:
    """Parse one ``enrichment-sweep-results`` page (section 6.2) or raise SweepContractError.

    The page must be for ``sweep_id``. Each result's ``response`` is kept
    unchanged (frozen) and parsed by ``parse_sweep_converge_response_v2``.
    """
    _need(isinstance(payload, dict), "results reply is not an object")
    _exact_keys(payload, _PAGE_KEYS, "results reply")
    _need(payload["sweep_id"] == sweep_id, f"results reply is for sweep {payload['sweep_id']!r}, not {sweep_id!r}")
    state = payload["state"]
    _need(isinstance(state, str) and state in SWEEP_STATES, f"results reply state {state!r} is unrecognised")
    cursor = payload["next_cursor"]
    _need(cursor is None or _is_str(cursor), "next_cursor must be a non-empty string or null")
    budget = payload["budget"]
    _need(isinstance(budget, dict), "budget is not an object")
    for key, value in budget.items():
        _need(_is_number(value), f"budget.{key} is not a number")
    stats = payload["stats"]
    _need(isinstance(stats, dict), "stats is not an object")
    for key, value in stats.items():
        _need(
            _is_str(key) and isinstance(value, int) and not isinstance(value, bool) and value >= 0,
            f"stats.{key} is not a counter",
        )
    raw_results = payload["results"]
    _need(isinstance(raw_results, list), "results is not a list")
    results = []
    seen = set()
    for i, item in enumerate(raw_results):
        _need(isinstance(item, dict), f"results[{i}] is not an object")
        _exact_keys(item, frozenset({"entity_id", "response"}), f"results[{i}]")
        _need(_is_str(item["entity_id"]), f"results[{i}].entity_id is missing")
        _need(item["entity_id"] not in seen, f"results[{i}].entity_id repeats on one page")
        _need(isinstance(item["response"], dict), f"results[{i}].response is not an object")
        seen.add(item["entity_id"])
        results.append(SweepResult(item["entity_id"], freeze(item["response"])))
    skipped = _entity_reasons(payload["skipped"], "skipped", SKIP_REASONS)
    return SweepResultsPage(
        sweep_id=sweep_id,
        state=state,
        results=tuple(results),
        next_cursor=cursor,
        budget=freeze(budget),
        skipped=skipped,
        stats=MappingProxyType(dict(stats)),
    )
