#!/usr/bin/env python3
"""Validate one or more import-run summaries against the shared schema.

Repo-level validator for the PlasticOS import-run-summary contract
(contracts/schemas/draft/import-run-summary.schema.json). Used by the
canonical import commands (make import-legacy-erp / make import-vanillasoft)
and by CI/tests. Pure stdlib — no Odoo import, no third-party dependency.

Usage:
    python3 scripts/validate_import_summary.py <summary.json> [<more>.json ...]

Exit 0 when every summary validates; exit 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "contracts" / "schemas" / "draft" / "import-run-summary.schema.json"

ISO_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")

# Secret-bearing keys/values must never appear in a summary.
SECRET_MARKERS = ("api_key", "apikey", "authorization", "password", "token", "bearer")


def _iso_utc(value: str) -> bool:
    return bool(ISO_UTC_RE.match(value))


def _valid_datetime(value: str) -> bool:
    if not _iso_utc(value):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _walk_secrets(obj: object, path: str = "") -> list[str]:
    """Return paths of any secret-looking key or value in the summary."""
    hits: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_l = str(key).lower()
            if any(marker in key_l for marker in SECRET_MARKERS):
                hits.append(f"{path}.{key} (key)")
            hits.extend(_walk_secrets(value, f"{path}.{key}"))
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            hits.extend(_walk_secrets(item, f"{path}[{idx}]"))
    elif isinstance(obj, str):
        low = obj.lower()
        for marker in SECRET_MARKERS:
            if f"{marker}=" in low or f"{marker}:" in low:
                hits.append(f"{path} (value contains {marker!r} marker)")
    return hits


def validate_summary(summary: dict) -> list[str]:
    errors: list[str] = []
    for field in (
        "source",
        "start_time",
        "completion_time",
        "records_seen",
        "records_valid",
        "records_rejected",
        "records_created",
        "records_updated",
        "records_unchanged",
        "duplicates",
        "errors",
        "final_status",
    ):
        if field not in summary:
            errors.append(f"missing required field: {field}")
    for field in (
        "records_seen",
        "records_valid",
        "records_rejected",
        "records_created",
        "records_updated",
        "records_unchanged",
        "duplicates",
    ):
        if field in summary and not isinstance(summary[field], int):
            errors.append(f"{field} must be an integer")
    if "start_time" in summary and not _valid_datetime(summary["start_time"]):
        errors.append("start_time must be an ISO 8601 UTC datetime")
    if "completion_time" in summary and not _valid_datetime(summary["completion_time"]):
        errors.append("completion_time must be an ISO 8601 UTC datetime")
    if "final_status" in summary and summary["final_status"] not in ("success", "partial", "failed"):
        errors.append("final_status must be success | partial | failed")
    if "errors" in summary and not isinstance(summary["errors"], list):
        errors.append("errors must be a list")
    hits = _walk_secrets(summary)
    if hits:
        errors.append(f"secret markers found in summary: {', '.join(hits[:5])}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate import-run summaries against the shared schema")
    parser.add_argument("summaries", nargs="+", help="summary JSON file(s)")
    args = parser.parse_args(argv)

    if not SCHEMA_PATH.is_file():
        print(f"ERROR: schema not found: {SCHEMA_PATH}")
        return 1

    failed = False
    for raw in args.summaries:
        path = Path(raw)
        try:
            summary = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            print(f"FAIL: {path}: cannot read ({exc})")
            failed = True
            continue
        except json.JSONDecodeError as exc:
            print(f"FAIL: {path}: invalid JSON ({exc})")
            failed = True
            continue
        if not isinstance(summary, dict):
            print(f"FAIL: {path}: root must be an object")
            failed = True
            continue
        errors = validate_summary(summary)
        if errors:
            failed = True
            print(f"FAIL: {path}")
            for error in errors:
                print(f"  {error}")
        else:
            print(f"PASS: {path} (source={summary.get('source')}, status={summary.get('final_status')})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
