#!/usr/bin/env python3
"""Production-rehearsal kit helpers: gate receipts, verdict, and proof checks.

Pure stdlib, no Odoo import. ``run.sh``, ``weblead_e2e.sh`` and
``erp_slice.sh`` call it as ``python3 common.py <command> ...``; the
kit tests import it by path.

Contract (SPEC.md):

* Every gate ends in exactly one receipt ``gate-<n>.json`` with a state from
  ``STATES``. A gate that never wrote one is ``UNKNOWN`` and the run cannot be
  ``ready``.
* ``ready`` needs all seven gates ``PASS``. ``blocked`` needs every non-PASS
  gate to be ``BLOCKED`` on a blocker that ``expected/blockers.yaml`` marks
  ``verdict_effect: blocked`` (or ``SKIPPED`` behind one). Anything else is
  ``failed``.
* Import proof reads the importer's own summary and census files and the
  owner functions that judge them. The kit never writes into those files.
* Nothing here prints, stores or passes a secret value on argv. Secret values
  are read from environment variables named on the command line.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

KIT_DIR = Path(__file__).resolve().parent
REPO_ROOT = KIT_DIR.parents[1]
VALIDATOR = REPO_ROOT / "scripts" / "validate_import_summary.py"
CRM_COHORT = REPO_ROOT / "plasticos_crm_sync" / "services" / "historical_cohort.py"
BLOCKERS = KIT_DIR / "expected" / "blockers.yaml"

# The one execution path each gate must observe: the Make target, the shell
# driver it pipes into `odoo shell`, and the service that driver dispatches to.
# Production runs the same target and driver; the rehearsal differs only in the
# database, the bounds, the credentials and where the evidence lands.
ERP_EXECUTION_PATH = {
    "make_target": "import-erp",
    "driver": "plasticos_partner_import/scripts/import_erp_shell.py",
    "dispatcher": "plasticos.erp.import (plasticos_partner_import/models/erp_import_service.py)",
    "commercial_extension": "plasticos_transaction/models/legacy_erp_import_service.py (_inherit plasticos.erp.import)",
    "source": "restored ERP SQL Server database (reader.PayloadKind.DATABASE)",
}
VS_EXECUTION_PATH = {
    "make_target": "import-vanillasoft",
    "driver": "plasticos_crm_sync/scripts/import_vanillasoft_shell.py",
    "dispatcher": "history() → SyncOrchestrator.upsert_contact_external_id, one ContactID at a time",
    "source": "operator-supplied frozen 4,876-ContactID census + VanillaSoft API",
}
# Lines the drivers themselves print; the gate reads them as the runtime trace.
ERP_SOURCE_LINE = "ERP source: direct database read ("
ERP_VERDICT_LINE = "DATA VERDICT "
VS_AUDIT_PREFIX = "VANILLASOFT_HISTORY_AUDIT "
VS_VERDICT_PREFIX = "HISTORY VERDICT "
VS_ROLLING_BANNER = "=== VANILLASOFT IMPORT SUMMARY ==="
VS_STOP_OK = (None, "max_ids")

GATES: tuple[tuple[int, str], ...] = (
    (1, "branch-identity"),
    (2, "merge-tree"),
    (3, "install-smoke"),
    (4, "cutover-clone"),
    (5, "weblead-e2e"),
    (6, "erp-slice"),
    (7, "vanillasoft"),
)
GATE_NAMES = dict(GATES)
STATES = ("PASS", "FAIL", "BLOCKED", "SKIPPED", "UNKNOWN")
RECEIPT_SCHEMA = "l9.plasticos.rehearsal.gate.v1"
VERDICT_SCHEMA = "l9.plasticos.rehearsal.verdict.v1"
# Gate helper exit codes: the shell maps a receipt state onto these.
EXIT_FOR_STATE = {"PASS": 0, "FAIL": 1, "BLOCKED": 3, "SKIPPED": 4, "UNKNOWN": 5}

# ERP summary error refs that are run-level failures, not source rows.
ERP_RUN_LEVEL_REFS = frozenset({"reconciliation", "payables_reconciliation"})
# Shortest environment value the evidence scan treats as a secret.
MIN_SECRET_LEN = 6
REDACTED = "[redacted]"

_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(authorization\s*:\s*(?:bearer|basic)\s+|(?:api[_-]?key|password|passwd|token|bearer)\s*[:=]\s*)"
    r"(\"[^\"]*\"|'[^']*'|[^\s,;&)\]}]+)"
)


class ProofError(ValueError):
    """A proof input that cannot be read as evidence."""


# ── small utilities ─────────────────────────────────────────────────────────


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def redact(text: object) -> str:
    """Remove secret-looking assignments and auth headers from a diagnostic string."""
    return _SECRET_ASSIGNMENT.sub(lambda m: m.group(1) + REDACTED, str(text or ""))


def atomic_write(path: Path | str, text: str) -> None:
    """Write ``text`` to ``path`` through a private temp file and an atomic rename (mode 0600)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def parse_count(text: str) -> int:
    """Strict non-negative integer from one line of ``psql -At`` output.

    Empty output, several values, text or a negative number is not a count:
    a failed query must never read as zero.
    """
    lines = [line.strip() for line in str(text).splitlines() if line.strip()]
    if len(lines) != 1 or not re.fullmatch(r"\d+", lines[0]):
        raise ProofError(f"not a single non-negative integer: {str(text)[:80]!r}")
    return int(lines[0])


def parse_json_object(text: str, what: str) -> dict:
    try:
        value = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise ProofError(f"{what} is not JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ProofError(f"{what} is not a JSON object")
    return value


def load_json_file(path: Path | str, what: str) -> dict:
    path = Path(path)
    if not path.is_file():
        raise ProofError(f"{what} missing: {path.name}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ProofError(f"{what} unreadable: {exc}") from exc
    return parse_json_object(text, what)


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ProofError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    # Registered before execution: a dataclass in the owner module resolves its
    # annotations through sys.modules.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def validate_import_summary(summary: dict) -> list[str]:
    """Shared schema check, delegated to ``scripts/validate_import_summary.py``."""
    return list(_load_module("_rehearsal_summary_validator", VALIDATOR).validate_summary(summary))


def crm_cohort():
    """The history owner (``plasticos_crm_sync.services.historical_cohort``): cohort size, classes, partition."""
    return _load_module("_rehearsal_crm_cohort", CRM_COHORT)


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _not_before(stamp: object, run_started: str | None) -> bool:
    if not run_started:
        return True
    try:
        made = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        start = datetime.fromisoformat(run_started.replace("Z", "+00:00"))
    except ValueError:
        return False
    return made >= start


def _common_summary_failures(summary: dict, source: str, run_started: str | None) -> list[tuple[str, str]]:
    """Failures every import summary shares: schema, source, freshness, reconciliation."""
    failures: list[tuple[str, str]] = []
    schema_errors = validate_import_summary(summary)
    if schema_errors:
        failures.append(("summary-schema-invalid", "; ".join(schema_errors[:5])))
        return failures
    if summary.get("source") != source:
        failures.append(("summary-wrong-source", f"source={summary.get('source')!r}, expected {source!r}"))
    if not _not_before(summary.get("start_time"), run_started):
        failures.append(("summary-stale", f"start_time {summary.get('start_time')} precedes run start {run_started}"))
    seen = summary["records_seen"]
    total = (
        summary["records_created"]
        + summary["records_updated"]
        + summary["records_unchanged"]
        + summary["records_rejected"]
    )
    if seen != total:
        failures.append(("summary-census-mismatch", f"seen={seen} != created+updated+unchanged+rejected={total}"))
    if summary["duplicates"] != 0:
        failures.append(("summary-duplicates", f"duplicates={summary['duplicates']}"))
    if seen == 0:
        failures.append(("summary-empty", "records_seen=0"))
    return failures


def _result(state: str, reason: str, detail: str = "", **facts) -> dict:
    return {"state": state, "reason": reason, "detail": detail, "facts": facts}


# ── gate receipts and verdict ───────────────────────────────────────────────


def receipt_path(evidence_dir: Path | str, gate: int) -> Path:
    return Path(evidence_dir) / f"gate-{gate}.json"


def write_gate(
    evidence_dir: Path | str,
    gate: int,
    state: str,
    reason: str,
    detail: str = "",
    *,
    evidence: list[str] | tuple[str, ...] = (),
    exit_code: int | None = None,
    side_effects: bool = False,
    facts: dict | None = None,
) -> dict:
    """Write the one receipt for ``gate``. An existing receipt is never overwritten."""
    if gate not in GATE_NAMES:
        raise ProofError(f"unknown gate {gate}")
    if state not in STATES:
        raise ProofError(f"unknown state {state}")
    path = receipt_path(evidence_dir, gate)
    if path.exists():
        raise ProofError(f"gate {gate} already has a receipt")
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "gate": gate,
        "name": GATE_NAMES[gate],
        "state": state,
        "reason": reason,
        "detail": redact(detail)[:2000],
        "evidence": [str(item) for item in evidence],
        "exit_code": exit_code,
        "side_effects": bool(side_effects),
        "facts": facts or {},
        "recorded_at": utc_now(),
    }
    atomic_write(path, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def read_gate(evidence_dir: Path | str, gate: int) -> dict | None:
    path = receipt_path(evidence_dir, gate)
    if not path.is_file():
        return None
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"gate": gate, "name": GATE_NAMES[gate], "state": "UNKNOWN", "reason": "receipt-unreadable"}
    if not isinstance(receipt, dict) or receipt.get("state") not in STATES or receipt.get("gate") != gate:
        return {"gate": gate, "name": GATE_NAMES[gate], "state": "UNKNOWN", "reason": "receipt-invalid"}
    return receipt


def load_blockers(path: Path | str = BLOCKERS) -> dict[str, dict[str, str]]:
    """Scalar ``key: value`` fields of each ``- id:`` entry in ``blockers.yaml`` (stdlib parse)."""
    blockers: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        start = re.match(r"^\s*-\s+id:\s*([A-Za-z0-9_.-]+)\s*$", raw)
        if start:
            current = {"id": start.group(1)}
            blockers[current["id"]] = current
            continue
        field = re.match(r"^\s{4,}([a-z_]+):\s*(\S.*?)\s*$", raw)
        if current is not None and field and not field.group(2).startswith(">"):
            current[field.group(1)] = field.group(2)
    return blockers


def verdict_blocker_ids(path: Path | str = BLOCKERS) -> frozenset[str]:
    return frozenset(bid for bid, entry in load_blockers(path).items() if entry.get("verdict_effect") == "blocked")


def compute_verdict(gates: list[dict], run_failures: list[str], blocker_ids: frozenset[str]) -> tuple[str, list[str]]:
    """Terminal verdict from the seven gate receipts and run-level failures."""
    reasons = [f"run:{item}" for item in run_failures]
    non_pass = [g for g in gates if g["state"] != "PASS"]
    for g in non_pass:
        reasons.append(f"Gate{g['gate']}-{g['state']}:{g.get('reason', '')}")
    if not non_pass and not run_failures:
        return "ready", reasons
    if run_failures or any(g["state"] in ("FAIL", "UNKNOWN") for g in non_pass):
        return "failed", reasons
    blocked = [g for g in non_pass if g["state"] == "BLOCKED"]
    if blocked and all(g.get("reason") in blocker_ids for g in blocked):
        return "blocked", reasons
    # An undocumented block, or a skip with nothing that explains it.
    return "failed", reasons


def finalize(evidence_dir: Path | str, meta: dict, run_failures: list[str]) -> dict:
    """Write ``verdict.json`` and the backward-compatible ``verdict.txt``."""
    evidence_dir = Path(evidence_dir)
    gates = []
    for gate, name in GATES:
        receipt = read_gate(evidence_dir, gate)
        if receipt is None:
            receipt = {"gate": gate, "name": name, "state": "UNKNOWN", "reason": "no-receipt"}
        gates.append(receipt)
    try:
        blocker_ids = verdict_blocker_ids()
    except OSError:
        blocker_ids = frozenset()
        run_failures = [*run_failures, "blockers-file-unreadable"]
    verdict, reasons = compute_verdict(gates, run_failures, blocker_ids)
    record = {
        "schema": VERDICT_SCHEMA,
        **{key: meta.get(key, "") for key in ("run_ts", "staging_sha", "production_sha", "head_sha", "branch")},
        "verdict": verdict,
        "failures": reasons,
        "gates": [{key: g.get(key) for key in ("gate", "name", "state", "reason", "side_effects")} for g in gates],
        "finalized_at": utc_now(),
    }
    atomic_write(evidence_dir / "verdict.json", json.dumps(record, indent=2, sort_keys=True) + "\n")
    lines = [
        f"run_ts={record['run_ts']}",
        f"staging_sha={record['staging_sha']}",
        f"production_sha={record['production_sha']}",
        f"verdict={verdict}",
    ]
    if reasons:
        lines.append("failures=" + " ".join(reasons))
    lines.extend(f"gate{g['gate']}={g['state']} {g.get('reason', '')}".rstrip() for g in gates)
    atomic_write(evidence_dir / "verdict.txt", "\n".join(lines) + "\n")
    return record


def link_latest(evidence_root: Path | str, run_dir: Path | str) -> None:
    """Point ``evidence/latest`` at ``run_dir`` with one atomic rename."""
    evidence_root = Path(evidence_root)
    target = os.path.relpath(Path(run_dir), evidence_root)
    tmp = evidence_root / f".latest.{os.getpid()}"
    with contextlib.suppress(FileNotFoundError):
        os.unlink(tmp)
    os.symlink(target, tmp)
    os.replace(tmp, evidence_root / "latest")


def scan_secrets(evidence_dir: Path | str, env_names: list[str]) -> list[str]:
    """Redact in place every evidence file that holds the value of a named environment variable.

    Returns the relative paths that held a value. The values come from the
    environment, never from argv, and are never printed.
    """
    values = []
    for name in env_names:
        value = os.environ.get(name, "")
        if len(value.strip()) >= MIN_SECRET_LEN:
            values.append(value.strip())
    hits: list[str] = []
    if not values:
        return hits
    root = Path(evidence_dir)
    for path in sorted(p for p in root.rglob("*") if p.is_file() and not p.is_symlink()):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            hits.append(f"{path.relative_to(root)} (unreadable)")
            continue
        cleaned = text
        for value in values:
            cleaned = cleaned.replace(value, REDACTED)
        if cleaned != text:
            atomic_write(path, cleaned)
            hits.append(str(path.relative_to(root)))
    return hits


# ── Gate 5: web lead persistence and idempotency ───────────────────────────


def _id(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str) and re.fullmatch(r"[1-9]\d*", value.strip()):
        return int(value.strip())
    return None


def check_weblead_receipt(receipt: dict) -> list[tuple[str, str]]:
    """The controller receipt of an accepted HOT lead (``web_lead_api.py``)."""
    failures = []
    if receipt.get("status") != "ok":
        failures.append(("weblead-status", f"status={receipt.get('status')!r}"))
    if receipt.get("decision") != "hot":
        failures.append(("weblead-decision", f"decision={receipt.get('decision')!r} (selection value is hot)"))
    if receipt.get("state") != "intake_created":
        failures.append(("weblead-state", f"state={receipt.get('state')!r} error={receipt.get('error')!r}"))
    if _id(receipt.get("intake_id")) is None:
        failures.append(("weblead-intake-missing", "intake_id is empty"))
    if _id(receipt.get("web_lead_id")) is None:
        failures.append(("weblead-id-missing", "web_lead_id is empty"))
    return failures


SNAPSHOT_KEYS = ("web_leads", "intakes", "crm_leads", "partners")


def _snapshot(value: dict, what: str) -> dict[str, int]:
    out = {}
    for key in SNAPSHOT_KEYS:
        count = _int(value.get(key))
        if count is None or count < 0:
            raise ProofError(f"{what} snapshot has no count for {key}")
        out[key] = count
    return out


def check_weblead_persistence(
    receipt: dict,
    replay: dict,
    before: dict,
    after_first: dict,
    after_replay: dict,
    row: dict,
) -> list[tuple[str, str]]:
    """Read-back proof: one web lead, one intake, one unassigned non-Won opportunity, no partner, idempotent replay."""
    failures = check_weblead_receipt(receipt)
    web_lead_id = _id(receipt.get("web_lead_id"))
    intake_id = _id(receipt.get("intake_id"))
    try:
        b = _snapshot(before, "before")
        a1 = _snapshot(after_first, "after-first")
        a2 = _snapshot(after_replay, "after-replay")
    except ProofError as exc:
        return [*failures, ("weblead-snapshot-invalid", str(exc))]

    expected_delta = {"web_leads": 1, "intakes": 1, "crm_leads": 1, "partners": 0}
    for key, want in expected_delta.items():
        got = a1[key] - b[key]
        if got != want:
            failures.append((f"weblead-delta-{key}", f"first POST changed {key} by {got}, expected {want}"))
    for key in SNAPSHOT_KEYS:
        if a2[key] != a1[key]:
            failures.append((f"weblead-replay-{key}", f"replay changed {key}: {a1[key]} -> {a2[key]}"))

    if replay.get("status") != "ok" or _id(replay.get("web_lead_id")) != web_lead_id:
        failures.append(
            (
                "weblead-replay-identity",
                f"replay status={replay.get('status')!r} web_lead_id={replay.get('web_lead_id')!r}",
            )
        )

    lead = row.get("web_lead") if isinstance(row.get("web_lead"), dict) else None
    if lead is None:
        return [*failures, ("weblead-row-missing", f"no plasticos.web.lead row {web_lead_id}")]
    if _id(lead.get("id")) != web_lead_id:
        failures.append(("weblead-row-identity", f"row id {lead.get('id')!r} != {web_lead_id}"))
    if lead.get("state") != "intake_created":
        failures.append(("weblead-row-state", f"stored state={lead.get('state')!r}"))
    if _id(lead.get("intake_id")) != intake_id:
        failures.append(("weblead-row-intake", f"stored intake_id={lead.get('intake_id')!r} != {intake_id}"))
    if lead.get("partner_id") is not None:
        failures.append(("weblead-partner-created", f"web lead partner_id={lead.get('partner_id')!r}"))
    crm_lead_id = _id(lead.get("crm_lead_id"))
    if crm_lead_id is None:
        failures.append(("weblead-crm-link-missing", "plasticos.web.lead.crm_lead_id is empty"))
    if _int(row.get("same_lead_id_rows")) != 1:
        failures.append(("weblead-duplicate-rows", f"rows with this lead_id={row.get('same_lead_id_rows')!r}"))
    if _int(row.get("intake_exists")) != 1:
        failures.append(("weblead-intake-row", f"intake rows={row.get('intake_exists')!r}"))
    if _int(row.get("crm_for_intake")) != 1:
        failures.append(("weblead-crm-cardinality", f"crm.lead rows for intake={row.get('crm_for_intake')!r}"))

    crm = row.get("crm") if isinstance(row.get("crm"), dict) else None
    if crm is None:
        failures.append(("weblead-crm-row-missing", f"no crm.lead row {crm_lead_id}"))
        return failures
    if _id(crm.get("id")) != crm_lead_id:
        failures.append(("weblead-crm-identity", f"crm.lead id {crm.get('id')!r} != link {crm_lead_id}"))
    if crm.get("type") != "opportunity":
        failures.append(("weblead-crm-type", f"type={crm.get('type')!r}"))
    if _id(crm.get("source_intake_id")) != intake_id:
        failures.append(("weblead-crm-intake", f"source_intake_id={crm.get('source_intake_id')!r} != {intake_id}"))
    if crm.get("user_id") is not None:
        failures.append(("weblead-crm-assigned", f"user_id={crm.get('user_id')!r}"))
    if crm.get("partner_id") is not None:
        failures.append(("weblead-crm-partner", f"partner_id={crm.get('partner_id')!r}"))
    if crm.get("active") is not True:
        failures.append(("weblead-crm-inactive", f"active={crm.get('active')!r}"))
    if crm.get("is_won") is not False:
        failures.append(("weblead-crm-won", f"is_won={crm.get('is_won')!r}"))
    return failures


# ── Gate 6: ERP slice ───────────────────────────────────────────────────────

ERP_LAYERS = ("counterparties", "addresses", "contacts")


def _read_text(path: Path | str | None) -> str | None:
    if not path:
        return None
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def check_erp(
    summary_path: Path | str,
    census_path: Path | str,
    *,
    import_exit: int,
    layers: dict | None,
    run_started: str | None = None,
    log_text: str | None = None,
    database: str = "",
    limit: str = "",
    release_sha: str = "",
) -> dict:
    """Judge a ``make import-erp`` run from its own summary, census, log and the clone's layer counts.

    ``log_text`` is the importer's stdout (``05-erp-import.log``): the driver
    prints ``ERP source: direct database read (...)`` only when it selected
    the SQL source, and ``DATA VERDICT`` only for an applied run, so both are
    the runtime trace of the one canonical path (``ERP_EXECUTION_PATH``).
    ``None`` means the log was not read, which is a failure, not a pass.
    """
    execution_path = {**ERP_EXECUTION_PATH, "database": database, "limit": limit, "release_sha": release_sha}
    if import_exit != 0:
        return _result(
            "FAIL",
            "erp-import-exit",
            f"import-erp exited {import_exit}",
            import_exit=import_exit,
            execution_path=execution_path,
        )
    try:
        summary = load_json_file(summary_path, "ERP summary")
    except ProofError as exc:
        return _result("FAIL", "erp-summary-unreadable", str(exc), execution_path=execution_path)
    try:
        census = load_json_file(census_path, "ERP census")
    except ProofError as exc:
        return _result("FAIL", "erp-census-unreadable", str(exc), execution_path=execution_path)

    failures = [(f"erp-{code}", text) for code, text in _common_summary_failures(summary, "erp", run_started)]
    kind = census.get("payload_kind")
    if kind != "database":
        failures.append(("erp-source-not-database", f"payload_kind={kind!r}; Gate 6 accepts only database"))
    if not str(census.get("source_origin") or "").strip():
        failures.append(("erp-source-unattributed", "census source_origin is empty"))
    if log_text is None:
        failures.append(("erp-log-unreadable", "the import log was not read; the driver trace is unproven"))
    else:
        if ERP_SOURCE_LINE not in log_text:
            failures.append(("erp-dispatcher-unobserved", "the driver never reported a direct database read"))
        if ERP_VERDICT_LINE not in log_text:
            failures.append(("erp-verdict-unobserved", "the driver printed no DATA VERDICT; the run was not applied"))

    status = summary.get("final_status")
    unresolved = census.get("unresolved")
    disposition = status
    if status == "failed":
        failures.append(("erp-final-status-failed", "summary final_status=failed"))
    elif status == "partial":
        run_level = [row for row in summary.get("errors") or [] if row.get("record_ref") in ERP_RUN_LEVEL_REFS]
        attributed = (
            isinstance(unresolved, list)
            and unresolved
            and all(isinstance(r, dict) and r.get("table") and r.get("kind") and r.get("key") for r in unresolved)
        )
        if run_level or not attributed:
            failures.append(
                ("erp-unexpected-partial", "partial without source-attributed unresolved references in the census")
            )
        else:
            disposition = "partial-source-explained"
    elif status != "success":
        failures.append(("erp-final-status-unknown", f"final_status={status!r}"))

    if not summary.get("records_created"):
        failures.append(("erp-nothing-created", "records_created=0 on a fresh clone"))

    layer_counts: dict[str, int] = {}
    if not isinstance(layers, dict):
        failures.append(("erp-layer-census-unavailable", "clone layer counts were not read"))
    else:
        for layer in ERP_LAYERS:
            count = _int(layers.get(layer))
            if count is None:
                failures.append(("erp-layer-census-invalid", f"{layer} count missing"))
            elif count < 1:
                failures.append((f"erp-layer-missing-{layer}", f"{layer}: 0 imported identities in the clone"))
            else:
                layer_counts[layer] = count

    facts = {
        "final_status": status,
        "disposition": disposition,
        "payload_kind": kind,
        "source_origin": census.get("source_origin"),
        "records_seen": summary.get("records_seen"),
        "records_created": summary.get("records_created"),
        "records_rejected": summary.get("records_rejected"),
        "unresolved": len(unresolved) if isinstance(unresolved, list) else None,
        "layers": layer_counts,
        "execution_path": execution_path,
        "scope": "newest 10% of transaction worksheets; every partner layer; not a full historical import",
    }
    if failures:
        facts["failure_codes"] = [code for code, _text in failures]
        return _result("FAIL", failures[0][0], "; ".join(text for _c, text in failures), **facts)
    return _result("PASS", f"erp-{disposition}", "", **facts)


# ── Gate 7: VanillaSoft historical cohort (bounded) ─────────────────────────


def _audit_events(log_text: str) -> list[dict]:
    """The ``crm_history.*`` audit records the history driver prints, in order."""
    events = []
    for line in log_text.splitlines():
        if line.startswith(VS_AUDIT_PREFIX):
            with contextlib.suppress(ValueError):
                record = json.loads(line[len(VS_AUDIT_PREFIX) :])
                if isinstance(record, dict):
                    events.append(record)
    return events


def _history_report_shape(report: dict, cohort) -> list[str]:
    """Why ``report`` is not a ``historical_cohort.report`` document (empty when it is)."""
    problems = []
    classes = report.get("classes")
    if _int(report.get("cohort")) != cohort.COHORT:
        problems.append(f"cohort={report.get('cohort')!r}, expected {cohort.COHORT}")
    if not isinstance(classes, dict) or set(classes) != set(cohort.CLASSES):
        problems.append("classes is not the owner's class set")
        classes = {}
    for name, count in classes.items():
        if _int(count) is None or count < 0:
            problems.append(f"classes.{name} is not a count")
    by_decision = report.get("by_decision")
    if not isinstance(by_decision, dict) or set(by_decision) != set(cohort.PARTITION):
        problems.append("by_decision is not the YES/NO/PENDING partition")
    for key in (
        "dispositioned",
        "undispositioned",
        "dispositions_without_a_source_reason",
        "imported_with_error_signals",
    ):
        if _int(report.get(key)) is None or report[key] < 0:
            problems.append(f"{key} is not a count")
    for key in ("HISTORICAL_SNAPSHOT_COMPLETE", "historical_data_complete"):
        if not isinstance(report.get(key), bool):
            problems.append(f"{key} is not a boolean")
    for key in ("LIVE_DELTA_COMPLETENESS", "FULL_CURRENT_CONTACT_COVERAGE", "census_sha256"):
        if key not in report:
            problems.append(f"{key} is missing")
    if report.get("stopped") is not None and report.get("stopped") not in cohort_stop_values():
        problems.append(f"stopped={report.get('stopped')!r} is not a stop reason")
    if not problems and sum(classes.values()) != report["dispositioned"]:
        problems.append("classes do not sum to dispositioned")
    if not problems and report["dispositioned"] + report["undispositioned"] != cohort.COHORT:
        problems.append("dispositioned + undispositioned != cohort")
    return problems


def cohort_stop_values() -> tuple[str, ...]:
    return ("max_ids", "auth", "budget")


def _read_ledger(path: Path | str | None, cohort, *, census_sha256: str) -> tuple[dict | None, list[dict], str]:
    """``(header, rows, problem)`` of the checkpoint ledger; ``problem`` is empty when it is trustworthy."""
    if not path:
        return None, [], "no ledger path"
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return None, [], f"ledger unreadable: {exc}"
    try:
        header = json.loads(lines[0])
    except (IndexError, ValueError):
        return None, [], "ledger has no readable header"
    if not isinstance(header, dict) or header.get("kind") != cohort.LEDGER_HEADER_KIND:
        return header, [], "ledger header is not a cohort ledger header"
    if header.get("version") != cohort.LEDGER_VERSION:
        return header, [], f"ledger version {header.get('version')!r} is not {cohort.LEDGER_VERSION}"
    if header.get("census_sha256") != census_sha256:
        return header, [], "ledger belongs to another census"
    rows = []
    for position, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            return header, rows, f"ledger line {position} is not JSON"
        if not isinstance(row, dict) or row.get("class") not in cohort.CLASSES:
            return header, rows, f"ledger line {position} is not a cohort disposition"
        rows.append(row)
    return header, rows, ""


def check_vanillasoft_history(
    report_path: Path | str,
    *,
    import_exit: int,
    ledger_path: Path | str | None,
    log_text: str | None,
    refs_before: int | None,
    refs_after: int | None,
    census_sha256: str,
    database: str,
    max_ids: int | None,
    run_started: str | None = None,
    release_sha: str = "",
) -> dict:
    """Judge a bounded ``make import-vanillasoft`` history session on the clone.

    A ``PASS`` means only that the authorized sample exercised the production
    pipeline: history mode was admitted on this database for this census, every
    fetched ContactID has a source-attributed disposition, none failed, and at
    least one landed durably. It never asserts the cohort is complete.
    """
    cohort = crm_cohort()
    execution_path = {
        **VS_EXECUTION_PATH,
        "database": database,
        "census_sha256": census_sha256,
        "max_ids": max_ids,
        "release_sha": release_sha,
    }
    bounds = {
        "scope": "bounded sample of the frozen cohort; not historical completeness",
        "full_cohort_claimed": False,
        "max_ids": max_ids,
    }
    base = {"execution_path": execution_path, **bounds}
    if import_exit == 2:
        return _result("FAIL", "vanillasoft-preflight-failed", "import-vanillasoft refused (exit 2)", **base)
    if import_exit != 0:
        return _result("FAIL", "vanillasoft-history-import-exit", f"import-vanillasoft exited {import_exit}", **base)
    try:
        report = load_json_file(report_path, "history report")
    except ProofError as exc:
        return _result("FAIL", "vanillasoft-history-report-unreadable", str(exc), **base)

    failures: list[tuple[str, str]] = []
    problems = _history_report_shape(report, cohort)
    if problems:
        return _result("FAIL", "vanillasoft-history-report-shape", "; ".join(problems[:5]), **base)
    classes = report["classes"]
    if str(report.get("census_sha256") or "").lower() != census_sha256:
        failures.append(("vanillasoft-history-census-mismatch", "the report names another census"))
    if report.get("stopped") == "auth":
        failures.append(("vanillasoft-history-credential-rejected", "VanillaSoft rejected the credential"))
    elif report.get("stopped") == "budget":
        failures.append(("vanillasoft-history-failure-budget", "the consecutive failure budget stopped the run"))
    if report["dispositions_without_a_source_reason"]:
        failures.append(
            (
                "vanillasoft-history-unexplained-dispositions",
                f"{report['dispositions_without_a_source_reason']} dispositions carry no source reason",
            )
        )
    if report["imported_with_error_signals"]:
        failures.append(
            (
                "vanillasoft-history-imported-with-errors",
                f"{report['imported_with_error_signals']} imported ids logged ERROR",
            )
        )
    if classes[cohort.GENUINE_FAILED]:
        failures.append(("vanillasoft-history-genuine-failures", f"{classes[cohort.GENUINE_FAILED]} ContactIDs failed"))

    header, rows, ledger_problem = _read_ledger(ledger_path, cohort, census_sha256=census_sha256)
    fetched = sum(1 for row in rows if row.get("importer_outcome") != "not_fetched")
    if ledger_problem:
        failures.append(("vanillasoft-history-ledger-invalid", ledger_problem))
    elif len(rows) != report["dispositioned"]:
        failures.append(
            (
                "vanillasoft-history-ledger-mismatch",
                f"{len(rows)} ledger rows != {report['dispositioned']} dispositioned",
            )
        )

    admitted = None
    if log_text is None:
        failures.append(("vanillasoft-history-log-unreadable", "the import log was not read"))
    else:
        events = _audit_events(log_text)
        admitted = next((e for e in events if e.get("event") == "crm_history.admitted"), None)
        if VS_ROLLING_BANNER in log_text:
            failures.append(("vanillasoft-rolling-mode-observed", "the driver ran the rolling full import"))
        if admitted is None:
            failures.append(("vanillasoft-history-not-admitted", "no crm_history.admitted audit event"))
        else:
            if admitted.get("database") != database:
                failures.append(("vanillasoft-history-wrong-database", f"admitted on {admitted.get('database')!r}"))
            if admitted.get("census_sha256") != census_sha256:
                failures.append(("vanillasoft-history-admitted-other-census", "admitted for another census"))
            if admitted.get("permit") is not False:
                failures.append(("vanillasoft-history-permit-used", "a permit was consumed on the rehearsal clone"))
        if VS_VERDICT_PREFIX not in log_text:
            failures.append(("vanillasoft-history-verdict-unobserved", "the driver printed no HISTORY VERDICT"))

    landed = None
    if refs_before is None or refs_after is None:
        failures.append(("vanillasoft-history-refs-unavailable", "durable external refs were not read back"))
    else:
        landed = refs_after - refs_before
        if landed < classes[cohort.IMPORTED]:
            failures.append(
                (
                    "vanillasoft-history-durable-mismatch",
                    f"{landed} refs landed on the clone but the report counts {classes[cohort.IMPORTED]} imported",
                )
            )

    facts = {
        **base,
        "fetched": fetched,
        "attempted": classes[cohort.IMPORTED] + classes[cohort.HELD] + classes[cohort.GENUINE_FAILED],
        "imported": classes[cohort.IMPORTED],
        "held": classes[cohort.HELD],
        "duplicate_skipped": classes[cohort.DUPLICATE_SKIPPED],
        "genuine_failed": classes[cohort.GENUINE_FAILED],
        "dispositioned": report["dispositioned"],
        "undispositioned": report["undispositioned"],
        "stopped": report.get("stopped"),
        "historical_snapshot_complete": report["HISTORICAL_SNAPSHOT_COMPLETE"],
        "durable_refs_before": refs_before,
        "durable_refs_after": refs_after,
        "durable_refs_landed": landed,
        "ledger_rows": len(rows),
        "ledger_database_uuid": (header or {}).get("database_uuid"),
        "admitted": admitted is not None,
    }
    if failures:
        facts["failure_codes"] = [code for code, _text in failures]
        return _result("FAIL", failures[0][0], "; ".join(text for _c, text in failures), **facts)
    if fetched == 0 or classes[cohort.IMPORTED] == 0 or not landed:
        return _result(
            "BLOCKED",
            "vanillasoft-history-sample-no-import",
            "the bounded sample landed no durable import; the positive contact import is unproven and "
            "the cohort order is never changed to manufacture one",
            **facts,
        )
    return _result("PASS", "vanillasoft-history-sample-exercised", "", **facts)


# ── CLI ─────────────────────────────────────────────────────────────────────


def _emit_result(args, result: dict, evidence: list[str], side_effects: bool) -> int:
    write_gate(
        args.evidence_dir,
        args.gate,
        result["state"],
        result["reason"],
        result["detail"],
        evidence=evidence,
        exit_code=getattr(args, "import_exit", None),
        side_effects=side_effects,
        facts=result["facts"],
    )
    print(f"  Gate {args.gate} {result['state']}: {result['reason']} {redact(result['detail'])}".rstrip())
    return EXIT_FOR_STATE[result["state"]]


def _read_layers(path: str | None) -> dict | None:
    if not path:
        return None
    try:
        return load_json_file(path, "layer census")
    except ProofError:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("gate-write")
    p.add_argument("evidence_dir")
    p.add_argument("gate", type=int)
    p.add_argument("state", choices=STATES)
    p.add_argument("reason")
    p.add_argument("--detail", default="")
    p.add_argument("--evidence", action="append", default=[])
    p.add_argument("--exit-code", type=int)
    p.add_argument("--side-effects", action="store_true")

    p = sub.add_parser("gate-state")
    p.add_argument("evidence_dir")
    p.add_argument("gate", type=int)

    p = sub.add_parser("finalize")
    p.add_argument("evidence_dir")
    for key in ("run-ts", "staging-sha", "production-sha", "head-sha", "branch"):
        p.add_argument(f"--{key}", default="")
    p.add_argument("--run-failure", action="append", default=[])

    p = sub.add_parser("link-latest")
    p.add_argument("evidence_root")
    p.add_argument("run_dir")

    p = sub.add_parser("scan-secrets")
    p.add_argument("evidence_dir")
    p.add_argument("--env", action="append", default=[], help="environment variable NAME whose value must not appear")

    p = sub.add_parser("count")
    p.add_argument("file")

    p = sub.add_parser("sha256")
    p.add_argument("file")

    p = sub.add_parser("check-weblead")
    p.add_argument("evidence_dir")
    p.add_argument("--gate", type=int, default=5)
    for key in ("receipt", "replay", "before", "after-first", "after-replay", "row"):
        p.add_argument(f"--{key}", required=True)

    p = sub.add_parser("check-erp")
    p.add_argument("evidence_dir")
    p.add_argument("--gate", type=int, default=6)
    p.add_argument("--summary", required=True)
    p.add_argument("--import-exit", type=int, required=True)
    p.add_argument("--layers")
    p.add_argument("--run-started")
    p.add_argument("--log", help="the importer's stdout; the driver's own source and verdict lines are the trace")
    p.add_argument("--database", default="")
    p.add_argument("--limit", default="")
    p.add_argument("--release-sha", default="")

    p = sub.add_parser("check-vanillasoft-history")
    p.add_argument("evidence_dir")
    p.add_argument("--gate", type=int, default=7)
    p.add_argument("--report", required=True, help="the history driver's verdict JSON (VANILLASOFT_REPORT_PATH)")
    p.add_argument("--import-exit", type=int, required=True)
    p.add_argument("--ledger", help="the append-only checkpoint written for this run")
    p.add_argument("--log", help="the importer's stdout; the audit and verdict lines are the trace")
    p.add_argument("--refs-before")
    p.add_argument("--refs-after")
    p.add_argument("--census-sha256", required=True)
    p.add_argument("--database", required=True)
    p.add_argument("--max-ids", type=int)
    p.add_argument("--run-started")
    p.add_argument("--release-sha", default="")

    args = parser.parse_args(argv)

    if args.command == "gate-write":
        try:
            write_gate(
                args.evidence_dir,
                args.gate,
                args.state,
                args.reason,
                args.detail,
                evidence=args.evidence,
                exit_code=args.exit_code,
                side_effects=args.side_effects,
            )
        except ProofError as exc:
            print(f"gate-write refused: {exc}", file=sys.stderr)
            return 2
        return 0
    if args.command == "gate-state":
        receipt = read_gate(args.evidence_dir, args.gate)
        print(receipt["state"] if receipt else "MISSING")
        return 0
    if args.command == "finalize":
        record = finalize(
            args.evidence_dir,
            {
                "run_ts": args.run_ts,
                "staging_sha": args.staging_sha,
                "production_sha": args.production_sha,
                "head_sha": args.head_sha,
                "branch": args.branch,
            },
            args.run_failure,
        )
        print(record["verdict"])
        return 0
    if args.command == "link-latest":
        link_latest(args.evidence_root, args.run_dir)
        return 0
    if args.command == "scan-secrets":
        hits = scan_secrets(args.evidence_dir, args.env)
        for hit in hits:
            print(f"redacted a secret value in {hit}")
        return 1 if hits else 0
    if args.command == "count":
        try:
            print(parse_count(Path(args.file).read_text(encoding="utf-8")))
        except (OSError, ProofError) as exc:
            print(f"invalid count: {exc}", file=sys.stderr)
            return 2
        return 0
    if args.command == "sha256":
        try:
            print(sha256_file(args.file))
        except OSError as exc:
            print(f"unreadable: {exc}", file=sys.stderr)
            return 2
        return 0
    if args.command == "check-weblead":
        try:
            docs = {
                key: load_json_file(getattr(args, key.replace("-", "_")), key)
                for key in ("receipt", "replay", "before", "after-first", "after-replay", "row")
            }
        except ProofError as exc:
            result = _result("FAIL", "weblead-proof-unreadable", str(exc))
        else:
            failures = check_weblead_persistence(
                docs["receipt"], docs["replay"], docs["before"], docs["after-first"], docs["after-replay"], docs["row"]
            )
            result = (
                _result("FAIL", failures[0][0], "; ".join(t for _c, t in failures))
                if failures
                else _result(
                    "PASS",
                    "weblead-crm-opportunity-proven",
                    "",
                    web_lead_id=docs["receipt"].get("web_lead_id"),
                    intake_id=docs["receipt"].get("intake_id"),
                    crm_lead_id=(docs["row"].get("crm") or {}).get("id"),
                )
            )
        return _emit_result(args, result, ["04-weblead-result.json", "04-weblead-db.json"], True)
    if args.command == "check-erp":
        summary = Path(args.summary)
        census = summary.with_name(summary.stem + "-census.json")
        result = check_erp(
            summary,
            census,
            import_exit=args.import_exit,
            layers=_read_layers(args.layers),
            run_started=args.run_started,
            log_text=_read_text(args.log),
            database=args.database,
            limit=args.limit,
            release_sha=args.release_sha,
        )
        evidence = [summary.name, census.name] + ([Path(args.log).name] if args.log else [])
        return _emit_result(args, result, evidence, True)
    if args.command == "check-vanillasoft-history":

        def _count(path: str | None) -> int | None:
            if not path:
                return None
            with contextlib.suppress(OSError, ProofError):
                return parse_count(Path(path).read_text(encoding="utf-8"))
            return None

        result = check_vanillasoft_history(
            args.report,
            import_exit=args.import_exit,
            ledger_path=args.ledger,
            log_text=_read_text(args.log),
            refs_before=_count(args.refs_before),
            refs_after=_count(args.refs_after),
            census_sha256=args.census_sha256.strip().lower(),
            database=args.database,
            max_ids=args.max_ids,
            run_started=args.run_started,
            release_sha=args.release_sha,
        )
        evidence = [Path(p).name for p in (args.report, args.ledger, args.log) if p]
        return _emit_result(args, result, evidence, True)
    return 2


if __name__ == "__main__":
    sys.exit(main())
