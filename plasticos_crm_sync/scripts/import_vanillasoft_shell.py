"""Odoo-shell driver for ``make import-vanillasoft``.

Executed inside ``odoo shell`` against the target database (the Makefile pipes
this file into the shell). Configuration arrives via environment variables:

* ``VANILLASOFT_CALL_FLOOR`` — call history floor (ISO UTC). **Required.** A
  full import has no safe default floor: a 30-day fallback would run the
  rolling window under the full-import name and report it complete.
* ``VANILLASOFT_CONTACT_FLOOR`` — contact floor (ISO UTC); defaults to the call
  floor (full-import semantics).
* ``VANILLASOFT_REPORT_PATH`` — write the machine-readable summary JSON here
  (default ``.l9/pr/import-vanillasoft-summary.json``).

Preflight is fail-closed: a missing call floor, a missing VanillaSoft API key
or an unreachable endpoint exits nonzero BEFORE any write. Exit codes:
0 success/partial, 1 material failure, 2 preflight failure.

The printed summary names the run's kind and the bounds it asked the provider
for, beside the counters: ``partial`` with a scope note means the declared
scope completed with a named limitation (an unproven census, a clamped
watermark, orphaned calls), never an implied full history.

Repository-cohort mode (``VANILLASOFT_CONTACT_EXPORT`` set) builds the census
in this shell from the export plus the server crosswalk. Crosswalk ids and the
four omitted duplicates are YES; every other id is PENDING. It does not call
``load_census``. A same-database ``erp_partners`` witness whose ``final_status``
is not ``failed`` replaces the commercial-phase refusal. An empty API-key
parameter is filled from ``VANILLASOFT_API_KEY`` and the value is never printed.
An active incremental cron is deactivated before the fetch.
``VANILLASOFT_PRODUCTION_CONFIRM=1`` with no permit file writes a one-use
``crm_history`` permit bound to the observed database, the release SHA, and the
generated census SHA-256, expiring inside 24 hours, then consumes it.

History mode (``VANILLASOFT_HISTORY_CENSUS`` set) replaces the full import
with the frozen 4,876-ContactID cohort, fetched one id at a time through
``SyncOrchestrator.upsert_contact_external_id``:

* ``VANILLASOFT_HISTORY_CENSUS`` — path of the no-PII
  ``vanillasoft_contact_id,decision`` census (an operator runtime input).
* ``VANILLASOFT_HISTORY_CENSUS_SHA256`` — its declared SHA-256. **Required.**
* ``VANILLASOFT_HISTORY_CHECKPOINT`` — append-only JSONL ledger on durable
  operator storage. **Required.** Bound to the census and the database.
* ``VANILLASOFT_HISTORY_MAX_IDS`` — fetch at most this many ids this session
  (default: all). A later session resumes.
* ``VANILLASOFT_HISTORY_FAILURE_BUDGET`` — stop after this many consecutive
  failed ids (default 25).
* ``VANILLASOFT_PRODUCTION_PERMIT`` — one-use permit file. Required on a
  production target (``ODOO_STAGE=production`` or a production-named database),
  after a committed ``erp_commercial`` phase; refused anywhere else.

Durable ``plasticos.crm.external.ref`` rows decide what is imported; a ledger
row only carries the reason. The run holds the connection's advisory lock, so
the incremental cron and the manual sync cannot overlap it, and refuses while
the cron is active. Lead writes run without mail tracking or assignment
notifications. Exit codes: 0 session completed (read the HISTORY VERDICT),
1 stopped on a failure budget or an unexplained disposition, 2 refused or
stopped on a rejected credential.
"""

import csv
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

HISTORY_CENSUS_ENV = "VANILLASOFT_HISTORY_CENSUS"
CONTACT_EXPORT_ENV = "VANILLASOFT_CONTACT_EXPORT"
CONFIRM_ENV = "VANILLASOFT_PRODUCTION_CONFIRM"
PARTNERS_WITNESS_PARAM = "plasticos_partner_import.production_phase1_witness"
PARTNERS_PHASE = "erp_partners"
PRODUCTION_STAGE = "production"
PRODUCTION_NAME_MARKERS = ("production", "prod")
DEFAULT_FAILURE_BUDGET = 25
CRM_CRON_XMLID = "plasticos_crm_sync.cron_crm_sync_all"
STOP_AUTH = "auth"
STOP_BUDGET = "budget"
STOP_SESSION_LIMIT = "max_ids"
NO_SEND_CONTEXT = {"tracking_disable": True, "mail_notrack": True, "mail_auto_subscribe_no_notify": True}


def _env_flag(name: str) -> str:
    return os.environ.get(name, "").strip()


def _odoo_env():
    env = globals().get("env")
    if env is None:
        raise SystemExit("no Odoo environment (run inside `odoo shell`)")
    return env


def main() -> int:
    if _env_flag(HISTORY_CENSUS_ENV) or _env_flag(CONTACT_EXPORT_ENV):
        return history(_odoo_env())
    # The floor is checked before the Odoo environment is touched: the refusal
    # is about the operator's request, not the database, and it must hold in
    # the pure-python tier too.
    call_floor = _env_flag("VANILLASOFT_CALL_FLOOR")
    if not call_floor:
        print(
            "PRECHECK FAILED: VANILLASOFT_CALL_FLOOR is not set. A full import has no safe default floor — "
            "pass an explicit ISO-8601 UTC instant, e.g. VANILLASOFT_CALL_FLOOR=2019-01-01T00:00:00Z "
            "(VANILLASOFT_CONTACT_FLOOR defaults to it)."
        )
        print("Nothing was imported.")
        return 2
    env = _odoo_env()
    from odoo.addons.plasticos_crm_sync.models.crm_connection import ICP_ROOT, ICP_VS_KEY_PARAM
    from odoo.addons.plasticos_crm_sync.services.import_summary import build_run_summary, utc_now
    from odoo.addons.plasticos_crm_sync.services.orchestrator import SyncOrchestrator

    icp = env["ir.config_parameter"].sudo()
    api_key = (icp.get_param(ICP_VS_KEY_PARAM) or "").strip()
    root = (icp.get_param(ICP_ROOT) or "").strip() or "https://vanillasoft.net"
    if not api_key:
        print("PRECHECK FAILED: VanillaSoft API key is not set (Settings → PlasticOS CRM Sync).")
        print("Nothing was imported.")
        return 2
    if not root.startswith("https://"):
        print(f"PRECHECK FAILED: VanillaSoft root endpoint is not HTTPS: {root!r}.")
        print("Nothing was imported.")
        return 2

    connection = env["plasticos.crm.connection"].get_or_create_vanillasoft_connection()

    contact_floor = _env_flag("VANILLASOFT_CONTACT_FLOOR") or None

    report_path = _env_flag("VANILLASOFT_REPORT_PATH") or ".l9/pr/import-vanillasoft-summary.json"

    start_time = utc_now()
    orch = SyncOrchestrator(env)
    orch.error_rows = []
    try:
        run = orch.run_full_import(
            connection,
            call_history_floor=call_floor,
            contact_modified_floor=contact_floor,
        )
    except Exception as exc:  # noqa: BLE001 - fail closed with the real reason
        print(f"IMPORT FAILED: {type(exc).__name__}: {str(exc).strip().splitlines()[0]}")
        return 1

    summary = build_run_summary(run, error_rows=orch.error_rows, start_time=start_time)
    parent = os.path.dirname(os.path.abspath(report_path))
    os.makedirs(parent, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True)
        handle.write("\n")

    print("=== VANILLASOFT IMPORT SUMMARY ===")
    print(f"status      : {summary['final_status']}")
    print(f"kind        : {run.kind or 'unknown'}")
    print(f"contacts    : modified_after >= {run.contact_scope_from_utc or 'unknown'}")
    print(f"calls       : {run.call_scope_from_utc or 'unknown'} -> {run.call_scope_to_utc or 'not reached'}")
    if run.error_excerpt:
        print("scope note  :")
        for line in str(run.error_excerpt).splitlines()[:8]:
            print(f"  {line[:200]}")
    print(
        f"seen/valid  : {summary['records_seen']} / {summary['records_valid']} (rejected {summary['records_rejected']})"
    )
    print(
        "created/updated/unchanged: "
        f"{summary['records_created']} / {summary['records_updated']} / {summary['records_unchanged']}"
    )
    print(f"duplicates  : {summary['duplicates']}  orphans buffered: {run.orphans_buffered or 0}")
    if summary["errors"]:
        print(f"errors      : {len(summary['errors'])} (first 10 below)")
        for row in summary["errors"][:10]:
            print(f"  - {row['record_ref']}: {row['message'][:160]}")
    if summary["final_status"] == "failed":
        print("IMPORT FAILED: material errors — see summary errors list")
        return 1
    return 0


# ── history mode ────────────────────────────────────────────────────────────


class _SignalCapture(logging.Handler):
    """WARNING and ERROR lines the CRM sync loggers emit for the current ContactID."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.rows: list[tuple[str, str]] = []

    def emit(self, record: logging.LogRecord) -> None:
        reason = record.getMessage()
        if record.exc_info and record.exc_info[1] is not None:
            reason = f"{reason}: {record.exc_info[1]}"
        self.rows.append((record.levelname, reason))


def _audit(event: str, **fields) -> None:
    record = {"event": f"crm_history.{event}", **fields}
    print("VANILLASOFT_HISTORY_AUDIT " + json.dumps(record, sort_keys=True, default=str), flush=True)


def _refuse(reason: str) -> int:
    _audit("refused", reasons=[reason])
    print(f"PRECHECK FAILED: {reason}")
    print("Nothing was imported.")
    return 2


def _param(env, key: str) -> str | None:
    # Direct SQL justification: read the committed row, bypassing the ir.config_parameter ormcache.
    env.cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s", (key,))
    row = env.cr.fetchone()
    return row[0] if row else None


def _positive_int(name: str, default: int | None) -> int | None:
    raw = _env_flag(name)
    if not raw:
        return default
    if not raw.isdigit() or int(raw) < 1:
        raise ValueError(f"{name} must be a positive integer")
    return int(raw)


@dataclass(frozen=True)
class _HistoryInputs:
    census: dict
    sha256: str
    checkpoint: str
    report: str
    max_ids: int | None
    budget: int


def _history_inputs(cohort) -> _HistoryInputs:
    checkpoint = _env_flag("VANILLASOFT_HISTORY_CHECKPOINT")
    if not checkpoint:
        raise cohort.CohortError("VANILLASOFT_HISTORY_CHECKPOINT is not set; name a ledger on durable operator storage")
    census_path = Path(_env_flag(HISTORY_CENSUS_ENV))
    if not census_path.is_file():
        raise cohort.CohortError("the census file named by VANILLASOFT_HISTORY_CENSUS is missing")
    sha256 = _env_flag("VANILLASOFT_HISTORY_CENSUS_SHA256").lower()
    # read_text() translates CRLF to LF, so its digest cannot match the raw file SHA-256.
    with census_path.open(encoding="utf-8", newline="") as handle:
        text = handle.read()
    return _HistoryInputs(
        census=cohort.load_census(text, expected_sha256=sha256),
        sha256=sha256,
        checkpoint=checkpoint,
        report=_env_flag("VANILLASOFT_REPORT_PATH") or f"{checkpoint}.report.json",
        max_ids=_positive_int("VANILLASOFT_HISTORY_MAX_IDS", None),
        budget=_positive_int("VANILLASOFT_HISTORY_FAILURE_BUDGET", DEFAULT_FAILURE_BUDGET),
    )


def _endpoint_problem(env) -> str | None:
    from odoo.addons.plasticos_crm_sync.models.crm_connection import ICP_ROOT, ICP_VS_KEY_PARAM  # noqa: PLC0415

    icp = env["ir.config_parameter"].sudo()  # settings read: the API key parameter is admin-only
    if not (icp.get_param(ICP_VS_KEY_PARAM) or "").strip():
        return "VanillaSoft API key is not set (Settings → PlasticOS CRM Sync)"
    root = (icp.get_param(ICP_ROOT) or "").strip() or "https://vanillasoft.net"
    if not root.startswith("https://"):
        return "VanillaSoft root endpoint is not HTTPS"
    return None


def _observed(env, cohort):
    import odoo.addons.plasticos_crm_sync as addon  # noqa: PLC0415

    # Direct SQL justification: the connected database's own name is the identity being verified.
    env.cr.execute("SELECT current_database()")
    name = str(env.cr.fetchone()[0])
    release_sha, clean = cohort.release_identity(Path(addon.__file__).resolve().parent.parent)
    return cohort.Observed(
        database_name=name,
        database_uuid=(_param(env, "database.uuid") or "").strip().lower(),
        odoo_stage=(os.environ.get("ODOO_STAGE") or "").strip().lower(),
        release_sha=release_sha,
        release_clean=clean,
    )


def _verified_permit(env, cohort, observed, census_sha256: str, *, commercial: bool = True):
    """``None`` off production. On a production target, the verified permit or ``PermitRefused``."""
    path = _env_flag(cohort.PERMIT_ENV)
    production = observed.odoo_stage == PRODUCTION_STAGE or any(
        marker in observed.database_name.lower() for marker in PRODUCTION_NAME_MARKERS
    )
    if not production and not path:
        return None
    if not path:
        raise cohort.PermitRefused([f"production target: {cohort.PERMIT_ENV} must name a one-use permit"])
    permit = cohort.load_permit(path)
    cohort.verify_permit(permit, observed, fingerprint=census_sha256)
    if commercial:
        cohort.check_erp_completion(_param(env, cohort.ERP_PHASE2_WITNESS_PARAM), observed)
    return permit


def _consume(env, cohort, permit, observed) -> None:
    value = json.dumps(
        {
            "permit_bindings": {**permit, "expires_at": permit["expires_at"].isoformat()},
            "observed_target": observed.__dict__,
            "consumed_at": cohort.iso_now(),
        },
        sort_keys=True,
    )
    # Direct SQL justification: one-use consumption must be a single atomic insert on the unique key,
    # so two concurrent runs cannot both consume one permit; the ORM set_param reads then writes.
    env.cr.execute(
        """
        INSERT INTO ir_config_parameter (key, value, create_uid, write_uid, create_date, write_date)
        VALUES (%s, %s, %s, %s, now() AT TIME ZONE 'UTC', now() AT TIME ZONE 'UTC')
        ON CONFLICT (key) DO NOTHING
        RETURNING id
        """,
        (cohort.consumed_key(permit["permit_id"]), value, env.uid, env.uid),
    )
    if env.cr.fetchone() is None:
        env.cr.rollback()
        raise cohort.PermitRefused([f"permit {permit['permit_id']} was already consumed"])
    env.cr.commit()
    _audit("consumed", permit_id=permit["permit_id"], source_fingerprint=permit["source_fingerprint"])


def _durable_ids(env, census: dict) -> set[str]:
    """ContactIDs with the ref their decision requires: an ERP person for YES, a CRM lead otherwise."""
    refs = (
        env["plasticos.crm.external.ref"]
        .sudo()  # import operator: refs are system identity rows, read in full
        .search_read(
            [("provider", "=", "vanillasoft"), ("external_id", "in", list(census))], ["external_id", "res_model"]
        )
    )
    wanted = {"YES": "res.partner"}
    return {
        ref["external_id"] for ref in refs if ref["res_model"] == wanted.get(census[ref["external_id"]], "crm.lead")
    }


def _fetch_one(env, cohort, orchestrator, connection, contact_id: str, capture: _SignalCapture):
    before = len(orchestrator.error_rows)
    capture.rows.clear()
    raw, exc_text = "exception", ""
    try:
        with env.cr.savepoint():
            orchestrator.upsert_contact_external_id(connection, contact_id)
        raw = orchestrator.last_lead_outcome or "none"
        env.cr.commit()
    except Exception as exc:  # noqa: BLE001 - one ContactID must not abort the cohort
        env.cr.rollback()
        raw, exc_text = type(exc).__name__, str(exc)
    messages = [str(row.get("message") or "") for row in orchestrator.error_rows[before:]]
    return raw, exc_text, messages


def _history_loop(env, cohort, orchestrator, connection, inputs, ledger, imported: set[str]) -> str:
    """Process the plan in id order. Returns the stop reason, or ``""`` when the plan ran out."""
    census = inputs.census
    capture = _SignalCapture()
    logger = logging.getLogger("odoo.addons.plasticos_crm_sync")
    logger.addHandler(capture)
    fetched = consecutive = 0
    try:
        for contact_id, action in cohort.plan(census, cohort.OMITTED_DUPLICATE_VS_IDS, imported, ledger.rows):
            base = {"vanillasoft_contact_id": contact_id, "decision": census[contact_id]}
            if action == cohort.SKIP_DUPLICATE:
                reason = "second VanillaSoft id for a person the approved crosswalk already binds; not fetched"
                ledger.append(
                    {
                        **base,
                        "class": cohort.DUPLICATE_SKIPPED,
                        "importer_outcome": "not_fetched",
                        "signals": [{"level": "WARNING", "reason": reason}],
                    }
                )
                continue
            if inputs.max_ids is not None and fetched >= inputs.max_ids:
                return STOP_SESSION_LIMIT
            fetched += 1
            raw, exc_text, messages = _fetch_one(env, cohort, orchestrator, connection, contact_id, capture)
            if cohort.is_auth_failure(exc_text):
                _audit("stopped", reason="credential rejected", detail=cohort.redact(exc_text))
                return STOP_AUTH
            durable = contact_id in _durable_ids(env, {contact_id: census[contact_id]})
            cls = cohort.classify(raw, messages, durable=durable)
            ledger.append(
                {
                    **base,
                    "class": cls,
                    "importer_outcome": raw,
                    "signals": cohort.signals(raw, messages, exc_text, list(capture.rows), cls),
                }
            )
            if durable:
                imported.add(contact_id)
            consecutive = 0 if cls in (cohort.IMPORTED, cohort.HELD) else consecutive + 1
            if consecutive >= inputs.budget:
                _audit("stopped", reason="consecutive failure budget", budget=inputs.budget)
                return STOP_BUDGET
            if fetched % 25 == 0:
                print(f"progress fetched={fetched} durable={len(imported)}/{cohort.COHORT}", flush=True)
    finally:
        logger.removeHandler(capture)
    return ""


def repository_census(export_ids: set[str], crosswalk_ids: set[str], omitted: set[str]) -> dict[str, str]:
    """YES is the crosswalk plus the omitted duplicates. Every other named id is PENDING."""
    yes = set(crosswalk_ids) | set(omitted)
    universe = set(export_ids) | set(crosswalk_ids) | set(omitted)
    return {contact_id: ("YES" if contact_id in yes else "PENDING") for contact_id in universe}


def census_text(census: dict[str, str]) -> str:
    """Canonical ``vanillasoft_contact_id,decision`` text, sorted by numeric ContactID."""
    lines = ["vanillasoft_contact_id,decision"]
    for contact_id in sorted(census, key=int):
        lines.append(f"{contact_id},{census[contact_id]}")
    return "\n".join(lines) + "\n"


def _export_contact_ids(path: Path) -> set[str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError("export is empty") from exc
        try:
            index = header.index("ContactID")
        except ValueError as exc:
            raise ValueError("export has no ContactID column") from exc
        found: set[str] = set()
        for row in reader:
            if len(row) <= index:
                continue
            contact_id = row[index].strip()
            if not contact_id:
                continue
            if not contact_id.isdigit():
                raise ValueError(f"export ContactID {contact_id!r} is not numeric")
            found.add(contact_id)
    if not found:
        raise ValueError("export names no ContactID")
    return found


def _repository_inputs(cohort, crosswalk: dict) -> _HistoryInputs:
    if _env_flag("VANILLASOFT_CALL_FLOOR") or _env_flag("VANILLASOFT_CONTACT_FLOOR"):
        raise cohort.CohortError("the repository cohort does not accept a call or contact floor")
    if _env_flag("VANILLASOFT_HISTORY_MAX_IDS"):
        raise cohort.CohortError("the repository cohort does not accept VANILLASOFT_HISTORY_MAX_IDS")
    checkpoint = _env_flag("VANILLASOFT_HISTORY_CHECKPOINT")
    if not checkpoint:
        raise cohort.CohortError("VANILLASOFT_HISTORY_CHECKPOINT is not set; name a ledger on durable operator storage")
    export_path = Path(_env_flag(CONTACT_EXPORT_ENV))
    if not export_path.is_file():
        raise cohort.CohortError("the export file named by VANILLASOFT_CONTACT_EXPORT is missing")
    census = repository_census(_export_contact_ids(export_path), set(crosswalk), set(cohort.OMITTED_DUPLICATE_VS_IDS))
    return _HistoryInputs(
        census=census,
        sha256=cohort.sha256_text(census_text(census)),
        checkpoint=checkpoint,
        report=_env_flag("VANILLASOFT_REPORT_PATH") or f"{checkpoint}.report.json",
        max_ids=None,
        budget=_positive_int("VANILLASOFT_HISTORY_FAILURE_BUDGET", DEFAULT_FAILURE_BUDGET),
    )


def _bind_api_key(env) -> None:
    """Fill an empty API-key parameter from the environment. The value is never printed."""
    from odoo.addons.plasticos_crm_sync.models.crm_connection import ICP_VS_KEY_PARAM  # noqa: PLC0415

    icp = env["ir.config_parameter"].sudo()  # settings write: the API key parameter is admin-only
    if (icp.get_param(ICP_VS_KEY_PARAM) or "").strip():
        return
    key = _env_flag("VANILLASOFT_API_KEY")
    if key:
        icp.set_param(ICP_VS_KEY_PARAM, key)


def _require_partners_witness(env, cohort, observed) -> None:
    """The partner phase on this database. ``partial`` is accepted; ``failed`` is not."""
    raw = _param(env, PARTNERS_WITNESS_PARAM)
    if not raw:
        raise cohort.PermitRefused(["no committed erp_partners phase on this database"])
    try:
        witness = json.loads(raw)
    except ValueError:
        raise cohort.PermitRefused(["erp_partners witness is not readable JSON"]) from None
    reasons = []
    if witness.get("phase") != PARTNERS_PHASE:
        reasons.append("erp_partners witness names another phase")
    if witness.get("database_uuid") != observed.database_uuid:
        reasons.append("erp_partners witness belongs to another database")
    if witness.get("final_status") == "failed":
        reasons.append("the erp_partners phase failed")
    if reasons:
        raise cohort.PermitRefused(reasons)


def _mint_confirm_permit(cohort, observed, fingerprint: str, checkpoint: str) -> None:
    """Write a one-use permit when confirm is set and no permit file was named."""
    if _env_flag(CONFIRM_ENV) != "1" or _env_flag(cohort.PERMIT_ENV):
        return
    from datetime import UTC, datetime, timedelta  # noqa: PLC0415

    if observed.odoo_stage != PRODUCTION_STAGE or not observed.release_sha or not observed.release_clean:
        raise cohort.PermitRefused(["production confirm does not mint a matching permit"])
    now = datetime.now(UTC)
    stamp = now.strftime("%Y%m%d%H%M%S")
    permit_id = f"crmhist-{fingerprint[:16]}-{stamp}"
    document = {
        "permit_id": permit_id,
        "phase": cohort.PERMIT_PHASE,
        "database_name": observed.database_name,
        "database_uuid": observed.database_uuid,
        "odoo_stage": PRODUCTION_STAGE,
        "release_sha": observed.release_sha,
        "source_fingerprint": fingerprint,
        "expires_at": (now + timedelta(hours=23)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "approved_by": "VANILLASOFT_PRODUCTION_CONFIRM",
    }
    path = Path(checkpoint).parent / f"{permit_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")
    os.environ[cohort.PERMIT_ENV] = str(path)


def _repository_history(env) -> int:
    """Import the export-plus-crosswalk cohort. The frozen 4,876 census is a different mode."""
    from odoo.addons.plasticos_crm_sync.services import historical_cohort as cohort  # noqa: PLC0415
    from odoo.addons.plasticos_crm_sync.services.approved_identity import load_crosswalk_map  # noqa: PLC0415
    from odoo.addons.plasticos_crm_sync.services.orchestrator import (  # noqa: PLC0415
        SyncOrchestrator,
        advisory_lock_key,
    )

    crosswalk = load_crosswalk_map(env) or {}
    try:
        inputs = _repository_inputs(cohort, crosswalk)
        cohort.verify_identity(inputs.census, crosswalk, cohort.OMITTED_DUPLICATE_VS_IDS)
    except (ValueError, OSError) as exc:
        return _refuse(str(exc))
    _bind_api_key(env)
    problem = _endpoint_problem(env)
    if problem:
        return _refuse(problem)
    if not _param(env, cohort.ERP_READY_PARAM):
        return _refuse("ERP contacts are not imported on this database; YES ContactIDs have no person to bind")
    observed = _observed(env, cohort)
    cron = env.ref(CRM_CRON_XMLID, raise_if_not_found=False)
    try:
        _require_partners_witness(env, cohort, observed)
        _mint_confirm_permit(cohort, observed, inputs.sha256, inputs.checkpoint)
        permit = _verified_permit(env, cohort, observed, inputs.sha256, commercial=False)
    except cohort.PermitRefused as refused:
        _audit("refused", reasons=list(refused.reasons), observed=observed.__dict__)
        env.cr.rollback()
        print("PRECHECK FAILED: production permit refused")
        print("Nothing was imported.")
        return 2
    try:
        ledger = cohort.Ledger(inputs.checkpoint, census_sha256=inputs.sha256, database_uuid=observed.database_uuid)
    except (cohort.CohortError, OSError) as exc:
        return _refuse(str(exc))
    _audit("ledger", rows=len(ledger.rows), torn_tail=ledger.torn_tail)
    if cron and cron.active:
        cron.active = False

    quiet = env(context={**env.context, **NO_SEND_CONTEXT})
    connection = quiet["plasticos.crm.connection"].get_or_create_vanillasoft_connection()
    orchestrator = SyncOrchestrator(quiet)
    orchestrator.error_rows = []
    lock_key = advisory_lock_key(connection.id)
    if not orchestrator._try_advisory_lock(lock_key):
        env.cr.rollback()
        return _refuse("another CRM sync or history run holds this connection's lock")
    try:
        if permit is not None:
            try:
                _consume(env, cohort, permit, observed)
            except cohort.PermitRefused as refused:
                _audit("refused", reasons=list(refused.reasons))
                print("PRECHECK FAILED: production permit refused")
                print("Nothing was imported.")
                return 2
        else:
            env.cr.commit()
        _audit("admitted", database=observed.database_name, permit=bool(permit), census_sha256=inputs.sha256)
        imported = _durable_ids(env, inputs.census)
        stop = _history_loop(quiet, cohort, orchestrator, connection, inputs, ledger, imported)
    finally:
        orchestrator._advisory_unlock(lock_key)
    return _history_verdict(env, cohort, inputs, ledger, stop)


def history(env) -> int:
    """Import the frozen census one ContactID at a time. See the module docstring."""
    if _env_flag(CONTACT_EXPORT_ENV):
        if _env_flag(HISTORY_CENSUS_ENV):
            return _refuse("VANILLASOFT_CONTACT_EXPORT cannot be combined with VANILLASOFT_HISTORY_CENSUS")
        return _repository_history(env)
    from odoo.addons.plasticos_crm_sync.services import historical_cohort as cohort  # noqa: PLC0415
    from odoo.addons.plasticos_crm_sync.services.approved_identity import load_crosswalk_map  # noqa: PLC0415
    from odoo.addons.plasticos_crm_sync.services.orchestrator import (  # noqa: PLC0415
        SyncOrchestrator,
        advisory_lock_key,
    )

    try:
        inputs = _history_inputs(cohort)
        cohort.verify_identity(inputs.census, load_crosswalk_map(env) or {}, cohort.OMITTED_DUPLICATE_VS_IDS)
    except (ValueError, OSError) as exc:
        return _refuse(str(exc))
    problem = _endpoint_problem(env)
    if problem:
        return _refuse(problem)
    cron = env.ref(CRM_CRON_XMLID, raise_if_not_found=False)
    if cron and cron.active:
        return _refuse("the CRM incremental cron is active; deactivate it for the history run")
    if not _param(env, cohort.ERP_READY_PARAM):
        return _refuse("ERP contacts are not imported on this database; YES ContactIDs have no person to bind")
    observed = _observed(env, cohort)
    try:
        permit = _verified_permit(env, cohort, observed, inputs.sha256)
    except cohort.PermitRefused as refused:
        _audit("refused", reasons=list(refused.reasons), observed=observed.__dict__)
        env.cr.rollback()
        print("PRECHECK FAILED: production permit refused")
        print("Nothing was imported.")
        return 2
    try:
        ledger = cohort.Ledger(inputs.checkpoint, census_sha256=inputs.sha256, database_uuid=observed.database_uuid)
    except (cohort.CohortError, OSError) as exc:
        return _refuse(str(exc))
    _audit("ledger", rows=len(ledger.rows), torn_tail=ledger.torn_tail)

    quiet = env(context={**env.context, **NO_SEND_CONTEXT})
    connection = quiet["plasticos.crm.connection"].get_or_create_vanillasoft_connection()
    orchestrator = SyncOrchestrator(quiet)
    orchestrator.error_rows = []
    lock_key = advisory_lock_key(connection.id)
    if not orchestrator._try_advisory_lock(lock_key):
        env.cr.rollback()
        return _refuse("another CRM sync or history run holds this connection's lock")
    try:
        if permit is not None:
            try:
                _consume(env, cohort, permit, observed)
            except cohort.PermitRefused as refused:
                _audit("refused", reasons=list(refused.reasons))
                print("PRECHECK FAILED: production permit refused")
                print("Nothing was imported.")
                return 2
        else:
            env.cr.commit()
        _audit("admitted", database=observed.database_name, permit=bool(permit), census_sha256=inputs.sha256)
        imported = _durable_ids(env, inputs.census)
        stop = _history_loop(quiet, cohort, orchestrator, connection, inputs, ledger, imported)
    finally:
        orchestrator._advisory_unlock(lock_key)
    return _history_verdict(env, cohort, inputs, ledger, stop)


def _history_verdict(env, cohort, inputs, ledger, stop: str) -> int:
    verdict = cohort.report(inputs.census, _durable_ids(env, inputs.census), ledger.rows)
    verdict["stopped"] = stop or None
    verdict["census_sha256"] = inputs.sha256
    parent = os.path.dirname(os.path.abspath(inputs.report))
    os.makedirs(parent, exist_ok=True)
    with open(inputs.report, "w", encoding="utf-8") as handle:
        json.dump(verdict, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print("HISTORY VERDICT " + json.dumps(verdict, sort_keys=True))
    if stop == STOP_AUTH:
        print("STOPPED: VanillaSoft rejected the credential. Nothing after the last committed id was imported.")
        return 2
    if stop == STOP_BUDGET:
        print("STOPPED: consecutive failure budget reached. Resume after reading the ledger reasons.")
        return 1
    if verdict["dispositions_without_a_source_reason"]:
        print("HISTORY FAILED: a disposition without a source reason is not a result")
        return 1
    if stop == STOP_SESSION_LIMIT:
        print("SESSION LIMIT: resume with the same census, checkpoint and a new session.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
