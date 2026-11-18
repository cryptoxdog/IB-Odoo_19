"""ERP contact identity (campaign C1, lane A): one real human, one ``res.partner``.

The contact, role and counterparty stages of ``plasticos.erp.import`` run
unmodified against the in-memory ORM of ``test_erp_import_contract``. Every
name, number, address and mailbox here is synthetic.

Rules under test (``docs/erp_import_mapping.md`` §5):

* R1 weak name: blank, one word, a role word, or an e-mail prefix.
* R2 fold: a weak row joins the one full-name person of its company whose
  phone digits or external email match it. A plain first name only checks
  persons with that first word.
* R3 never: two full names never merge; zero, several, or conflicting
  candidates do not fold and are reported.
* Email: internal mailboxes dropped, entries split, shape-checked,
  lower-cased, de-duplicated, joined with ``", "``.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest
from erp import mapping
from erp.report import ImportReport
from erp.summary import import_run_summary

from tests import test_erp_import_contract as contract

ROOT_SHELL = Path(__file__).resolve().parents[1] / "plasticos_partner_import" / "scripts" / "import_erp_shell.py"
_TAG_IDS = {"Decision Maker": 901, "AR/AP": 902, "Logistics": 903, "Admin": 904}
_TAG_NAMES = {value: key for key, value in _TAG_IDS.items()}


class _TaggedPartner(contract._Partner):
    def __init__(self, rec_id, vals, registry=None):
        self.registry = registry
        self.category_id = types.SimpleNamespace(ids=[])
        self.function = False
        super().__init__(rec_id, vals)

    # parent_id and child_ids read as records, as under Odoo; parent_id is written as an id.
    @property
    def parent_id(self):
        parent = self.registry.rows.get(self._parent_ref) if self.registry and self._parent_ref else None
        return parent or contract._Empty()

    @parent_id.setter
    def parent_id(self, value):
        self._parent_ref = getattr(value, "id", value) or False

    @property
    def child_ids(self):
        return [row for row in self.registry.rows.values() if row._parent_ref == self.id]

    def _apply(self, vals):
        vals = dict(vals)
        commands = vals.pop("category_id", None)
        if commands:
            ids = list(self.category_id.ids)
            for _cmd, tag_id in commands:
                if tag_id not in ids:
                    ids.append(tag_id)
            self.category_id = types.SimpleNamespace(ids=ids)
        sites = vals.get("location_partner_ids")
        if sites and sites[0][0] == 4:  # add-one-link commands; (6, 0, ids) is handled by the base fake
            vals.pop("location_partner_ids")
            ids = list(self.location_partner_ids.ids)
            ids.extend(site_id for _cmd, site_id in sites if site_id not in ids)
            self.location_partner_ids = types.SimpleNamespace(ids=ids)
        super()._apply(vals)

    def tags(self):
        return {_TAG_NAMES[tag_id] for tag_id in self.category_id.ids}


class _TaggedPartnerModel(contract._PartnerModel):
    def create(self, vals):
        record = _TaggedPartner(len(self.rows) + 1, vals, registry=self)
        record._model = self
        self.rows[record.id] = record
        return record


class _Row(types.SimpleNamespace):
    """One record of a stand-in model: ``partner_id`` and the material keys are ids."""

    def __getattr__(self, name):
        if name.endswith("_id"):  # an unset many2one reads as an empty record
            return types.SimpleNamespace(id=False)
        raise AttributeError(name)


class _Rows(list):
    def __init__(self, items=(), model=None):
        super().__init__(items)
        self.model = model

    def __or__(self, other):
        other = [other] if isinstance(other, _Row) else other  # Odoo iterates as one-record sets
        return _Rows([*self, *(row for row in other if row not in self)], self.model)

    def write(self, vals):
        for row in self:
            for key, value in vals.items():
                setattr(row, key, types.SimpleNamespace(id=value) if key.endswith("_id") else value)
        self.model.writes.append((len(self), dict(vals)))


class _Model:
    """A stand-in model searched by ``(field, '=', id)`` on many2one ids."""

    def __init__(self):
        self.rows: list[_Row] = []
        self.writes: list = []

    def with_context(self, **_ctx):
        return self

    def browse(self):
        return _Rows((), self)

    def add(self, **values):
        row = _Row(id=len(self.rows) + 1, **{k: types.SimpleNamespace(id=v) for k, v in values.items()})
        self.rows.append(row)
        return row

    def search(self, domain, limit=None):
        hits = [row for row in self.rows if all(getattr(row, f).id == v for f, _op, v in domain)]
        return _Rows(hits[:limit] if limit else hits, self)

    def on(self, partner):
        return [row.id for row in self.rows if row.partner_id.id == partner.id]


class _Params:
    def set_param(self, _key, _value):
        return True


class _World:
    """One company, its sites and its markers, reusable across runs."""

    def __init__(self, sites=(), earlier=None):
        self.module = contract._load_contact_service()
        self.partners = _TaggedPartnerModel()
        self.markers = contract._MarkerModel()
        self.company = self.partners.create({"name": "Synthetic Co", "is_company": True})
        self.leads, self.materials, self.facilities = _Model(), _Model(), _Model()
        self.site_ids: dict[str, int] = {}
        for label in sites:
            site = self.partners.create({"name": label, "parent_id": self.company.id, "is_company": True})
            self.site_ids[label] = site.id
        for name, ct_ids in (earlier or {}).items():
            person = self.partners.create({"name": name, "parent_id": self.company.id})
            for ct_id in ct_ids:
                self._marker(f"legacy_erp_contact_{ct_id}", person.id)

    def _marker(self, name, res_id):
        self.markers.create(
            {
                "module": self.module.XMLID_MODULE,
                "name": name,
                "model": "res.partner",
                "res_id": res_id,
                "noupdate": True,
            }
        )

    def service(self):
        service = self.module.PlasticosErpImport()
        service.env = contract._ContactEnv(
            {
                "res.partner": self.partners,
                "ir.model.data": self.markers,
                "ir.config_parameter": _Params(),
                "crm.lead": self.leads,
                "plasticos.material.profile": self.materials,
                "plasticos.facility.profile": self.facilities,
            }
        )
        catalog = [("C1", f"A{index}", label, pid) for index, (label, pid) in enumerate(self.site_ids.items())]
        service._address_catalog = lambda: catalog
        service._role_tag_id = lambda role, _cache, _report: _TAG_IDS[role]
        return service

    def run(self, rows, roles=None):
        contacts = {str(row["CT_ID"]): {"CpID": "C1", "Location": "", "Notes": "", **row} for row in rows}
        role_rows = {}
        roles_by_contact = {}
        for ct_id, names in (roles or {}).items():
            for position, role in enumerate(names):
                role_id = f"R{ct_id}-{position}"
                role_rows[role_id] = {"RoleNm": role}
                roles_by_contact.setdefault(ct_id, []).append(role_id)
        index = types.SimpleNamespace(
            contacts=contacts,
            contacts_by_cp={"C1": list(contacts)},
            roles_by_contact=roles_by_contact,
            contact_roles=role_rows,
            addresses={},
            addresses_by_cp={},
            omitted_contact_ids=set(),
        )
        report = ImportReport()
        report.source_counts = {"Contact": len(contacts), "ContactRoleAssignment": len(role_rows)}
        service = self.service()
        service._import_contacts(index, report, {"C1": self.company.id}, dry_run=False)
        service._import_roles(index, report, dry_run=False)
        return report

    def people(self, active=True):
        return [p for p in self.partners.rows.values() if not p.is_company and p.active is active]

    def resolve(self, ct_id):
        marker = self.markers.search([("name", "=", f"legacy_erp_contact_{ct_id}")], limit=1)
        return self.partners.rows.get(marker.res_id) if marker else None

    def anomalies(self, report, detail):
        return sorted(row["key"] for row in report.anomalies if row["detail"].startswith(detail))


def _row(ct_id, name, **extra):
    return {"CT_ID": ct_id, "ContactNm": name, "IsActive": "Y", **extra}


DANA_PHONE = "704-555-0101"
DANA_EMAIL = "dana@skyco.test"


def _sky_rows():
    rows = [
        _row(
            str(100 + n),
            "Dana Sky",
            PhoneBusiness=DANA_PHONE,
            Email=DANA_EMAIL,
            Location="Site A" if n < 4 else "Site B",
        )
        for n in range(1, 8)
    ]
    rows.append(_row("108", "Dana", PhoneBusiness=DANA_PHONE, Email=DANA_EMAIL, Location="Site C"))
    rows.append(_row("109", "BILLING", Email=DANA_EMAIL))
    rows.append(_row("110", "Lee Rivers", PhoneBusiness="704-555-0199", Email="lee@skyco.test", Location="Site D"))
    return rows


SKY_ROLES = {"101": ["Primary"], "102": ["Collections"], "109": ["Billing"]}
SKY_SITES = ("Site A", "Site B", "Site C", "Site D")


# 1 ------------------------------------------------------------------------
def test_sky_shape_folds_weak_rows_into_one_person_with_all_roles_and_sites():
    world = _World(sites=SKY_SITES)
    report = world.run(_sky_rows(), roles=SKY_ROLES)
    people = world.people()
    assert sorted(p.name for p in people) == ["Dana Sky", "Lee Rivers"]
    dana = next(p for p in people if p.name == "Dana Sky")
    lee = next(p for p in people if p.name == "Lee Rivers")
    assert dana.tags() == {"Decision Maker", "AR/AP"}
    assert dana.function == "Decision Maker"
    assert set(dana.location_partner_ids.ids) == {world.site_ids[s] for s in ("Site A", "Site B", "Site C")}
    assert lee.location_partner_ids.ids == [world.site_ids["Site D"]]
    for ct_id in range(101, 110):
        assert world.resolve(ct_id) is dana, ct_id
    assert world.resolve("110") is lee
    assert world.markers.names().count("legacy_erp_contact_101") == 1
    assert report.counts["contacts"]["rejected"] == 0


# 2 ------------------------------------------------------------------------
def test_a_role_mailbox_is_no_person_and_its_address_joins_the_company():
    # Brief test 2 superseded by the operator decision of 2026-11-17: a function
    # mailbox never becomes a person. ``AP`` with ``ap@`` is an accounting mailbox.
    world = _World()
    world.run(
        [
            _row("201", "Dana Sky", PhoneBusiness=DANA_PHONE, Email=DANA_EMAIL),
            _row("202", "AP", PhoneBusiness="704-555-0202", Email="ap@skyco.test"),
        ]
    )
    assert [p.name for p in world.people()] == ["Dana Sky"]
    assert world.resolve("202") is None
    assert world.company.email == f"{DANA_EMAIL}, ap@skyco.test", "appended, the existing address kept first"
    assert world.company.phone == DANA_PHONE, "the mailbox's number never reaches the company"


# 3 ------------------------------------------------------------------------
def test_an_email_prefix_row_folds_into_a_multi_person_card_and_adds_its_site():
    world = _World(sites=("Site A", "Site B"))
    world.run(
        [
            _row("301", "Kim Ek & Ray Ek", PhoneBusiness="555-010-0301", Email="kimray@ekco.test", Location="Site A"),
            _row("302", "kimray", Email="kimray@ekco.test", Location="Site B"),
        ]
    )
    (card,) = world.people()
    assert card.name == "Kim Ek & Ray Ek", "a multi-person title is one full-name person, never split"
    assert set(card.location_partner_ids.ids) == set(world.site_ids.values())
    assert world.resolve("302") is card


# 4 ------------------------------------------------------------------------
def test_an_email_prefix_row_matching_nobody_is_its_own_title_cased_card():
    world = _World()
    report = world.run(
        [
            _row("401", "Dana Sky", PhoneBusiness=DANA_PHONE, Email=DANA_EMAIL),
            _row("402", "todd.antonick", Email="todd.antonick@cust.test"),
        ]
    )
    assert sorted(p.name for p in world.people()) == ["Dana Sky", "Todd Antonick"]
    assert world.anomalies(report, "alias ambiguous") == ["402"]


# 5 / 6 --------------------------------------------------------------------
@pytest.mark.parametrize(
    "shared",
    [{"PhoneBusiness": "704-555-0500"}, {"Email": "office@skyco.test"}],
    ids=["shared-phone", "shared-email"],
)
def test_two_full_names_sharing_a_channel_stay_two_people(shared):
    world = _World()
    world.run([_row("501", "Pat Doe", **shared), _row("502", "Lee Roe", **shared)])
    assert sorted(p.name for p in world.people()) == ["Lee Roe", "Pat Doe"]
    assert world.resolve("501") is not world.resolve("502")


# 7 ------------------------------------------------------------------------
def test_an_ambiguous_first_name_does_not_fold_and_is_reported():
    world = _World()
    report = world.run(
        [
            _row("701", "Pat Doe", PhoneBusiness="704-555-0700"),
            _row("702", "Pat Roe", PhoneBusiness="704-555-0700"),
            _row("703", "Pat", PhoneBusiness="704-555-0700"),
        ]
    )
    assert sorted(p.name for p in world.people()) == ["Pat", "Pat Doe", "Pat Roe"]
    assert world.anomalies(report, "alias ambiguous") == ["703"]


# 8 ------------------------------------------------------------------------
def test_phone_to_one_person_and_email_to_another_is_a_conflict():
    world = _World()
    report = world.run(
        [
            _row("801", "Pat Doe", PhoneBusiness="704-555-0801"),
            _row("802", "Pat Roe", Email="pat.roe@cust.test"),
            _row("803", "Pat", PhoneBusiness="704-555-0801", Email="pat.roe@cust.test"),
        ]
    )
    assert world.resolve("803").name == "Pat"
    assert world.anomalies(report, "alias conflict") == ["803"]


# 9 ------------------------------------------------------------------------
def test_an_internal_mailbox_is_never_a_match():
    world = _World()
    report = world.run(
        [
            _row("901", "Pat Doe", Email="ops@scrapmanagement.com"),
            _row("902", "Pat", Email="ops@scrapmanagement.com"),
        ]
    )
    assert sorted(p.name for p in world.people()) == ["Pat", "Pat Doe"]
    assert all(p.email is False for p in world.people()), "the internal mailbox reaches no partner"
    assert world.anomalies(report, "alias ambiguous") == ["902"]


# 10 -----------------------------------------------------------------------
def test_phone_formats_match_on_digits_with_the_us_country_code_dropped():
    assert mapping.phone_digits("+1 (980) 555-0100") == mapping.phone_digits("980-555-0100") == "9805550100"
    world = _World()
    world.run(
        [_row("1001", "Pat Doe", PhoneBusiness="+1 (980) 555-0100"), _row("1002", "Pat", PhoneMobile="980-555-0100")]
    )
    (person,) = world.people()
    assert world.resolve("1002") is person


# 11 -----------------------------------------------------------------------
def test_a_blank_name_with_a_matching_phone_folds_and_is_not_rejected():
    world = _World()
    report = world.run(
        [_row("1101", "Pat Doe", PhoneBusiness="704-555-1101"), _row("1102", "", PhoneBusiness="704-555-1101")]
    )
    (person,) = world.people()
    assert world.resolve("1102") is person
    assert report.counts["contacts"]["rejected"] == 0
    assert not world.anomalies(report, "blank ContactNm")


def test_a_blank_name_that_does_not_fold_is_still_rejected():
    world = _World()
    report = world.run([_row("1111", "Pat Doe", PhoneBusiness="704-555-1111"), _row("1112", "")])
    assert report.counts["contacts"]["rejected"] == 1
    assert world.anomalies(report, "blank ContactNm") == ["1112"]
    assert world.resolve("1112") is None


# 12 -----------------------------------------------------------------------
def test_a_replay_creates_and_updates_nothing():
    world = _World(sites=SKY_SITES)
    world.run(_sky_rows(), roles=SKY_ROLES)
    replay = world.run(_sky_rows(), roles=SKY_ROLES)
    assert replay.counts["contacts"]["created"] == 0
    assert replay.counts["contacts"]["updated"] == 0
    assert replay.counts["contact_roles"]["created"] == 0
    assert len(world.people()) == 2


def test_an_earlier_split_is_archived_and_its_markers_move_to_the_survivor():
    world = _World(
        sites=SKY_SITES,
        earlier={"Dana Sky": [str(n) for n in range(101, 108)], "Dana": ["108"], "BILLING": ["109"]},
    )
    old_dana_sky = world.resolve("101")
    old_first, old_role = world.resolve("108"), world.resolve("109")
    world.run(_sky_rows(), roles=SKY_ROLES)
    assert world.resolve("108") is old_dana_sky and world.resolve("109") is old_dana_sky
    assert old_first.active is False and old_role.active is False, "archived, never deleted"
    assert old_first.id in world.partners.rows and old_role.id in world.partners.rows
    assert sorted(p.name for p in world.people()) == ["Dana Sky", "Lee Rivers"]


def test_a_superseded_partner_another_marker_still_names_stays_active():
    world = _World(earlier={"Pat Doe": ["1201"], "Pat": ["1202", "1299"]})
    old = world.resolve("1202")
    world.run(
        [_row("1201", "Pat Doe", PhoneBusiness="704-555-1201"), _row("1202", "Pat", PhoneBusiness="704-555-1201")]
    )
    assert world.resolve("1202").name == "Pat Doe"
    assert old.active is True, "legacy_erp_contact_1299 still points at it"


# 13 -----------------------------------------------------------------------
def test_the_summary_balances_with_folded_rows():
    world = _World(sites=SKY_SITES)
    report = world.run([*_sky_rows(), _row("111", ""), _row("112", "AP", Email="ap@skyco.test")], roles=SKY_ROLES)
    summary = import_run_summary(report.as_dict())
    assert summary["records_seen"] == 12 + 3
    assert summary["records_seen"] == (
        summary["records_created"]
        + summary["records_updated"]
        + summary["records_unchanged"]
        + summary["records_rejected"]
    )
    assert summary["duplicates"] == 0
    assert summary["records_rejected"] == 1, "only the unfolded blank row"


# 14 / 15 ------------------------------------------------------------------
@pytest.mark.parametrize(
    ("cell", "expected"),
    [
        ("x@cust.com; rep@scrapmanagement.com;", "x@cust.com"),
        ("A@Cust.com ; rep@ucsincny.com;;", "a@cust.com"),
        ("rep@scrapmanagement.com; ab@ussmrecycle.com", ""),
        ("Zach P <z@cust.com>; b@cust.com, B@CUST.COM , c@cust", "b@cust.com"),
        ("one@cust.com,two@cust.com", "one@cust.com, two@cust.com"),
        ("", ""),
        (None, ""),
    ],
)
def test_email_cells_are_cleaned_in_order(cell, expected):
    assert mapping.email_cell(cell) == expected


def _counterparty_run(ap_email):
    world = _World()
    service = world.service()
    index = types.SimpleNamespace(
        counterparties={"9": {"CpID": "9", "CompanyNm": "Synthetic Buyer", "APEMail": ap_email}},
        counterparty_ids=lambda: ["9"],
    )
    service._import_counterparties(index, ImportReport(), dry_run=False)
    return world.partners.rows[max(world.partners.rows)]


def test_counterparty_ap_email_is_cleaned():
    assert _counterparty_run("x@cust.com; rep@scrapmanagement.com;").email == "x@cust.com"


def test_counterparty_ap_email_of_only_internal_mailboxes_writes_no_email():
    assert _counterparty_run("rep@scrapmanagement.com; ab@ucsincny.com").email is False


def test_contact_email_is_cleaned_and_internal_only_writes_nothing():
    world = _World()
    world.run(
        [
            _row("1501", "Pat Doe", Email="A@Cust.com ; rep@ucsincny.com;;"),
            _row("1502", "Lee Roe", Email="rep@scrapmanagement.com"),
        ]
    )
    assert world.resolve("1501").email == "a@cust.com"
    assert world.resolve("1502").email is False


def test_weak_name_kinds():
    assert mapping.weak_name_kind("", []) == "blank"
    assert mapping.weak_name_kind("BILLING", []) == "role"
    assert mapping.weak_name_kind("Ship / Del Appt", []) == "role"
    assert mapping.weak_name_kind("todd.antonick", ["todd.antonick@cust.test"]) == "email_prefix"
    assert mapping.weak_name_kind("Dana", ["dana@cust.test"]) == "email_prefix"
    assert mapping.weak_name_kind("Dana", []) == "first_name"
    assert mapping.weak_name_kind("Dana Sky", []) is None
    assert mapping.weak_name_kind("Kim Ek & Ray Ek", []) is None
    assert mapping.email_prefix_title("todd.antonick") == "Todd Antonick"
    assert mapping.email_prefix_title("AP") == "AP", "a typed title keeps its spelling"


# Phone lines compare on digits ---------------------------------------------
def _formatted(number):
    digits = mapping.phone_digits(number)
    return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"


def test_a_formatted_phone_line_already_holds_the_raw_erp_number():
    world = _World()
    partner = world.partners.create({"name": "Pat Doe", "parent_id": world.company.id})
    partner.phone_line_ids.append(types.SimpleNamespace(label="other", number="(732) 202-9500"))
    world.service()._sync_phone_lines(partner, [("other", "732-202-9500"), ("other", "+1 732.202.9500")])
    assert [(line.label, line.number) for line in partner.phone_line_ids] == [("other", "(732) 202-9500")]
    assert partner.writes == [], "nothing new, so nothing is written"


def test_the_same_digits_under_another_label_is_still_added():
    world = _World()
    partner = world.partners.create({"name": "Pat Doe", "parent_id": world.company.id})
    partner.phone_line_ids.append(types.SimpleNamespace(label="other", number="(732) 202-9500"))
    world.service()._sync_phone_lines(partner, [("mobile", "732-202-9500")])
    assert [(line.label, line.number) for line in partner.phone_line_ids] == [
        ("other", "(732) 202-9500"),
        ("mobile", "732-202-9500"),
    ]


def test_a_replay_after_phone_lines_are_reformatted_adds_no_line():
    world = _World(sites=SKY_SITES)
    rows = [*_sky_rows(), _row("111", "Pat Doe", PhoneBusiness="732-202-9500", PhoneMobile="732-202-9501")]
    world.run(rows, roles=SKY_ROLES)
    for partner in world.partners.rows.values():
        for line in partner.phone_line_ids:
            line.number = _formatted(line.number)
    before = {p.id: [(line.label, line.number) for line in p.phone_line_ids] for p in world.partners.rows.values()}
    assert any(before.values()), "the fixture stores at least one phone line"
    world.run(rows, roles=SKY_ROLES)
    after = {p.id: [(line.label, line.number) for line in p.phone_line_ids] for p in world.partners.rows.values()}
    assert after == before


# Fold carries what names the superseded card -------------------------------------
def _ekman_rows():
    return [
        _row("1301", "Kim Ek & Ray Ek", PhoneBusiness="555-010-1301", Email="kim.ek@ekco.test", Location="Site A"),
        _row("1302", "kim.ek", Email="kim.ek@ekco.test", Location="Site B"),
    ]


def test_a_folded_card_hands_its_lead_profiles_and_sites_to_the_survivor():
    world = _World(sites=("Site A", "Site B", "Site C"), earlier={"Kim Ek & Ray Ek": ["1301"], "Kim Ek": ["1302"]})
    survivor, old = world.resolve("1301"), world.resolve("1302")
    old.location_partner_ids = types.SimpleNamespace(ids=[world.site_ids["Site C"]])  # linked by hand
    lead = world.leads.add(partner_id=old.id)
    material = world.materials.add(partner_id=old.id, polymer_id=7, form_id=8)
    facility = world.facilities.add(partner_id=old.id)
    report = world.run(_ekman_rows())
    assert world.resolve("1302") is survivor and old.active is False and old.id in world.partners.rows
    assert world.leads.on(survivor) == [lead.id]
    assert world.materials.on(survivor) == [material.id]
    assert world.facilities.on(survivor) == [facility.id]
    assert set(survivor.location_partner_ids.ids) == set(world.site_ids.values()), "hand-linked Site C is kept"
    (moved,) = [a for a in report.anomalies if a["detail"].startswith("fold re-pointed")]
    to = f"-> partner {survivor.id}"
    assert moved["detail"] == (
        f"fold re-pointed: crm.lead 1 {to}, plasticos.material.profile 1 {to}, "
        f"plasticos.facility.profile 1 {to}, location_partner_ids 1 {to}"
    )
    writes = (len(world.leads.writes), len(world.materials.writes), len(world.facilities.writes))
    replay = world.run(_ekman_rows())
    assert (len(world.leads.writes), len(world.materials.writes), len(world.facilities.writes)) == writes
    assert not [a for a in replay.anomalies if a["detail"].startswith("fold")]
    assert replay.counts["contacts"]["created"] == replay.counts["contacts"]["updated"] == 0
    assert set(survivor.location_partner_ids.ids) == set(world.site_ids.values())


def test_a_profile_the_survivor_already_holds_keeps_the_old_card_visible():
    world = _World(sites=("Site A", "Site B"), earlier={"Kim Ek & Ray Ek": ["1301"], "Kim Ek": ["1302"]})
    survivor, old = world.resolve("1301"), world.resolve("1302")
    world.materials.add(partner_id=survivor.id, polymer_id=7, form_id=8)
    clash = world.materials.add(partner_id=old.id, polymer_id=7, form_id=8)
    lead = world.leads.add(partner_id=old.id)
    report = world.run(_ekman_rows())
    assert old.active is True, "never archive a card that still owns a record"
    assert world.materials.on(old) == [clash.id], "never merged, never deleted"
    assert world.leads.on(survivor) == [lead.id]
    assert world.resolve("1302") is survivor
    (kept,) = [a for a in report.anomalies if a["detail"].startswith("fold kept")]
    assert f"plasticos.material.profile {clash.id}" in kept["detail"]


def test_without_crm_or_profile_modules_the_fold_still_archives():
    world = _World(sites=("Site A", "Site B"), earlier={"Kim Ek & Ray Ek": ["1301"], "Kim Ek": ["1302"]})
    old = world.resolve("1302")
    service = world.service
    world.service = lambda: _strip(service())
    world.run(_ekman_rows())
    assert old.active is False


def _strip(service):
    for name in ("crm.lead", "plasticos.material.profile", "plasticos.facility.profile"):
        service.env.pop(name)
    return service


# Retire without a surviving person (ADR in #530: a profile never ends on a person) ------
def _retire_world(site_labels=("Site A",), linked=()):
    """An earlier run stored ``Pat Doe`` for CT_ID 1401; the source row is now inactive."""
    world = _World(sites=site_labels, earlier={"Pat Doe": ["1401"]})
    person = world.resolve("1401")
    person.location_partner_ids = types.SimpleNamespace(ids=[world.site_ids[label] for label in linked])
    return world, person


def _retire(world):
    return world.run([_row("1401", "Pat Doe", IsActive="N")])


def _notes(report, prefix):
    return [a["detail"] for a in report.anomalies if a["detail"].startswith(prefix)]


def test_retire_moves_the_lead_to_the_company_and_profiles_to_the_one_linked_site():
    world, person = _retire_world(site_labels=("Site A", "Site B"), linked=("Site A",))
    lead = world.leads.add(partner_id=person.id)
    material = world.materials.add(partner_id=person.id, polymer_id=7, form_id=8)
    facility = world.facilities.add(partner_id=person.id)
    report = _retire(world)
    site_a = world.site_ids["Site A"]
    assert person.active is False and person.id in world.partners.rows
    assert world.leads.on(world.company) == [lead.id]
    assert [r.id for r in world.materials.rows if r.partner_id.id == site_a] == [material.id]
    assert [r.id for r in world.facilities.rows if r.partner_id.id == site_a] == [facility.id]
    assert _notes(report, "retire re-pointed") == [
        f"retire re-pointed: crm.lead 1 -> partner {world.company.id}, "
        f"plasticos.material.profile 1 -> partner {site_a}, plasticos.facility.profile 1 -> partner {site_a}"
    ]
    writes = (len(world.leads.writes), len(world.materials.writes), len(world.facilities.writes))
    replay = _retire(world)
    assert (len(world.leads.writes), len(world.materials.writes), len(world.facilities.writes)) == writes
    assert not _notes(replay, "retire")


def test_retire_with_no_linked_site_puts_profiles_on_a_company_without_sites():
    world, person = _retire_world(site_labels=())
    material = world.materials.add(partner_id=person.id, polymer_id=7, form_id=8)
    _retire(world)
    assert person.active is False
    assert world.materials.on(world.company) == [material.id]


def test_retire_with_no_linked_site_but_company_sites_keeps_the_person_visible():
    world, person = _retire_world(site_labels=("Site A",))
    lead = world.leads.add(partner_id=person.id)
    material = world.materials.add(partner_id=person.id, polymer_id=7, form_id=8)
    report = _retire(world)
    assert person.active is True
    assert world.materials.on(person) == [material.id], "never on a guessed site, never deleted"
    assert world.leads.on(world.company) == [lead.id], "the lead still reaches the company"
    assert _notes(report, "retire kept") == [f"retire kept partner {person.id} visible: profiles need a site"]


def test_retire_with_several_linked_sites_keeps_the_person_visible():
    world, person = _retire_world(site_labels=("Site A", "Site B"), linked=("Site A", "Site B"))
    world.facilities.add(partner_id=person.id)
    report = _retire(world)
    assert person.active is True
    assert _notes(report, "retire kept") == [f"retire kept partner {person.id} visible: profiles need a site"]


def test_retire_keeps_the_person_visible_when_the_site_already_holds_the_profile():
    world, person = _retire_world(linked=("Site A",))
    site_a = world.site_ids["Site A"]
    world.materials.add(partner_id=site_a, polymer_id=7, form_id=8)
    clash = world.materials.add(partner_id=person.id, polymer_id=7, form_id=8)
    report = _retire(world)
    assert person.active is True
    assert world.materials.on(person) == [clash.id]
    assert _notes(report, "retire kept") == [
        f"retire kept partner {person.id} visible: partner {site_a} already holds plasticos.material.profile {clash.id}"
    ]


def test_retire_of_a_person_nothing_names_archives_as_before():
    world, person = _retire_world(site_labels=("Site A", "Site B"), linked=("Site A", "Site B"))
    report = _retire(world)
    assert person.active is False
    assert not _notes(report, "retire")


def test_a_stale_non_person_row_retires_through_the_same_rule():
    world = _World(sites=("Site A",), earlier={"Pat Doe": ["1501"]})
    person = world.resolve("1501")
    person.location_partner_ids = types.SimpleNamespace(ids=[world.site_ids["Site A"]])
    lead = world.leads.add(partner_id=person.id)
    world.run([_row("1501", "704-555-1501", PhoneBusiness="704-555-1501")])  # a number, not a person
    assert person.active is False
    assert world.leads.on(world.company) == [lead.id]
    assert world.resolve("1501") is None


# Probe-3 tie-breaks, R2b sites, E.164 matching, review ----------------------------------
def _site(world, label, **channels):
    site = world.partners.rows[world.site_ids[label]]
    for field, value in channels.items():
        setattr(site, field, value)
    return site


@pytest.mark.parametrize("local", ["pat.doe", "patdoe", "pdoe", "patd", "pat", "doe"])
def test_an_email_prefix_with_two_candidates_folds_into_the_name_that_produces_it(local):
    world = _World()
    report = world.run(
        [
            _row("1601", "Pat Doe", PhoneBusiness="704-555-1600"),
            _row("1602", "Lee Roe", PhoneBusiness="704-555-1600"),
            _row("1603", local, PhoneBusiness="704-555-1600", Email=f"{local}@cust.test"),
        ]
    )
    assert world.resolve("1603") is world.resolve("1601")
    assert report.review["ambiguous_contacts"] == []


def test_an_email_prefix_that_no_candidate_name_produces_stays_ambiguous_and_is_listed():
    world = _World()
    report = world.run(
        [
            _row("1611", "Pat Doe", PhoneBusiness="704-555-1610"),
            _row("1612", "Lee Roe", PhoneBusiness="704-555-1610"),
            _row("1613", "frontdesk", PhoneBusiness="704-555-1610", Email="frontdesk@cust.test"),
        ]
    )
    assert world.resolve("1613").name == "Frontdesk"
    (entry,) = report.review["ambiguous_contacts"]
    assert entry == {
        "ct_id": "1613",
        "kind": "email_prefix",
        "reason": "shared phone",
        "candidate_ct_ids": ["1611", "1612"],
        "candidate_partner_ids": sorted([world.resolve("1611").id, world.resolve("1612").id]),
    }


def test_an_accounting_mailbox_goes_to_the_company_never_to_a_matching_site():
    world = _World(sites=("Site A", "Site B"))
    site_a = _site(world, "Site A", phone="704-555-1700")
    world.company.email = "office@cust.test"
    world.company.phone = "704-555-1799"
    report = world.run(
        [
            _row("1701", "Pat Doe", Email="billing@cust.test"),  # a person sharing the mailbox
            _row("1702", "BILLING", PhoneBusiness="704-555-1700", Email="billing@cust.test"),
        ]
    )
    assert world.resolve("1702") is None, "no person, no marker"
    assert site_a.email is False, "an accounting mailbox never lands on a site"
    assert world.company.email == "office@cust.test, billing@cust.test"
    assert world.company.phone == "704-555-1799"
    assert [p.name for p in world.people()] == ["Pat Doe"]
    assert report.counts["contacts"]["rejected"] == 0


def test_an_accounting_mailbox_already_on_the_company_is_not_added_twice():
    world = _World()
    world.company.email = "AR@Cust.test"
    world.run([_row("1711", "COLLECTIONS", PhoneBusiness="704-555-1711", Email="ar@cust.test")])
    assert world.people() == []
    assert world.company.email == "AR@Cust.test", "same address once cleaned: nothing written"
    assert world.company.phone is False


def test_an_accounting_mailbox_matching_no_person_but_one_site_still_goes_to_the_company():
    world = _World(sites=("Site A", "Site B"))
    site_a = _site(world, "Site A", email="ap@cust.test")
    world.run([_row("1721", "Pat Doe", PhoneBusiness="704-555-1721"), _row("1722", "", Email="ap@cust.test")])
    assert world.resolve("1722") is None
    assert site_a.email == "ap@cust.test", "the site keeps what it had and gains nothing"
    assert "ap@cust.test" in world.company.email.split(", ")


def test_an_operational_mailbox_goes_to_its_one_site_else_to_the_company():
    world = _World(sites=("Site A", "Site B"))
    site_a = _site(world, "Site A", phone="704-555-1730")
    world.run(
        [
            _row("1731", "FREIGHT", PhoneBusiness="704-555-1730", Email="shipping@cust.test"),
            _row("1732", "Orders", Email="orders@cust.test"),
        ]
    )
    assert world.people() == []
    assert site_a.email == "shipping@cust.test"
    assert world.company.email == "orders@cust.test", "no matching site: the company"


@pytest.mark.parametrize(("holders", "reported"), [(["Collections"], False), ([], True), (["Billing", "AR/AP"], True)])
def test_a_mailbox_role_tag_stays_with_its_single_holder_else_is_reported(holders, reported):
    world = _World()
    rows = [_row("1741", "BILLING", Email="ap@cust.test")]
    roles = {"1741": ["Billing"]}
    for position, role in enumerate(holders):
        ct_id = str(1750 + position)
        rows.append(_row(ct_id, ("Ann Roe", "Bea Low")[position], PhoneBusiness=f"704-555-17{50 + position}"))
        roles[ct_id] = [role]
    report = world.run(rows, roles=roles)
    assert world.resolve("1741") is None
    held = [p for p in world.people() if "AR/AP" in p.tags()]
    assert len(held) == len(holders), "the mailbox adds the tag to nobody"
    notes = [a for a in report.anomalies if "function mailbox CT_ID=1741" in a["detail"]]
    assert bool(notes) is reported


@pytest.mark.parametrize(("name", "email"), [("", "dock@cust.test"), ("dock", "dock@cust.test"), ("SALES", "")])
def test_r2b_an_unnamed_row_matching_one_site_gives_the_site_its_channel_and_makes_no_person(name, email):
    world = _World(sites=("Site A", "Site B"))
    site_a = _site(world, "Site A", phone="704-555-1800")
    report = world.run(
        [
            _row("1801", "Pat Doe", PhoneBusiness="704-555-1899"),
            _row("1802", name, PhoneBusiness="704-555-1800", Email=email),
        ]
    )
    assert world.resolve("1802") is None
    assert [p.name for p in world.people()] == ["Pat Doe"]
    assert site_a.email == (email or False)
    assert report.counts["contacts"]["rejected"] == 0


def test_r2b_a_first_name_matching_one_site_stays_a_person_linked_to_that_site():
    world = _World(sites=("Site A", "Site B"))
    _site(world, "Site A", email="dock@cust.test")
    world.run([_row("1811", "Pat Doe", PhoneBusiness="704-555-1811"), _row("1812", "Sam", Email="dock@cust.test")])
    sam = world.resolve("1812")
    assert sam.name == "Sam"
    assert sam.location_partner_ids.ids == [world.site_ids["Site A"]]


def test_r2b_a_row_matching_several_sites_keeps_todays_behaviour_and_is_listed():
    world = _World(sites=("Site A", "Site B"))
    _site(world, "Site A", phone="704-555-1820")
    _site(world, "Site B", phone="704-555-1820")
    report = world.run(
        [_row("1821", "Pat Doe", PhoneBusiness="704-555-1829"), _row("1822", "Sam", PhoneBusiness="704-555-1820")]
    )
    assert world.resolve("1822").name == "Sam"
    assert "site ambiguous: 2 sites match" in [a["detail"] for a in report.anomalies if a["key"] == "1822"]


class _FakePhonenumbers(types.ModuleType):
    """Stand-in for the ``phonenumbers`` library: US and GB national and +international forms."""

    COUNTRY = {"US": "1", "GB": "44"}

    class NumberParseException(Exception):
        pass

    PhoneNumberFormat = types.SimpleNamespace(E164=0)

    def __init__(self):
        super().__init__("phonenumbers")

    def parse(self, text, region):
        import re

        extension = None
        match = re.search(r"\s*(?:x|ext\.?)\s*(\d+)\s*$", text, re.IGNORECASE)
        if match:
            extension, text = match.group(1), text[: match.start()]
        digits = "".join(char for char in text if char.isdigit())
        if text.strip().startswith("+"):
            for code in sorted(self.COUNTRY.values(), key=len, reverse=True):
                if digits.startswith(code):
                    return types.SimpleNamespace(code=code, national=digits[len(code) :], extension=extension)
            raise self.NumberParseException(text)
        code = self.COUNTRY.get(region)
        if not code:
            raise self.NumberParseException(region)
        if code == "1" and len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        if code == "44":
            digits = digits.removeprefix("0")
        return types.SimpleNamespace(code=code, national=digits, extension=extension)

    def is_possible_number(self, number):
        return len(number.national) == 10 if number.code == "1" else 9 <= len(number.national) <= 10

    def format_number(self, number, _fmt):
        return f"+{number.code}{number.national}"


@pytest.fixture
def phonenumbers_lib(monkeypatch):
    fake = _FakePhonenumbers()
    monkeypatch.setitem(sys.modules, "phonenumbers", fake)
    return fake


def test_parse_phone_uses_e164_with_the_extension_and_the_region(phonenumbers_lib):
    assert mapping.parse_phone("(980) 555-0100 x12") == "+19805550100x12"
    assert mapping.parse_phone("020 7946 0958", "GB") == "+442079460958"
    assert mapping.parse_phone("12-34-56-78", "US") is None, "not a possible US number"
    assert mapping.phone_keys("+44 20 7946 0958") & mapping.phone_keys("020 7946 0958", "GB")


def test_without_the_library_phone_keys_are_digits_only(monkeypatch):
    monkeypatch.setitem(sys.modules, "phonenumbers", None)  # import fails
    assert mapping.parse_phone("+44 20 7946 0958") is None
    assert mapping.phone_keys("+44 20 7946 0958") == {"442079460958"}


def test_an_international_and_a_national_form_of_one_number_fold_in_the_company_region(phonenumbers_lib):
    world = _World()
    world.company.country_id = types.SimpleNamespace(code="GB")
    world.run(
        [_row("1901", "Pat Doe", PhoneBusiness="+44 20 7946 0958"), _row("1902", "Pat", PhoneBusiness="020 7946 0958")]
    )
    assert world.resolve("1902") is world.resolve("1901")


def test_the_review_lists_only_ambiguous_rows_and_retire_kept_people(phonenumbers_lib):
    world = _World()
    report = world.run([_row("1911", "Pat Doe", PhoneBusiness="12-34-56-78")])  # not a possible number
    assert set(report.review) == {"ambiguous_contacts", "retire_kept"}, "unparsed phones are not reviewed"


def test_review_lines_list_every_entry_and_end_with_the_count():
    from erp.summary import review_lines

    world, person = _retire_world(site_labels=("Site A",))
    world.materials.add(partner_id=person.id, polymer_id=7, form_id=8)
    report = _retire(world)
    report.review["ambiguous_contacts"].append({"ct_id": "1", "kind": "first_name", "reason": "shared phone"})
    lines = review_lines(report.as_dict())
    assert lines[0] == "NEEDS REVIEW"
    assert lines[-1] == "NEEDS REVIEW: 2"
    assert any(f'"partner_id": {person.id}' in line for line in lines)
    summary = import_run_summary(report.as_dict())
    assert summary["records_seen"] == (
        summary["records_created"]
        + summary["records_updated"]
        + summary["records_unchanged"]
        + summary["records_rejected"]
    ), "review entries are diagnostics, not rows"


def test_review_lines_are_present_with_nothing_to_review():
    from erp.summary import review_lines

    assert review_lines(ImportReport().as_dict())[-1] == "NEEDS REVIEW: 0"


def test_make_import_erp_prints_the_review_block_last():
    import ast

    shell = ROOT_SHELL.read_text(encoding="utf-8")
    tree = ast.parse(shell)
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    tail = main.body[-2:]
    assert "review_lines" in ast.dump(tail[0]), "the review block is printed after every other line"
    assert isinstance(tail[1], ast.Return)
