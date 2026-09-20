"""Shared-summary projection tests for the LegacyErp import report.

Pure-python tier (no Odoo import) — see tests/conftest.py collection rules.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plasticos_transaction"))
sys.path.insert(0, str(ROOT))

from legacy_erp import summary  # noqa: E402
from legacy_erp.report import ImportReport  # noqa: E402

from scripts.validate_import_summary import validate_summary  # noqa: E402


def sample_result() -> dict:
    report = ImportReport()
    report.payload_kind = "grid"
    report.source_counts = {"CounterParty": 2, "Address": 1, "WKSDetail": 1}
    report.bump("counterparties", "created", 1)
    report.bump("counterparties", "updated", 1)
    report.bump("locations", "created", 1)
    report.bump("transactions", "created", 1)
    report.bump("transaction_lines", "skipped", 1)
    return report.as_dict()


def test_success_projection_validates():
    projected = summary.import_run_summary(sample_result())
    assert validate_summary(projected) == []
    assert projected["final_status"] == "success"
    assert projected["records_seen"] == 4
    assert projected["records_created"] == 3
    assert projected["records_updated"] == 1
    assert projected["records_unchanged"] == 1
    assert projected["records_rejected"] == 0
    assert projected["duplicates"] == 0


def test_rejection_and_unresolved_count_as_rejected():
    report = ImportReport()
    report.source_counts = {"CounterParty": 3}
    report.bump("counterparties", "created", 1)
    report.bump("counterparties", "rejected", 1)
    report.unresolved_ref("Contact", "parent_not_imported", "cp1", "counterparty partner was not created")
    report.error("B-100", "boom")
    projected = summary.import_run_summary(report.as_dict())
    assert validate_summary(projected) == []
    assert projected["final_status"] == "failed"
    assert projected["records_rejected"] == 3
    assert projected["records_valid"] == 0
    assert len(projected["errors"]) == 2
    assert projected["errors"][0]["record_ref"] == "B-100"


def test_partial_when_only_rejections():
    report = ImportReport()
    report.source_counts = {"CounterParty": 2}
    report.bump("counterparties", "created", 1)
    report.bump("counterparties", "rejected", 1)
    projected = summary.import_run_summary(report.as_dict())
    assert validate_summary(projected) == []
    assert projected["final_status"] == "partial"


def test_reconciliation_closes():
    report = ImportReport()
    report.source_counts = {"CounterParty": 10, "Address": 5}
    report.bump("counterparties", "created", 8)
    report.bump("counterparties", "rejected", 2)
    report.bump("locations", "created", 3)
    report.bump("locations", "skipped", 2)
    projected = summary.import_run_summary(report.as_dict())
    assert (
        projected["records_created"]
        + projected["records_updated"]
        + projected["records_unchanged"]
        + projected["records_rejected"]
        == projected["records_seen"]
    )


def test_timestamps_pass_through():
    projected = summary.import_run_summary(
        sample_result(),
        start_time="2026-09-17T10:00:00Z",
        completion_time="2026-09-17T10:05:00Z",
    )
    assert projected["start_time"] == "2026-09-17T10:00:00Z"
    assert projected["completion_time"] == "2026-09-17T10:05:00Z"


def test_no_secret_keys():
    projected = summary.import_run_summary(sample_result())
    assert validate_summary(projected) == []
