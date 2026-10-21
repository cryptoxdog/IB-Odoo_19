"""Crosswalk-only VanillaSoft import for one disposable clone.

The ID list is the pinned crosswalk loaded by the orchestrator. Pending and
rejected IDs are not in that file and are not fetched. The checkpoint is
written only after that ID's transaction commits. Resume skips IDs already
present. This script prints counts and exception class names only.
"""

import json
from pathlib import Path

ROOT = Path("/mnt/extra-addons/Current Work - IGNORE/erp-contacts-vs-crosswalk")
CHECKPOINT = ROOT / "crm_checkpoint.jsonl"
CROSSWALK = str(ROOT / "03_APPROVED_CONTACT_CROSSWALK.csv")


def classify(raw: str, messages: list[str]) -> str:
    """Map one importer outcome onto imported, held, or genuine_failed."""
    if raw in {"created", "updated", "unchanged"}:
        return "imported"
    text = " ".join(messages)
    if raw == "failed" and "ERP marker" in text:
        return "held"
    return "genuine_failed"


def main(env) -> None:
    """Bind each crosswalk ContactID to its ERP person. Stop on a dead credential."""
    from odoo.addons.plasticos_crm_sync.services.orchestrator import SyncOrchestrator

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
    mapping = dict(getattr(orchestrator, "_crosswalk", {}) or {})
    remaining = sorted(contact_id for contact_id in mapping if contact_id not in done)
    print(f"crosswalk={len(mapping)} already={len(done)} remaining={len(remaining)}")

    processed = 0
    for contact_id in remaining:
        before = len(getattr(orchestrator, "error_rows", []) or [])
        raw = "exception"
        try:
            with env.cr.savepoint():
                orchestrator.upsert_contact_external_id(connection, contact_id)
            raw = orchestrator.last_lead_outcome or "none"
        except Exception as exc:  # noqa: BLE001 - one ID must not abort the cohort
            raw = type(exc).__name__
            env.cr.rollback()
            text = str(exc)
            if "VanillaSoft auth failed" in text or "requires api_key" in text:
                print(f"STOPPED credential rejected class={raw}")
                raise SystemExit(2) from None
        messages = [str(item.get("message") or "") for item in (getattr(orchestrator, "error_rows", []) or [])[before:]]
        env.cr.commit()
        record = {
            "vanillasoft_contact_id": contact_id,
            "erp_ct_id": mapping[contact_id],
            "decision": "YES",
            "class": classify(raw, messages),
            "importer_outcome": raw,
        }
        with CHECKPOINT.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        done[contact_id] = record
        processed += 1
        if processed % 25 == 0:
            print(f"progress {sum(1 for key in done if key in mapping)}/{len(mapping)}")

    classes = {}
    for contact_id, row in done.items():
        if contact_id not in mapping:
            continue
        classes[row["class"]] = classes.get(row["class"], 0) + 1
    covered = sum(classes.values())
    print(f"finished processed_this_run={processed} classes={json.dumps(classes, sort_keys=True)}")
    if covered != len(mapping):
        raise SystemExit(f"checkpoint {covered} != crosswalk {len(mapping)}")


env = globals().get("env")
if env is None:
    raise SystemExit("no Odoo environment (run inside odoo shell)")
main(env)
