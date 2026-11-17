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


# ── Trade role badge from native ranks ──────────────────────────────────


@pytest.mark.parametrize(
    ("customer_rank", "supplier_rank", "current", "expected"),
    [
        (1, 0, False, "buyer"),
        (0, 3, False, "supplier"),
        (2, 5, False, "both"),
        (2, 5, "broker", "both"),
        (1, 0, "supplier", "buyer"),
        (0, 0, "carrier", "carrier"),
        (0, 0, "broker", "broker"),
        (0, 0, "other", "other"),
        (0, 0, "prospect", "prospect"),
        (0, 0, "buyer", False),
        (0, 0, "both", False),
        (None, None, None, False),
    ],
)
def test_trade_role_badge_follows_the_native_ranks(customer_rank, supplier_rank, current, expected):
    assert CL.trade_role(customer_rank, supplier_rank, current) == expected


def test_a_buyer_and_supplier_is_both_never_broker():
    assert CL.trade_role(1, 1, "broker") == "both"


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


def test_the_twelve_company_type_names_and_four_status_names():
    assert len(CL.COMPANY_TYPE_NAMES) == len(set(CL.COMPANY_TYPE_NAMES)) == 12
    assert set(CL.STATUS_NAMES) == {"Needs Enrichment", "Do Not Contact", "Key Account", "Preferred Carrier"}
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
    assert set(CL.STATUS_NAMES) <= base_names


# ── Wiring ──────────────────────────────────────────────────────────────


def _manifest():
    return ast.literal_eval((MODULE / "__manifest__.py").read_text(encoding="utf-8"))


def test_manifest_loads_the_classification_data_after_its_dependency():
    manifest = _manifest()
    assert "plasticos_base" in manifest["depends"]
    assert "data/partner_classification_data.xml" in manifest["data"]
    assert tuple(int(part) for part in manifest["version"].split(".")) > (19, 0, 5, 4, 17)
    assert (MODULE / "migrations" / manifest["version"] / "post-migrate.py").is_file()


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
        "plasticos_base.tag_needs_enrichment": "partner_category_status",
        "plasticos_base.tag_do_not_contact": "partner_category_status",
        "plasticos_base.tag_key_account": "partner_category_status",
        "plasticos_base.tag_preferred_carrier": "partner_category_status",
    }
    assert root.find(".//function[@name='_plasticos_ensure_company_type_tags']") is not None


def test_models_are_wired():
    init = (MODULE / "models/__init__.py").read_text(encoding="utf-8")
    for name in ("res_partner_category", "res_partner_trade_role", "res_partner_company_type_mirror"):
        assert f"from . import {name}\n" in init
    # The trade-role class must load after res_partner, which defines the field it extends.
    assert init.index("from . import res_partner\n") < init.index("from . import res_partner_trade_role\n")


def test_contacts_search_has_the_trade_role_filters_and_group_by():
    arch = (MODULE / "views/partner_ux.xml").read_text(encoding="utf-8")
    assert "[('customer_rank', '&gt;', 0), ('supplier_rank', '&gt;', 0)]" in arch
    assert "{'group_by': 'company_role'}" in arch
    assert "('category_id.parent_id.name', '=', 'Company Type')" in arch


def test_locations_list_has_a_contact_column():
    arch = (MODULE / "views/facility_profile_views.xml").read_text(encoding="utf-8")
    locations = arch[arch.index('name="location_child_ids"') :]
    locations = locations[: locations.index("</list>")]
    assert '<field name="contact_header_name" string="Contact"/>' in locations
