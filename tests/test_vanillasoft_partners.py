"""VanillaSoft Company Type everywhere, and qualified records become partners (C1 F1 + C4).

Pure: the rule functions in ``plasticos_crm_sync/services/vanillasoft_partners.py``
and the orchestrator methods that apply them, run against small stand-ins for
the ORM. No Odoo runtime.
"""

from __future__ import annotations

import ast
import contextlib
import itertools
import sys
import types
from pathlib import Path

import pytest

from plasticos_crm_sync.adapters.base import CanonicalLead
from plasticos_crm_sync.services import vanillasoft_partners as vp
from plasticos_crm_sync.services.orchestrator import SyncOrchestrator

ROOT = Path(__file__).resolve().parents[1]
MAPPING = ROOT / "plasticos_crm_bridge" / "models" / "crm_mapping.py"

ALL_STATUSES = (
    "1= Currently Working With",
    "2=Qualified/Open",
    vp.STATUS_HOT,
    vp.STATUS_WARM,
    vp.STATUS_COLD,
    vp.STATUS_RESIST,
    "4=Unqualified",
    vp.STATUS_DEAD,
    vp.STATUS_WRONG_NUMBER,
    vp.STATUS_DO_NOT_CALL,
    vp.STATUS_DUPLICATE,
    "New",
)
BUYER_NO = {vp.STATUS_COLD, vp.STATUS_DEAD, vp.STATUS_WRONG_NUMBER, vp.STATUS_DO_NOT_CALL, vp.STATUS_DUPLICATE}
SUPPLIER_YES = {vp.STATUS_HOT, vp.STATUS_WARM, vp.STATUS_RESIST}


# ── The rule (D32/D33): every status × role combination ─────────────────────
@pytest.mark.parametrize(("status", "roles"), itertools.product(ALL_STATUSES, ("Buyer", "Buyer/Supplier")))
def test_buyer_becomes_a_partner_except_at_the_five_excluded_statuses(status, roles):
    allowed = vp.partner_allowed(status, vp.parse_roles(roles), approved=False)
    assert allowed is (status not in BUYER_NO)


@pytest.mark.parametrize(("status", "roles"), itertools.product(ALL_STATUSES, ("Supplier", "", "Unknown")))
def test_supplier_only_or_unspecified_needs_hot_warm_or_resist(status, roles):
    allowed = vp.partner_allowed(status, vp.parse_roles(roles), approved=False)
    assert allowed is (status in SUPPLIER_YES)


@pytest.mark.parametrize("status", ALL_STATUSES)
def test_approved_supplier_or_unspecified_is_a_partner_except_do_not_call(status):
    for roles in ("Supplier", ""):
        allowed = vp.partner_allowed(status, vp.parse_roles(roles), approved=True)
        assert allowed is (status != vp.STATUS_DO_NOT_CALL)


def test_role_parsing():
    assert vp.parse_roles("Buyer/Supplier") == {"Buyer", "Supplier"}
    assert vp.parse_roles("supplier; buyer") == {"Buyer", "Supplier"}
    assert vp.parse_roles("Supplier") == {"Supplier"}
    assert vp.parse_roles("Broker") == frozenset()
    assert vp.parse_roles(None) == frozenset()


def test_trade_ranks():
    assert vp.trade_ranks({"Buyer"}) == {"customer_rank": 1}
    assert vp.trade_ranks({"Supplier"}) == {"supplier_rank": 1}
    assert vp.trade_ranks(set()) == {}


@pytest.mark.parametrize(
    "name", ["Acme Plastics, Inc.", "ACME PLASTICS INC", "Acme Plastics L.L.C.", "acme  plastics", "Acme Plastics Co."]
)
def test_company_names_match_across_case_punctuation_and_suffix(name):
    assert vp.normalized_company_name(name) == "acme plastics"


def test_ampersand_and_and_match():
    assert vp.normalized_company_name("Smith & Sons") == vp.normalized_company_name("Smith and Sons")


def test_pick_existing_prefers_erp_and_refuses_ambiguity():
    assert vp.pick_existing({5}, {7}) == (5, "")
    assert vp.pick_existing(set(), {7}) == (7, "")
    assert vp.pick_existing(set(), set()) == (None, "")
    assert vp.pick_existing({5, 6}, set())[0] is None
    assert vp.pick_existing(set(), {7, 8})[0] is None


def test_company_type_is_read_from_the_recorded_paragraph():
    assert vp.company_type_from_text("<p>VanillaSoft Company Type: MRF</p><p>Other</p>") == "MRF"
    assert vp.company_type_from_text("<p>VanillaSoft ContactID 9 Company Type: Broker</p>") == "Broker"
    assert vp.company_type_from_text("<p>Company Type: MRF</p>") == ""
    assert vp.company_type_from_text(None) == ""


# ── Backfill: idempotent, with counts ────────────────────────────────────────
class _BackfillLead:
    def __init__(self, description, tag_ids=()):
        self.description = description
        self.tag_ids = list(tag_ids)


def test_backfill_sets_counts_and_is_idempotent():
    leads = [
        _BackfillLead("<p>VanillaSoft Company Type: MRF</p>"),
        _BackfillLead("<p>VanillaSoft Company Type: Broker</p>", tag_ids=[2]),
        _BackfillLead("<p>no source</p>"),
        _BackfillLead("<p>VanillaSoft Company Type: Space Station</p>"),
    ]
    tags = {"MRF": 1, "Broker": 2}

    def link(lead, tag_id):
        lead.tag_ids.append(tag_id)

    first = vp.backfill_company_type_tags(leads, tags.get, link)
    assert first == {"set": 1, "already_set": 1, "no_source_value": 1, "unmapped": 1}
    second = vp.backfill_company_type_tags(leads, tags.get, link)
    assert second == {"set": 0, "already_set": 2, "no_source_value": 1, "unmapped": 1}
    assert leads[0].tag_ids == [1]


# ── Mapping constants ────────────────────────────────────────────────────────
def _mapping(name):
    tree = ast.parse(MAPPING.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(name)


COMPANY_TYPES = (
    "Distribution Center",
    "Commercial Recycler",
    "Pallet Recycler",
    "Compounder",
    "Grinder/Processor",
    "E-Waste",
    "MRF",
    "Manufacturer",
    "Broker",
    "Carrier",
    "Exporter",
    "Toll Processor",
)


def test_twelve_company_types_on_crm_tags_and_partner_tags():
    crm = _mapping("CRM_COMPANY_TYPE_TAG_MAPPING")
    partner = _mapping("COMPANY_TYPE_MAPPING")
    assert tuple(crm) == COMPANY_TYPES
    assert set(partner) == set(COMPANY_TYPES)
    assert all(xmlid.startswith("plasticos_crm_bridge.crm_tag_company_type_") for xmlid in crm.values())
    assert partner["Exporter"] == "plasticos_base.tag_exporter"
    assert partner["Toll Processor"] == "plasticos_base.tag_toll_processor"
    data = (ROOT / "plasticos_crm_bridge" / "data" / "crm_tag_data.xml").read_text(encoding="utf-8")
    for name, xmlid in crm.items():
        assert f"<value>{name}</value>\n        <value>{xmlid}</value>" in data


# ── Orchestrator application, against ORM stand-ins ─────────────────────────
class _Set(list):
    """A tiny recordset: a list of records."""

    @property
    def ids(self):
        return [record.id for record in self]

    @property
    def id(self):
        return self[0].id if self else False

    def filtered(self, fn):
        return _Set(record for record in self if fn(record))

    def mapped(self, name):
        return [getattr(record, name) for record in self]

    def with_context(self, **_):
        return self

    def __bool__(self):
        return len(self) > 0

    def __contains__(self, record):
        return any(item.id == getattr(record, "id", None) for item in self)

    def __getattr__(self, name):
        # A one-record recordset answers field and method access like its record.
        if len(self) == 1:
            return getattr(self[0], name)
        raise AttributeError(name)


class _Partner:
    def __init__(self, env, pid, vals):
        self.env = env
        self.id = pid
        self.name = vals.get("name", "")
        self.is_company = vals.get("is_company", False)
        self.parent_id = vals.get("parent_id") or _Set()
        self.type = vals.get("type", "contact")
        self.email = vals.get("email", False)
        self.customer_rank = vals.get("customer_rank", 0)
        self.supplier_rank = vals.get("supplier_rank", 0)
        self.category_id = _Set()
        self.company_role_tag_ids = _Set()
        self.vals = vals

    @property
    def child_ids(self):
        return _Set(p for p in self.env.partners.values() if p.parent_id and p.parent_id.id == self.id)

    def with_context(self, **_):
        return self

    def __getitem__(self, name):
        return getattr(self, name)

    def __bool__(self):
        return True

    def _plasticos_is_site(self):
        return bool(self.parent_id) and (self.is_company or self.type in ("delivery", "invoice"))

    def _plasticos_site_company(self):
        if self.is_company and not self.parent_id:
            return self
        return self.parent_id[0]._plasticos_site_company() if self.parent_id else None

    def write(self, vals):
        for key, value in vals.items():
            if key in ("category_id", "company_role_tag_ids"):
                for command in value:
                    if command[0] == 6:
                        setattr(self, key, _Set(self.env.tags[tag_id] for tag_id in command[2]))
                    else:
                        getattr(self, key).append(self.env.tags[command[1]])
            else:
                setattr(self, key, value)


class _Partners:
    def __init__(self, env):
        self.env = env

    def with_context(self, **_):
        return self

    def browse(self, pid):
        return self.env.partners[pid]

    def search(self, domain):
        probe = next(value for field, _, value in domain if field == "name").casefold()
        return _Set(
            p for p in self.env.partners.values() if p.is_company and not p.parent_id and probe in p.name.casefold()
        )

    def create(self, vals):
        pid = max(self.env.partners, default=0) + 1
        parent = vals.get("parent_id")
        record = _Partner(self.env, pid, {**vals, "parent_id": _Set([self.env.partners[parent]]) if parent else _Set()})
        self.env.partners[pid] = record
        return record


class _ModelData:
    def __init__(self, env):
        self.env = env

    def sudo(self):
        return self

    def search(self, domain):
        ids = next(value for field, _, value in domain if field == "res_id")
        return _Set(types.SimpleNamespace(res_id=pid) for pid in ids if pid in self.env.erp_ids)


class _Blacklist:
    def __init__(self):
        self.entries = []

    def sudo(self):
        return self

    def _add(self, value, message=None):
        self.entries.append(value if isinstance(value, str) else tuple(value))


class _Lead:
    def __init__(self, env):
        self.env = env
        self.id = 77
        self.partner_id = _Set()
        self.email_from = "buyer@acme.test"
        self.phone = "732-202-9500"
        self.mobile = False
        self.tag_ids = _Set()

    def write(self, vals):
        if "partner_id" in vals:
            self.partner_id = _Set([self.env.partners[vals["partner_id"]]])


class _Env(dict):
    def __init__(self):
        super().__init__()
        self.partners = {}
        self.erp_ids = set()
        self.tags = {
            900: types.SimpleNamespace(id=900, _name="res.partner.category", name="DNC"),
            801: types.SimpleNamespace(id=801, _name="plasticos.company.role.tag", name="Buyer"),
            802: types.SimpleNamespace(id=802, _name="plasticos.company.role.tag", name="Supplier"),
        }
        self.refs = {
            "plasticos_base.tag_do_not_contact": 900,
            "plasticos_facility_profile.company_role_buyer": 801,
            "plasticos_facility_profile.company_role_supplier": 802,
        }
        self["res.partner"] = _Partners(self)
        self["ir.model.data"] = _ModelData(self)
        self["mail.blacklist"] = _Blacklist()
        self["phone.blacklist"] = _Blacklist()
        self.user = types.SimpleNamespace(
            _phone_format=lambda number: "+1" + "".join(c for c in number if c.isdigit())[-10:]
        )
        self.cr = types.SimpleNamespace(savepoint=contextlib.nullcontext)

    def ref(self, xmlid, raise_if_not_found=True):
        return self.tags.get(self.refs.get(xmlid))


class _Orch(SyncOrchestrator):
    def __init__(self, env):
        super().__init__(env)
        self.outcomes = None
        self.error_rows = []

    def _resolve_country_id(self, code):
        return False


@pytest.fixture
def harness(monkeypatch):
    mapping = types.ModuleType("odoo.addons.plasticos_crm_bridge.models.crm_mapping")
    mapping.DNC_PARTNER_TAG_XMLID = "plasticos_base.tag_do_not_contact"
    monkeypatch.setitem(sys.modules, mapping.__name__, mapping)
    env = _Env()
    return env, _Orch(env), _Lead(env)


def _dto(status, roles="Buyer", company="Acme Plastics", **extra):
    return CanonicalLead(
        provider="vanillasoft",
        external_id="vs-1",
        company=company,
        first_name="Ada",
        last_name="Byron",
        email="ada@acme.test",
        phone="732-202-9500",
        lead_status_raw=status,
        custom_fields={"Buyer/Supplier": roles},
        **extra,
    )


def test_qualified_buyer_creates_company_and_person_and_lead_keeps_pipeline(harness):
    env, orch, lead = harness
    orch._resolve_vanillasoft_partner_body(lead, _dto("4=Unqualified", "Buyer"))
    companies = [p for p in env.partners.values() if p.is_company]
    people = [p for p in env.partners.values() if not p.is_company]
    assert len(companies) == 1 and len(people) == 1
    company = companies[0]
    assert company.name == "Acme Plastics" and company.customer_rank == 1 and company.supplier_rank == 0
    assert people[0].parent_id[0] is company and people[0].name == "Ada Byron"
    assert lead.partner_id[0] is company  # the lead stays the pipeline record and points at the company


def test_existing_erp_company_is_linked_not_duplicated(harness):
    env, orch, lead = harness
    erp = env["res.partner"].create({"name": "ACME PLASTICS, INC.", "is_company": True})
    env["res.partner"].create({"name": "Acme Plastics", "is_company": True})  # a non-ERP namesake
    env.erp_ids.add(erp.id)
    orch._resolve_vanillasoft_partner_body(lead, _dto(vp.STATUS_HOT, "Supplier"))
    assert lead.partner_id[0] is erp
    assert len([p for p in env.partners.values() if p.is_company]) == 2
    assert erp.supplier_rank == 1


def test_ambiguous_match_creates_nothing(harness):
    env, orch, lead = harness
    for name in ("Acme Plastics Inc", "Acme Plastics LLC"):
        env["res.partner"].create({"name": name, "is_company": True})
    orch._resolve_vanillasoft_partner_body(lead, _dto(vp.STATUS_HOT, "Buyer"))
    assert not lead.partner_id
    assert len(env.partners) == 2
    assert any("BLOCKED_PARTNER_AMBIGUOUS" in row["message"] for row in orch.error_rows)


def test_existing_person_is_reused(harness):
    env, orch, lead = harness
    company = env["res.partner"].create({"name": "Acme Plastics", "is_company": True})
    env["res.partner"].create({"name": "Ada Byron", "parent_id": company.id})
    orch._resolve_vanillasoft_partner_body(lead, _dto(vp.STATUS_WARM, ""))
    assert len(env.partners) == 2


def test_unqualified_supplier_stays_a_lead(harness):
    env, orch, lead = harness
    orch._resolve_vanillasoft_partner_body(lead, _dto("4=Unqualified", "Supplier"))
    assert not env.partners and not lead.partner_id


def test_rank_is_raised_never_lowered(harness):
    env, orch, lead = harness
    company = env["res.partner"].create({"name": "Acme Plastics", "is_company": True, "supplier_rank": 7})
    orch._resolve_vanillasoft_partner_body(lead, _dto(vp.STATUS_HOT, "Supplier"))
    assert company.supplier_rank == 7


def test_do_not_call_on_an_existing_company_tags_and_blacklists(harness):
    env, orch, lead = harness
    company = env["res.partner"].create({"name": "Acme Plastics", "is_company": True})
    orch._resolve_vanillasoft_partner_body(lead, _dto(vp.STATUS_DO_NOT_CALL, "Buyer"))
    assert [tag.name for tag in company.category_id] == ["DNC"]
    assert set(env["mail.blacklist"].entries) == {"ada@acme.test", "buyer@acme.test"}
    assert env["phone.blacklist"].entries == [("+17322029500",)]
    assert not lead.partner_id  # Do Not Call never links or creates


def test_do_not_call_without_a_partner_does_nothing(harness):
    env, orch, lead = harness
    orch._resolve_vanillasoft_partner_body(lead, _dto(vp.STATUS_DO_NOT_CALL, "Buyer"))
    assert not env.partners
    assert env["mail.blacklist"].entries == [] and env["phone.blacklist"].entries == []


def test_company_type_lands_on_the_lead_crm_tags_without_a_partner(harness, monkeypatch):
    env, orch, lead = harness
    tag = types.SimpleNamespace(id=31, _name="crm.tag", name="MRF")
    links = []
    lead.write = lambda vals: links.append(vals)
    monkeypatch.setattr(orch, "_crm_role_tag", lambda name, mapping: tag if name == "MRF" else None)
    command = types.SimpleNamespace(link=lambda tag_id: ("link", tag_id))
    dto = _dto("4=Unqualified", "Supplier")
    orch._apply_lead_company_type(lead, dto, {"Company Type": "MRF"}, command, {"MRF": "x.y"}, {})
    assert links == [{"tag_ids": [("link", 31)]}]
    assert not lead.partner_id


def test_partner_company_type_goes_to_the_commercial_entity_not_a_site(harness):
    env, orch, lead = harness
    company = env["res.partner"].create({"name": "Acme Plastics", "is_company": True})
    site = env["res.partner"].create({"name": "Acme Plant", "is_company": True, "parent_id": company.id})
    lead.partner_id = _Set([site])
    from plasticos_crm_sync.services.orchestrator import _verified_company

    assert _verified_company(lead, None) is company


def test_approved_contact_raises_ranks_and_handles_dnc_on_its_erp_company(harness):
    env, orch, lead = harness
    company = env["res.partner"].create({"name": "ERP Co", "is_company": True})
    person = env["res.partner"].create({"name": "Ada Byron", "parent_id": company.id})
    lead.id = False  # approved contact bound to the ERP person only
    orch._apply_existing_partner_rules(lead, _dto("2c=Qualified/COLD", "Buyer"), person)
    assert company.customer_rank == 1
    orch._apply_existing_partner_rules(lead, _dto(vp.STATUS_DO_NOT_CALL, ""), person)
    assert [tag.name for tag in company.category_id] == ["DNC"]
    assert "ada@acme.test" in env["mail.blacklist"].entries


def test_approved_contact_without_role_or_dnc_writes_nothing(harness):
    env, orch, lead = harness
    company = env["res.partner"].create({"name": "ERP Co", "is_company": True})
    person = env["res.partner"].create({"name": "Ada Byron", "parent_id": company.id})
    orch._apply_existing_partner_rules(lead, _dto(vp.STATUS_HOT, ""), person)
    assert company.customer_rank == 0 and company.supplier_rank == 0 and not company.category_id


def test_company_roles_follow_the_ranks_for_gate_and_are_never_removed(harness):
    env, orch, lead = harness
    orch._resolve_vanillasoft_partner_body(lead, _dto(vp.STATUS_HOT, "Buyer/Supplier"))
    company = lead.partner_id[0]
    assert sorted(tag.name for tag in company.company_role_tag_ids) == ["Buyer", "Supplier"]
    orch._resolve_vanillasoft_partner_body(lead, _dto(vp.STATUS_HOT, "Buyer"))  # replay, fewer roles
    assert sorted(tag.name for tag in company.company_role_tag_ids) == ["Buyer", "Supplier"]


def test_company_role_tag_absent_is_skipped_quietly(harness):
    env, orch, lead = harness
    env.refs.pop("plasticos_facility_profile.company_role_supplier")
    orch._resolve_vanillasoft_partner_body(lead, _dto(vp.STATUS_HOT, "Supplier"))
    company = lead.partner_id[0]
    assert company.supplier_rank == 1 and not company.company_role_tag_ids
    assert not orch.error_rows


def test_company_role_xmlids():
    assert vp.COMPANY_ROLE_TAG_XMLIDS == {
        "Buyer": "plasticos_facility_profile.company_role_buyer",
        "Supplier": "plasticos_facility_profile.company_role_supplier",
    }


# ── Materials on the person's one linked site (case RDS of Virginia) ────────
class _Node:
    def __init__(self, pid, name, *, is_company=False, parent=None, site=False, facility=False):
        self.id = pid
        self.name = name
        self.is_company = is_company
        self.parent_id = _Set([parent]) if parent else _Set()
        self.is_facility = facility
        self._site = site
        self.location_partner_ids = _Set()
        self.child_ids = _Set()
        self.zip = self.city = self.street = ""
        self.display_name = name

    def _plasticos_is_site(self):
        return self._site


class _MaterialLead:
    def __init__(self, partner):
        self.id = 5
        self.vanillasoft_id = "vs-rds"
        self.partner_id = _Set([partner])


def _rds(site_count):
    company = _Node(1, "RDS of Virginia", is_company=True)
    person = _Node(2, "Todd Antonick", parent=company)
    sites = [_Node(10 + i, f"PORTSMOUTH, VA {i}", parent=company, site=True, facility=True) for i in range(site_count)]
    person.location_partner_ids = _Set(sites)
    return person, sites


@pytest.fixture
def materials(monkeypatch):
    env = _Env()
    env["plasticos.facility.profile"] = types.SimpleNamespace(search=lambda domain: _Set(), browse=lambda: _Set())
    orch = _Orch(env)
    calls = []
    monkeypatch.setattr(
        orch, "_import_section_materials", lambda lead, maps, partner, facility_profile: calls.append(partner)
    )
    return orch, calls


def test_person_with_one_linked_site_puts_all_three_materials_on_the_site(materials):
    orch, calls = materials
    person, sites = _rds(1)
    fields = {"Materials": "MRP,LDPE,PP Supersacs"}
    from plasticos_crm_sync.services.orchestrator import _parse_material_sections

    assert _parse_material_sections(fields)[""]["phrases"] == ["MRP", "LDPE", "PP Supersacs"]
    orch._apply_resolved_approved_materials(_MaterialLead(person), fields)
    # Every phrase of the call lands on the site, none on the person.
    assert [call.id for call in calls] == [sites[0].id]
    assert not orch.error_rows


def test_person_with_two_linked_sites_stores_nothing_and_reports_ambiguity(materials):
    orch, calls = materials
    person, _sites = _rds(2)
    orch._apply_resolved_approved_materials(_MaterialLead(person), {"Materials": "MRP,LDPE,PP Supersacs"})
    assert calls == []  # a material profile never lands on a person
    [row] = orch.error_rows
    assert row["message"].startswith("facility ambiguous: 2 linked sites: no address match")
    assert row["message"].endswith("materials: MRP, LDPE, PP Supersacs")
    assert (row["category"], row["error_type"]) == ("optional_context", "MATERIAL_PLACEMENT_REVIEW")


def test_person_with_two_sites_uses_the_one_whose_address_matches(materials):
    orch, calls = materials
    person, sites = _rds(2)
    sites[0].zip, sites[0].city, sites[0].street = "23701", "Portsmouth", "1 Dock Rd"
    sites[1].zip, sites[1].city, sites[1].street = "23502", "Norfolk", "9 Yard Ln"
    orch._apply_resolved_approved_materials(_MaterialLead(person), {"Materials": "MRP"}, address=("23502-1234", "", ""))
    assert [call.id for call in calls] == [sites[1].id]
    calls.clear()
    orch._apply_resolved_approved_materials(
        _MaterialLead(person), {"Materials": "MRP"}, address=("", "Portsmouth", "1 DOCK  rd")
    )
    assert [call.id for call in calls] == [sites[0].id]


def test_person_with_two_sites_and_no_matching_address_stores_nothing(materials):
    orch, calls = materials
    person, sites = _rds(2)
    for site in sites:
        site.zip, site.city, site.street = "11111", "Elsewhere", "2 Other St"
    orch._apply_resolved_approved_materials(_MaterialLead(person), {"Materials": "MRP"}, address=("23502", "", ""))
    assert calls == []
    assert orch.error_rows[0]["message"].startswith("facility ambiguous: 2 linked sites")


def test_person_whose_company_has_no_sites_stores_on_the_company(materials):
    orch, calls = materials
    person, _sites = _rds(0)
    orch._apply_resolved_approved_materials(_MaterialLead(person), {"Materials": "MRP"})
    assert [call.id for call in calls] == [person.parent_id[0].id]
    assert not orch.error_rows


def test_person_unlinked_whose_company_has_sites_stores_nothing(materials):
    orch, calls = materials
    person, _sites = _rds(0)
    company = person.parent_id[0]
    company.child_ids = _Set([_Node(30, "Plant", parent=company, site=True, facility=True)])
    orch._apply_resolved_approved_materials(_MaterialLead(person), {"Materials": "MRP"})
    assert calls == []
    assert orch.error_rows and orch.error_rows[0]["category"] == "required_mapping"


# ── Material Type / Material Form: one value applies to all, several are ignored ──
class _Lookup(_Set):
    def search(self, domain):
        return self


class _Profile:
    def __init__(self, phrase, form):
        self.phrase = phrase
        self.form = form
        self.source_type_id = None
        self.packaging_type_id = None


def _named(rid, name, code):
    return types.SimpleNamespace(id=rid, name=name, code=code)


@pytest.fixture
def typed(monkeypatch):
    env = _Env()
    post_consumer = _named(1, "Post-Consumer", "POST_CONSUMER")
    env["plasticos.source.type"] = _Lookup([post_consumer, _named(2, "Post-Industrial", "POST_INDUSTRIAL")])
    bales = _named(11, "Bales", "bales")
    env["plasticos.packaging.type"] = _Lookup([bales, _named(12, "Gaylords", "gaylords")])
    env["plasticos.material.form"] = _Lookup([_named(21, "Film", "FILM")])  # form_bale is archived: not active
    orch = _Orch(env)
    stored = []

    def store(
        lead,
        phrases,
        partner=None,
        facility_profile=None,
        structured=None,
        record_form=None,
        external_id=None,
        direction=None,
    ):
        made = [_Profile(phrase, record_form) for phrase in phrases]
        stored.extend(made)
        return made

    monkeypatch.setattr(orch, "_store_normalized_materials", store)
    monkeypatch.setattr(orch, "_profiles_for_material", lambda partner, facility_profile: _Set())
    monkeypatch.setattr(orch, "_apply_section_specs", lambda *args: None)
    return orch, stored, post_consumer, bales


def test_one_type_and_bales_apply_to_every_profile_and_bales_is_packaging(typed):
    orch, stored, post_consumer, bales = typed
    fields = {"Materials": "MRP, LDPE, PP Supersacs", "Material Type": "Post Consumer", "Material Form": "Bales"}
    orch._import_section_materials(None, (fields,), partner=object(), external_id="VS-RDS")
    assert [profile.phrase for profile in stored] == ["MRP", "LDPE", "PP Supersacs"]
    assert all(profile.source_type_id.id == post_consumer.id for profile in stored)
    assert all(profile.packaging_type_id.id == bales.id for profile in stored)
    assert all(profile.form is None for profile in stored)  # Bales never becomes a form
    assert orch.error_rows == []


def test_two_type_values_are_ignored_and_reported_packaging_still_applies(typed):
    orch, stored, _post_consumer, bales = typed
    fields = {
        "Materials": "MRP, HDPE, PET, PP",
        "Material Type": "Post Consumer, Post Industrial",
        "Material Form": "Bales",
    }
    orch._import_section_materials(None, (fields,), partner=object(), external_id="VS-4")
    assert len(stored) == 4
    assert all(profile.source_type_id is None for profile in stored)
    assert all(profile.packaging_type_id.id == bales.id for profile in stored)
    assert [(row["message"], row["category"]) for row in orch.error_rows] == [
        ("Material Type ignored: 2 values", "optional_context")
    ]


def test_one_real_form_is_the_record_form(typed):
    orch, stored, _post_consumer, _bales = typed
    orch._import_section_materials(None, ({"Materials": "MRP, LDPE", "Material Form": "Film"},), partner=object())
    assert [profile.form.code for profile in stored] == ["FILM", "FILM"]


def test_a_stored_source_is_kept(typed, monkeypatch):
    orch, _stored, _post_consumer, _bales = typed
    kept = types.SimpleNamespace(id=99, code="PRIME")
    profile = _Profile("MRP", None)
    profile.source_type_id = kept
    monkeypatch.setattr(orch, "_store_normalized_materials", lambda *args, **kwargs: [profile])
    orch._import_section_materials(None, ({"Materials": "MRP", "Material Type": "Post Consumer"},), partner=object())
    assert profile.source_type_id is kept


def test_unknown_type_is_reported_and_not_guessed(typed):
    orch, stored, _post_consumer, _bales = typed
    orch._import_section_materials(
        None, ({"Materials": "MRP", "Material Type": "PE"},), partner=object(), external_id="X"
    )
    assert stored[0].source_type_id is None
    assert orch.error_rows[0]["message"] == "Material Type unresolved: PE"


def test_parser_keeps_type_and_form_apart():
    from plasticos_crm_sync.services.orchestrator import _parse_material_sections

    slot = _parse_material_sections({"Materials": "MRP", "Material Type": "Post Consumer", "Material Form": "Bales"})[
        ""
    ]
    assert slot["types"] == ["Post Consumer"] and slot["forms"] == ["Bales"]
    assert "hints" not in slot


# ── ADR-132: unplaced materials are loud and reviewable ─────────────────────
class _Activity:
    def __init__(self, store, aid, summary, note, user_id):
        self.store, self.id, self.summary, self.note, self.user_id, self.done = (
            store,
            aid,
            summary,
            note,
            user_id,
            False,
        )

    def write(self, vals):
        for key, value in vals.items():
            setattr(self, key, value)


class _Activities(_Set):
    def unlink(self):
        for activity in self:
            activity.store.remove(activity)

    def action_feedback(self, feedback=False):
        for activity in self:
            activity.done = True
            activity.store.remove(activity)  # a done activity leaves the open list

    def __getitem__(self, key):
        result = list.__getitem__(self, key)
        return _Activities(result) if isinstance(key, slice) else result


class _ActivityModel:
    def __init__(self):
        self.open = []
        self.closed = []

    def search(self, domain):
        return _Activities(self.open)


class _ReviewLead(_MaterialLead):
    def __init__(self, partner, store):
        super().__init__(partner)
        self.user_id = types.SimpleNamespace(id=7)
        self.store = store

    def activity_schedule(self, act_type_xmlid="", summary="", note="", **values):
        self.store.open.append(_Activity(self.store.open, len(self.store.open) + 1, summary, note, values["user_id"]))


@pytest.fixture
def review(monkeypatch):
    env = _Env()
    env["plasticos.facility.profile"] = types.SimpleNamespace(search=lambda domain: _Set(), browse=lambda: _Set())
    env["mail.activity"] = _ActivityModel()
    orch = _Orch(env)
    calls = []
    monkeypatch.setattr(
        orch, "_import_section_materials", lambda lead, maps, partner, facility_profile: calls.append(partner)
    )
    return env, orch, calls


def _two_site_person():
    person, sites = _rds(2)
    for site, (zip_code, city) in zip(sites, (("11111", "Alpha"), ("22222", "Beta")), strict=True):
        site.zip, site.city, site.street, site.display_name = zip_code, city, "1 Main St", f"Site {city}"
    return person, sites


def test_ambiguous_placement_gives_one_review_row_one_banner_line_and_one_activity(review):
    from plasticos_crm_sync.services.import_summary import review_report_lines

    env, orch, calls = review
    person, sites = _two_site_person()
    lead = _ReviewLead(person, env["mail.activity"])
    fields = {"Materials": "MRP, LDPE"}
    orch._apply_resolved_approved_materials(lead, fields, address=("33333", "Gamma", ""))
    assert calls == []
    assert len(orch.placement_review) == 1
    row = orch.placement_review[0]
    assert row["candidate_site_ids"] == [site.id for site in sites]
    assert row["candidate_site_cities"] == ["Alpha", "Beta"]
    assert (row["source_zip"], row["source_city"], row["reason"]) == ("33333", "Gamma", "no address match")
    assert row["phrases"] == ["MRP", "LDPE"]
    assert [r["error_type"] for r in orch.error_rows] == ["MATERIAL_PLACEMENT_REVIEW"]
    assert [r["category"] for r in orch.error_rows] == ["optional_context"]
    summary = {"errors": orch.error_rows}
    lines = review_report_lines(summary)
    assert lines[0].startswith("=== NEEDS REVIEW: 1 VanillaSoft records have materials that were NOT placed")
    assert "MRP, LDPE" in lines[1]
    assert len(env["mail.activity"].open) == 1
    activity = env["mail.activity"].open[0]
    assert activity.summary == "Place materials: 2 candidate sites" and activity.user_id == 7
    assert "MRP, LDPE" in activity.note and "Site Alpha" in activity.note

    orch._apply_resolved_approved_materials(lead, fields, address=("33333", "Gamma", ""))  # replay
    assert len(env["mail.activity"].open) == 1


def test_a_later_placement_closes_the_activity(review):
    env, orch, calls = review
    person, sites = _two_site_person()
    lead = _ReviewLead(person, env["mail.activity"])
    orch._apply_resolved_approved_materials(lead, {"Materials": "MRP"}, address=("33333", "", ""))
    assert len(env["mail.activity"].open) == 1
    orch._apply_resolved_approved_materials(lead, {"Materials": "MRP"}, address=("22222", "", ""))
    assert [call.id for call in calls] == [sites[1].id]
    assert env["mail.activity"].open == []


def test_review_sections_are_always_printed_even_with_zero():
    from plasticos_crm_sync.services.import_summary import review_report_lines

    lines = review_report_lines({"errors": []})
    assert lines[0].startswith("=== NEEDS REVIEW: 0 VanillaSoft records")
    assert lines[1].startswith("=== NEEDS REVIEW: 0 Material Type/Form fields ignored")


def test_review_rows_neither_fail_the_run_nor_break_the_balance():
    from plasticos_crm_sync.services.import_summary import build_run_summary

    run = types.SimpleNamespace(
        status="done",
        contacts_seen=3,
        calls_seen=0,
        orphans_buffered=0,
        contacts_duplicate_rejected=0,
        contacts_failed=0,
        calls_failed=0,
        contacts_created=2,
        calls_created=0,
        contacts_updated=1,
        calls_updated=0,
        contacts_unchanged=0,
        calls_unchanged=0,
    )
    rows = [
        {"record_ref": "a", "message": "x", "category": "optional_context", "error_type": "MATERIAL_PLACEMENT_REVIEW"},
        {"record_ref": "b", "message": "y", "category": "optional_context", "error_type": "MATERIAL_FIELD_IGNORED"},
    ]
    summary = build_run_summary(run, error_rows=rows)
    assert summary["final_status"] == "success"
    seen = summary["records_seen"]
    assert (
        seen
        == summary["records_created"]
        + summary["records_updated"]
        + summary["records_unchanged"]
        + summary["records_rejected"]
    )
    assert [row["error_type"] for row in summary["errors"]] == ["MATERIAL_PLACEMENT_REVIEW", "MATERIAL_FIELD_IGNORED"]


def test_ignored_type_is_a_review_row(typed):
    orch, _stored, _post_consumer, _bales = typed
    fields = {"Materials": "MRP, HDPE, PET, PP", "Material Type": "Post Consumer, Post Industrial"}
    orch._import_section_materials(None, (fields,), partner=object(), external_id="VS-4")
    assert [row["error_type"] for row in orch.error_rows] == ["MATERIAL_FIELD_IGNORED"]


# ── Lead Status -> one Status tag (ADR-133 "Status") ──────────────────────────
STATUS_TAGS = {
    "status_current": (701, "Current"),
    "status_open": (702, "Open"),
    "status_hot": (703, "Hot"),
    "status_warm": (704, "Warm"),
    "status_cold": (705, "Cold"),
    "status_resist": (706, "Resist"),
    "status_unqualified": (707, "Unqualified"),
}
OTHER_TAG = 950  # a tag of another group (an ERP Contact Role, say): never touched


@pytest.fixture
def status_harness(harness):
    env, orch, lead = harness
    for xmlid, (tag_id, name) in STATUS_TAGS.items():
        env.tags[tag_id] = types.SimpleNamespace(id=tag_id, _name="res.partner.category", name=name)
        env.refs[f"plasticos_facility_profile.{xmlid}"] = tag_id
    env.tags[OTHER_TAG] = types.SimpleNamespace(id=OTHER_TAG, _name="res.partner.category", name="Broker Contact")
    return env, orch, lead


def _status_names(partner):
    return sorted(tag.name for tag in partner.category_id)


@pytest.mark.parametrize(
    ("status", "tag"),
    [
        ("1= Currently Working With", "Current"),
        ("2=Qualified/Open", "Open"),
        (vp.STATUS_HOT, "Hot"),
        (vp.STATUS_WARM, "Warm"),
        (vp.STATUS_COLD, "Cold"),
        (vp.STATUS_RESIST, "Resist"),
        ("4=Unqualified", "Unqualified"),
        (vp.STATUS_DO_NOT_CALL, "DNC"),
    ],
)
def test_each_lead_status_writes_its_one_status_tag_on_an_existing_company(status_harness, status, tag):
    env, orch, lead = status_harness
    company = env["res.partner"].create({"name": "Acme Plastics", "is_company": True})
    orch._resolve_vanillasoft_partner_body(lead, _dto(status, "Buyer"))
    assert _status_names(company) == [tag]


def test_status_codes_and_mapping_cover_the_seven_tags():
    assert vp.lead_status_code("2a=Qualified/HOT") == "2a"
    assert vp.lead_status_code("1= Currently Working With") == "1"
    assert vp.lead_status_code("New") == ""
    assert sorted(x.split(".", 1)[1] for x in vp.LEAD_STATUS_TAG_XMLIDS.values()) == sorted(STATUS_TAGS)
    assert not vp.status_acts("") and vp.status_acts("5") and vp.status_acts("7") and vp.status_acts("2c")


def test_a_new_status_replaces_the_old_one_and_keeps_other_tags(status_harness):
    env, orch, lead = status_harness
    company = env["res.partner"].create({"name": "Acme Plastics", "is_company": True})
    company.category_id = _Set([env.tags[OTHER_TAG], env.tags[703]])  # Broker Contact + Hot
    orch._apply_lead_status_tag(company, _dto(vp.STATUS_COLD))
    assert _status_names(company) == ["Broker Contact", "Cold"]


def test_dnc_is_sticky_and_no_status_is_added_while_it_is_present(status_harness):
    env, orch, lead = status_harness
    company = env["res.partner"].create({"name": "Acme Plastics", "is_company": True})
    company.category_id = _Set([env.tags[704]])  # Warm
    orch._resolve_vanillasoft_partner_body(lead, _dto(vp.STATUS_DO_NOT_CALL, "Buyer"))
    assert _status_names(company) == ["DNC"]  # one Status tag at a time
    later = _Orch(env)  # a later run: no precedence carried over
    later._resolve_vanillasoft_partner_body(lead, _dto(vp.STATUS_HOT, "Buyer"))
    later._apply_lead_status_tag(company, _dto(vp.STATUS_DEAD))
    assert _status_names(company) == ["DNC"]


@pytest.mark.parametrize("status", [vp.STATUS_DEAD, vp.STATUS_WRONG_NUMBER, vp.STATUS_DUPLICATE])
def test_dead_wrong_number_and_duplicate_clear_the_status_and_set_nothing(status_harness, status):
    env, orch, lead = status_harness
    company = env["res.partner"].create({"name": "Acme Plastics", "is_company": True})
    company.category_id = _Set([env.tags[OTHER_TAG], env.tags[703]])
    orch._resolve_vanillasoft_partner_body(lead, _dto(status, "Buyer"))
    assert _status_names(company) == ["Broker Contact"]
    assert not lead.partner_id  # still no partner link


def test_dead_never_clears_dnc(status_harness):
    env, orch, lead = status_harness
    company = env["res.partner"].create({"name": "Acme Plastics", "is_company": True})
    company.category_id = _Set([env.tags[900]])
    orch._apply_lead_status_tag(company, _dto(vp.STATUS_DEAD))
    assert _status_names(company) == ["DNC"]


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ((vp.STATUS_COLD, vp.STATUS_HOT), "Hot"),
        ((vp.STATUS_HOT, vp.STATUS_COLD), "Hot"),
        (("1= Currently Working With", vp.STATUS_HOT), "Current"),
        ((vp.STATUS_WARM, vp.STATUS_RESIST), "Warm"),
        ((vp.STATUS_RESIST, "2=Qualified/Open"), "Resist"),
        (("2=Qualified/Open", "4=Unqualified"), "Open"),
        (("4=Unqualified", vp.STATUS_COLD), "Unqualified"),
        ((vp.STATUS_HOT, vp.STATUS_DEAD), "Hot"),
        ((vp.STATUS_DEAD, vp.STATUS_WARM), "Warm"),
        (("1= Currently Working With", vp.STATUS_DO_NOT_CALL), "DNC"),
    ],
)
def test_most_advanced_status_of_one_run_wins(status_harness, statuses, expected):
    env, orch, lead = status_harness
    company = env["res.partner"].create({"name": "Acme Plastics", "is_company": True})
    for status in statuses:
        orch._apply_lead_status_tag(company, _dto(status))
    assert _status_names(company) == [expected]


def test_precedence_order():
    order = ["1", "2a", "2b", "3", "2", "4", "2c"]
    for stronger, weaker in itertools.pairwise(order):
        assert vp.stronger_status(weaker, stronger) == stronger
        assert vp.stronger_status(stronger, weaker) == stronger
    assert vp.stronger_status("2c", "7") == "7" and vp.stronger_status("7", "1") == "7"
    assert vp.stronger_status("5", "2c") == "2c"


def test_erp_partner_matched_by_a_cold_lead_gets_cold_and_no_new_partner(status_harness):
    env, orch, lead = status_harness
    erp = env["res.partner"].create({"name": "ACME PLASTICS, INC.", "is_company": True})
    env.erp_ids.add(erp.id)
    orch._resolve_vanillasoft_partner_body(lead, _dto(vp.STATUS_COLD, "Supplier"))
    assert _status_names(erp) == ["Cold"]
    assert len(env.partners) == 1 and not lead.partner_id  # COLD creates and links nothing


def test_cold_without_a_partner_creates_nothing(status_harness):
    env, orch, lead = status_harness
    orch._resolve_vanillasoft_partner_body(lead, _dto(vp.STATUS_COLD, "Buyer"))
    assert not env.partners and not lead.partner_id


def test_created_company_gets_its_status(status_harness):
    env, orch, lead = status_harness
    orch._resolve_vanillasoft_partner_body(lead, _dto(vp.STATUS_HOT, "Supplier"))
    assert _status_names(lead.partner_id[0]) == ["Hot"]


def test_status_goes_to_the_commercial_company_not_the_site_or_person(status_harness):
    env, orch, lead = status_harness
    company = env["res.partner"].create({"name": "Acme Plastics", "is_company": True})
    site = env["res.partner"].create({"name": "Acme Plant", "is_company": True, "parent_id": company.id})
    lead.partner_id = _Set([site])
    orch._resolve_vanillasoft_partner_body(lead, _dto(vp.STATUS_WARM, "Buyer"))
    assert _status_names(company) == ["Warm"] and not site.category_id  # the facility mirror owns the sites


def test_approved_contact_status_lands_on_its_erp_company(status_harness):
    env, orch, lead = status_harness
    company = env["res.partner"].create({"name": "ERP Co", "is_company": True})
    person = env["res.partner"].create({"name": "Ada Byron", "parent_id": company.id})
    lead.id = False
    orch._apply_existing_partner_rules(lead, _dto("1= Currently Working With", ""), person)
    assert _status_names(company) == ["Current"] and not person.category_id


def test_new_status_changes_nothing(status_harness):
    env, orch, lead = status_harness
    company = env["res.partner"].create({"name": "Acme Plastics", "is_company": True})
    company.category_id = _Set([env.tags[704]])
    orch._apply_lead_status_tag(company, _dto("New"))
    assert _status_names(company) == ["Warm"]
