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
