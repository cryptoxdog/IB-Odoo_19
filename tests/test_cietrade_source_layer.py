"""CieTrade source-layer contract tests (no Odoo runtime required).

These run against the **real** tracked payload at
``data/legacy_erp_sm_export/``, so a source-shape regression or a vocabulary
drift in a future extract fails here rather than mid-import.

Covered by the contract's ``test_contract.required_before_full_test``:
parser reads the actual files; CpID / AddressID / CT_ID / CRA_ID / BuySellNo /
DetailID identity; facility, contact, and contact-role parent linkage; buyer and
supplier linkage; transaction-line mapping; shared weight-UOM mapping.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plasticos_transaction"))

from cietrade import header_forensics, mapping, reader, source_index  # noqa: E402

PAYLOAD_ROOT = ROOT / "data" / "legacy_erp_sm_export"

pytestmark = pytest.mark.skipif(
    not (PAYLOAD_ROOT / "bulk").is_dir(),
    reason="CieTrade extract pack is not present in this checkout",
)


@pytest.fixture(scope="module")
def payload():
    return reader.load_payload(PAYLOAD_ROOT)


@pytest.fixture(scope="module")
def index(payload):
    return source_index.build_source_index(payload)


@pytest.fixture(scope="module")
def headers(index):
    return header_forensics.reconstruct_all_headers(index)


# ---------------------------------------------------------------------------
# Reader — the payload parses, with types and NULLs preserved
# ---------------------------------------------------------------------------
def test_payload_loads_every_required_source_table(payload):
    for table in reader.REQUIRED_TABLES:
        assert payload.rows(table), f"{table} carries no rows"


def test_payload_row_counts_are_stable(payload):
    # Golden extract of 2026-08-07. A changed count means a re-extract landed
    # and every downstream expectation in this file must be re-proven.
    assert payload.row_counts() == {
        "Address": 2950,
        "Contact": 4058,
        "ContactRoleAssignment": 3091,
        "CounterParty": 1290,
        "GPLedger": 8220,
        "Payables": 14453,
        "Receipt": 7425,
        "ReceiptBatch": 4545,
        "WKSDetail": 11303,
        "WksDelivery": 8327,
    }


def test_sql_null_and_empty_string_stay_distinct(payload):
    countries = [row["Country"] for row in payload.rows("Address")]
    assert None in countries, "SQL NULL must decode to None"
    assert "" in countries, "an empty cell must stay an empty string"


def test_source_strings_and_decimals_are_preserved_verbatim(payload):
    amounts = [row["SAmount"] for row in payload.rows("WKSDetail") if row["SAmount"]]
    assert amounts, "WKSDetail carries no sale amounts"
    # Values stay exact strings; nothing is rounded before mapping converts it.
    assert all(isinstance(amount, str) for amount in amounts)
    assert any("." in amount for amount in amounts)


def test_missing_payload_root_fails_loudly(tmp_path):
    with pytest.raises(reader.SourcePayloadError):
        reader.load_payload(tmp_path / "does-not-exist")


def test_incomplete_payload_fails_loudly(tmp_path):
    (tmp_path / "bulk").mkdir()
    (tmp_path / "bulk" / "CounterParty.csv").write_text("CpID,CompanyNm\n1,Acme\n", encoding="utf-8")
    with pytest.raises(reader.SourcePayloadError, match="missing source tables"):
        reader.load_payload(tmp_path)


def test_ragged_row_fails_loudly(tmp_path):
    bulk = tmp_path / "bulk"
    bulk.mkdir()
    (bulk / "CounterParty.csv").write_text("CpID,CompanyNm\n1\n", encoding="utf-8")
    with pytest.raises(reader.SourcePayloadError, match="cells, header declares"):
        reader._read_grid_file(bulk / "CounterParty.csv", "CounterParty")


def test_statement_payload_is_supported(tmp_path):
    """An INSERT-bearing extract parses without touching the mappers."""
    (tmp_path / "seed.sql").write_text(
        "INSERT INTO dbo.CounterParty (CpID, CompanyNm, Role) VALUES "
        "('1', 'O''Brien Plastics', 'V'), ('2', NULL, 'X');\n",
        encoding="utf-8",
    )
    tables = reader._read_statement_payload(tmp_path)
    assert tables["CounterParty"] == [
        {"CpID": "1", "CompanyNm": "O'Brien Plastics", "Role": "V"},
        {"CpID": "2", "CompanyNm": None, "Role": "X"},
    ]


# ---------------------------------------------------------------------------
# Source identity — every PK is unique and non-blank
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("attribute", "table", "expected"),
    [
        ("counterparties", "CounterParty", 1290),
        ("addresses", "Address", 2950),
        ("contacts", "Contact", 4058),
        ("contact_roles", "ContactRoleAssignment", 3091),
        ("lines", "WKSDetail", 11303),
    ],
)
def test_primary_keys_are_unique(index, payload, attribute, table, expected):
    indexed = getattr(index, attribute)
    assert len(indexed) == expected == len(payload.rows(table))
    assert all(key.strip() for key in indexed), f"{table} has a blank primary key"


def test_duplicate_primary_key_is_rejected(payload):
    duplicated = dict(payload.tables)
    first = payload.rows("CounterParty")[0]
    duplicated["CounterParty"] = [first, dict(first)]
    clone = reader.SourcePayload(kind=payload.kind, root=payload.root, tables=duplicated)
    with pytest.raises(reader.SourcePayloadError, match="duplicate primary key"):
        source_index.build_source_index(clone)


def test_transaction_universe_is_every_buysellno_owning_lines(index):
    assert len(index.buysell_numbers()) == 8257
    assert sum(len(index.detail_ids(b)) for b in index.buysell_numbers()) == len(index.lines)


# ---------------------------------------------------------------------------
# Parent linkage — resolved by source key only, never by name
# ---------------------------------------------------------------------------
def test_every_linked_address_resolves_to_an_exported_counterparty(index):
    for cp_id, address_ids in index.addresses_by_cp.items():
        assert cp_id in index.counterparties
        assert address_ids


def test_every_linked_contact_resolves_to_an_exported_counterparty(index):
    for cp_id, contact_ids in index.contacts_by_cp.items():
        assert cp_id in index.counterparties
        assert contact_ids


def test_every_linked_role_resolves_to_an_exported_contact(index):
    for contact_id, role_ids in index.roles_by_contact.items():
        assert contact_id in index.contacts
        assert role_ids


def test_children_of_unexported_counterparties_are_reported_not_orphaned(index):
    """Only active counterparties were exported; their children are reported."""
    unresolved = index.unresolved("unresolved_counterparty")
    assert unresolved, "expected children of inactive counterparties"
    linked = {a for ids in index.addresses_by_cp.values() for a in ids}
    for violation in unresolved:
        if violation.table == "Address":
            assert violation.key not in linked


def test_multiple_roles_per_contact_survive(index):
    multi = [c for c, roles in index.roles_by_contact.items() if len(roles) > 1]
    assert len(multi) >= 500, "contacts with several CieTrade roles must keep all of them"


# ---------------------------------------------------------------------------
# Transaction header forensics — supplier / buyer / date / state
# ---------------------------------------------------------------------------
def test_every_transaction_reconstructs_deterministically(index, headers):
    assert set(headers) == set(index.buysell_numbers())
    for buysell_no, header in headers.items():
        assert header.buysell_no == buysell_no
        assert header.state in header_forensics.HISTORICAL_STATES
        assert header.detail_ids == tuple(index.detail_ids(buysell_no))


def test_reconstruction_is_repeatable(index):
    sample = index.buysell_numbers()[:200]
    first = [header_forensics.reconstruct_transaction_header(index, b).as_dict() for b in sample]
    second = [header_forensics.reconstruct_transaction_header(index, b).as_dict() for b in sample]
    assert first == second


def test_supplier_comes_from_material_payables_only(index, headers):
    """Supplier is the payable with no delivery leg; freight vendors are excluded."""
    resolved = {b: h.supplier_cp_id for b, h in headers.items() if h.supplier_cp_id}
    assert len(resolved) >= 6000

    for buysell_no, supplier_cp_id in list(resolved.items())[:400]:
        material = {
            (row.get("CpID") or "").strip()
            for row in index.payables_by_buysell[buysell_no]
            if (row.get("ItemID") or "").strip() in {"", "0"}
        }
        assert material == {supplier_cp_id}
        # A freight-only counterparty is never promoted to supplier.
        freight_only = {
            (row.get("CpID") or "").strip()
            for row in index.payables_by_buysell[buysell_no]
            if (row.get("ItemID") or "").strip() not in {"", "0"}
        } - material
        assert supplier_cp_id not in freight_only


def test_buyer_comes_from_receipt_batch(index, headers):
    resolved = {b: h.buyer_cp_id for b, h in headers.items() if h.buyer_cp_id}
    assert len(resolved) >= 6400

    for buysell_no, buyer_cp_id in list(resolved.items())[:400]:
        batches = {
            (index.receipt_batches[batch]["CPID"] or "").strip()
            for row in index.receipts_by_buysell[buysell_no]
            if (batch := (row.get("ARBatchNo") or "").strip()) in index.receipt_batches
            and (index.receipt_batches[batch]["CPID"] or "").strip()
        }
        assert batches == {buyer_cp_id}


def test_resolved_parties_are_always_exported_counterparties(headers, index):
    for header in headers.values():
        if header.supplier_cp_id:
            assert header.supplier_cp_id in index.counterparties
        if header.buyer_cp_id:
            assert header.buyer_cp_id in index.counterparties


def test_designated_cp_id_is_never_used_as_a_party(index, headers):
    """DesignatedCpID matches neither party and must not leak into one."""
    checked = 0
    for header in headers.values():
        designated = {
            value
            for detail_id in header.detail_ids
            if (value := (index.lines[detail_id].get("DesignatedCpID") or "").strip())
        }
        if not designated:
            continue
        checked += 1
        assert header.supplier_cp_id not in designated
        assert header.buyer_cp_id not in designated
    assert checked >= 20, "expected the populated DesignatedCpID rows to be present"


def test_ambiguous_party_is_left_unresolved_not_guessed(index, headers):
    ambiguous = [h for h in headers.values() if any("ambiguous" in a for a in h.anomalies)]
    assert ambiguous, "expected the known ambiguous-supplier rows"
    for header in ambiguous:
        assert header.supplier_cp_id is None or header.buyer_cp_id is None


def test_missing_party_is_reported_with_a_reason(headers):
    for header in headers.values():
        if header.supplier_cp_id is None:
            assert header.anomalies, f"{header.buysell_no}: unresolved supplier without a reason"
        if header.buyer_cp_id is None:
            assert header.anomalies, f"{header.buysell_no}: unresolved buyer without a reason"


def test_trade_date_is_the_earliest_ledger_date(index, headers):
    dated = [h for h in headers.values() if h.trade_date]
    assert len(dated) >= 7000
    for header in dated[:300]:
        raw = [(row.get("TradeDt") or "").strip() for row in index.ledger_by_buysell[header.buysell_no]]
        parsed = [d for d in (mapping.parse_date(value) for value in raw) if d]
        assert header.trade_date == min(parsed)


def test_state_is_derived_from_settlement_evidence(index, headers):
    for header in list(headers.values())[:800]:
        booked = bool(index.ledger_by_buysell.get(header.buysell_no))
        if header.state == "closed":
            assert booked
            assert index.receipts_by_buysell.get(header.buysell_no)
        elif header.state == "invoiced":
            assert booked
        elif header.state == "delivered":
            assert not booked
            assert index.deliveries_by_buysell.get(header.buysell_no)
        else:
            assert header.state == "draft"
            assert not booked


def test_complete_transactions_carry_both_parties_and_a_date(headers):
    complete = [h for h in headers.values() if h.is_complete]
    assert len(complete) >= 5000
    for header in complete:
        assert header.supplier_cp_id and header.buyer_cp_id and header.trade_date


# ---------------------------------------------------------------------------
# Mapping vocabularies — no silent coercion
# ---------------------------------------------------------------------------
def test_every_counterparty_role_in_the_payload_is_mapped(index):
    codes = {(row.get("Role") or "").strip().upper() for row in index.counterparties.values()}
    assert codes == set(mapping.COMPANY_ROLE_BY_CIETRADE_ROLE)


def test_unknown_role_is_reported_not_defaulted():
    role, anomaly = mapping.company_role("ZZZ")
    assert role is None
    assert "unmapped" in anomaly


def test_role_ranks_match_observed_trade_behaviour():
    assert mapping.trade_ranks("V") == (1, 0)
    assert mapping.trade_ranks("X") == (0, 1)
    assert mapping.trade_ranks("A") == (1, 1)  # trades on both sides
    assert mapping.trade_ranks("D") == (0, 0)  # carrier only


def test_shared_weight_uom_is_used_when_both_sides_agree():
    assert mapping.weight_uom("L", "L") == ("L", None)
    assert mapping.weight_uom("E", "") == ("E", None)
    assert mapping.weight_uom("", "S") == ("S", None)


def test_weight_uom_mismatch_is_flagged_not_resolved():
    uom, anomaly = mapping.weight_uom("L", "E")
    assert uom is None
    assert "mismatch" in anomaly


def test_weight_uom_outside_the_model_selection_is_flagged():
    uom, anomaly = mapping.weight_uom("A", "A")
    assert uom is None
    assert "unmapped" in anomaly


def test_weight_uom_mismatches_in_the_payload_are_a_bounded_known_set(index):
    """Every line whose shared weight UOM cannot be resolved is accounted for.

    163 of 11303 lines: 161 where the sale and purchase UOM genuinely disagree
    (flagged as source-data anomalies, per the locked shared-UOM decision), and
    2 where both sides agree on a code outside the model's L/S/E selection.
    None is silently defaulted to ``L``.
    """
    kinds = {"mismatch": 0, "unmapped": 0}
    for row in index.lines.values():
        uom, anomaly = mapping.weight_uom(row.get("SWeightUOM"), row.get("PWeightUOM"))
        if uom is None:
            kinds["mismatch" if "mismatch" in anomaly else "unmapped"] += 1
    assert kinds == {"mismatch": 161, "unmapped": 2}


def test_unit_type_legacy_code_maps_and_unknown_is_flagged():
    assert mapping.unit_type("9") == ("O", None)
    assert mapping.unit_type("B") == ("B", None)
    assert mapping.unit_type("") == (None, None)
    unit, anomaly = mapping.unit_type("Y")
    assert unit is None
    assert "unmapped" in anomaly


def test_unparsable_number_is_none_not_zero():
    assert mapping.parse_decimal("not-a-number") is None
    assert mapping.parse_decimal("") is None
    assert mapping.parse_decimal("1234.56") == pytest.approx(1234.56)


def test_contact_active_flag_parses_the_char_spelling():
    assert mapping.parse_bool("Y") is True
    assert mapping.parse_bool("N") is False
    assert mapping.parse_bool("") is None


def test_address_kind_falls_back_without_losing_the_label():
    assert mapping.address_kind({"Type": "INVOICE"}) == "invoice"
    assert mapping.address_kind({"Type": "PICK UP ADDRESS"}) == "delivery"
    assert mapping.address_kind({"Type": "OMAHA, NE"}) == "other"


def test_billing_flags_are_honoured_beyond_the_free_text_label():
    """289 InvoiceAddr + 88 RemitTo addresses carry no invoice-like Type."""
    assert mapping.address_kind({"Type": "OMAHA, NE", "InvoiceAddr": "Y"}) == "invoice"
    assert mapping.address_kind({"Type": "WAREHOUSE", "RemitToAddress": "1"}) == "invoice"
    assert mapping.address_kind({"Type": "PRIMARY", "isBillingAddressOnly": "1"}) == "invoice"
    assert mapping.address_kind({"Type": "PRIMARY", "InvoiceAddr": "N"}) == "primary"


def test_billing_address_population_matches_the_payload(index):
    kinds = {}
    for row in index.addresses.values():
        kind = mapping.address_kind(row)
        kinds[kind] = kinds.get(kind, 0) + 1

    assert sum(kinds.values()) == 2950
    assert kinds == {"invoice": 1580, "other": 1273, "delivery": 53, "primary": 44}

    # The free-text Type labels 1212 of them; the billing flags add 368 that
    # the label alone would have mis-filed as ordinary locations.
    by_label = sum(
        1
        for row in index.addresses.values()
        if mapping.ADDRESS_TYPE_KIND.get((row.get("Type") or "").strip().upper()) == "invoice"
    )
    assert by_label == 1212
    assert kinds["invoice"] - by_label == 368


def test_contact_location_resolves_to_an_address_composite_key(index):
    """Location is an exact (CpID, Type) join, never a fuzzy text match."""
    matched = unmatched = 0
    for cp_id, contact_ids in index.contacts_by_cp.items():
        types = {
            (index.addresses[a].get("Type") or "").strip().upper(): a for a in index.addresses_by_cp.get(cp_id, [])
        }
        for contact_id in contact_ids:
            location = (index.contacts[contact_id].get("Location") or "").strip().upper()
            if not location:
                continue
            if location in types:
                matched += 1
            else:
                unmatched += 1
    assert matched > 3000
    assert unmatched < matched / 50
