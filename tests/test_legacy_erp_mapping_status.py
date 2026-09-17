"""Mapping-status completeness tests against the tracked LegacyErp export.

Pure-python tier (no Odoo import). Every column of every tracked bulk CSV must
have an explicit disposition in plasticos_transaction/legacy_erp/mapping_status.py:
no silently discarded source data, no UNKNOWN columns for consumed tables.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plasticos_transaction"))

from legacy_erp import mapping_status  # noqa: E402
from legacy_erp.reader import DEFAULT_PAYLOAD_ROOT, SOURCE_TABLES  # noqa: E402

PAYLOAD_ROOT = ROOT / DEFAULT_PAYLOAD_ROOT


@pytest.fixture(scope="module")
def status():
    return mapping_status.build_mapping_status(ROOT)


@pytest.fixture(scope="module")
def rows_by_key(status):
    return {
        (row["source_table"], row["source_field"]): row
        for row in status.rows
    }


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
        if row["status"] == "UNMAPPED_INTENTIONALLY" and row["source_table"] not in SOURCE_TABLES
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
        row["source_table"]
        for row in status.rows
        if row["source_type"] and row["source_table"] in SOURCE_TABLES
    }
    assert typed == set(SOURCE_TABLES), f"tables missing SQL types: {set(SOURCE_TABLES) - typed}"


def test_needs_correction_rows_are_explicit(status):
    needs = [row for row in status.rows if row["status"] == "NEEDS_CORRECTION"]
    for row in needs:
        assert row["reason"].strip(), row
        assert row["target_field"], row
