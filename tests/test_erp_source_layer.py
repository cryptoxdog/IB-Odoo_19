"""ERP source-layer contract tests (no Odoo runtime required).

These run against the **real** frozen extract at
``plasticos_partner_import/erp_extracted_data/bulk/`` (the regression fixture;
the runtime source is the restored ERP database, ADR-021), so a source-shape
regression or a vocabulary drift in a future extract fails here rather than
mid-import. The frozen extract is source truth: no row of it is edited to make
an import pass, and the counts below pin that.

Covered by the contract's ``test_contract.required_before_full_test``:
parser reads the actual files; CpID / AddressID / CT_ID / CRA_ID / BuySellNo /
DetailID identity; facility, contact, and contact-role parent linkage; buyer and
supplier linkage; transaction-line mapping; shared weight-UOM mapping.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plasticos_partner_import"))

from erp import header_forensics, mapping, reader, source_index  # noqa: E402

PAYLOAD_ROOT = ROOT / "plasticos_partner_import" / "erp_extracted_data"
# A fixture marker standing in for the SQL credential; never a real value, never credential-shaped.
FIXTURE_MARKER = "fixture-marker-never-a-real-credential"

pytestmark = pytest.mark.skipif(
    not (PAYLOAD_ROOT / "bulk").is_dir(),
    reason="ERP extract pack is not present in this checkout",
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
        "SalesReps": 977,
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
    assert len(multi) >= 500, "contacts with several ERP roles must keep all of them"


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
    assert codes == set(mapping.COMPANY_ROLE_BY_ERP_ROLE)


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
    assert mapping.address_kind({"Type": "PICK UP"}) == "delivery"
    assert mapping.address_kind({"Type": "HOUSTON TX - PICK UP"}) == "delivery"
    assert mapping.address_kind({"Type": "OMAHA, NE"}) == "delivery"
    assert mapping.address_kind({"Type": "LINCOLN, IL"}) == "delivery"
    assert mapping.address_kind({"Type": "FAYETTEVILLE AR - SITE 425"}) == "delivery"
    assert mapping.address_kind({"Type": "PRIMARY"}) == "invoice"
    assert mapping.address_kind({"Type": "PRIMARY ADDRESS"}) == "invoice"


def test_billing_flags_are_honoured_beyond_the_free_text_label():
    """289 InvoiceAddr + 88 RemitTo addresses carry no invoice-like Type."""
    assert mapping.address_kind({"Type": "OMAHA, NE", "InvoiceAddr": "Y"}) == "invoice"
    assert mapping.address_kind({"Type": "WAREHOUSE", "RemitToAddress": "1"}) == "invoice"
    assert mapping.address_kind({"Type": "PRIMARY", "isBillingAddressOnly": "1"}) == "invoice"
    assert mapping.address_kind({"Type": "PRIMARY", "InvoiceAddr": "N"}) == "invoice"
    assert mapping.address_kind({"Type": "PRIMARY ADDRESS", "InvoiceAddr": "N"}) == "invoice"


def test_address_type_meaning_follows_the_company_role():
    import importlib.util

    path = ROOT / "plasticos_facility_profile" / "address_meaning.py"
    spec = importlib.util.spec_from_file_location("address_meaning", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    meaning = module.address_type_meaning
    assert (
        meaning("contact", is_company=True, company_role="supplier", source_label=None)
        == "This record is the company itself."
    )
    assert meaning("invoice", is_company=True, company_role="supplier", source_label="INVOICE") == "Mailing address"
    assert meaning("delivery", is_company=True, company_role="supplier", source_label="PICK UP") == "Pickup address"
    assert meaning("delivery", is_company=True, company_role="buyer", source_label="DELIVERY") == "Ship-to address"
    assert (
        meaning("delivery", is_company=True, company_role="broker", source_label="PICK UP LOCATION") == "Pickup address"
    )
    assert meaning("delivery", is_company=True, company_role="carrier", source_label="WAREHOUSE") == "Delivery"
    assert "neither" in meaning("other", is_company=True, company_role="supplier", source_label="LINCOLN, IL").lower()


def test_kind_word_is_not_a_location_title():
    assert mapping.is_kind_only_label("INVOICE")
    assert mapping.is_kind_only_label("PRIMARY")
    assert mapping.is_kind_only_label("PRIMARY ADDRESS")
    assert mapping.is_kind_only_label("PICK UP LOCATION")
    assert mapping.is_kind_only_label("PICK-UP ADDRESS")
    assert mapping.is_kind_only_label("DELIVERY ADDRESS")
    assert not mapping.is_kind_only_label("HOUSTON TX - PICK UP")
    assert not mapping.is_kind_only_label("LINCOLN, IL")
    assert not mapping.is_kind_only_label("100 Abbott Park Rd")


def test_site425_is_a_mailbox_and_a_person_name_is_not():
    addresses = [("404235", "FAYETTEVILLE AR - SITE 425")]
    keys = mapping.site_mailbox_keys([(["Site425", "Mike Reed", "PRIMARY"], ["FAYETTEVILLE AR - SITE 425"])])
    assert keys == {"SITE425"}
    assert mapping.site_mailbox_target("Site425", addresses, "FAYETTEVILLE AR", keys) == "404235"
    assert mapping.site_mailbox_target("Mike Reed", addresses, "FAYETTEVILLE AR", keys) is None
    assert mapping.site_mailbox_target("PRIMARY", [("1", "PRIMARY")], "PRIMARY", keys) is None
    assert mapping.mailbox_key("AR") is None
    other_company = [("9", "FAYETTEVILLE AR")]
    assert mapping.site_mailbox_target("Site425", other_company, "FAYETTEVILLE AR", keys) == "9"


def test_location_title_uses_the_place_or_the_city_never_the_street():
    assert mapping.location_title("LINCOLN, IL", "Lincoln", "100 Main St", "", "ACME") == "LINCOLN, IL"
    assert mapping.location_title("INVOICE", "Abbott Park", "100 Abbott Park Rd", "", "ABBOTT") == "Abbott Park"
    assert (
        mapping.location_title("1600 STIEVE ROAD", "East Jordan", "1600 Stieve Road", "", "EAST JORDAN")
        == "East Jordan"
    )
    assert mapping.location_title("PRIMARY ADDRESS", "Portsmouth", "1342 Court St", "", "ABBOTT") == "Portsmouth"
    assert "Court" not in mapping.location_title(
        "TUCKAHOE NURSERIES, INC", "Elmar", "148 Jefferson Rd.", "", "TUCKAHOE NURSERIES INC"
    )


def test_person_key_is_first_and_last_name_inside_one_company():
    assert mapping.person_key("Robert Sheperdson") == mapping.person_key("robert sheperdson")
    assert mapping.person_key("Daron A. Warren") == "DARON|WARREN"
    assert mapping.person_key("accounting") == mapping._alnum("accounting")
    assert ";" in "Linda Combs; Nicole Brown"
    assert mapping.person_key("Linda Combs; Nicole Brown") == mapping._alnum("Linda Combs; Nicole Brown")
    assert mapping.is_person_name("Eli Vogel")
    assert not mapping.is_person_name("16098610383")
    assert mapping.real_phone("1478") == ""
    assert mapping.real_phone("NULL") == ""
    assert mapping.real_phone("(609) 861-0533") == "(609) 861-0533"


def test_contact_roles_collapse_and_rr_stays_unresolved():
    assert mapping.map_contact_role("Primary") == ("Decision Maker", None)
    assert mapping.map_contact_role("Collections") == ("AR/AP", None)
    assert mapping.map_contact_role("Ship / Del Appt") == ("Logistics", None)
    assert mapping.map_contact_role("Admin:Pics/Docs") == ("Admin", None)
    assert mapping.map_contact_role("DM Assistant") == ("Assistant", None)
    assert mapping.map_contact_role("RR") == (None, "rr")
    assert mapping.map_contact_role("Something New") == (None, "unmapped")
    assert mapping.job_position(["Decision Maker", "Logistics"]) == "Decision Maker"
    assert mapping.job_position(["AR/AP"]) == "AR/AP"
    assert mapping.job_position(["Logistics", "Admin"]) == ""


def test_address_layer_groups_rows_without_the_counterparty_file(payload):
    tables = {"Address": payload.rows("Address")[:3]}
    clone = reader.SourcePayload(kind=payload.kind, root=payload.root, tables=tables)
    indexed = source_index.build_source_index(clone)
    assert indexed.addresses
    assert indexed.addresses_by_cp
    assert not indexed.counterparties
    assert not any(item.kind == "unresolved_counterparty" for item in indexed.violations)


def test_partner_only_payload_does_not_open_deal_files():
    payload = reader.load_payload(PAYLOAD_ROOT, only=reader.PARTNER_SOURCE_TABLES)
    assert set(payload.tables) == set(reader.PARTNER_SOURCE_TABLES)
    partner_index = source_index.build_source_index(payload)
    assert partner_index.counterparties
    assert partner_index.addresses
    assert not partner_index.lines


def test_billing_address_population_matches_the_payload(index):
    kinds = {}
    for row in index.addresses.values():
        kind = mapping.address_kind(row)
        kinds[kind] = kinds.get(kind, 0) + 1

    assert sum(kinds.values()) == 2950
    assert kinds == {"invoice": 1624, "delivery": 1326}

    # Invoice, remit, and primary labels. Billing flags add the rest.
    by_label = sum(
        1
        for row in index.addresses.values()
        if mapping.ADDRESS_TYPE_KIND.get((row.get("Type") or "").strip().upper()) == "invoice"
    )
    assert by_label == 1587
    assert kinds["invoice"] - by_label == 37


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


# ---------------------------------------------------------------------------
# SalesReps — company Salesperson
# ---------------------------------------------------------------------------
def test_sales_reps_link_to_loaded_counterparties(index, payload):
    assert len(index.sales_reps_by_cp) == 833
    linked = sum(len(rows) for rows in index.sales_reps_by_cp.values())
    assert linked == 835
    orphans = [v for v in index.violations if v.table == "SalesReps"]
    assert len(orphans) == 142
    assert {v.kind for v in orphans} == {"unresolved_counterparty"}
    # Every SalesReps row is counted exactly once: the linked rows plus the
    # orphans reported as violations. That is the figure the summary reconciles.
    assert index.counts()["sales_reps"] == len(payload.rows("SalesReps")) == linked + len(orphans) == 977


def test_every_assigned_sales_rep_has_a_name(index):
    defaults = {}
    for rows in index.sales_reps_by_cp.values():
        code, anomaly = mapping.default_sales_rep(rows)
        assert anomaly is None
        if code:
            defaults[code] = defaults.get(code, 0) + 1
            assert mapping.sales_rep_login(code), code
    # Includes the sole IsDefault=0 assignment on each company that has no default row.
    assert defaults == {"AA": 113, "AB": 111, "DAVE": 1, "IB": 269, "LR": 60, "MM": 52, "RP": 133, "TF": 94}
    code, anomaly = mapping.default_sales_rep(index.sales_reps_by_cp["2354"])
    assert (code, anomaly) == ("AB", None)


def test_default_sales_rep_uses_the_sole_assignment_when_none_is_default():
    assert mapping.default_sales_rep([{"ReferrerNo": "AB        ", "IsDefault": "0"}]) == ("AB", None)
    assert mapping.default_sales_rep(
        [{"ReferrerNo": "IB", "IsDefault": "1"}, {"ReferrerNo": "AA", "IsDefault": "0"}]
    ) == (
        "IB",
        None,
    )
    code, anomaly = mapping.default_sales_rep(
        [{"ReferrerNo": "IB", "IsDefault": "1"}, {"ReferrerNo": "AA", "IsDefault": "1"}]
    )
    assert code is None
    assert anomaly == "more than one default rep: AA, IB"
    code, anomaly = mapping.default_sales_rep(
        [{"ReferrerNo": "IB", "IsDefault": "0"}, {"ReferrerNo": "AA", "IsDefault": "0"}]
    )
    assert code is None
    assert anomaly == "more than one rep and no default: AA, IB"


def test_sales_rep_login_matches_seeded_user_logins():
    assert mapping.sales_rep_login("ab ") == "ab@scrapmanagement.com"
    assert mapping.sales_rep_login("TF") == "sa@scrapmanagement.com"
    assert mapping.sales_rep_login("MM") == "sales2@scrapmanagement.com"
    assert mapping.sales_rep_login("DAVE") == "sales2@scrapmanagement.com"
    assert mapping.sales_rep_login("LR") == "lm@scrapmanagement.com"
    assert mapping.sales_rep_login("XX") is None
    assert mapping.sales_rep_login(None) is None
    assert mapping.sales_rep_name("TF") == "Tiffany White"


def test_former_rep_initials_are_reassigned_in_the_mapping_not_the_source():
    """docs/erp_import_mapping.md §3a: former reps' accounts belong to MM. A live row still saying JB maps."""
    for former in mapping.SALES_REP_REASSIGNED:
        assert mapping.sales_rep_code(f"{former}   ") == "MM"
        assert mapping.sales_rep_login(former) == "sales2@scrapmanagement.com"
        assert mapping.sales_rep_name(former) == "Mack McMurray"
    assert mapping.sales_rep_code("ib") == "IB"
    # Two default rows that both resolve to MM are one rep, not a conflict.
    assert mapping.default_sales_rep(
        [{"ReferrerNo": "JB", "IsDefault": "1"}, {"ReferrerNo": "MM", "IsDefault": "1"}]
    ) == ("MM", None)


# ---------------------------------------------------------------------------
# Frozen source stays frozen: brokerage mailboxes are dropped in the mapping
# ---------------------------------------------------------------------------
def test_internal_mailboxes_are_dropped_by_the_mapping_not_by_editing_the_extract(index):
    """The extract still carries staff CC addresses (it is source truth); the mapping drops them."""
    carrying = [
        row
        for row in index.contacts.values()
        if mapping.external_emails(row.get("Email") or "") != (row.get("Email") or "")
    ]
    assert len(carrying) == 1104, "the frozen Contact extract must keep its staff mailboxes"
    assert mapping.external_emails("dwarren@kwplastics.com; ib@scrapmanagement.com") == "dwarren@kwplastics.com"
    assert mapping.external_emails("Justin@certifiedusa.net, ib@scrapmanagement.com") == "Justin@certifiedusa.net"
    assert mapping.external_emails("a@x.com; AB@UCSINCNY.COM; b@y.com") == "a@x.com; b@y.com"
    assert mapping.external_emails("ib@scrapmanagement.com") == ""
    assert mapping.external_emails("") == ""
    assert mapping.external_emails(None) == ""
    # A cell with no internal mailbox is returned verbatim, whitespace included.
    assert mapping.external_emails("  a@x.com ; b@y.com") == "  a@x.com ; b@y.com"
    # The display-name form survives when the internal address is a separate entry.
    assert mapping.external_emails("Zach P <z@adv.com>; nmask@adv.com; ab@scrapmanagement.com") == (
        "Zach P <z@adv.com>; nmask@adv.com"
    )


def test_placeholder_counterparty_rows_stay_in_the_extract_and_are_reported(index):
    """Placeholder CpIDs stay in the extract. ``(INV)`` is a destination; every other placeholder stays unresolved."""
    placeholder_rows = [row for row in index.addresses.values() if (row.get("CpID") or "").startswith(("(", "{", "["))]
    assert placeholder_rows, "the frozen Address extract must keep its placeholder rows"
    reported = {v.key for v in index.violations if v.table == "Address" and v.kind == "unresolved_counterparty"}
    linked = {address_id for ids in index.addresses_by_cp.values() for address_id in ids}
    inventory = [
        row for row in placeholder_rows if (row.get("CpID") or "").strip() == source_index.INVENTORY_COUNTERPARTY
    ]
    assert inventory, "the frozen Address extract must keep its (INV) destination rows"
    for row in placeholder_rows:
        address_id = row["AddressID"]
        assert address_id not in linked
        if (row.get("CpID") or "").strip() == source_index.INVENTORY_COUNTERPARTY:
            assert address_id not in reported
            assert address_id in index.inventory_destinations
            assert index.inventory_destination_ids(row.get("CpID"), row.get("Type"))
        else:
            assert address_id in reported
            assert address_id not in index.inventory_destinations


def test_inventory_destination_selector_holds_zero_or_many_and_the_summary_closes():
    """(CustID, ShipToID) matches (CpID, Type). Other placeholders stay rejected and the equation closes."""
    from erp.report import ImportReport
    from erp.summary import import_run_summary

    payload = reader.SourcePayload(
        kind=reader.PayloadKind.GRID,
        root=PAYLOAD_ROOT,
        tables={
            "CounterParty": [{"CpID": "2106", "CompanyNm": "JEI"}],
            "Address": [
                {"AddressID": "404812", "CpID": "(INV)", "Type": "GREENVIEW WASHINGTON WAREHOUSE"},
                {"AddressID": "405026", "CpID": "(INV)", "Type": "JEI DALLAS WAREHOUSE"},
                {"AddressID": "405027", "CpID": "(INV)", "Type": "JEI DALLAS WAREHOUSE"},
                {"AddressID": "404811", "CpID": "2106", "Type": "INVOICE"},
                {"AddressID": "1", "CpID": "(HOLD)", "Type": "GREENVIEW WASHINGTON WAREHOUSE"},
            ],
        },
    )
    indexed = source_index.build_source_index(payload)
    assert indexed.inventory_destination_ids("(INV)", "GREENVIEW WASHINGTON WAREHOUSE") == ["404812"]
    assert indexed.inventory_destination_ids("(INV)", "JEI DALLAS WAREHOUSE") == ["405026", "405027"]
    assert indexed.inventory_destination_ids("(INV)", "") == []
    assert "1" not in indexed.inventory_destinations
    assert "404811" not in indexed.inventory_destinations
    assert indexed.addresses_by_cp == {"2106": ["404811"]}
    assert indexed.inventory_destination_ids("2106", "GREENVIEW WASHINGTON WAREHOUSE") == []
    # The address population under test is the three (INV) rows plus the other
    # placeholder. The exported company is a partner row, not one of those.
    report = ImportReport()
    report.source_counts = {"addresses": 4}
    for violation in indexed.violations:
        if violation.table == "Address":
            report.unresolved.append(violation.as_dict())
    source_index.account_inventory_destinations(indexed, report)
    summary = import_run_summary(report.as_dict())
    accounted = (
        summary["records_created"]
        + summary["records_updated"]
        + summary["records_unchanged"]
        + summary["records_rejected"]
    )
    assert summary["records_seen"] == accounted
    assert summary["records_unchanged"] == 3
    assert summary["records_rejected"] == 1
    assert summary["final_status"] == "partial"


# ---------------------------------------------------------------------------
# Direct database read — the ADR-021 target form
# ---------------------------------------------------------------------------
class _FakeCursor:
    def __init__(self, result_sets):
        self._result_sets = result_sets
        self.description = ()
        self.executed: list[str] = []
        self._rows: list = []

    def execute(self, statement):
        self.executed.append(statement)
        source_table = next(name for name in self._result_sets if f"FROM dbo.{name}\n" in statement)
        columns, rows = self._result_sets[source_table]
        self.description = tuple((column, None, None, None, None, None, None) for column in columns)
        self._rows = rows

    def fetchall(self):
        return list(self._rows)

    def close(self):
        pass


class _FakeConnection:
    def __init__(self, result_sets):
        self.result_sets = result_sets
        self.cursors: list[_FakeCursor] = []
        self.closed = False

    def cursor(self):
        cursor = _FakeCursor(self.result_sets)
        self.cursors.append(cursor)
        return cursor

    def close(self):
        self.closed = True


def _database_fixture():
    from decimal import Decimal

    # Keyed by the source table each projection script reads (FROM dbo.<table>).
    result_sets = {
        "CounterParty": (
            ["CpID", "CompanyNm", "Role", "ActiveStatus", "CreditLimit", "CpLastEdit"],
            [("1004", "PIER", "V", "A", Decimal("25000.00"), "2026-08-07 10:11:12")],
        ),
        "Address": (
            ["AddressID", "CpID", "Type", "Addr1", "Country", "InvoiceAddr", "RemitToAddress"],
            [
                (402426, "1004", "INVOICE", "PIER", None, "Y", False),
                (402427, "(INV)", "[STAGING]", None, "", "N", True),
                (402428, "(HOLD)", "OTHER", None, "", "N", False),
            ],
        ),
        "Contact": (["CT_ID", "CpID", "ContactNm", "Email", "IsActive"], [(100001, "1004", "Heather", "", "Y")]),
        "ContactRoleAssignment": (["CRA_ID", "CT_ID", "RoleNm"], [(1, 100001, "Primary")]),
        "Counterparty_Referrer": (
            ["CpID", "ReferrerNo", "Rate", "Charge", "IsDefault", "ChgPer"],
            [("1004", "MM        ", Decimal("25"), 0, True, "%")],
        ),
    }
    connection = _FakeConnection(result_sets)
    return connection, reader.DatabaseSource(connect=lambda: connection, label="erp-host/ERP_RESTORED")


def test_direct_database_read_executes_the_projection_scripts_with_source_fidelity():
    connection, source = _database_fixture()
    payload = reader.load_payload(database=source, only=reader.PARTNER_SOURCE_TABLES)

    assert payload.kind == reader.PayloadKind.DATABASE
    assert payload.origin == "erp-host/ERP_RESTORED"
    assert set(payload.tables) == set(reader.PARTNER_SOURCE_TABLES)
    # One projection script per partner table, read from the extract-authority folder.
    executed = "\n".join(statement for cursor in connection.cursors for statement in cursor.executed)
    for table in reader.PARTNER_SOURCE_TABLES:
        script = reader.PROJECTION_SCRIPTS[table]
        text = (PAYLOAD_ROOT / script).read_text(encoding="utf-8-sig")
        assert text in executed, f"{table} must be read through {script}"
    for table in reader.SOURCE_TABLES.keys() - reader.PARTNER_SOURCE_TABLES:
        text = (PAYLOAD_ROOT / reader.PROJECTION_SCRIPTS[table]).read_text(encoding="utf-8-sig")
        assert text not in executed, f"partner-only read must not open {table}"
    assert connection.closed

    counterparty = payload.rows("CounterParty")[0]
    assert counterparty["CpID"] == "1004" and isinstance(counterparty["CpID"], str)
    assert counterparty["CreditLimit"] == "25000", "decimals render as the grid did: no trailing zeros"
    assert counterparty["CpLastEdit"] == "2026-08-07 10:11:12"
    addresses = payload.rows("Address")
    assert addresses[0]["AddressID"] == "402426", "integers become exact strings"
    assert addresses[0]["Country"] is None, "SQL NULL is None"
    assert addresses[1]["Country"] == "", "an empty string stays an empty string"
    assert addresses[0]["RemitToAddress"] == "0" and addresses[1]["RemitToAddress"] == "1", "bits render 1/0"
    rep = payload.rows("SalesReps")[0]
    assert rep["ReferrerNo"] == "MM        ", "char padding is preserved; the mapping strips it"
    assert rep["IsDefault"] == "1" and rep["Rate"] == "25"
    # The rows feed the same identity layer as every other form.
    indexed = source_index.build_source_index(payload)
    assert indexed.counterparty_ids() == ["1004"]
    assert indexed.addresses_by_cp == {"1004": ["402426"]}
    assert set(indexed.inventory_destinations) == {"402427"}
    assert indexed.inventory_destination_ids("(INV)", "[STAGING]") == ["402427"]
    address_violations = [v for v in indexed.violations if v.table == "Address"]
    assert [v.key for v in address_violations] == ["402428"]
    assert [v.kind for v in address_violations] == ["unresolved_counterparty"]
    assert indexed.counts()["sales_reps"] == 1


def test_direct_database_read_wins_over_a_payload_root():
    connection, source = _database_fixture()
    payload = reader.load_payload(PAYLOAD_ROOT, database=source, only=reader.PARTNER_SOURCE_TABLES)
    assert payload.kind == reader.PayloadKind.DATABASE
    assert payload.row_counts()["CounterParty"] == 1


def test_direct_database_read_covers_transaction_reconstruction_tables():
    """Concern 2A reads the six deal tables through the same projection scripts."""
    connection, source = _database_fixture()
    deal_rows = {
        "Payables": (["BuySellNo", "ItemID", "CpID"], [("BS1", "0", "1004")]),
        "Receipt": (["BuySellNo", "ARBatchNo"], [("BS1", "B1")]),
        "ReceiptBatch": (["ARBatchNo", "CPID"], [("B1", "1004")]),
        "GPLedger": (["BuySellNo", "TradeDt"], [("BS1", "2026-01-02 00:00:00")]),
        "WKSDetail": (
            ["DetailID", "BuySellNo", "SWeightUOM", "PWeightUOM"],
            [(7, "BS1", "L", "L")],
        ),
        "WksDelivery": (["ItemID", "BuySellNo", "VendorID"], [(9, "BS1", "1004")]),
    }
    connection.result_sets.update(deal_rows)
    payload = reader.load_payload(database=source)

    assert payload.kind == reader.PayloadKind.DATABASE
    assert set(payload.tables) == set(reader.SOURCE_TABLES)
    executed = "\n".join(statement for cursor in connection.cursors for statement in cursor.executed)
    for table in ("WKSDetail", "Payables", "Receipt", "ReceiptBatch", "GPLedger", "WksDelivery"):
        script = reader.PROJECTION_SCRIPTS[table]
        text = (PAYLOAD_ROOT / script).read_text(encoding="utf-8-sig")
        assert text in executed, f"{table} must be read through {script}"
        assert f"FROM dbo.{'Counterparty_Referrer' if table == 'SalesReps' else table}" in text

    index = source_index.build_source_index(payload)
    assert index.buysell_numbers() == ["BS1"]
    assert index.detail_ids("BS1") == ["7"]
    header = header_forensics.reconstruct_transaction_header(index, "BS1")
    assert header.supplier_cp_id == "1004"
    assert header.buyer_cp_id == "1004"
    assert header.trade_date is not None
    assert header.detail_ids == ("7",)


def test_direct_database_read_reports_an_unreachable_database_without_a_credential():
    leaked = FIXTURE_MARKER

    def refuse():
        raise OSError(f"login failed for user 'erp_reader' (driver echoed {leaked})")

    source = reader.DatabaseSource(connect=refuse, label="erp-host/ERP_RESTORED")
    with pytest.raises(reader.SourcePayloadError) as excinfo:
        reader.load_payload(database=source, only=reader.PARTNER_SOURCE_TABLES)
    assert leaked not in str(excinfo.value)
    assert "erp-host/ERP_RESTORED" in str(excinfo.value)


def test_database_source_is_bound_from_the_environment_without_leaking_the_password():
    assert reader.database_source_from_env({}) is None
    assert reader.database_source_from_env({"ERP_PAYLOAD_ROOT": "/x"}) is None
    with pytest.raises(reader.SourcePayloadError, match="both be set"):
        reader.database_source_from_env({"ERP_SQL_SERVER": "host"})
    with pytest.raises(reader.SourcePayloadError, match="port number"):
        reader.database_source_from_env({"ERP_SQL_SERVER": "host", "ERP_SQL_DATABASE": "db", "ERP_SQL_PORT": "x"})
    with pytest.raises(reader.SourcePayloadError, match="ERP_SQL_DRIVER"):
        reader.database_source_from_env({"ERP_SQL_SERVER": "host", "ERP_SQL_DATABASE": "db", "ERP_SQL_DRIVER": "odbc"})
    marker = FIXTURE_MARKER
    source = reader.database_source_from_env(
        {
            "ERP_SQL_SERVER": "erp-host",
            "ERP_SQL_DATABASE": "ERP_RESTORED",
            "ERP_SQL_USER": "u",
            reader.ENV_SQL_CREDENTIAL: marker,
        }
    )
    assert source is not None
    assert source.label == "erp-host/ERP_RESTORED"
    assert marker not in repr(source)


def test_projection_scripts_exist_and_are_select_only():
    for table, script in reader.PROJECTION_SCRIPTS.items():
        text = (PAYLOAD_ROOT / script).read_text(encoding="utf-8-sig")
        upper = text.upper()
        assert "SELECT" in upper, f"{script} is not a projection"
        for forbidden in ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER ", "TRUNCATE ", "SELECT *"):
            assert forbidden not in upper, f"{script} must not contain {forbidden.strip()}"
        assert "ORDER BY" in upper, f"{script} must be deterministically ordered ({table})"


# ---------------------------------------------------------------------------
# Runtime gate G5 — the projection inventory it holds the registry to
# ---------------------------------------------------------------------------
# G5 (tests/runtime_gates/run_erp_import.py) refuses to import before it has
# checked the projection registry. That expectation must follow the registry's
# consumer — a full direct-SQL run reads REQUIRED_TABLES | COMMERCIAL_SQL_TABLES
# (erp_import_service) — not a count pinned when the registry had 11 entries:
# PR #231 registered the four commercial projections and the pinned gate could
# no longer pass against the very inventory it was meant to prove (FX-011).
GATE = ROOT / "tests" / "runtime_gates" / "run_erp_import.py"
SERVICE = ROOT / "plasticos_partner_import" / "models" / "erp_import_service.py"
FULL_DIRECT_SQL_TABLES = frozenset(reader.REQUIRED_TABLES) | frozenset(reader.COMMERCIAL_SQL_TABLES)
SOURCE_LABEL = "erp-host/ERP_RESTORED"


def test_registered_projection_inventory_is_the_full_direct_sql_read_set():
    """The registry carries exactly what the full run consumes, and each script exists."""
    assert "reader.REQUIRED_TABLES | reader.COMMERCIAL_SQL_TABLES" in SERVICE.read_text(encoding="utf-8"), (
        "erp_import_service no longer reads REQUIRED_TABLES | COMMERCIAL_SQL_TABLES on a full "
        "direct-SQL run; update FULL_DIRECT_SQL_TABLES and the G5 expectation together"
    )
    assert set(reader.PROJECTION_SCRIPTS) == set(FULL_DIRECT_SQL_TABLES)
    assert reader.COMMERCIAL_SQL_TABLES.isdisjoint(reader.REQUIRED_TABLES)
    for table, script in reader.PROJECTION_SCRIPTS.items():
        assert (reader.sql_payload_root() / script).is_file(), f"{table} -> {script} is not checked in"


@pytest.fixture
def erp_gate(monkeypatch):
    """The live G5 gate module, loaded without Odoo, PostgreSQL, or any database.

    Only the module-level runtime bindings are stubbed (``odoo`` config and
    registry path setup, ``psycopg2``); the reader the gate imports is the real
    one, so the gate is judged against the real projection registry.
    """
    import importlib.util
    import types

    def stub(name, **attrs):
        module = types.ModuleType(name)
        for attr, value in attrs.items():
            setattr(module, attr, value)
        monkeypatch.setitem(sys.modules, name, module)
        return module

    odoo = stub("odoo", SUPERUSER_ID=1)
    odoo.modules = stub("odoo.modules")
    odoo.modules.module = stub("odoo.modules.module", initialize_sys_path=lambda: None)
    odoo.sql_db = stub("odoo.sql_db")
    stub("odoo.api", Environment=object)
    stub("odoo.tools", config={})
    stub("psycopg2")
    stub("odoo.addons")
    stub("odoo.addons.plasticos_partner_import")
    stub("odoo.addons.plasticos_partner_import.erp", reader=reader)
    monkeypatch.setitem(sys.modules, "odoo.addons.plasticos_partner_import.erp.reader", reader)
    # The gate puts its own directory on sys.path to import its helpers; keep that local to the test.
    monkeypatch.setattr(sys, "path", list(sys.path))
    for helper in ("_runtime_env", "scratch_db"):
        monkeypatch.delitem(sys.modules, helper, raising=False)
    spec = importlib.util.spec_from_file_location("erp_runtime_gate_under_test", GATE)
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    yield gate
    for helper in ("_runtime_env", "scratch_db"):
        sys.modules.pop(helper, None)


def _run_g5(gate, monkeypatch):
    """Run G5 against the real registry with the runtime seams recorded instead of driven.

    The import, the direct read, and the marker census are the Odoo and
    SQL Server seams; each is replaced by a recorder that returns a closing,
    database-sourced result, so the only thing left to decide G5 is the
    registry check under test and the tables the gate asks the reader for.
    """
    calls: dict[str, list] = {"imports": [], "reads": []}
    closing = {
        "records_seen": 3,
        "records_created": 3,
        "records_updated": 0,
        "records_unchanged": 0,
        "records_rejected": 0,
        "duplicates": 0,
        "final_status": "success",
        "errors": [],
    }

    def import_once(payload_root=None, database=None, partners_only=True):
        calls["imports"].append((database.label, partners_only))
        return {"summary": dict(closing), "counts": {}, "payload_kind": reader.PayloadKind.DATABASE.value}

    def load_payload(root=None, *, only=None, database=None):
        calls["reads"].append(only)
        tables = {table: [] for table in (only if only is not None else reader.REQUIRED_TABLES)}
        return reader.SourcePayload(
            kind=reader.PayloadKind.DATABASE, root=PAYLOAD_ROOT, tables=tables, origin=database.label
        )

    monkeypatch.setattr(gate, "import_once", import_once)
    monkeypatch.setattr(reader, "load_payload", load_payload)
    monkeypatch.setattr(gate, "_deal_marker_census", lambda: dict.fromkeys(gate.DEAL_MARKERS, 0))
    source = reader.DatabaseSource(connect=lambda: None, label=SOURCE_LABEL)
    return gate.gate_g5_direct_sql_import_reconciles(source), calls


def test_g5_holds_the_registry_to_the_full_direct_sql_read(erp_gate, monkeypatch, capsys):
    """Against the real registry G5 passes its inventory check and reads every registered projection."""
    passed, calls = _run_g5(erp_gate, monkeypatch)
    out = capsys.readouterr().out
    assert passed, f"G5 refused the real projection registry:\n{out}"
    assert "projection registry" not in out
    assert calls["imports"] == [(SOURCE_LABEL, True), (SOURCE_LABEL, False)]
    assert calls["reads"] == [FULL_DIRECT_SQL_TABLES], "the direct read must cover every table the full run reads"


@pytest.mark.parametrize(
    ("drift", "registry"),
    [
        pytest.param(
            "consumed table unregistered",
            {table: script for table, script in reader.PROJECTION_SCRIPTS.items() if table != "PO"},
            id="unregistered",
        ),
        pytest.param(
            "orphan projection registered",
            {**reader.PROJECTION_SCRIPTS, "Ghost": "10_counterparty.sql"},
            id="orphan",
        ),
        pytest.param(
            "registered script file missing",
            {**reader.PROJECTION_SCRIPTS, "PO": "22_po_renamed.sql"},
            id="script-missing",
        ),
    ],
)
def test_g5_fails_closed_before_any_write_on_registry_drift(erp_gate, monkeypatch, capsys, drift, registry):
    monkeypatch.setattr(reader, "PROJECTION_SCRIPTS", registry)
    passed, calls = _run_g5(erp_gate, monkeypatch)
    out = capsys.readouterr().out
    assert not passed, f"G5 passed with {drift}:\n{out}"
    assert "projection registry" in out, out
    assert calls["imports"] == [] and calls["reads"] == [], f"G5 reached the runtime with {drift}"


# ---------------------------------------------------------------------------
# Runtime gate exit status — a partial proof is INCOMPLETE, never PASS
# ---------------------------------------------------------------------------
# Without ERP_SQL_* the gate runs G1–G4 only and prints NOT RUN for G5/G6. It
# used to exit 0 on that run, so `make runtime-gates` counted the script as
# passed and its skipped-gate accounting never saw the unrun seam (FX-005,
# Codex finding on PR #246). The exit code is driven here with every runtime
# seam stubbed: 0 only when G1–G6 all ran and passed, 1 on any failure, 77
# when the direct-SQL seam did not run.
def _drive_gate_main(gate, monkeypatch, tmp_path, *, source, results: dict[str, bool]):
    """Run ``main()`` with the runtime seams recorded instead of driven; returns (exit, ran, output)."""
    ran: list[str] = []

    def gate_fn(name):
        def run(*_args):
            ran.append(name)
            return results[name]

        return run

    monkeypatch.setattr(gate, "ODOO_SRC", str(tmp_path))
    monkeypatch.setattr(gate, "ODOO_ADDONS", str(tmp_path))
    monkeypatch.setattr(gate, "direct_sql_source", lambda: source)
    monkeypatch.setattr(gate, "create_scratch_db", lambda: True)
    monkeypatch.setattr(gate, "release_scratch_db", lambda: None)
    monkeypatch.setattr(gate, "drop_scratch_db", lambda: None)
    monkeypatch.setattr(gate, "gate_g1_first_import_reconciles", gate_fn("G1"))
    monkeypatch.setattr(gate, "gate_g2_repeat_is_idempotent", gate_fn("G2"))
    monkeypatch.setattr(gate, "gate_g3_changed_source_updates", gate_fn("G3"))
    monkeypatch.setattr(gate, "gate_g4_full_import_writes_no_transaction_object", gate_fn("G4"))
    monkeypatch.setattr(gate, "gate_g5_direct_sql_import_reconciles", gate_fn("G5"))
    monkeypatch.setattr(gate, "gate_g6_direct_sql_replay_is_idempotent", gate_fn("G6"))
    monkeypatch.delenv(gate.REQUIRE_DIRECT_SQL_ENV, raising=False)
    return gate.main(), ran


ALL_PASS = dict.fromkeys(("G1", "G2", "G3", "G4", "G5", "G6"), True)


def test_gate_passes_only_when_every_gate_ran_and_passed(erp_gate, monkeypatch, tmp_path, capsys):
    source = reader.DatabaseSource(connect=lambda: None, label=SOURCE_LABEL)
    code, ran = _drive_gate_main(erp_gate, monkeypatch, tmp_path, source=source, results=ALL_PASS)
    out = capsys.readouterr().out
    assert ran == ["G1", "G2", "G3", "G4", "G5", "G6"]
    assert code == 0, out
    assert "NOT RUN" not in out and "INCOMPLETE" not in out


def test_gate_without_direct_sql_is_incomplete_never_pass(erp_gate, monkeypatch, tmp_path, capsys):
    """G1–G4 pass, G5/G6 do not run: exit 77 so the aggregator counts the unrun seam."""
    code, ran = _drive_gate_main(erp_gate, monkeypatch, tmp_path, source=None, results=ALL_PASS)
    out = capsys.readouterr().out
    assert ran == ["G1", "G2", "G3", "G4"]
    assert "NOT RUN  G5/G6" in out
    assert code != 0, f"a run that never proved the direct-SQL seam exited 0 (false green):\n{out}"
    assert code == 77 and "INCOMPLETE" in out, out


@pytest.mark.parametrize("source_present", [False, True], ids=["fixture-only", "direct-sql"])
def test_gate_failure_outranks_the_incomplete_verdict(erp_gate, monkeypatch, tmp_path, capsys, source_present):
    source = reader.DatabaseSource(connect=lambda: None, label=SOURCE_LABEL) if source_present else None
    code, ran = _drive_gate_main(erp_gate, monkeypatch, tmp_path, source=source, results={**ALL_PASS, "G2": False})
    out = capsys.readouterr().out
    assert "G1" in ran and "G2" in ran
    assert code == 1, f"a failed gate must exit 1, not pass or read INCOMPLETE:\n{out}"
    assert "INCOMPLETE" not in out


def test_required_direct_sql_without_a_source_skips_before_any_gate(erp_gate, monkeypatch, tmp_path, capsys):
    monkeypatch.setenv(erp_gate.REQUIRE_DIRECT_SQL_ENV, "1")
    ran: list[str] = []
    monkeypatch.setattr(erp_gate, "ODOO_SRC", str(tmp_path))
    monkeypatch.setattr(erp_gate, "ODOO_ADDONS", str(tmp_path))
    monkeypatch.setattr(erp_gate, "direct_sql_source", lambda: None)
    monkeypatch.setattr(erp_gate, "create_scratch_db", lambda: ran.append("scratch") or True)
    assert erp_gate.main() == 77
    assert ran == [], "no scratch database may be created when the required seam cannot run"
    assert "cannot run" in capsys.readouterr().out
