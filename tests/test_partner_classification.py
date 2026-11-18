"""Partner classification on native fields (C1 lane F2, ADR-131 Decision B).

The rules are pure functions in ``plasticos_facility_profile/classification.py``;
the models delegate to them. The wiring checks read the module files.
"""

from __future__ import annotations

import ast
import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "plasticos_facility_profile"


def _load():
    spec = importlib.util.spec_from_file_location("partner_classification", MODULE / "classification.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CL = _load()


# ── Trade Role tags from native ranks ───────────────────────────────────

MEMBERS = {"Buyer": 11, "Supplier": 12}


@pytest.mark.parametrize(
    ("customer_rank", "supplier_rank", "expected"),
    [
        (1, 0, {"Buyer"}),
        (0, 3, {"Supplier"}),
        (2, 5, {"Buyer", "Supplier"}),
        (0, 0, set()),
        (None, None, set()),
    ],
)
def test_trade_role_names_follow_the_native_ranks(customer_rank, supplier_rank, expected):
    assert CL.trade_role_names(customer_rank, supplier_rank) == expected


def test_a_buyer_and_supplier_gets_both_tags_and_no_both_or_broker_label():
    assert CL.synced_trade_tag_ids({7}, MEMBERS, 1, 1) == {7, 11, 12}
    assert "Both" not in CL.TRADE_ROLE_NAMES
    assert "Broker" not in CL.TRADE_ROLE_NAMES


def test_ranks_are_the_source_of_truth_for_trade_role_tags():
    # A Supplier tag with no supplier rank is removed; other tags stay.
    assert CL.synced_trade_tag_ids({7, 12}, MEMBERS, 1, 0) == {7, 11}
    assert CL.synced_trade_tag_ids({7, 11, 12}, MEMBERS, 0, 0) == {7}


def test_a_trade_role_tag_not_yet_in_the_group_is_skipped():
    assert CL.synced_trade_tag_ids({7}, {"Buyer": 11}, 1, 1) == {7, 11}


# ── Do Not Contact ──────────────────────────────────────────────────────


def test_do_not_contact_triggers_only_when_newly_set():
    assert CL.newly_tagged({1}, {1, 9}, 9)
    assert not CL.newly_tagged({1, 9}, {1, 9}, 9)
    assert not CL.newly_tagged({1, 9}, {1}, 9)


def test_blacklists_are_only_added_to_never_removed():
    code = (MODULE / "models/res_partner_classification.py").read_text(encoding="utf-8")
    assert "mail_blacklist._add(" in code
    assert "phone_blacklist.add(" in code
    assert '"phone.blacklist" in self.env' in code
    for removal in ("._remove(", ".remove(", "action_archive", "unlink("):
        assert removal not in code


# ── Company Type mirror ─────────────────────────────────────────────────

GROUP = {101, 102, 103}  # Company Type members
ERP_ROLE = 201  # ERP Contact Role tag
STATUS = 301  # Status tag


def test_mirror_sets_only_company_type_tags_on_a_child():
    child = {ERP_ROLE, STATUS, 103}
    company = {101, 102, STATUS}
    assert CL.mirrored_tag_ids(child, company, GROUP) == {ERP_ROLE, STATUS, 101, 102}


def test_mirror_keeps_erp_role_and_status_when_company_type_is_cleared():
    assert CL.mirrored_tag_ids({ERP_ROLE, STATUS, 101}, set(), GROUP) == {ERP_ROLE, STATUS}


def test_mirror_does_not_copy_the_company_status_tags():
    assert STATUS not in CL.mirrored_tag_ids({ERP_ROLE}, {101, STATUS}, GROUP)


def test_trade_role_mirror_uses_the_same_rule():
    trade = {11, 12}
    assert CL.mirrored_tag_ids({ERP_ROLE, STATUS}, {11, 12, 101}, trade) == {ERP_ROLE, STATUS, 11, 12}


def test_mirror_is_idempotent():
    once = CL.mirrored_tag_ids({ERP_ROLE, 103}, {101}, GROUP)
    assert CL.mirrored_tag_ids(once, {101}, GROUP) == once


# ── Same-name tags join the group, never duplicated ─────────────────────

GROUP_ID = 900


def test_existing_root_tags_are_reparented_not_duplicated():
    tags = [(5, "Broker", False), (6, "Carrier", None), (7, "Unrelated", False)]
    reparent, missing = CL.reparent_plan(tags, GROUP_ID, ("Broker", "Carrier", "MRF"))
    assert reparent == [5, 6]
    assert missing == ["MRF"]


def test_a_name_already_in_the_group_is_not_reparented_again():
    tags = [(5, "Broker", GROUP_ID), (6, "Broker", False)]
    reparent, missing = CL.reparent_plan(tags, GROUP_ID, ("Broker",))
    assert reparent == []
    assert missing == []


def test_two_root_tags_with_one_name_move_only_the_oldest():
    tags = [(8, "MRF", False), (4, "MRF", False)]
    reparent, _missing = CL.reparent_plan(tags, GROUP_ID, ("MRF",))
    assert reparent == [4]


def test_a_tag_under_another_parent_is_left_where_it_is():
    reparent, missing = CL.reparent_plan([(5, "Broker", 77)], GROUP_ID, ("Broker",))
    assert reparent == []
    assert missing == ["Broker"]


def test_the_classification_names():
    assert len(CL.COMPANY_TYPE_NAMES) == len(set(CL.COMPANY_TYPE_NAMES)) == 12
    assert CL.TRADE_ROLE_NAMES == ("Buyer", "Supplier")
    assert CL.STATUS_NAMES == ("Current", "Open", "Hot", "Warm", "Cold", "Resist", "Unqualified", "DNC")
    crm_names = {
        node.findtext("field[@name='name']")
        for node in ET.parse(ROOT / "plasticos_crm_bridge/data/partner_category_data.xml").iter("record")
    }
    base_names = {
        node.findtext("field[@name='name']")
        for node in ET.parse(ROOT / "plasticos_base/data/partner_tags.xml").iter("record")
    }
    # Every Company Type name already exists in crm_bridge or base: re-parented, not created again.
    assert set(CL.COMPANY_TYPE_NAMES) <= crm_names | base_names
    assert set(CL.TRADE_ROLE_NAMES) <= crm_names
    # DNC is plasticos_base "Do Not Contact" renamed in place (same record, same external id).
    assert "Do Not Contact" in base_names


# ── Wiring ──────────────────────────────────────────────────────────────


def _manifest():
    return ast.literal_eval((MODULE / "__manifest__.py").read_text(encoding="utf-8"))


def test_manifest_loads_the_classification_data_after_its_dependency():
    manifest = _manifest()
    assert "plasticos_base" in manifest["depends"]
    assert "data/partner_classification_data.xml" in manifest["data"]
    assert tuple(int(part) for part in manifest["version"].split(".")) > (19, 0, 5, 4, 17)
    assert (MODULE / "migrations" / "19.0.5.5.0" / "post-migrate.py").is_file()


def test_base_tags_join_the_groups_on_every_upgrade():
    root = ET.parse(MODULE / "data/partner_classification_data.xml").getroot()
    overrides = {}
    for data in root.iter("data"):
        for record in data.iter("record"):
            if record.get("id", "").startswith("plasticos_base."):
                assert data.get("noupdate") == "0"
                overrides[record.get("id")] = record.find("field[@name='parent_id']").get("ref")
    assert overrides == {
        "plasticos_base.tag_exporter": "partner_category_company_type",
        "plasticos_base.tag_toll_processor": "partner_category_company_type",
        "plasticos_base.tag_do_not_contact": "partner_category_status",
    }
    groups = {record.get("id") for record in root.iter("record") if record.get("id").startswith("partner_category_")}
    assert groups == {"partner_category_company_type", "partner_category_trade_role", "partner_category_status"}
    dnc = root.find(".//record[@id='plasticos_base.tag_do_not_contact']")
    assert dnc.findtext("field[@name='name']") == "DNC"
    assert root.find(".//function[@name='_plasticos_ensure_classification_tags']") is not None


def test_models_are_wired():
    init = (MODULE / "models/__init__.py").read_text(encoding="utf-8")
    for name in ("res_partner_category", "res_partner_classification"):
        assert f"from . import {name}\n" in init
    # company_role is left as it is: no compute, no badge.
    assert "company_role" not in (MODULE / "models/res_partner_classification.py").read_text(encoding="utf-8")


def test_contacts_search_has_the_trade_role_filters_and_group_by():
    arch = (MODULE / "views/partner_ux.xml").read_text(encoding="utf-8")
    assert "[('customer_rank', '&gt;', 0), ('supplier_rank', '&gt;', 0)]" in arch
    assert "group_by': 'company_role'" not in arch
    assert "('category_id.parent_id.name', '=', 'Company Type')" in arch


def test_locations_list_has_a_contact_column():
    arch = (MODULE / "views/facility_profile_views.xml").read_text(encoding="utf-8")
    locations = arch[arch.index('name="location_child_ids"') :]
    locations = locations[: locations.index("</list>")]
    assert '<field name="contact_header_name" string="Contact"/>' in locations


def test_every_data_file_is_loaded_by_the_manifest():
    """A data file left out of the manifest is never loaded (Company Roles were never created that way)."""
    listed = set(_manifest()["data"])
    on_disk = {
        path.relative_to(MODULE).as_posix() for path in (MODULE / "data").rglob("*") if path.suffix in {".xml", ".csv"}
    }
    assert on_disk - listed == set()


def test_company_role_tags_load_before_anything_else_in_the_module_data():
    data = _manifest()["data"]
    assert data.index("data/company_role_tag_data.xml") == data.index("security/ir.model.access.csv") + 1
    root = ET.parse(MODULE / "data/company_role_tag_data.xml").getroot()
    records = {record.get("id"): record.findtext("field[@name='code']") for record in root.iter("record")}
    assert records == {
        "company_role_buyer": "buyer",
        "company_role_supplier": "supplier",
        "company_role_service": "service",
        "company_role_carrier": "carrier",
    }
    assert {record.get("model") for record in root.iter("record")} == {"plasticos.company.role.tag"}


# ── Status group: VanillaSoft lead status + DNC, nothing else ───────────


def _status_records():
    root = ET.parse(MODULE / "data/partner_classification_data.xml").getroot()
    out = {}
    for data in root.iter("data"):
        for record in data.iter("record"):
            parent = record.find("field[@name='parent_id']")
            if parent is not None and parent.get("ref") == "partner_category_status":
                out[record.get("id")] = (record.findtext("field[@name='name']"), data.get("noupdate"))
    return root, out


def test_status_group_members_and_external_ids():
    root, records = _status_records()
    assert records == {
        "status_current": ("Current", "1"),
        "status_open": ("Open", "1"),
        "status_hot": ("Hot", "1"),
        "status_warm": ("Warm", "1"),
        "status_cold": ("Cold", "1"),
        "status_resist": ("Resist", "1"),
        "status_unqualified": ("Unqualified", "1"),
        "plasticos_base.tag_do_not_contact": ("DNC", "0"),
    }
    assert dict(CL.LEAD_STATUS_TAGS) == {xmlid: name for xmlid, (name, _nu) in records.items() if "." not in xmlid}
    # The binding runs before the Status records, so an existing same-name tag is reused.
    children = list(root)
    bind = next(i for i, node in enumerate(children) if node.get("name") == "_plasticos_bind_status_tags")
    first_status = next(i for i, node in enumerate(children) if node.find("record[@id='status_current']") is not None)
    assert bind < first_status


def test_retired_status_tags_appear_nowhere_in_the_module():
    retired = ("tag_needs_enrichment", "tag_key_account", "tag_preferred_carrier")
    for path in MODULE.rglob("*"):
        if path.is_file() and path.suffix in {".py", ".xml", ".csv", ".js"}:
            text = path.read_text(encoding="utf-8")
            for name in retired:
                assert name not in text, f"{name} referenced in {path.relative_to(ROOT)}"
    for name in ("Needs Enrichment", "Key Account", "Preferred Carrier"):
        assert name not in CL.STATUS_NAMES


def test_dnc_is_still_the_renamed_do_not_contact_tag():
    _root, records = _status_records()
    assert records["plasticos_base.tag_do_not_contact"] == ("DNC", "0")
    code = (MODULE / "models/res_partner_category.py").read_text(encoding="utf-8")
    assert 'DO_NOT_CONTACT_XMLID = "plasticos_base.tag_do_not_contact"' in code


def test_existing_same_name_status_tags_are_bound_not_duplicated():
    group = 50
    tags = [(3, "Hot", False), (4, "Hot", False), (9, "Cold", group), (10, "Cold", False), (12, "Open", 77)]
    plan = CL.bind_plan(tags, group, {"status_warm"}, CL.LEAD_STATUS_TAGS)
    # Oldest root "Hot"; the "Cold" already in the group; "Open" under another parent is left alone.
    assert plan == [("status_hot", 3), ("status_cold", 9)]
    assert CL.bind_plan(tags, group, {xmlid for xmlid, _name in CL.LEAD_STATUS_TAGS}, CL.LEAD_STATUS_TAGS) == []


def test_lead_status_mirrors_to_sites_but_dnc_stays_per_record():
    code = (MODULE / "models/res_partner_classification.py").read_text(encoding="utf-8")
    assert "lead_status = set(categories._plasticos_group_members(STATUS_XMLID).values()) - {" in code
    assert "mirrored_tag_ids(target, company_ids, lead_status)" in code
    arch = (MODULE / "views/partner_ux.xml").read_text(encoding="utf-8")
    assert "('category_id.parent_id.name', '=', 'Status')" in arch
