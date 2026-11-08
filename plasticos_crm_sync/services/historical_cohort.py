"""Frozen 4,876-ContactID VanillaSoft history: census, plan, ledger, report.

Odoo-free so the pure-Python tier proves every decision. The Odoo side
(``scripts/import_vanillasoft_shell.py`` history mode) fetches each planned
ContactID through ``SyncOrchestrator.upsert_contact_external_id`` and reads the
durable ``plasticos.crm.external.ref`` rows that decide what is imported.

The census is an operator-supplied runtime input (amendment v1.2 D3): a
``vanillasoft_contact_id,decision`` CSV with no PII, verified against the
SHA-256 the operator declares. The approved crosswalk is the packaged pin in
``approved_identity``. A ledger row is evidence of a reason, never proof of
import: only a durable external ref is.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import subprocess  # noqa: S404 - read-only git identity probe with fixed arguments
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

CENSUS_HEADER = ("vanillasoft_contact_id", "decision")
COHORT = 4876
YES = "YES"
PARTITION = dict(((YES, 763), ("NO", 18), ("PENDING", 4095)))
FETCH = "fetch"
SKIP_DUPLICATE = "skip_duplicate"
LEDGER_HEADER_KIND = "header"
ERP_COMMERCIAL_PHASE = "erp_commercial"
LEDGER_VERSION = 1
IMPORTED = "imported"
HELD = "held"
DUPLICATE_SKIPPED = "duplicate_skipped"
GENUINE_FAILED = "genuine_failed"
CLASSES = (IMPORTED, HELD, DUPLICATE_SKIPPED, GENUINE_FAILED)
ADMITTED_OUTCOMES = ("created", "updated", "unchanged")
AUTH_FAILURE_MARKERS = ("VanillaSoft auth failed", "requires api_key")
ERP_READY_PARAM = "plasticos_partner_import.partner_count_after_contacts"
ERP_PHASE2_WITNESS_PARAM = "plasticos_partner_import.production_phase2_witness"
# YES ContactIDs that are a second VanillaSoft record of a person the packaged
# crosswalk already binds (759 crosswalk + these 4 = 763 YES). They are not
# fetched: the per-ID upsert would turn an unbound id into a new lead.
OMITTED_DUPLICATE_VS_IDS = frozenset({"1045036935", "1179868294", "584402429", "585278462"})

_SECRET = re.compile(r"(?i)(api[_-]?key|authorization|password|token)\s*[:=]\s*(?:bearer\s+)?\S+")
_BEARER = re.compile(r"(?i)\bbearer\s+\S+")
_EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")
_PHONE = re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?!\d)")
_MAX_REASON = 500


class CohortError(ValueError):
    """The census, the crosswalk or the ledger cannot be trusted. Nothing is fetched."""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_census(text: str, *, expected_sha256: str) -> dict[str, str]:
    """``{contact_id: YES|NO|PENDING}`` for the exact declared census, or ``CohortError``."""
    declared = (expected_sha256 or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", declared):
        raise CohortError("the census SHA-256 must be declared (64 hex characters)")
    digest = sha256_text(text)
    if digest != declared:
        raise CohortError(f"census SHA-256 {digest} != declared {declared}")
    rows = csv.reader(io.StringIO(text))
    try:
        header = tuple(next(rows))
    except StopIteration:
        raise CohortError("census is empty") from None
    if header != CENSUS_HEADER:
        raise CohortError(f"census header {header!r} is not the no-PII {CENSUS_HEADER!r}")
    census: dict[str, str] = {}
    for line_no, row in enumerate(rows, start=2):
        if not row:
            continue
        if len(row) != 2:
            raise CohortError(f"census row {line_no} is not two columns")
        contact_id, decision = row[0].strip(), row[1].strip()
        if not contact_id.isdigit() or decision not in PARTITION:
            raise CohortError(f"census row {line_no} is not a ContactID and YES/NO/PENDING")
        if contact_id in census:
            raise CohortError(f"census repeats ContactID at row {line_no}")
        census[contact_id] = decision
    if len(census) != COHORT:
        raise CohortError(f"census has {len(census)} ContactIDs, not {COHORT}")
    counts = {decision: 0 for decision in PARTITION}
    for decision in census.values():
        counts[decision] += 1
    if counts != PARTITION:
        raise CohortError(f"census partition {counts} != approved {PARTITION}")
    return census


def verify_identity(census: Mapping[str, str], crosswalk: Mapping[str, str], omitted: Iterable[str]) -> None:
    """YES is exactly the crosswalk plus the omitted duplicates; no NO/PENDING id is bound to an ERP person."""
    yes = {contact_id for contact_id, decision in census.items() if decision == YES}
    bound = set(crosswalk)
    skipped = set(omitted)
    reasons: list[str] = []
    if bound - yes:
        reasons.append(f"{len(bound - yes)} crosswalk ContactIDs are not YES in the census")
    if skipped - yes:
        reasons.append(f"{len(skipped - yes)} omitted duplicate ContactIDs are not YES in the census")
    if bound & skipped:
        reasons.append("an omitted duplicate ContactID is also in the crosswalk")
    if yes != bound | skipped:
        reasons.append(f"{len(yes - bound - skipped)} YES ContactIDs are neither in the crosswalk nor omitted")
    if reasons:
        raise CohortError("; ".join(reasons))


def plan(census: Mapping[str, str], omitted: Iterable[str], imported: Iterable[str], ledger: Mapping[str, dict]):
    """Ordered ``(contact_id, action)``: ``fetch`` or ``skip_duplicate``. Durably imported ids are not planned.

    A duplicate already recorded is not planned again; every other non-imported
    id is fetched again, which the per-ID upsert makes idempotent.
    """
    done = set(imported)
    skipped = set(omitted)
    steps = []
    for contact_id in sorted(census, key=int):
        if contact_id in done:
            continue
        if census[contact_id] == YES and contact_id in skipped:
            if (ledger.get(contact_id) or {}).get("class") != DUPLICATE_SKIPPED:
                steps.append((contact_id, SKIP_DUPLICATE))
            continue
        steps.append((contact_id, FETCH))
    return steps


def redact(text: str) -> str:
    """Drop credential-shaped text, email addresses and phone numbers. Keep the cause."""
    cleaned = _SECRET.sub(r"\1=[redacted]", text or "")
    cleaned = _BEARER.sub("bearer [redacted]", cleaned)
    cleaned = _EMAIL.sub("[redacted-email]", cleaned)
    cleaned = _PHONE.sub("[redacted-phone]", cleaned)
    return " ".join(cleaned.split())[:_MAX_REASON]


def classify(raw: str, messages: Iterable[str], *, durable: bool) -> str:
    """One importer outcome. ``durable`` is whether the external ref exists after the commit."""
    if raw in ADMITTED_OUTCOMES:
        return IMPORTED if durable else GENUINE_FAILED
    if raw == "failed" and "ERP marker" in " ".join(messages):
        return HELD
    return GENUINE_FAILED


def signals(raw: str, messages: Iterable[str], exc_text: str, logged: Iterable[tuple[str, str]], cls: str):
    """Sanitized reasons for one ContactID; a non-imported outcome without one is recorded UNKNOWN."""
    kept: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def remember(level: str, reason: str) -> None:
        cleaned = redact(reason)
        if cleaned and (level, cleaned) not in seen:
            seen.add((level, cleaned))
            kept.append({"level": level, "reason": cleaned})

    if exc_text:
        remember("ERROR", f"{raw}: {exc_text}")
    for message in messages:
        remember("ERROR", message)
    for level, reason in logged:
        remember(level, reason)
    if raw in ADMITTED_OUTCOMES and cls != IMPORTED:
        remember("ERROR", f"outcome {raw} left no durable external ref")
    if cls != IMPORTED and not kept:
        remember("UNKNOWN", f"outcome {raw} produced no reason")
    return kept


def is_auth_failure(exc_text: str) -> bool:
    return any(marker in (exc_text or "") for marker in AUTH_FAILURE_MARKERS)


class Ledger:
    """Append-only JSONL ledger bound to one census and one database. Each row is fsynced."""

    def __init__(self, path: str | Path, *, census_sha256: str, database_uuid: str):
        self.path = Path(path)
        self.census_sha256 = census_sha256
        self.database_uuid = database_uuid
        self.rows: dict[str, dict] = {}
        self.torn_tail = False
        if self.path.exists() and self.path.stat().st_size:
            self._read()
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._write_line(
                {
                    "kind": LEDGER_HEADER_KIND,
                    "version": LEDGER_VERSION,
                    "census_sha256": census_sha256,
                    "database_uuid": database_uuid,
                    "created_at": iso_now(),
                }
            )

    def _read(self) -> None:
        lines = self.path.read_text(encoding="utf-8").splitlines()
        try:
            header = json.loads(lines[0])
        except (IndexError, ValueError):
            raise CohortError("ledger has no readable header") from None
        if header.get("kind") != LEDGER_HEADER_KIND or header.get("version") != LEDGER_VERSION:
            raise CohortError("ledger header is not a version 1 cohort ledger")
        if header.get("census_sha256") != self.census_sha256:
            raise CohortError("ledger belongs to another census")
        if header.get("database_uuid") != self.database_uuid:
            raise CohortError("ledger belongs to another database")
        for position, line in enumerate(lines[1:], start=2):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                if position == len(lines):
                    self.torn_tail = True
                    continue
                raise CohortError(f"ledger line {position} is not JSON") from None
            contact_id = str(row.get("vanillasoft_contact_id") or "")
            if not contact_id.isdigit() or row.get("class") not in CLASSES:
                raise CohortError(f"ledger line {position} is not a cohort disposition")
            self.rows[contact_id] = row

    def _write_line(self, record: dict) -> None:
        if self.torn_tail:
            # A row cut short by a crash recorded nothing; the database decides that id again.
            raw = self.path.read_bytes()
            os.truncate(self.path, raw.rstrip(b"\n").rfind(b"\n") + 1)
            self.torn_tail = False
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def append(self, record: dict) -> None:
        record = {**record, "recorded_at": iso_now()}
        self._write_line(record)
        self.rows[record["vanillasoft_contact_id"]] = record


def report(census: Mapping[str, str], imported: Iterable[str], ledger: Mapping[str, dict]) -> dict:
    """Disposition of every frozen ContactID. Durable refs decide ``imported``; ledger rows give reasons."""
    durable = set(imported)
    classes = dict.fromkeys(CLASSES, 0)
    by_decision: dict[str, dict[str, int]] = {decision: dict.fromkeys(CLASSES, 0) for decision in PARTITION}
    undispositioned: list[str] = []
    unexplained: list[str] = []
    imported_with_errors = 0
    for contact_id, decision in census.items():
        if contact_id in durable:
            cls = IMPORTED
            row = ledger.get(contact_id) or {}
            if any(signal.get("level") == "ERROR" for signal in row.get("signals") or []):
                imported_with_errors += 1
        else:
            row = ledger.get(contact_id)
            cls = (row or {}).get("class")
            if cls is None:
                undispositioned.append(contact_id)
                continue
            if cls == IMPORTED:
                cls = GENUINE_FAILED
                unexplained.append(contact_id)
            elif not [s for s in row.get("signals") or [] if s.get("level") != "UNKNOWN"]:
                unexplained.append(contact_id)
        classes[cls] += 1
        by_decision[decision][cls] += 1
    dispositioned = sum(classes.values())
    size = len(census)
    complete = dispositioned == size and not undispositioned
    return {
        "cohort": size,
        "dispositioned": dispositioned,
        "undispositioned": len(undispositioned),
        "classes": classes,
        "by_decision": by_decision,
        "dispositions_without_a_source_reason": len(unexplained),
        "imported_with_error_signals": imported_with_errors,
        "HISTORICAL_SNAPSHOT_COMPLETE": complete,
        "historical_data_complete": complete
        and not imported_with_errors
        and classes[IMPORTED] + classes[DUPLICATE_SKIPPED] == size,
        "LIVE_DELTA_COMPLETENESS": "NOT_RUN",
        "FULL_CURRENT_CONTACT_COVERAGE": "UNKNOWN",
    }


def iso_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Production permit (amendment v1.2 D2). Local to this module because
# plasticos_crm_sync does not depend on plasticos_partner_import; a parity test
# holds this decision table equal to erp/production_permit.verify_permit.
# ---------------------------------------------------------------------------

PERMIT_ENV = "VANILLASOFT_PRODUCTION_PERMIT"
PERMIT_PHASE = "crm_history"
PRODUCTION_STAGE = "production"
CONSUMED_PREFIX = "plasticos_crm_sync.production_permit."
MAX_VALIDITY = timedelta(hours=24)
_PERMIT_FIELDS = (
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
_PERMIT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,79}$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class PermitRefused(RuntimeError):
    def __init__(self, reasons: Iterable[str]):
        self.reasons = tuple(reasons)
        super().__init__("; ".join(self.reasons))


@dataclass(frozen=True)
class Observed:
    database_name: str
    database_uuid: str
    odoo_stage: str
    release_sha: str | None
    release_clean: bool


def load_permit(path: str | Path) -> dict:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PermitRefused([f"permit file unreadable: {type(exc).__name__}"]) from None
    if not isinstance(document, dict):
        raise PermitRefused(["permit file is not a JSON object"])
    reasons = [f"permit field {name} is missing or empty" for name in _PERMIT_FIELDS if not _text(document.get(name))]
    unknown = sorted(set(document) - set(_PERMIT_FIELDS))
    if unknown:
        reasons.append(f"permit has unknown fields: {', '.join(unknown)}")
    if reasons:
        raise PermitRefused(reasons)
    if not _PERMIT_ID.match(document["permit_id"]):
        reasons.append("permit_id must be 8-80 characters of letters, digits, dot, dash or underscore")
    if document["phase"] != PERMIT_PHASE:
        reasons.append(f"permit phase must be {PERMIT_PHASE}")
    if not _UUID.match(document["database_uuid"].strip().lower()):
        reasons.append("database_uuid is not a UUID")
    if not _GIT_SHA.match(document["release_sha"].strip().lower()):
        reasons.append("release_sha is not a 40-character git SHA")
    if not _SHA256.match(document["source_fingerprint"].strip().lower()):
        reasons.append("source_fingerprint is not a SHA-256 hex digest")
    try:
        expires_at = _parse_time(document["expires_at"])
    except ValueError as exc:
        reasons.append(str(exc))
        expires_at = None
    if reasons:
        raise PermitRefused(reasons)
    permit = {name: document[name].strip() for name in _PERMIT_FIELDS}
    for name in ("database_uuid", "odoo_stage", "release_sha", "source_fingerprint"):
        permit[name] = permit[name].lower()
    permit["expires_at"] = expires_at
    return permit


def verify_permit(permit: Mapping, observed: Observed, *, fingerprint: str, now: datetime | None = None) -> None:
    now = (now or datetime.now(UTC)).astimezone(UTC)
    reasons: list[str] = []
    if observed.odoo_stage != PRODUCTION_STAGE:
        reasons.append(
            f"ODOO_STAGE is {observed.odoo_stage or 'unset'}: a permit is only valid on the production stage"
        )
    if permit["odoo_stage"] != PRODUCTION_STAGE:
        reasons.append(f"permit odoo_stage is {permit['odoo_stage']}, not production")
    if permit["database_name"] != observed.database_name:
        reasons.append(f"permit names database {permit['database_name']}, connected to {observed.database_name}")
    if permit["database_uuid"] != (observed.database_uuid or "").lower():
        reasons.append("permit database_uuid does not match the connected database")
    if not observed.release_sha:
        reasons.append("release identity is not provable on this host (no readable git checkout)")
    elif not observed.release_clean:
        reasons.append("the addon checkout has modified tracked files; release identity is not the reviewed commit")
    elif permit["release_sha"] != observed.release_sha:
        reasons.append(f"permit release_sha {permit['release_sha'][:12]} != running {observed.release_sha[:12]}")
    if permit["source_fingerprint"] != fingerprint:
        reasons.append("permit source_fingerprint is not the verified census SHA-256")
    if permit["expires_at"] <= now:
        reasons.append("permit expired")
    elif permit["expires_at"] - now > MAX_VALIDITY:
        reasons.append("permit validity exceeds 24 hours")
    if reasons:
        raise PermitRefused(reasons)


def check_erp_completion(raw: str | None, observed: Observed) -> None:
    """CRM history on Production follows a committed ERP commercial phase on the same database."""
    if not raw:
        raise PermitRefused(["no committed erp_commercial phase on this database"])
    try:
        witness = json.loads(raw)
    except ValueError:
        raise PermitRefused(["erp_commercial witness is not readable JSON"]) from None
    reasons = []
    if witness.get("phase") != ERP_COMMERCIAL_PHASE:
        reasons.append("erp_commercial witness names another phase")
    if witness.get("database_uuid") != observed.database_uuid:
        reasons.append("erp_commercial witness belongs to another database")
    if witness.get("final_status") == "failed":
        reasons.append("the erp_commercial phase failed")
    if reasons:
        raise PermitRefused(reasons)


def consumed_key(permit_id: str) -> str:
    return f"{CONSUMED_PREFIX}{permit_id}"


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


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _parse_time(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        raise ValueError("expires_at must be an ISO-8601 UTC timestamp") from None
    if moment.tzinfo is None:
        raise ValueError("expires_at must carry a UTC offset")
    return moment.astimezone(UTC)
