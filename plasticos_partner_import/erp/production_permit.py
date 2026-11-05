"""One-use operator permit for an ERP import on the Production database.

Odoo-free: the decisions are pure functions over the permit file, the observed
target identity, and the loaded source rows, so the pure-Python CI tier proves
them. ``scripts/import_erp_shell.py`` gathers the observations and performs the
single database write that consumes a permit.

Production is denied by default. A permit is a JSON file an operator writes on
the execution host (``ERP_PRODUCTION_PERMIT`` names its path). It admits one
applied run of one phase on one database and is consumed before the first
import write by an ``ir_config_parameter`` insert that only one caller can win.
There is no environment switch that admits Production without a permit.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess  # noqa: S404 - read-only git identity probe with fixed arguments
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from . import reader

__all__ = [
    "CONSUMED_PREFIX",
    "PERMIT_ENV",
    "PHASE1_WITNESS_PARAM",
    "PHASE2_WITNESS_PARAM",
    "PHASE_COMMERCIAL",
    "PHASE_PARTNERS",
    "Observed",
    "Permit",
    "PermitRefused",
    "check_phase1_witness",
    "consumed_key",
    "load_permit",
    "phase_tables",
    "release_identity",
    "source_fingerprint",
    "verify_permit",
    "witness_record",
]

PERMIT_ENV = "ERP_PRODUCTION_PERMIT"
PRODUCTION_STAGE = "production"
PHASE_PARTNERS = "erp_partners"
PHASE_COMMERCIAL = "erp_commercial"
PHASES = (PHASE_PARTNERS, PHASE_COMMERCIAL)
CONSUMED_PREFIX = "plasticos_partner_import.production_permit."
PHASE1_WITNESS_PARAM = "plasticos_partner_import.production_phase1_witness"
PHASE2_WITNESS_PARAM = "plasticos_partner_import.production_phase2_witness"
MAX_VALIDITY = timedelta(hours=24)

REQUIRED_FIELDS = (
    "permit_id",
    "phase",
    "database_name",
    "database_uuid",
    "odoo_stage",
    "release_sha",
    "source_fingerprint",
    "expires_at",
    "approved_by",
)
OPTIONAL_FIELDS = ("accept_phase1_exceptions_digest",)
_PERMIT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,79}$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class PermitRefused(RuntimeError):
    """The run is not admitted. Nothing may be written."""

    def __init__(self, reasons: Iterable[str]):
        self.reasons = tuple(reasons)
        super().__init__("; ".join(self.reasons))


@dataclass(frozen=True)
class Permit:
    permit_id: str
    phase: str
    database_name: str
    database_uuid: str
    odoo_stage: str
    release_sha: str
    source_fingerprint: str
    expires_at: datetime
    approved_by: str
    accept_phase1_exceptions_digest: str | None = None

    def bindings(self) -> dict:
        """The permit's identity bindings, for audit lines. Carries no secret."""
        return {
            "permit_id": self.permit_id,
            "phase": self.phase,
            "database_name": self.database_name,
            "database_uuid": self.database_uuid,
            "odoo_stage": self.odoo_stage,
            "release_sha": self.release_sha,
            "source_fingerprint": self.source_fingerprint,
            "expires_at": _iso(self.expires_at),
            "approved_by": self.approved_by,
        }


@dataclass(frozen=True)
class Observed:
    """What the execution host reports about the target, gathered by the shell."""

    database_name: str
    database_uuid: str
    odoo_stage: str
    release_sha: str | None
    release_clean: bool

    def as_dict(self) -> dict:
        return {
            "database_name": self.database_name,
            "database_uuid": self.database_uuid,
            "odoo_stage": self.odoo_stage,
            "release_sha": self.release_sha,
            "release_clean": self.release_clean,
        }


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_time(value: object) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("expires_at must be an ISO-8601 UTC timestamp")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        raise ValueError("expires_at must carry a UTC offset")
    return moment.astimezone(UTC)


def load_permit(path: str | Path) -> Permit:
    """Read and shape-check a permit file. Raises ``PermitRefused`` on any defect."""
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PermitRefused([f"permit file unreadable: {type(exc).__name__}"]) from None
    if not isinstance(document, dict):
        raise PermitRefused(["permit file is not a JSON object"])
    reasons: list[str] = []
    unknown = sorted(set(document) - set(REQUIRED_FIELDS) - set(OPTIONAL_FIELDS))
    if unknown:
        reasons.append(f"permit has unknown fields: {', '.join(unknown)}")
    for name in REQUIRED_FIELDS:
        value = document.get(name)
        if not isinstance(value, str) or not value.strip():
            reasons.append(f"permit field {name} is missing or empty")
    if reasons:
        raise PermitRefused(reasons)
    if not _PERMIT_ID.match(document["permit_id"]):
        reasons.append("permit_id must be 8-80 characters of letters, digits, dot, dash or underscore")
    if document["phase"] not in PHASES:
        reasons.append(f"permit phase must be one of {', '.join(PHASES)}")
    if not _UUID.match(document["database_uuid"].strip().lower()):
        reasons.append("database_uuid is not a UUID")
    if not _GIT_SHA.match(document["release_sha"].strip().lower()):
        reasons.append("release_sha is not a 40-character git SHA")
    if not _SHA256.match(document["source_fingerprint"].strip().lower()):
        reasons.append("source_fingerprint is not a SHA-256 hex digest")
    accepted = document.get("accept_phase1_exceptions_digest")
    if accepted is not None and (not isinstance(accepted, str) or not _SHA256.match(accepted.strip().lower())):
        reasons.append("accept_phase1_exceptions_digest is not a SHA-256 hex digest")
    try:
        expires_at = _parse_time(document["expires_at"])
    except ValueError as exc:
        reasons.append(str(exc))
        expires_at = None
    if reasons:
        raise PermitRefused(reasons)
    return Permit(
        permit_id=document["permit_id"].strip(),
        phase=document["phase"].strip(),
        database_name=document["database_name"].strip(),
        database_uuid=document["database_uuid"].strip().lower(),
        odoo_stage=document["odoo_stage"].strip().lower(),
        release_sha=document["release_sha"].strip().lower(),
        source_fingerprint=document["source_fingerprint"].strip().lower(),
        expires_at=expires_at,
        approved_by=document["approved_by"].strip(),
        accept_phase1_exceptions_digest=accepted.strip().lower() if accepted else None,
    )


def verify_permit(permit: Permit, observed: Observed, *, phase: str, now: datetime | None = None) -> None:
    """Every binding must match the observed target. Raises ``PermitRefused`` naming each mismatch."""
    now = (now or datetime.now(UTC)).astimezone(UTC)
    reasons: list[str] = []
    if permit.phase != phase:
        reasons.append(f"permit is for phase {permit.phase}, this run is {phase}")
    if observed.odoo_stage != PRODUCTION_STAGE:
        reasons.append(
            f"ODOO_STAGE is {observed.odoo_stage or 'unset'}: a permit is only valid on the production stage"
        )
    if permit.odoo_stage != PRODUCTION_STAGE:
        reasons.append(f"permit odoo_stage is {permit.odoo_stage}, not production")
    if permit.database_name != observed.database_name:
        reasons.append(f"permit names database {permit.database_name}, connected to {observed.database_name}")
    if permit.database_uuid != (observed.database_uuid or "").lower():
        reasons.append("permit database_uuid does not match the connected database")
    if not observed.release_sha:
        reasons.append("release identity is not provable on this host (no readable git checkout)")
    elif not observed.release_clean:
        reasons.append("the addon checkout has modified tracked files; release identity is not the reviewed commit")
    elif permit.release_sha != observed.release_sha:
        reasons.append(f"permit release_sha {permit.release_sha[:12]} != running {observed.release_sha[:12]}")
    if permit.expires_at <= now:
        reasons.append(f"permit expired at {_iso(permit.expires_at)}")
    elif permit.expires_at - now > MAX_VALIDITY:
        reasons.append("permit validity exceeds 24 hours")
    if reasons:
        raise PermitRefused(reasons)


def phase_tables(phase: str) -> frozenset[str]:
    """Source tables the phase reads, which the fingerprint covers."""
    if phase == PHASE_PARTNERS:
        return reader.PARTNER_SOURCE_TABLES
    if phase == PHASE_COMMERCIAL:
        return reader.REQUIRED_TABLES | reader.COMMERCIAL_SQL_TABLES
    raise ValueError(f"unknown phase {phase!r}")


def _table_digest(rows: list[Mapping[str, object]]) -> str:
    lines = sorted(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False) for row in rows)
    digest = hashlib.sha256()
    for line in lines:
        digest.update(line.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def source_fingerprint(tables: Mapping[str, list[Mapping[str, object]]], names: Iterable[str]) -> dict:
    """Order-independent digest of the named source tables.

    Each table digest is SHA-256 over its rows as sorted canonical JSON lines.
    The aggregate is SHA-256 over the sorted ``{table: digest}`` map, so a
    partner-only fingerprint can be recomputed from a full payload.
    """
    wanted = sorted(names)
    missing = [name for name in wanted if name not in tables]
    if missing:
        raise PermitRefused([f"source payload lacks tables: {', '.join(missing)}"])
    per_table = {name: {"rows": len(tables[name]), "sha256": _table_digest(tables[name])} for name in wanted}
    aggregate = hashlib.sha256(
        json.dumps({name: per_table[name]["sha256"] for name in wanted}, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    return {"sha256": aggregate, "tables": per_table}


def consumed_key(permit_id: str) -> str:
    return f"{CONSUMED_PREFIX}{permit_id}"


def witness_record(
    permit: Permit, observed: Observed, fingerprint: dict, verdict: Mapping, *, now: datetime | None = None
) -> dict:
    """Durable record that a permitted phase committed, written in the same transaction as its data."""
    return {
        "phase": permit.phase,
        "permit_id": permit.permit_id,
        "database_uuid": observed.database_uuid,
        "release_sha": observed.release_sha,
        "source_fingerprint": fingerprint["sha256"],
        "partner_fingerprint": partner_fingerprint(fingerprint),
        "final_status": verdict.get("final_status"),
        "data_complete": bool(verdict.get("data_complete")),
        "exceptions_digest": verdict.get("exceptions_digest"),
        "committed_at": _iso(now or datetime.now(UTC)),
    }


def partner_fingerprint(fingerprint: dict) -> str:
    """Aggregate over the partner tables only, recomputed from a phase fingerprint."""
    tables = fingerprint["tables"]
    names = sorted(reader.PARTNER_SOURCE_TABLES)
    missing = [name for name in names if name not in tables]
    if missing:
        raise PermitRefused([f"fingerprint lacks partner tables: {', '.join(missing)}"])
    return hashlib.sha256(
        json.dumps({name: tables[name]["sha256"] for name in names}, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def check_phase1_witness(raw: str | None, permit: Permit, observed: Observed, fingerprint: dict) -> None:
    """The commercial phase runs only after a committed partner phase on this database and this partner source."""
    if not raw:
        raise PermitRefused(["no committed erp_partners phase on this database"])
    try:
        witness = json.loads(raw)
    except ValueError:
        raise PermitRefused(["erp_partners witness is not readable JSON"]) from None
    reasons: list[str] = []
    if witness.get("phase") != PHASE_PARTNERS:
        reasons.append("erp_partners witness names another phase")
    if witness.get("database_uuid") != observed.database_uuid:
        reasons.append("erp_partners witness belongs to another database")
    if witness.get("partner_fingerprint") != partner_fingerprint(fingerprint):
        reasons.append("partner source changed since the erp_partners phase")
    if not witness.get("data_complete"):
        accepted = permit.accept_phase1_exceptions_digest
        if not accepted:
            reasons.append(
                "erp_partners phase left open exceptions; the permit must carry accept_phase1_exceptions_digest"
            )
        elif accepted != witness.get("exceptions_digest"):
            reasons.append("accept_phase1_exceptions_digest does not match the erp_partners exceptions")
    if reasons:
        raise PermitRefused(reasons)


def release_identity(path: str | Path) -> tuple[str | None, bool]:
    """``(HEAD sha, tracked tree clean)`` of the git checkout holding ``path``; ``(None, False)`` when unprovable."""
    root = str(Path(path).resolve())
    base = ["git", "-c", f"safe.directory={root}", "-C", root]
    try:
        head = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [*base, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=15, check=False
        )
        if head.returncode != 0:
            return None, False
        status = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [*base, "status", "--porcelain", "--untracked-files=no"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None, False
    sha = head.stdout.strip().lower()
    if not _GIT_SHA.match(sha) or status.returncode != 0:
        return None, False
    return sha, not status.stdout.strip()
