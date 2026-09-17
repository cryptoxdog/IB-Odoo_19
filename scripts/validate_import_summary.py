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


# ---------------------------------------------------------------------------
# Schema-driven validation (stdlib only).
#
# The contract file is the authority: every constraint it states is enforced
# here by walking the schema, not by a hand-maintained copy of its rules. The
# walker implements the JSON Schema keywords the contract uses and fails closed
# on any other structural keyword, so a schema edit that this validator does not
# understand is reported instead of silently ignored.
# ---------------------------------------------------------------------------

# Keywords carried as documentation only; they never change validation.
_ANNOTATION_KEYWORDS = frozenset({"$schema", "$id", "title", "description", "x-publication-status"})
_STRUCTURAL_KEYWORDS = frozenset(
    {
        "type",
        "enum",
        "required",
        "properties",
        "additionalProperties",
        "items",
        "maxItems",
        "minimum",
        "minLength",
        "maxLength",
        "format",
    }
)
_SUPPORTED_FORMATS = frozenset({"date-time"})

_schema_cache: dict | None = None


def load_schema() -> dict:
    """The shared contract, read once from SCHEMA_PATH."""
    global _schema_cache
    if _schema_cache is None:
        _schema_cache = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return _schema_cache


def _type_matches(expected: str, value: object) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        # JSON Schema: booleans are not integers.
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "null":
        return value is None
    return False


def _check(schema: dict, value: object, path: str, errors: list[str]) -> None:
    """Validate ``value`` against ``schema`` at ``path``, appending to ``errors``."""
    unsupported = sorted(k for k in schema if k not in _ANNOTATION_KEYWORDS and k not in _STRUCTURAL_KEYWORDS)
    if unsupported:
        errors.append(
            f"{path}: schema uses unsupported keyword(s) {', '.join(unsupported)} (validator must be extended)"
        )
        return

    expected = schema.get("type")
    if expected is not None:
        expected_types = expected if isinstance(expected, list) else [expected]
        if not any(_type_matches(t, value) for t in expected_types):
            errors.append(f"{path}: expected {' | '.join(expected_types)}, got {type(value).__name__}")
            return

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: must be one of {' | '.join(map(str, schema['enum']))}")

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: shorter than minLength {schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: longer than maxLength {schema['maxLength']}")
        fmt = schema.get("format")
        if fmt is not None:
            if fmt not in _SUPPORTED_FORMATS:
                errors.append(f"{path}: schema uses unsupported format {fmt!r} (validator must be extended)")
            elif fmt == "date-time" and not _valid_datetime(value):
                errors.append(f"{path}: must be an ISO 8601 UTC datetime")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: below minimum {schema['minimum']}")

    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                errors.append(f"{path}: missing required field: {name}")
        if schema.get("additionalProperties", True) is False:
            for name in sorted(set(value) - set(properties)):
                errors.append(f"{path}: unexpected field: {name}")
        for name, subschema in properties.items():
            if name in value:
                _check(subschema, value[name], f"{path}.{name}", errors)

    if isinstance(value, list):
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: more than maxItems {schema['maxItems']} entries")
        items = schema.get("items")
        if items is not None:
            for idx, item in enumerate(value):
                _check(items, item, f"{path}[{idx}]", errors)


def validate_summary(summary: dict) -> list[str]:
    """Every contract violation plus any secret marker, as human-readable strings."""
    errors: list[str] = []
    _check(load_schema(), summary, "summary", errors)
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
