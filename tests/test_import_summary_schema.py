"""Tests for the shared import-run summary contract and its validator.

Pure-python tier (no Odoo import) — see tests/conftest.py collection rules.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.validate_import_summary import (  # noqa: E402
    SCHEMA_PATH,
    SECRET_MARKERS,
    validate_summary,
)

VALID_SUMMARY = {
    "source": "legacy_erp",
    "start_time": "2026-09-17T10:00:00Z",
    "completion_time": "2026-09-17T10:05:00Z",
    "records_seen": 10,
    "records_valid": 9,
    "records_rejected": 1,
    "records_created": 5,
    "records_updated": 3,
    "records_unchanged": 1,
    "duplicates": 0,
    "errors": [],
    "final_status": "success",
}


def test_schema_exists_and_is_json():
    assert SCHEMA_PATH.is_file()
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["type"] == "object"
    assert "records_seen" in schema["properties"]


def test_schema_requires_all_report_fields():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    required = set(schema["required"])
    assert required == {
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
    }


def test_valid_summary_passes():
    assert validate_summary(VALID_SUMMARY) == []


@pytest.mark.parametrize("field", sorted(set(VALID_SUMMARY) - {"source"}))
def test_missing_field_fails(field):
    broken = dict(VALID_SUMMARY)
    broken.pop(field)
    assert validate_summary(broken)


def test_bad_final_status_fails():
    broken = dict(VALID_SUMMARY, final_status="total")
    assert validate_summary(broken)


def test_non_integer_counter_fails():
    broken = dict(VALID_SUMMARY, records_created="five")
    assert validate_summary(broken)


def test_bad_datetime_fails():
    broken = dict(VALID_SUMMARY, start_time="yesterday morning")
    assert validate_summary(broken)


def test_secret_key_fails():
    broken = dict(VALID_SUMMARY)
    broken["vanillasoft_api_key"] = "x"
    assert validate_summary(broken)


def test_secret_value_marker_fails():
    broken = dict(VALID_SUMMARY, errors=[{"record_ref": "r1", "message": "token=abc123"}])
    assert validate_summary(broken)


def test_partial_status_allowed():
    ok = dict(VALID_SUMMARY, final_status="partial", errors=[{"record_ref": "r2", "message": "malformed"}])
    assert validate_summary(ok) == []


def test_cli_roundtrip(tmp_path):
    good = tmp_path / "good.json"
    good.write_text(json.dumps(VALID_SUMMARY), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_import_summary.py"), str(good)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "PASS" in result.stdout

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(dict(VALID_SUMMARY, final_status="nope")), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_import_summary.py"), str(bad)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "FAIL" in result.stdout


def test_secret_markers_registered():
    assert "api_key" in SECRET_MARKERS and "token" in SECRET_MARKERS
