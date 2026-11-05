"""Mothball local intelligence — dry-run retirement coordinator (M5 / TASK-050).

Default mode is dry-run inventory only. Never drops business audit records,
never uninstalls modules, and never runs destructive SQL without an explicit
--execute flag plus a verified backup receipt digest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

# Business / audit records that MUST be retained across mothball.
RETAINED_MODELS: dict[str, str] = {
    "plasticos.match.run": "Gate match-run audit trail",
    "plasticos.match.result": "Gate match results written back to Odoo",
    "plasticos.match.result.link": "Match result linkage",
    "plasticos.match.exclusion": "Operator exclusion policy (matching home)",
    "plasticos.enrichment.run": "Gate enrichment-run audit trail",
    "plasticos.enrichment.provenance": "Enrichment provenance / writeback audit",
    "plasticos.enrichment.extraction": "Extraction audit (Gate path)",
    "plasticos.enrichment.source": "Configured enrichment sources (config)",
}

# Legacy local-intelligence surfaces catalogued for later physical retirement.
# M5 does NOT drop these tables or delete addon directories.
DISCARDABLE_CATALOG: dict[str, str] = {
    "plasticos.buyer.matcher": "Local BME matcher (authority retired; code retained until physical uninstall)",
    "plasticos.match.result.writer": "Local result writer (BME)",
    "plasticos.graph.service": "Local Neo4j graph helper (CEG owns graph)",
    "plasticos.graph.sync.log": "Local graph sync log",
    "plasticos.enrichment.service": "Local crawl/extract/inference service (fail-closed)",
}

FORBIDDEN_ACTIONS = (
    "drop_business_audit_records",
    "automatic_production_uninstall",
    "delete_legacy_source_directories",
    "destructive_sql_without_backup",
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def inventory() -> dict[str, Any]:
    """Build a static inventory of retained vs discardable surfaces."""
    cron = (REPO_ROOT / "plasticos_enrichment/data/cron.xml").read_text(encoding="utf-8")
    matching_manifest = (REPO_ROOT / "plasticos_matching/__manifest__.py").read_text(encoding="utf-8")
    enrichment_manifest = (REPO_ROOT / "plasticos_enrichment/__manifest__.py").read_text(encoding="utf-8")
    return {
        "recorded_at": _utc_now(),
        "mode": "inventory",
        "retained_models": RETAINED_MODELS,
        "discardable_catalog": DISCARDABLE_CATALOG,
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "preflight": {
            "enrichment_crons_disabled": cron.count("False") >= 2 and 'name="active">False</field>' in cron,
            "matching_gate_only": "plasticos_gate" in matching_manifest,
            "enrichment_no_inference_dep": "plasticos_inference_engine" not in enrichment_manifest,
            "enrichment_gate_dep": "plasticos_gate" in enrichment_manifest,
        },
        "uninstall": {
            "automatic": False,
            "requires_verified_backup": True,
            "requires_operator_command": True,
        },
    }


def digest_payload(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(body).hexdigest()


def uninstall_preflight(
    *,
    backup_receipt_digest: str | None,
    allow_uninstall: bool,
) -> dict[str, Any]:
    """Refuse uninstall unless backup receipt present and operator explicitly allows."""
    inv = inventory()
    ok_preflight = all(inv["preflight"].values())
    backup_ok = bool(backup_receipt_digest and backup_receipt_digest.startswith("sha256:"))
    result = {
        "recorded_at": _utc_now(),
        "mode": "uninstall_preflight",
        "preflight_pass": ok_preflight,
        "backup_receipt_present": backup_ok,
        "allow_uninstall": allow_uninstall,
        "would_uninstall": False,
        "blocked_reasons": [],
        "inventory_digest": digest_payload(inv),
    }
    if not ok_preflight:
        result["blocked_reasons"].append("preflight_checks_failed")
    if not backup_ok:
        result["blocked_reasons"].append("missing_verified_backup_receipt")
    if not allow_uninstall:
        result["blocked_reasons"].append("operator_allow_uninstall_not_set")
    # Hard lock: this coordinator never performs uninstall.
    if allow_uninstall and backup_ok and ok_preflight:
        result["blocked_reasons"].append("coordinator_refuses_automatic_uninstall_use_manual_runbook")
    result["status"] = "BLOCKED" if result["blocked_reasons"] else "READY_FOR_MANUAL"
    return result


def dry_run_migrate() -> dict[str, Any]:
    """Describe migrate steps without mutating any database."""
    return {
        "recorded_at": _utc_now(),
        "mode": "dry_run_migrate",
        "steps": [
            "snapshot retained model row counts (pre-migrate)",
            "verify enrichment crons inactive",
            "verify Gate-only matching/enrichment authority flags",
            "preserve all retained audit tables (no DELETE/DROP)",
            "catalog discardable local-intelligence surfaces for later retirement",
            "write post-migrate identity markers via ir.config_parameter when env available",
        ],
        "destructive_sql": False,
        "retained_models": sorted(RETAINED_MODELS),
        "inventory": inventory(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("inventory", "dry-run", "uninstall-preflight"),
        help="Coordinator command (default dry-run via dry-run)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Reserved. Destructive execute is intentionally unsupported in M5.",
    )
    parser.add_argument(
        "--backup-receipt-digest",
        default=None,
        help="sha256:… digest of verified backup/restore rehearsal receipt",
    )
    parser.add_argument(
        "--allow-uninstall",
        action="store_true",
        help="Operator intent flag; coordinator still refuses automatic uninstall",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON output path",
    )
    args = parser.parse_args(argv)

    if args.execute:
        print(
            "REFUSED: --execute is not supported; mothball M5 is dry-run only",
            file=sys.stderr,
        )
        return 2

    if args.command == "inventory":
        payload = inventory()
    elif args.command == "dry-run":
        payload = dry_run_migrate()
    else:
        payload = uninstall_preflight(
            backup_receipt_digest=args.backup_receipt_digest,
            allow_uninstall=args.allow_uninstall,
        )

    payload["payload_digest"] = digest_payload({k: v for k, v in payload.items() if k != "payload_digest"})
    text = json.dumps(payload, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
