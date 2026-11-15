"""Enrichment sweep contract (Odoo side): the ONE module that knows the wire shape.

Two Gate actions (EIE owns the run and the budget; Odoo owns buyer selection
and review — operator decisions 2026-11-14/15, ADR-012 amendment 2026-11-15):

* ``enrichment-sweep``          — submit candidates; reply names the sweep.
* ``enrichment-sweep-results``  — page the results of one sweep.

Every other part of PlasticOS depends on the frozen types below, never on raw
dicts, so reconciling with the published contract is a one-file change.

CONTRACT STATUS: the authoritative EIE document (``docs/contracts/enrichment-sweep.md``)
was NOT published when this module was written. The shape was described by the
EIE CTO. Every detail not stated there is an ASSUMPTION, marked ``ASSUMPTION``
below and listed in ``SWEEP_CONTRACT_ASSUMPTIONS``. The parsers fail closed:
an unknown member, a wrong type or an unknown state rejects the whole reply.
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

SWEEP_ACTION = "enrichment-sweep"
SWEEP_RESULTS_ACTION = "enrichment-sweep-results"
SWEEP_ACTIONS: tuple[str, ...] = (SWEEP_ACTION, SWEEP_RESULTS_ACTION)

# gate-integration ADR-005: the entity id is LOCKED to res.partner:<id>.
SWEEP_NODE_LABEL = "Facility"
_ENTITY_ID_RE = re.compile(r"^res\.partner:[1-9][0-9]*$")

# ASSUMPTION: the four run states a results page may report.
SWEEP_STATE_RUNNING = "running"
SWEEP_STATE_COMPLETED = "completed"
SWEEP_STATE_BUDGET_EXHAUSTED = "budget_exhausted"
SWEEP_STATE_FAILED = "failed"
SWEEP_STATES = frozenset({SWEEP_STATE_RUNNING, SWEEP_STATE_COMPLETED, SWEEP_STATE_BUDGET_EXHAUSTED, SWEEP_STATE_FAILED})

SWEEP_CONTRACT_ASSUMPTIONS: tuple[str, ...] = (
    "candidate: entity_id 'res.partner:<id>', node_label 'Facility', entity = {cartridge_field: current value}, "
    "field_confidences optional {field: number in [0,1]}",
    "send request: exactly candidates, daily_budget_usd (number > 0), idempotency_key (string)",
    "send reply: exactly sweep_id (non-empty string), accepted, rejected; accepted is a list of entity ids "
    "(string or {entity_id}) or an integer count; rejected is a list of {entity_id, reason} or an integer count",
    "EIE answers each candidate as one converge v2 run on node Facility, subject 'material', requesting the "
    "subject's cartridge fields absent from entity; identity subject_ref is the candidate entity_id",
    "results request: {sweep_id, cursor}; cursor is null for the first page",
    "results reply: exactly state, results, next_cursor, budget, skipped; state in running|completed|"
    "budget_exhausted|failed; next_cursor string or null (null = no further page)",
    "results[]: exactly {entity_id, response}; response is the converge v2 response body, unchanged",
    "skipped[]: {entity_id, reason}; budget: an object kept as opaque audit data",
    "a refused request arrives as a Gate/SDK transport error, never as an error member in a success reply",
)


class SweepContractError(ValueError):
    """A sweep request could not be built, or a reply does not match the contract."""


def _need(condition: bool, detail: str) -> None:
    if not condition:
        raise SweepContractError(detail)


def _is_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _exact_keys(raw: Mapping[str, Any], required: frozenset[str], optional: frozenset[str], where: str) -> None:
    keys = set(raw)
    missing = sorted(required - keys)
    unknown = sorted(keys - required - optional)
    _need(not missing, f"{where} is missing {missing}")
    _need(not unknown, f"{where} carries unknown member(s) {unknown}")


def is_sweep_entity_id(value: Any) -> bool:
    return isinstance(value, str) and bool(_ENTITY_ID_RE.match(value))


def partner_id_of(entity_id: str) -> int:
    """The res.partner id an entity id names (ADR-005)."""
    _need(is_sweep_entity_id(entity_id), f"entity_id {entity_id!r} is not res.partner:<id>")
    return int(entity_id.split(":", 1)[1])


# ── Requests ──────────────────────────────────────────────────────────────


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
        return dict((("sweep_id", self.sweep_id), ("cursor", self.cursor)))


def build_sweep_idempotency_key(tenant: str, utc_date: str, entity_ids) -> str:
    """Deterministic: tenant + UTC date + sorted candidate ids (one sweep per tenant per day and set)."""
    _need(_is_str(tenant), "tenant is required")
    _need(bool(re.match(r"^\d{4}-\d{2}-\d{2}$", utc_date or "")), "utc_date must be YYYY-MM-DD")
    ids = sorted(entity_ids)
    _need(bool(ids), "no candidate ids")
    digest = hashlib.sha256("\n".join(ids).encode("utf-8")).hexdigest()[:32]
    return f"odoo:enrichment-sweep:{tenant}:{utc_date}:{digest}"


# ── Replies ───────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class SweepRejection:
    entity_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class SweepSendReply:
    sweep_id: str
    accepted_count: int
    rejected_count: int
    accepted: tuple[str, ...]
    rejected: tuple[SweepRejection, ...]


def _entity_reasons(raw: Any, where: str) -> tuple[SweepRejection, ...]:
    _need(isinstance(raw, list), f"{where} is not a list")
    out = []
    for i, item in enumerate(raw):
        _need(isinstance(item, dict), f"{where}[{i}] is not an object")
        _exact_keys(item, frozenset({"entity_id", "reason"}), frozenset(), f"{where}[{i}]")
        _need(is_sweep_entity_id(item["entity_id"]), f"{where}[{i}].entity_id is not res.partner:<id>")
        _need(_is_str(item["reason"]), f"{where}[{i}].reason is missing")
        out.append(SweepRejection(item["entity_id"], item["reason"]))
    return tuple(out)


def _is_count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def parse_sweep_send_reply(payload: Any, *, request: SweepRequest) -> SweepSendReply:
    """Parse the ``enrichment-sweep`` reply or raise SweepContractError."""
    _need(isinstance(payload, dict), "sweep reply is not an object")
    _exact_keys(payload, frozenset({"sweep_id", "accepted", "rejected"}), frozenset(), "sweep reply")
    _need(_is_str(payload["sweep_id"]), "sweep reply sweep_id is missing")
    sent = {c.entity_id for c in request.candidates}
    raw_acc, raw_rej = payload["accepted"], payload["rejected"]
    accepted: tuple[str, ...] = ()
    rejected: tuple[SweepRejection, ...] = ()
    if _is_count(raw_acc):
        accepted_count = raw_acc
    else:
        _need(isinstance(raw_acc, list), "sweep reply accepted is neither a list nor a count")
        ids = []
        for i, item in enumerate(raw_acc):
            entity_id = item.get("entity_id") if isinstance(item, dict) else item
            if isinstance(item, dict):
                _exact_keys(item, frozenset({"entity_id"}), frozenset(), f"accepted[{i}]")
            _need(is_sweep_entity_id(entity_id), f"accepted[{i}] is not res.partner:<id>")
            ids.append(entity_id)
        accepted = tuple(ids)
        accepted_count = len(accepted)
    if _is_count(raw_rej):
        rejected_count = raw_rej
    else:
        rejected = _entity_reasons(raw_rej, "rejected")
        rejected_count = len(rejected)
    named = set(accepted) | {r.entity_id for r in rejected}
    _need(named <= sent, f"sweep reply names entities that were not sent: {sorted(named - sent)}")
    _need(not (set(accepted) & {r.entity_id for r in rejected}), "an entity is both accepted and rejected")
    _need(accepted_count + rejected_count <= len(sent), "sweep reply counts exceed the candidates sent")
    return SweepSendReply(payload["sweep_id"], accepted_count, rejected_count, accepted, rejected)


@dataclass(frozen=True, slots=True)
class SweepResult:
    entity_id: str
    response: Mapping[str, Any]

    def response_dict(self) -> dict[str, Any]:
        return _plain(self.response)


@dataclass(frozen=True, slots=True)
class SweepResultsPage:
    state: str
    results: tuple[SweepResult, ...]
    next_cursor: str | None
    budget: Mapping[str, Any]
    skipped: tuple[SweepRejection, ...]

    @property
    def finished(self) -> bool:
        """No further page and the run is no longer running."""
        return self.next_cursor is None and self.state != SWEEP_STATE_RUNNING

    def budget_dict(self) -> dict[str, Any]:
        return _plain(self.budget)


def parse_sweep_results_page(payload: Any) -> SweepResultsPage:
    """Parse one ``enrichment-sweep-results`` page or raise SweepContractError.

    The ``response`` of each result is kept unchanged (frozen); it is parsed by
    ``parse_converge_response_v2`` against the request stored for its entity.
    """
    _need(isinstance(payload, dict), "results reply is not an object")
    _exact_keys(
        payload,
        frozenset({"state", "results", "next_cursor", "budget", "skipped"}),
        frozenset(),
        "results reply",
    )
    state = payload["state"]
    _need(isinstance(state, str) and state in SWEEP_STATES, f"results reply state {state!r} is unrecognised")
    cursor = payload["next_cursor"]
    _need(cursor is None or _is_str(cursor), "next_cursor must be a non-empty string or null")
    _need(isinstance(payload["budget"], dict), "budget is not an object")
    raw_results = payload["results"]
    _need(isinstance(raw_results, list), "results is not a list")
    results = []
    seen = set()
    for i, item in enumerate(raw_results):
        _need(isinstance(item, dict), f"results[{i}] is not an object")
        _exact_keys(item, frozenset({"entity_id", "response"}), frozenset(), f"results[{i}]")
        _need(is_sweep_entity_id(item["entity_id"]), f"results[{i}].entity_id is not res.partner:<id>")
        _need(item["entity_id"] not in seen, f"results[{i}].entity_id repeats on one page")
        _need(isinstance(item["response"], dict), f"results[{i}].response is not an object")
        seen.add(item["entity_id"])
        results.append(SweepResult(item["entity_id"], freeze(item["response"])))
    skipped = _entity_reasons(payload["skipped"], "skipped")
    return SweepResultsPage(
        state=state,
        results=tuple(results),
        next_cursor=cursor,
        budget=freeze(payload["budget"]) if payload["budget"] else MappingProxyType({}),
        skipped=skipped,
    )
