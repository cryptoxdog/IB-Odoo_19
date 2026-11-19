"""Mapping-status completeness tests against the tracked ERP extract.

Pure-python tier (no Odoo import). Every column of every tracked bulk CSV must
have an explicit disposition in plasticos_partner_import/erp/mapping_status.py:
no silently discarded source data, no UNKNOWN columns for consumed tables.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plasticos_partner_import"))

from erp import mapping_status  # noqa: E402
from erp.reader import DEFAULT_PAYLOAD_ROOT, SOURCE_TABLES  # noqa: E402

PAYLOAD_ROOT = ROOT / DEFAULT_PAYLOAD_ROOT


@pytest.fixture(scope="module")
def status():
    return mapping_status.build_mapping_status(ROOT)


@pytest.fixture(scope="module")
def rows_by_key(status):
    return {(row["source_table"], row["source_field"]): row for row in status.rows}


def bulk_columns():
    """Yield (table, column) for every tracked bulk CSV header."""
    for table, filename in sorted(SOURCE_TABLES.items()):
        with open(PAYLOAD_ROOT / "bulk" / filename, encoding="utf-8-sig", newline="") as handle:
            for column in next(csv.reader(handle)):
                column = column.strip()
                if column:
                    yield table, column


def test_every_consumed_table_column_has_a_disposition(rows_by_key):
    missing = [(t, c) for t, c in bulk_columns() if (t, c) not in rows_by_key]
    assert not missing, f"columns without a disposition: {missing}"


def test_no_unknown_columns_for_consumed_tables(status):
    unknown = [
        (row["source_table"], row["source_field"])
        for row in status.rows
        if row["status"] == "UNKNOWN" and row["source_table"] in SOURCE_TABLES
    ]
    assert not unknown, f"UNKNOWN columns in consumed tables: {unknown}"


def test_unconsumed_tables_are_all_intentional(status):
    unconsumed = {
        row["source_table"]
        for row in status.rows
        if row["status"] == "UNMAPPED_INTENTIONALLY"
        and row["source_table"] not in SOURCE_TABLES
        and row["source_table"] not in mapping_status.DIRECT_SQL_DISPOSITION_TABLES
    }
    assert unconsumed == set(mapping_status.UNCONSUMED_TABLES)


def test_every_intentional_drop_has_a_reason(status):
    missing = [
        (row["source_table"], row["source_field"])
        for row in status.rows
        if row["status"] == "UNMAPPED_INTENTIONALLY" and not row["reason"].strip()
    ]
    assert not missing, f"intentional drops without a reason: {missing}"


def test_status_vocabulary_closed(status):
    for row in status.rows:
        assert row["status"] in mapping_status.ALLOWED_STATUSES, row


def test_source_native_identities_are_marked(status):
    expected = {
        ("CounterParty", "CpID"),
        ("Address", "AddressID"),
        ("Contact", "CT_ID"),
        ("ContactRoleAssignment", "CRA_ID"),
        ("WKSDetail", "DetailID"),
    }
    found = {
        (row["source_table"], row["source_field"])
        for row in status.rows
        if row["identity_role"] != "none" and "identity" in row["identity_role"]
    }
    assert expected <= found, f"identity columns not marked: {expected - found}"


def test_sql_types_joined_for_consumed_tables(status):
    typed = {
        row["source_table"] for row in status.rows if row["source_sql_type"] and row["source_table"] in SOURCE_TABLES
    }
    assert typed == set(SOURCE_TABLES), f"tables missing SQL types: {set(SOURCE_TABLES) - typed}"


def test_needs_correction_rows_are_explicit(status):
    needs = [row for row in status.rows if row["status"] == "NEEDS_CORRECTION"]
    for row in needs:
        assert row["reason"].strip(), row
        assert row["target_field"], row


PAYABLES_BATCH_PROJECTED = {
    "APBatchNo",
    "PrePay",
    "NumofItems",
    "PostingDt",
    "FXAmount",
    "CurrencyCd",
    "PostedInAccting",
    "Comment",
    "APTerms",
    "CpID",
    "InvoiceNo",
    "InvoiceDt",
    "DueDate",
    "ReversedFxAmt",
    "ReverseBatchNo",
}


def test_payables_batch_is_consumed_not_unconsumed_evidence():
    assert "PayablesBatch" not in mapping_status.UNCONSUMED_TABLES
    assert "PayablesBatch" in mapping_status.DIRECT_SQL_DISPOSITION_TABLES


def test_every_payables_batch_column_has_an_explicit_disposition(status):
    with open(PAYLOAD_ROOT / "bulk" / "PayablesBatch.csv", encoding="utf-8-sig", newline="") as handle:
        columns = {column.strip() for column in next(csv.reader(handle)) if column.strip()}
    rows = {row["source_field"]: row for row in status.rows if row["source_table"] == "PayablesBatch"}
    assert set(rows) == columns
    assert not [row for row in rows.values() if row["status"] == "UNKNOWN"]
    assert PAYABLES_BATCH_PROJECTED <= columns
    for column, row in rows.items():
        projected = column in PAYABLES_BATCH_PROJECTED
        assert (row["reason"] == mapping_status.NOT_PROJECTED) is not projected, row
        assert row["source_sql_type"], f"PayablesBatch.{column} has no SQL type"


def test_payables_batch_header_columns_written_are_exactly_the_bill_header_facts(status):
    """Bills stay one per PayableID; only their date, vendor invoice number, terms and due date come from the header."""
    rows = [row for row in status.rows if row["source_table"] == "PayablesBatch"]
    verified = {row["source_field"] for row in rows if row["status"] == "VERIFIED"}
    assert verified == {"APBatchNo", "PrePay", "InvoiceDt", "InvoiceNo", "DueDate", "APTerms", "ReverseBatchNo"}
    written = {"InvoiceDt": "invoice_date", "InvoiceNo": "ref", "DueDate": "invoice_date_due"}
    for row in rows:
        if row["status"] != "VERIFIED":
            continue
        if row["source_field"] in written:
            assert row["target_model"] == "account.move", row
            assert row["target_field"].startswith(written[row["source_field"]]), row
        elif row["source_field"] == "APTerms":
            assert row["target_field"] == "invoice_payment_term_id" and "never created" in row["transformation"]
        elif row["source_field"] == "ReverseBatchNo":
            assert row["target_model"] == "account.move", row
            assert row["target_field"].startswith("reversed_entry_id"), row
            assert "Amounts are never used" in row["transformation"]
        else:
            assert row["target_model"] == "—", row
        if row["status"] == "NEEDS_CORRECTION":
            assert row["reason"] == mapping_status.UNRESOLVED_TARGET, row
            assert row["target_field"].startswith("unresolved"), row
    posted = next(row for row in rows if row["source_field"] == "PostedInAccting")
    assert "not vendor cash paid" in posted["reason"]


def test_payables_batch_link_on_payables_is_the_prepay_join(rows_by_key):
    row = rows_by_key[("Payables", "APBatchNo")]
    assert row["status"] == "VERIFIED"
    assert "PrePay=1 exclusion" in row["target_field"]
