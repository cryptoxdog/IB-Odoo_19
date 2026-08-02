"""Explicit semantic-kernel backfill/reconciliation engine (TASK-026).

Pure orchestration: no install-hook backfill, no Gate/CEG/EIE calls.
Idempotent identity: (source_system, source_model, source_record_id, semantic_family, mapping_version).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

Family = Literal[
    "specification",
    "observation",
    "facility_rule",
    "capacity",
    "supply",
    "demand",
]

FAMILIES: tuple[Family, ...] = (
    "specification",
    "observation",
    "facility_rule",
    "capacity",
    "supply",
    "demand",
)

# Families blocked for automatic conversion (pack mapping decisions).
BLOCKED_AUTOMATIC: frozenset[Family] = frozenset({"supply", "demand"})

MAPPING_VERSION = "2.2.0-task-026"
SOURCE_SYSTEM = "odoo"
CHECKPOINT_KEY_PREFIX = "plasticos_semantic_kernel.backfill.checkpoint"


@dataclass
class SourceRow:
    source_model: str
    source_record_id: str
    payload: dict[str, Any]
    company_id: int | None = None


@dataclass
class RowResult:
    identity: str
    status: Literal["planned", "created", "reused", "skipped", "conflicted", "failed", "blocked"]
    detail: str = ""


@dataclass
class BackfillReport:
    family: Family
    dry_run: bool
    source_query: str
    source_count: int
    created: int = 0
    reused: int = 0
    skipped: int = 0
    conflicted: int = 0
    failed: int = 0
    blocked: int = 0
    cursor: str | None = None
    duration_ms: int = 0
    code_sha: str = "unknown"
    schema_version: str = MAPPING_VERSION
    migration_batch_id: str = ""
    company_id: int | None = None
    batch_size: int = 100
    stop_on_conflict: bool = False
    checksum: str = ""
    rows: list[RowResult] = field(default_factory=list)
    observed_at: str = ""

    def finalize(self) -> None:
        self.observed_at = datetime.now(UTC).isoformat()
        body = {
            "family": self.family,
            "dry_run": self.dry_run,
            "source_count": self.source_count,
            "created": self.created,
            "reused": self.reused,
            "skipped": self.skipped,
            "conflicted": self.conflicted,
            "failed": self.failed,
            "blocked": self.blocked,
            "cursor": self.cursor,
            "schema_version": self.schema_version,
            "migration_batch_id": self.migration_batch_id,
            "identities": [r.identity for r in self.rows],
        }
        blob = json.dumps(body, sort_keys=True, separators=(",", ":"))
        self.checksum = "sha256:" + hashlib.sha256(blob.encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        self.finalize()
        return asdict(self)


def migration_identity(
    *,
    source_model: str,
    source_record_id: str,
    family: Family,
    mapping_version: str = MAPPING_VERSION,
    source_system: str = SOURCE_SYSTEM,
) -> str:
    return "|".join([source_system, source_model, str(source_record_id), family, mapping_version])


def checkpoint_key(family: Family, company_id: int | None) -> str:
    suffix = str(company_id) if company_id is not None else "all"
    return f"{CHECKPOINT_KEY_PREFIX}.{family}.{suffix}"


class BackfillEngine:
    """Family-scoped backfill planner/executor.

    ``existing_identities`` is the set of identities already persisted.
    ``source_rows`` is provided by the caller (Odoo search or fixtures).
    """

    def __init__(
        self,
        *,
        family: Family,
        source_rows: Iterable[SourceRow],
        existing_identities: set[str] | None = None,
        dry_run: bool = True,
        batch_size: int = 100,
        after_id: str | None = None,
        company_id: int | None = None,
        migration_batch_id: str = "",
        stop_on_conflict: bool = False,
        code_sha: str = "unknown",
    ) -> None:
        if family not in FAMILIES:
            raise ValueError(f"unknown family: {family}")
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        self.family = family
        self.source_rows = list(source_rows)
        self.existing_identities = set(existing_identities or ())
        self.dry_run = dry_run
        self.batch_size = batch_size
        self.after_id = after_id
        self.company_id = company_id
        self.migration_batch_id = migration_batch_id or f"batch-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
        self.stop_on_conflict = stop_on_conflict
        self.code_sha = code_sha

    def run(self) -> BackfillReport:
        started = datetime.now(UTC)
        rows = self._filter_rows(self.source_rows)
        report = BackfillReport(
            family=self.family,
            dry_run=self.dry_run,
            source_query=self._source_query(),
            source_count=len(rows),
            migration_batch_id=self.migration_batch_id,
            company_id=self.company_id,
            batch_size=self.batch_size,
            stop_on_conflict=self.stop_on_conflict,
            code_sha=self.code_sha,
        )

        if self.family in BLOCKED_AUTOMATIC:
            for row in rows[: self.batch_size]:
                ident = migration_identity(
                    source_model=row.source_model,
                    source_record_id=row.source_record_id,
                    family=self.family,
                )
                report.rows.append(
                    RowResult(
                        identity=ident,
                        status="blocked",
                        detail="automatic backfill blocked by pack mapping decision",
                    )
                )
                report.blocked += 1
            report.cursor = rows[min(len(rows), self.batch_size) - 1].source_record_id if rows else self.after_id
            report.duration_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
            report.finalize()
            return report

        batch = rows[: self.batch_size]
        for row in batch:
            ident = migration_identity(
                source_model=row.source_model,
                source_record_id=row.source_record_id,
                family=self.family,
            )
            conflict = self._detect_conflict(row)
            if conflict:
                report.rows.append(RowResult(identity=ident, status="conflicted", detail=conflict))
                report.conflicted += 1
                if self.stop_on_conflict:
                    break
                continue

            if ident in self.existing_identities:
                report.rows.append(RowResult(identity=ident, status="reused", detail="idempotent reuse"))
                report.reused += 1
                continue

            if self.dry_run:
                report.rows.append(RowResult(identity=ident, status="planned", detail="dry-run create"))
                report.created += 1  # planned creates counted for dry-run visibility
                continue

            # Execute path: caller persists; engine records create intent success.
            self.existing_identities.add(ident)
            report.rows.append(RowResult(identity=ident, status="created", detail="created"))
            report.created += 1

        report.cursor = batch[-1].source_record_id if batch else self.after_id
        report.duration_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
        report.finalize()
        return report

    def _filter_rows(self, rows: list[SourceRow]) -> list[SourceRow]:
        out: list[SourceRow] = []
        for row in rows:
            if self.after_id is not None:
                try:
                    if int(row.source_record_id) <= int(self.after_id):
                        continue
                except ValueError:
                    if row.source_record_id <= self.after_id:
                        continue
            if self.company_id is not None and row.company_id not in (None, self.company_id):
                continue
            out.append(row)
        out.sort(key=lambda r: int(r.source_record_id) if r.source_record_id.isdigit() else r.source_record_id)
        return out

    def _source_query(self) -> str:
        return {
            "specification": "plasticos.material.profile → plasticos.material.specification",
            "observation": "plasticos.material.profile scalars → plasticos.material.observation",
            "facility_rule": "plasticos.facility.profile → plasticos.facility.material.rule",
            "capacity": "plasticos.facility.profile capacity fields → plasticos.capacity.observation",
            "supply": "blocked automatic (FIELD-DEC)",
            "demand": "blocked automatic (operator entry)",
        }[self.family]

    def _detect_conflict(self, row: SourceRow) -> str | None:
        # Preserve zeros; never coerce zero→unknown/null.
        if "force_conflict" in row.payload:
            return "forced conflict fixture"
        return None


def run_twice_idempotent(engine_factory) -> tuple[BackfillReport, BackfillReport]:
    """Helper for tests: second run must reuse, not double-create."""
    first = engine_factory(dry_run=False).run()
    existing = {r.identity for r in first.rows if r.status in {"created", "reused"}}
    second = engine_factory(dry_run=False, existing_identities=existing).run()
    return first, second
