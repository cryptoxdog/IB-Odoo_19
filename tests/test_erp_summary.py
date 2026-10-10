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


# ── GMP-004: a mandatory run-level check that fails cannot produce a successful import ──
def _balanced_report() -> ImportReport:
    """Every source row has one outcome, nothing rejected: the counter reconciliation closes."""
    report = ImportReport()
    report.source_counts = {"counterparties": 2, "transactions": 1, "transaction_lines": 1}
    report.bump("counterparties", "created", 2)
    report.bump("transactions", "created", 1)
    report.bump("transaction_lines", "created", 1)
    return report


def test_a_run_level_failure_fails_the_run_without_touching_the_counters():
    report = _balanced_report()
    report.fail(summary.PAYABLES_RECONCILIATION_REF, "payables identity reconciliation does not close: 1 missing")
    result = report.as_dict()
    assert result["failures"] == [
        {"check": "payables_reconciliation", "detail": "payables identity reconciliation does not close: 1 missing"}
    ]
    projected = summary.import_run_summary(result)
    assert validate_summary(projected) == []
    assert projected["final_status"] == "failed"
    # The failure is not a row: counters are exactly what the run measured, and they still close.
    assert projected["records_seen"] == 4
    assert projected["records_created"] == 4
    assert projected["records_rejected"] == 0
    assert projected["records_valid"] == 4
    assert projected["errors"] == [
        {
            "record_ref": "payables_reconciliation",
            "message": "payables identity reconciliation does not close: 1 missing",
        }
    ]
    assert all(row["record_ref"] != summary.RECONCILIATION_REF for row in projected["errors"])
    # The same report without the failure is the success path, unchanged.
    clean = summary.import_run_summary(_balanced_report().as_dict())
    assert clean["final_status"] == "success" and clean["errors"] == []
    assert {key: clean[key] for key in clean if key.startswith("records_")} == {
        key: projected[key] for key in projected if key.startswith("records_")
    }


def test_an_omitted_or_blank_identity_payable_cannot_produce_a_successful_import():
    """The realizer's chain: identity gap -> reconciliation_gap -> report.fail -> summary failed -> exit 1."""
    from erp.native_orders import payables_reconciliation, reconciliation_gap

    rows = [("54839", "gl_50100_billed", 100.0)]
    for source_ids, expected in (
        (["591398", "591476"], "1 missing PayableID: 591476"),  # omitted from both sides
        (["591398", ""], "1 source rows without a PayableID"),  # blank identity
    ):
        reconciliation = payables_reconciliation(rows, [], source_ids, ["591398"])
        assert reconciliation["closes"] is False
        report = _balanced_report()
        gap = reconciliation_gap(reconciliation)
        assert gap.endswith(expected)
        report.fail(summary.PAYABLES_RECONCILIATION_REF, f"payables identity reconciliation does not close: {gap}")
        result = report.as_dict()
        result["summary"] = summary.import_run_summary(result)
        assert result["summary"]["final_status"] == "failed"
        assert result["summary"]["records_rejected"] == 0
        assert summary.run_exit_status(result) == 1
        assert summary.run_exit_status(result, dry_run=True) == 1
        assert summary.run_exit_status(result, layer="counterparties") == 1
    closing = payables_reconciliation(rows, [], ["591398"], ["591398"])
    assert closing["closes"] is True
    result = _balanced_report().as_dict()
    result["summary"] = summary.import_run_summary(result)
    assert summary.run_exit_status(result) == 0


def test_run_exit_status_follows_the_summary_only_for_an_applied_full_run():
    failed = {"failures": [], "summary": {"final_status": "failed"}}
    assert summary.run_exit_status(failed) == 1
    assert summary.run_exit_status(failed, dry_run=True) == 0, "a dry run emits no summary to read"
    assert summary.run_exit_status(failed, layer="contacts") == 0, "a layer run is gated by its validator"
    assert summary.run_exit_status({"failures": [], "summary": {"final_status": "partial"}}) == 0
    assert summary.run_exit_status({"failures": [], "summary": {"final_status": "success"}}) == 0
    assert summary.run_exit_status({}) == 0


def test_run_level_failures_keep_their_slots_when_diagnostics_overflow():
    report = ImportReport()
    report.source_counts = {"Address": 1000}
    for index in range(1000):
        report.unresolved_ref("Address", "unresolved_counterparty", str(index), "missing parent")
    report.fail(summary.PAYABLES_RECONCILIATION_REF, "x" * 5000)
    projected = summary.import_run_summary(report.as_dict())
    assert projected["final_status"] == "failed"
    assert projected["records_rejected"] == 1000, "the failure added no rejected row"
    assert len(projected["errors"]) == 1000
    assert projected["errors"][-1]["record_ref"] == "payables_reconciliation"
    assert len(projected["errors"][-1]["message"]) == summary.ERROR_MESSAGE_LIMIT
    assert projected["errors"][0]["record_ref"] == "0"
    assert validate_summary(projected) == []


def test_error_message_limit_matches_the_shared_contract():
    schema = json.loads((ROOT / "contracts/schemas/draft/import-run-summary.schema.json").read_text(encoding="utf-8"))
    assert summary.ERROR_MESSAGE_LIMIT == schema["properties"]["errors"]["items"]["properties"]["message"]["maxLength"]
