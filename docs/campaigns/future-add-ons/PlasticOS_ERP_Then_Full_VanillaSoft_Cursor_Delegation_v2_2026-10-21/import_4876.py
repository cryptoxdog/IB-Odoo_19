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
"""

import csv
import json
import logging
import re
from pathlib import Path

ROOT = Path("/mnt/extra-addons/Current Work - IGNORE/erp-then-vs-full-crm")
CHECKPOINT = ROOT / "crm_checkpoint.jsonl"
CROSSWALK = str(ROOT / "03_APPROVED_CONTACT_CROSSWALK.csv")
CENSUS = ROOT / "crm_id_census.csv"
COHORT = 4876
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


def _append(record: dict) -> None:
    with CHECKPOINT.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    for signal in record["signals"]:
        print(f"signal level={signal['level']} contact={record['vanillasoft_contact_id']} reason={signal['reason']}")


def main(env) -> None:
    """Import each census id once. Stop on a dead credential. Keep every reason."""
    from odoo.addons.plasticos_crm_sync.services.approved_identity import OMITTED_DUPLICATE_VS_IDS
    from odoo.addons.plasticos_crm_sync.services.orchestrator import SyncOrchestrator

    census = _load_census()
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
            _append(record)
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
            _append(record)
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
            _append(record)
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
                print(f"STOPPED credential rejected class={raw} reason={redact(exc_text)}")
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
        _append(record)
        done[contact_id] = record
        processed += 1
        if processed % 25 == 0:
            print(f"progress {sum(1 for key in done if key in census)}/{COHORT}")

    classes: dict[str, int] = {}
    signal_counts: dict[str, int] = {}
    missing_signals = 0
    unexplained = 0
    for contact_id, row in done.items():
        if contact_id not in census:
            continue
        classes[row.get("class") or "missing"] = classes.get(row.get("class") or "missing", 0) + 1
        if "signals" not in row:
            missing_signals += 1
            continue
        reasons = [str(signal.get("reason") or "") for signal in row["signals"]]
        if row.get("class") != "imported" and (
            not reasons or all("produced no reason" in reason for reason in reasons)
        ):
            unexplained += 1
        for signal in row["signals"]:
            key = f"{signal['level']}: {signal['reason']}"
            signal_counts[key] = signal_counts.get(key, 0) + 1
    covered = sum(classes.values())
    print(f"finished processed_this_run={processed} classes={json.dumps(classes, sort_keys=True)}")
    print(f"signals {json.dumps(signal_counts, sort_keys=True)}")
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
