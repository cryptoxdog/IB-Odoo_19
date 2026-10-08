"""Shared-summary projection tests for the ERP import report.

Pure-python tier (no Odoo import) — see tests/conftest.py collection rules.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plasticos_partner_import"))
sys.path.insert(0, str(ROOT))

from erp import summary  # noqa: E402
from erp.report import ImportReport  # noqa: E402

from scripts.validate_import_summary import validate_summary  # noqa: E402


def sample_result() -> dict:
    report = ImportReport()
    report.payload_kind = "grid"
    # 2 counterparties + 1 address + 1 transaction + 1 transaction line: every row has one outcome.
    report.source_counts = {"CounterParty": 2, "Address": 1, "transactions": 1, "transaction_lines": 1}
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
    assert projected["records_seen"] == 5
    assert projected["records_created"] == 3
    assert projected["records_updated"] == 1
    assert projected["records_unchanged"] == 1
    assert projected["records_rejected"] == 0
    assert projected["duplicates"] == 0


def test_rejection_and_unresolved_count_as_rejected():
    report = ImportReport()
    # 3 partner rows (created / rejected / unresolved) + 1 failed transaction unit.
    report.source_counts = {"CounterParty": 3, "transactions": 1}
    report.bump("counterparties", "created", 1)
    report.bump("counterparties", "rejected", 1)
    report.unresolved_ref("Contact", "parent_not_imported", "cp1", "counterparty partner was not created")
    report.error("B-100", "boom")
    projected = summary.import_run_summary(report.as_dict())
    assert validate_summary(projected) == []
    assert projected["final_status"] == "failed"
    assert projected["records_rejected"] == 3
    assert projected["records_valid"] == 1
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


def test_unresolved_rows_alone_make_the_run_partial_not_failed():
    """An unresolved source reference is a rejected row the source explains, not a failed unit."""
    report = ImportReport()
    report.source_counts = {"counterparties": 2, "addresses": 1}
    report.bump("counterparties", "created", 2)
    report.unresolved_ref("Address", "unresolved_counterparty", "402427", "CpID=(INV) not in exported counterparties")
    projected = summary.import_run_summary(report.as_dict())
    assert validate_summary(projected) == []
    assert projected["final_status"] == "partial"
    assert projected["records_rejected"] == 1
    assert len(projected["errors"]) == 1
    assert (
        projected["records_created"]
        + projected["records_updated"]
        + projected["records_unchanged"]
        + projected["records_rejected"]
        == projected["records_seen"]
        == 3
    )


def test_a_failed_unit_makes_the_run_failed():
    report = ImportReport()
    report.source_counts = {"transactions": 1, "transaction_lines": 1}
    report.error("B-100", "boom")
    projected = summary.import_run_summary(report.as_dict())
    assert projected["final_status"] == "failed"


def test_violation_tally_is_not_a_second_population_of_seen_rows():
    """Index violations are rows already counted in their table; seen must not double count them."""
    report = ImportReport()
    report.source_counts = {"counterparties": 1, "addresses": 2, "sales_reps": 3, "violations": 2}
    report.bump("counterparties", "created", 1)
    report.bump("locations", "created", 1)
    report.unresolved_ref("Address", "unresolved_counterparty", "a2", "placeholder parent")
    report.bump("salespersons", "updated", 1)
    report.skip("salespersons", 1)
    report.unresolved_ref("SalesReps", "unresolved_counterparty", "9/MM", "no company")
    projected = summary.import_run_summary(report.as_dict())
    assert projected["records_seen"] == 6
    assert (
        projected["records_created"]
        + projected["records_updated"]
        + projected["records_unchanged"]
        + projected["records_rejected"]
        == projected["records_seen"]
    )


def test_unaccounted_rows_fail_the_run_and_are_not_relabelled_as_rejected():
    """A deal population nothing realized must not close the books as rejected rows."""
    report = ImportReport()
    report.source_counts = {"counterparties": 2, "transactions": 3, "transaction_lines": 5}
    report.bump("counterparties", "created", 2)
    projected = summary.import_run_summary(report.as_dict())
    assert validate_summary(projected) == []
    assert projected["final_status"] == "failed"
    # Truthful counters: the gap stays a gap.
    assert projected["records_seen"] == 10
    assert projected["records_created"] == 2
    assert projected["records_rejected"] == 0
    reconciliation = [row for row in projected["errors"] if row["record_ref"] == summary.RECONCILIATION_REF]
    assert len(reconciliation) == 1
    assert "8 source rows unaccounted" in reconciliation[0]["message"]


def test_over_accounted_rows_also_fail_the_run():
    """More outcomes than source rows is a double count, never a success."""
    report = ImportReport()
    report.source_counts = {"counterparties": 1}
    report.bump("counterparties", "created", 1)
    report.bump("counterparties", "updated", 1)
    projected = summary.import_run_summary(report.as_dict())
    assert projected["final_status"] == "failed"
    assert any(row["record_ref"] == summary.RECONCILIATION_REF for row in projected["errors"])


def test_balanced_runs_carry_no_reconciliation_error():
    for result in (sample_result(),):
        projected = summary.import_run_summary(result)
        assert all(row["record_ref"] != summary.RECONCILIATION_REF for row in projected["errors"])
        assert projected["final_status"] == "success"


def test_error_row_limit_matches_the_shared_contract():
    schema = json.loads((ROOT / "contracts/schemas/draft/import-run-summary.schema.json").read_text(encoding="utf-8"))
    assert summary.ERROR_ROW_LIMIT == schema["properties"]["errors"]["maxItems"] == 1000


def test_rejected_accounting_stays_complete_when_diagnostics_exceed_the_contract_cap():
    report = ImportReport()
    report.source_counts = {"Address": 1289}
    for index in range(1289):
        report.unresolved_ref("Address", "unresolved_counterparty", str(index), "missing parent")
    projected = summary.import_run_summary(report.as_dict())
    assert projected["records_seen"] == 1289
    assert projected["records_rejected"] == 1289
    assert projected["records_valid"] == 0
    assert projected["final_status"] == "partial"
    assert len(projected["errors"]) == 1000
    assert projected["errors"][0]["record_ref"] == "0"
    assert projected["errors"][999]["record_ref"] == "999"
    assert validate_summary(projected) == []


def test_reconciliation_error_keeps_a_slot_when_diagnostics_overflow():
    report = ImportReport()
    report.source_counts = {"Address": 1001}
    for index in range(1000):
        report.unresolved_ref("Address", "unresolved_counterparty", str(index), "missing parent")
    projected = summary.import_run_summary(report.as_dict())
    reconciliation = [row for row in projected["errors"] if row["record_ref"] == summary.RECONCILIATION_REF]
    assert projected["records_seen"] == 1001
    assert projected["records_rejected"] == 1000
    assert projected["final_status"] == "failed"
    assert len(projected["errors"]) == 1000
    assert len(reconciliation) == 1
    assert validate_summary(projected) == []
