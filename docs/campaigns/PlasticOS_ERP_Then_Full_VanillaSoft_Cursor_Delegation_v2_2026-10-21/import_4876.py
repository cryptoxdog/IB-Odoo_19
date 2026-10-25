"""Full 4,876 VanillaSoft import. Every disposition keeps its reason.

The ID list is ``crm_id_census.csv`` (``vanillasoft_contact_id,decision``).
YES ids are bound through the loaded crosswalk. NO and PENDING ids take the
normal lead path and are not attached to an ERP person. A second VanillaSoft
id for a person the crosswalk already approves is not imported.

A warning or a failure without its reason is an absent signal. This script
keeps every warning and error the CRM sync logger emits for that contact,
every importer ``error_rows`` message, and the exception text. An imported
bind can still carry warnings. Those warnings stay on the row. A held,
skipped, or failed row that produced no reason is recorded as UNKNOWN, not
as a clean failure. Credential-shaped text and email addresses are redacted.
The operational reason is kept.

Each checkpoint row also stores ``placement`` and ``crosswalk_sha256``.
``open_exceptions.json`` is the distinct-reason ledger and is written before
a coverage or missing-reason exit. ``crosswalk_stamp.json`` refuses a resume
against a different file. A rejected credential writes ``credential_stop.json``
and exits 2 without discarding the checkpoint.
"""

import csv
import hashlib
import json
import logging
import re
from pathlib import Path

ROOT = Path("/mnt/extra-addons/Current Work - IGNORE/erp-then-vs-full-crm")
CHECKPOINT = ROOT / "crm_checkpoint.jsonl"
STAMP = ROOT / "crosswalk_stamp.json"
EXCEPTIONS = ROOT / "open_exceptions.json"
CROSSWALK = str(ROOT / "03_APPROVED_CONTACT_CROSSWALK.csv")
CENSUS = ROOT / "crm_id_census.csv"
COHORT = 4876
PINNED_SHA256 = "9aa6fcd0eee9fedf106c23090fa32b24c2faacc1576531c4f4fcc846663b72c1"
_SECRET = re.compile(r"(?i)(api[_-]?key|authorization|password|bearer)\s*[:=]\s*\S+")
_EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")
_MAX_REASON = 500


def redact(text: str) -> str:
    """Drop credential-shaped text and email addresses. Keep the cause."""
    cleaned = _SECRET.sub(r"\1=[redacted]", text or "")
    cleaned = _EMAIL.sub("[redacted-email]", cleaned)
    return " ".join(cleaned.split())[:_MAX_REASON]


def classify(raw: str, messages: list[str]) -> str:
    """Map one importer outcome onto imported, held, or genuine_failed."""
    if raw in {"created", "updated", "unchanged"}:
        return "imported"
    text = " ".join(messages)
    if raw == "failed" and "ERP marker" in text:
        return "held"
    return "genuine_failed"


def remember(signals: list[dict], seen: set[tuple[str, str]], level: str, reason: str) -> None:
    """Append one sanitized reason. A repeated reason on the same contact stays once."""
    cleaned = redact(reason)
    if not cleaned:
        return
    key = (level, cleaned)
    if key in seen:
        return
    seen.add(key)
    signals.append({"level": level, "reason": cleaned})


class _SignalCapture(logging.Handler):
    """Keep WARNING and ERROR lines from the CRM sync loggers for one contact."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.rows: list[tuple[str, str]] = []

    def emit(self, record: logging.LogRecord) -> None:
        reason = record.getMessage()
        error = record.exc_info[1] if record.exc_info else None
        if error is not None:
            reason = f"{reason}: {error}"
        self.rows.append((record.levelname, reason))


def _placement(classification: str, erp_ct_id: str, signals: list[dict]) -> str:
    """Name the path that produced the row. The class stays a separate fact."""
    reasons = " ".join(str(signal.get("reason") or "") for signal in signals)
    if classification == "duplicate_skipped":
        return "duplicate_skipped"
    if classification == "genuine_failed" and "not fetched" in reasons:
        return "not_fetched"
    if "placed on active company" in reasons:
        return "active_company"
    if "importing as crm lead" in reasons:
        return "crm_lead"
    if classification == "imported" and erp_ct_id:
        return "erp_person"
    if classification == "imported":
        return "crm_lead"
    if classification == "held":
        return "held"
    if classification == "genuine_failed":
        return "genuine_failed"
    return "unknown"


def _die(reason: str) -> None:
    """Leave the refusal on disk. A traceback with no file is not a result."""
    ROOT.mkdir(parents=True, exist_ok=True)
    EXCEPTIONS.write_text(
        json.dumps([{"level": "ERROR", "reason": reason, "count": 1}], indent=2) + "\n",
        encoding="utf-8",
    )
    raise SystemExit(reason)


def _require_crosswalk() -> str:
    path = Path(CROSSWALK)
    if not path.is_file():
        _die(f"crosswalk file is missing: {path}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != PINNED_SHA256:
        _die(f"crosswalk SHA256 {digest} != {PINNED_SHA256}")
    return digest


def _require_stamp(digest: str, vs_count: int, erp_count: int) -> None:
    """Refuse a checkpoint that was written against a different crosswalk."""
    payload = {"erp_ct_ids": erp_count, "sha256": digest, "vs_ids": vs_count}
    if STAMP.exists():
        prior = json.loads(STAMP.read_text(encoding="utf-8"))
        if prior != payload:
            _die(f"crosswalk_stamp {prior} != this file {payload}; refuse to resume a different crosswalk")
        return
    if CHECKPOINT.exists() and CHECKPOINT.stat().st_size:
        _die("crm_checkpoint.jsonl exists without crosswalk_stamp.json; refuse to resume a pre-v2.3 checkpoint")
    STAMP.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _signals_for_contact(raw: str, messages: list[str], exc_text: str, logged: list[tuple[str, str]]) -> list[dict]:
    signals: list[dict] = []
    seen: set[tuple[str, str]] = set()
    if exc_text:
        remember(signals, seen, "ERROR", f"{raw}: {exc_text}")
    for message in messages:
        remember(signals, seen, "ERROR", message)
    for level, reason in logged:
        remember(signals, seen, level, reason)
    if classify(raw, messages) != "imported" and not signals:
        remember(signals, seen, "UNKNOWN", f"outcome {raw} produced no reason")
    return signals


def _load_census() -> dict[str, str]:
    if not CENSUS.is_file():
        raise SystemExit(f"crm_id_census.csv is missing: {CENSUS}")
    mapping: dict[str, str] = {}
    with CENSUS.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["vanillasoft_contact_id", "decision"]:
            raise SystemExit(f"crm_id_census.csv header {reader.fieldnames!r} is not the no-PII census")
        for line_no, row in enumerate(reader, start=2):
            contact_id = (row.get("vanillasoft_contact_id") or "").strip()
            decision = (row.get("decision") or "").strip()
            if not contact_id.isdigit() or decision not in {"YES", "NO", "PENDING"}:
                raise SystemExit(f"crm_id_census.csv row {line_no} is not an id and YES/NO/PENDING")
            if contact_id in mapping:
                raise SystemExit(f"crm_id_census.csv repeats {contact_id}")
            mapping[contact_id] = decision
    if len(mapping) != COHORT:
        raise SystemExit(f"crm_id_census.csv has {len(mapping)} ids, not {COHORT}")
    return mapping


def _append(record: dict, digest: str) -> None:
    record["crosswalk_sha256"] = digest
    record["placement"] = _placement(record["class"], record.get("erp_ct_id") or "", record["signals"])
    with CHECKPOINT.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    print(
        f"placement={record['placement']} contact={record['vanillasoft_contact_id']} "
        f"class={record['class']} outcome={record['importer_outcome']}"
    )
    for signal in record["signals"]:
        print(f"signal level={signal['level']} contact={record['vanillasoft_contact_id']} reason={signal['reason']}")


def _file_census(path: Path) -> tuple[int, int]:
    vs_ids = 0
    erp_ids: set[str] = set()
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        for row in reader:
            if not row or (len(row) == 1 and row[0] == ""):
                continue
            vs_ids += 1
            if row[0]:
                erp_ids.add(row[0])
    return vs_ids, len(erp_ids)


def main(env) -> None:
    """Import each census id once. Stop on a dead credential. Keep every reason."""
    from odoo.addons.plasticos_crm_sync.services.approved_identity import OMITTED_DUPLICATE_VS_IDS
    from odoo.addons.plasticos_crm_sync.services.orchestrator import SyncOrchestrator

    ROOT.mkdir(parents=True, exist_ok=True)
    census = _load_census()
    digest = _require_crosswalk()
    file_vs, file_erp = _file_census(Path(CROSSWALK))
    _require_stamp(digest, file_vs, file_erp)
    icp = env["ir.config_parameter"].sudo()
    icp.set_param("plasticos_crm_sync.approved_contact_crosswalk", CROSSWALK)
    env.cr.commit()

    done = {}
    if CHECKPOINT.exists():
        for line in CHECKPOINT.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            done[row["vanillasoft_contact_id"]] = row

    connection = env["plasticos.crm.connection"].get_or_create_vanillasoft_connection()
    if not (connection.project_id or "").strip():
        connection.project_id = "139705"
        env.cr.commit()
    orchestrator = SyncOrchestrator(env)
    orchestrator._load_approved_crosswalk()
    crosswalk = dict(getattr(orchestrator, "_crosswalk", {}) or {})
    loaded_erp = len({ct_id for ct_id in crosswalk.values() if ct_id})
    if len(crosswalk) != file_vs or loaded_erp != file_erp:
        _die(f"orchestrator loaded {len(crosswalk)} VanillaSoft / {loaded_erp} ERP != file {file_vs} / {file_erp}")
    remaining = sorted(contact_id for contact_id in census if contact_id not in done)
    print(f"census={len(census)} crosswalk={len(crosswalk)} already={len(done)} remaining={len(remaining)}")

    capture = _SignalCapture()
    logging.getLogger("odoo.addons.plasticos_crm_sync").addHandler(capture)

    processed = 0
    for contact_id in remaining:
        decision = census[contact_id]
        ct_id = crosswalk.get(contact_id, "")
        if decision == "YES" and contact_id in OMITTED_DUPLICATE_VS_IDS:
            record = {
                "vanillasoft_contact_id": contact_id,
                "erp_ct_id": "",
                "decision": decision,
                "class": "duplicate_skipped",
                "importer_outcome": "not_imported",
                "signals": [
                    {
                        "level": "WARNING",
                        "reason": "second VanillaSoft id for a person already approved on an active contact",
                    }
                ],
            }
            _append(record, digest)
            done[contact_id] = record
            processed += 1
            continue
        if decision == "YES" and contact_id not in crosswalk:
            record = {
                "vanillasoft_contact_id": contact_id,
                "erp_ct_id": "",
                "decision": decision,
                "class": "genuine_failed",
                "importer_outcome": "not_fetched",
                "signals": [
                    {
                        "level": "ERROR",
                        "reason": "YES id is missing from the loaded crosswalk; not fetched and not turned into a lead",
                    }
                ],
            }
            _append(record, digest)
            done[contact_id] = record
            processed += 1
            continue
        if decision != "YES" and contact_id in crosswalk:
            record = {
                "vanillasoft_contact_id": contact_id,
                "erp_ct_id": ct_id,
                "decision": decision,
                "class": "genuine_failed",
                "importer_outcome": "not_fetched",
                "signals": [
                    {
                        "level": "ERROR",
                        "reason": f"{decision} id is in the approved crosswalk; not fetched",
                    }
                ],
            }
            _append(record, digest)
            done[contact_id] = record
            processed += 1
            continue

        before = len(getattr(orchestrator, "error_rows", []) or [])
        capture.rows.clear()
        raw = "exception"
        exc_text = ""
        try:
            with env.cr.savepoint():
                orchestrator.upsert_contact_external_id(connection, contact_id)
            raw = orchestrator.last_lead_outcome or "none"
        except Exception as exc:  # noqa: BLE001 - one ID must not abort the cohort
            raw = type(exc).__name__
            env.cr.rollback()
            exc_text = str(exc)
            if "VanillaSoft auth failed" in exc_text or "requires api_key" in exc_text:
                reason = redact(exc_text)
                (ROOT / "credential_stop.json").write_text(
                    json.dumps(
                        {"level": "ERROR", "reason": f"credential rejected: {reason}", "contact": contact_id},
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                print(f"STOPPED credential rejected class={raw} reason={reason}")
                raise SystemExit(2) from None
        messages = [str(item.get("message") or "") for item in (getattr(orchestrator, "error_rows", []) or [])[before:]]
        signals = _signals_for_contact(raw, messages, exc_text, list(capture.rows))
        env.cr.commit()
        record = {
            "vanillasoft_contact_id": contact_id,
            "erp_ct_id": ct_id,
            "decision": decision,
            "class": classify(raw, messages),
            "importer_outcome": raw,
            "signals": signals,
        }
        _append(record, digest)
        done[contact_id] = record
        processed += 1
        if processed % 25 == 0:
            print(f"progress {sum(1 for key in done if key in census)}/{COHORT}")

    classes: dict[str, int] = {}
    placements: dict[str, int] = {}
    signal_counts: dict[tuple[str, str], int] = {}
    missing_signals = 0
    unexplained = 0
    for contact_id, row in done.items():
        if contact_id not in census:
            continue
        classes[row.get("class") or "missing"] = classes.get(row.get("class") or "missing", 0) + 1
        placements[row.get("placement") or "missing"] = placements.get(row.get("placement") or "missing", 0) + 1
        if "signals" not in row or "placement" not in row or row.get("crosswalk_sha256") != digest:
            missing_signals += 1
            continue
        reasons = [str(signal.get("reason") or "") for signal in row["signals"]]
        if row.get("class") != "imported" and (
            not reasons or all("produced no reason" in reason for reason in reasons)
        ):
            unexplained += 1
        for signal in row["signals"]:
            key = (str(signal.get("level") or ""), str(signal.get("reason") or ""))
            signal_counts[key] = signal_counts.get(key, 0) + 1
    open_exceptions = [
        {"level": level, "reason": reason, "count": count} for (level, reason), count in sorted(signal_counts.items())
    ]
    EXCEPTIONS.write_text(json.dumps(open_exceptions, indent=2) + "\n", encoding="utf-8")
    printable = {f"{item['level']}: {item['reason']}": item["count"] for item in open_exceptions}
    covered = sum(classes.values())
    print(f"finished processed_this_run={processed} classes={json.dumps(classes, sort_keys=True)}")
    print(f"placements {json.dumps(placements, sort_keys=True)}")
    print(f"signals {json.dumps(printable, sort_keys=True)}")
    print(f"open_exceptions_file={EXCEPTIONS}")
    print(f"checkpoint_rows_missing_signals={missing_signals}")
    print(f"dispositions_without_a_source_reason={unexplained}")
    if covered != COHORT:
        raise SystemExit(f"checkpoint {covered} != census {COHORT}")
    if unexplained or missing_signals:
        raise SystemExit(
            f"{unexplained + missing_signals} dispositions have no source reason; "
            "a class without that reason is not a result"
        )


env = globals().get("env")
if env is None:
    raise SystemExit("no Odoo environment (run inside odoo shell)")
main(env)
