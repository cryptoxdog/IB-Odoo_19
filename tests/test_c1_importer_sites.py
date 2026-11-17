"""ERP sites as native addresses (campaign C1, lane E; ADR-131).

The address and contact stages of ``plasticos.erp.import`` run unmodified
against the in-memory ORM of ``test_erp_import_contract``. Every name, number
and mailbox here is synthetic.

* A new ERP site is a native delivery or invoice address: ``is_company`` False,
  parented to its counterparty.
* A replay rewrites a site an earlier run stored as a company with a parent
  into that shape in place: same record, same ``legacy_erp_address_<id>``
  marker, so a profile pointing at the record stays attached.
* A site with a blank phone or email takes it from its one linked person,
  never from two, and never over a value it has.
* The CSV importer, the validation audit, the bulk wizard and the layer
  validator read "site" through the one D1 predicate, so both shapes count.
"""

from __future__ import annotations

import ast
import types
from pathlib import Path

import pytest
from erp import mapping
from erp.report import ImportReport
from erp.summary import import_run_summary

from tests import test_erp_contact_identity as identity
from tests import test_erp_import_contract as contract

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "plasticos_partner_import"
SERVICE = ADDON / "models" / "erp_import_service.py"
CSV_SERVICE = ADDON / "models" / "partner_import_service.py"
VALIDATION = ADDON / "models" / "validation.py"
BULK_WIZARD = ADDON / "wizards" / "partner_bulk_update_wizard.py"
LAYER_SCRIPT = ADDON / "scripts" / "validate_partner_layer.py"


class _Env(contract._ContactEnv):
    pass


def _service(partners, markers):
    module = contract._load_contact_service()
    service = module.PlasticosErpImport()
    service.env = _Env({"res.partner": partners, "ir.model.data": markers})
    service._resolve_country_state = lambda _values, _row: None
    return module, service


def _address_row(address_id, label, **extra):
    return {"AddressID": address_id, "CpID": "C1", "Type": label, "Addr2": f"{address_id} Synthetic Rd", **extra}


def _create(service, partners, company, row, report, partner_by_address):
    service._create_location(
        partners, row, row["AddressID"], company.id, company.name, partner_by_address, report, dry_run=False
    )
    return partners.rows[partner_by_address[row["AddressID"]]]


# 1 ------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("label", "extra", "expected_type"),
    [
        ("OMAHA, NE", {}, "delivery"),
        ("REMIT", {}, "invoice"),
        ("OMAHA, NE", {"InvoiceAddr": "Y"}, "invoice"),
    ],
)
def test_a_new_site_is_a_native_address_of_its_company(label, extra, expected_type):
    partners, markers = contract._PartnerModel(), contract._MarkerModel()
    company = partners.create({"name": "Synthetic Co", "is_company": True, "supplier_rank": 1})
    _module, service = _service(partners, markers)
    report, by_address = ImportReport(), {}

    site = _create(service, partners, company, _address_row("A1", label, **extra), report, by_address)

    assert site.is_company is False
    assert site.type == expected_type
    assert site.parent_id == company.id
    assert site._plasticos_is_site()
    assert site.supplier_rank == 1, "ranks are copied from the company"
    assert markers.names() == ["legacy_erp_address_A1"]
    assert report.counts["locations"]["created"] == 1


# 2 ------------------------------------------------------------------------
def test_a_replay_converts_an_old_shape_site_in_place():
    partners, markers = contract._PartnerModel(), contract._MarkerModel()
    company = partners.create({"name": "Synthetic Co", "is_company": True})
    module, service = _service(partners, markers)
    old = partners.create(
        {"name": "Synthetic Co - Omaha", "parent_id": company.id, "is_company": True, "type": "delivery"}
    )
    markers.create(
        {
            "module": module.XMLID_MODULE,
            "name": "legacy_erp_address_A7",
            "model": "res.partner",
            "res_id": old.id,
            "noupdate": True,
        }
    )
    material_profile = types.SimpleNamespace(partner_id=old.id)  # a profile row pointing at the site
    report, by_address = ImportReport(), {}

    site = _create(service, partners, company, _address_row("A7", "OMAHA, NE"), report, by_address)

    assert site is old, "the same record is rewritten, not replaced"
    assert by_address["A7"] == old.id
    assert old.is_company is False and old.type == "delivery" and old._plasticos_is_site()
    assert markers.names() == ["legacy_erp_address_A7"]
    assert markers.search([("name", "=", "legacy_erp_address_A7")], limit=1).res_id == old.id
    assert partners.rows[material_profile.partner_id] is old
    assert len(partners.rows) == 2, "no second partner"
    assert report.counts["locations"]["created"] == 0
    assert report.counts["locations"]["updated"] == 1

    # A second replay of the converted site writes nothing.
    again = ImportReport()
    _create(service, partners, company, _address_row("A7", "OMAHA, NE"), again, {})
    assert again.counts["locations"]["updated"] == 0
    assert again.counts["locations"]["skipped"] == 1


# 3 ------------------------------------------------------------------------
def _site_world(site_values):
    world = identity._World()
    for label, values in site_values.items():
        site = world.partners.create(
            {"name": label, "parent_id": world.company.id, "is_company": False, "type": "delivery", **values}
        )
        world.site_ids[label] = site.id
    return world


def test_a_blank_site_phone_and_email_come_from_its_one_person():
    world = _site_world({"Site A": {}})
    report = world.run(
        [identity._row("301", "Pat Doe", PhoneBusiness="704-555-0301", Email="pat@synthetic.test", Location="Site A")]
    )
    site = world.partners.rows[world.site_ids["Site A"]]
    assert len(site.site_person_ids) == 1
    assert site.email == "pat@synthetic.test"
    assert site.phone
    assert site.phone == site.site_person_ids[0].phone

    summary = import_run_summary(report.as_dict())
    assert summary["records_seen"] == (
        summary["records_created"]
        + summary["records_updated"]
        + summary["records_unchanged"]
        + summary["records_rejected"]
    )
    assert summary["duplicates"] == 0


def test_a_site_with_two_people_takes_nothing():
    world = _site_world({"Site A": {}})
    world.run(
        [
            identity._row(
                "311", "Pat Doe", PhoneBusiness="704-555-0311", Email="pat@synthetic.test", Location="Site A"
            ),
            identity._row(
                "312", "Lee Rivers", PhoneBusiness="704-555-0312", Email="lee@synthetic.test", Location="Site A"
            ),
        ]
    )
    site = world.partners.rows[world.site_ids["Site A"]]
    assert len(site.site_person_ids) == 2
    assert not site.email and not site.phone


def test_a_site_value_is_never_overwritten():
    world = _site_world({"Site A": {"email": "dock@synthetic.test"}})
    world.run(
        [identity._row("321", "Pat Doe", PhoneBusiness="704-555-0321", Email="pat@synthetic.test", Location="Site A")]
    )
    site = world.partners.rows[world.site_ids["Site A"]]
    assert site.email == "dock@synthetic.test"
    assert site.phone, "the blank phone is still filled"


def test_an_old_shape_site_is_filled_too():
    world = identity._World(sites=("Site A",))
    world.run(
        [identity._row("331", "Pat Doe", PhoneBusiness="704-555-0331", Email="pat@synthetic.test", Location="Site A")]
    )
    site = world.partners.rows[world.site_ids["Site A"]]
    assert site.email == "pat@synthetic.test"


@pytest.mark.parametrize(
    ("site_phone", "site_email", "people", "expected"),
    [
        (None, None, [("1", "a@x.test")], {"phone": "1", "email": "a@x.test"}),
        ("9", None, [("1", "a@x.test")], {"email": "a@x.test"}),
        (None, "s@x.test", [("1", "a@x.test")], {"phone": "1"}),
        (None, None, [("1", "a@x.test"), ("2", "b@x.test")], {}),
        (None, None, [], {}),
        (None, None, [(None, None)], {}),
    ],
)
def test_site_contact_fill_rule(site_phone, site_email, people, expected):
    assert mapping.site_contact_fill(site_phone=site_phone, site_email=site_email, people=people) == expected


# 4 ------------------------------------------------------------------------
def test_person_guards_skip_both_site_shapes():
    module = contract._load_contact_service()
    partners = contract._PartnerModel()
    company = partners.create({"name": "Synthetic Co", "is_company": True})
    native = partners.create({"name": "Site N", "parent_id": company.id, "type": "invoice"})
    old = partners.create({"name": "Site O", "parent_id": company.id, "is_company": True, "type": "delivery"})
    person = partners.create({"name": "Pat Doe", "parent_id": company.id, "type": "contact"})
    assert [module._is_person(p) for p in (company, native, old, person)] == [False, False, False, True]


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_create_location_writes_the_native_shape():
    tree = ast.parse(_source(SERVICE))
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_create_location")
    text = ast.unparse(fn)
    assert "'is_company': False" in text
    assert "'is_company': True" not in text


def test_csv_importer_writes_sites_in_the_native_shape():
    text = _source(CSV_SERVICE)
    for fn_name in ("_load_facilities",):
        fn = next(n for n in ast.walk(ast.parse(text)) if isinstance(n, ast.FunctionDef) and n.name == fn_name)
        body = ast.unparse(fn)
        assert "'company_type': 'site'" in body and "'is_company': False" in body
    assert text.count('"company_type": "site"') == 2


def test_validation_audit_uses_the_company_child_predicate():
    """A site is company_type ``site``. The missing-role report lists company children only."""
    text = _source(VALIDATION)
    compact = " ".join(text.split())
    assert '("company_type", "=", "company"), ("parent_id", "!=", False)' in compact


def test_bulk_wizard_and_layer_validator_use_the_d1_predicate():
    assert _source(BULK_WIZARD).count("_plasticos_is_site()") >= 3
    layer = _source(LAYER_SCRIPT)
    assert "_plasticos_is_site()" in layer
    assert '("is_company", "=", False), ("parent_id"' not in layer


def test_d1_predicate_recognises_both_site_shapes():
    from importlib import util

    spec = util.spec_from_file_location("_am", ROOT / "plasticos_facility_profile" / "address_meaning.py")
    am = util.module_from_spec(spec)
    spec.loader.exec_module(am)
    assert am.is_site(has_parent=True, partner_type="delivery", is_company=False)
    assert am.is_site(has_parent=True, partner_type="contact", is_company=True)
    assert not am.is_site(has_parent=True, partner_type="contact", is_company=False)


# 5 ------------------------------------------------------------------------
def test_a_converted_site_takes_its_company_credit_limit():
    partners, markers = contract._PartnerModel(), contract._MarkerModel()
    company = partners.create({"name": "Synthetic Co", "is_company": True, "credit_limit": 5000})
    module, service = _service(partners, markers)
    old = partners.create(
        {"name": "Synthetic Co - Omaha", "parent_id": company.id, "is_company": True, "type": "delivery"}
    )
    old.credit_limit = 250  # the site's own limit from the old shape
    markers.create(
        {
            "module": module.XMLID_MODULE,
            "name": "legacy_erp_address_A9",
            "model": "res.partner",
            "res_id": old.id,
            "noupdate": True,
        }
    )
    _create(service, partners, company, _address_row("A9", "OMAHA, NE"), ImportReport(), {})
    assert old.credit_limit == 5000, "the parent wins"
    assert old.commercial_syncs == 1

    # A replay of an already native site does not re-sync.
    _create(service, partners, company, _address_row("A9", "OMAHA, NE"), ImportReport(), {})
    assert old.commercial_syncs == 1


class _SearchablePartners(contract._PartnerModel):
    def search(self, domain):
        def hit(row):
            for field, op, value in domain:
                current = getattr(row, field)
                if op == "=" and current != value:
                    return False
                if op == "!=" and current == value:
                    return False
            return True

        return contract._PartnerSet(row for row in self.rows.values() if hit(row))


def test_an_unmarked_old_shape_site_is_converted_and_other_company_children_are_left(caplog):
    partners, markers = _SearchablePartners(), contract._MarkerModel()
    company = partners.create({"name": "Synthetic Co", "is_company": True, "credit_limit": 900})
    module, service = _service(partners, markers)
    unmarked_site = partners.create({"name": "Dock", "parent_id": company.id, "is_company": True, "type": "invoice"})
    unmarked_site.credit_limit = 10
    division = partners.create({"name": "Division", "parent_id": company.id, "is_company": True, "type": "contact"})
    marked = partners.create({"name": "Yard", "parent_id": company.id, "is_company": True, "type": "delivery"})
    markers.create(
        {
            "module": module.XMLID_MODULE,
            "name": "legacy_erp_address_A3",
            "model": "res.partner",
            "res_id": marked.id,
            "noupdate": True,
        }
    )

    with caplog.at_level("INFO"):
        service._convert_unmarked_sites(partners)

    assert unmarked_site.is_company is False and unmarked_site.type == "invoice"
    assert unmarked_site.credit_limit == 900
    assert division.is_company is True, "not a site address type: left as a company"
    assert marked.is_company is True, "a marked site is converted by its own address row"
    assert f"converted unmarked old-shape site {unmarked_site.id}" in caplog.text
    assert f"left company child {division.id}" in caplog.text


# 6 F12 --------------------------------------------------------------------
_ADDRESS_FIELDS = {
    **contract._PARTNER_FIELDS,
    **{name: types.SimpleNamespace(type="char") for name in ("street", "street2", "city", "zip")},
    **{name: types.SimpleNamespace(type="many2one") for name in ("country_id", "state_id")},
}


class _AddressPartner(contract._Partner):
    _fields = _ADDRESS_FIELDS

    def __init__(self, rec_id, vals):
        self.street = self.street2 = self.city = self.zip = False
        self.country_id = self.state_id = False
        super().__init__(rec_id, vals)


class _AddressPartners(_SearchablePartners):
    _fields = _ADDRESS_FIELDS

    def create(self, vals):
        record = _AddressPartner(len(self.rows) + 1, vals)
        record._model = self
        self.rows[record.id] = record
        return record


def _f12_run(partners, markers, company, rows):
    _module, service = _service(partners, markers)
    index = types.SimpleNamespace(
        addresses={row["AddressID"]: row for row in rows},
        addresses_by_cp={"C1": [row["AddressID"] for row in rows]},
    )
    return service._import_addresses(index, ImportReport(), {"C1": company.id}, dry_run=False)


def _f12_rows():
    remit = {
        "AddressID": "B1",
        "CpID": "C1",
        "Type": "PRIMARY",
        "Addr1": "SYNTHETIC RECYCLING",
        "Addr2": "P.O. Box 100",
        "Addr3": "",
        "City": "Billtown",
        "InvoiceAddr": "Y",
    }
    # A site row that carries the company's name, with its street in Addr3.
    site = {
        "AddressID": "S1",
        "CpID": "C1",
        "Type": "HARBOR, VA",
        "Addr1": "SYNTHETIC RECYCLING",
        "Addr2": "Plant Gate",
        "Addr3": "1 Harbor Rd",
        "City": "Harbor",
        "InvoiceAddr": "N",
    }
    return remit, site


def test_f12_a_site_named_like_its_company_never_fills_the_company_address():
    partners, markers = _AddressPartners(), contract._MarkerModel()
    company = partners.create({"name": "Synthetic Recycling", "is_company": True})
    remit, site_row = _f12_rows()

    by_address = _f12_run(partners, markers, company, [remit, site_row])

    assert company.street == "P.O. Box 100"
    assert company.street2 is False, "the site's street is not the company's"
    assert company.city == "Billtown"
    site = partners.rows[by_address["S1"]]
    assert site.id != company.id and site.parent_id == company.id
    assert site.street == "Plant Gate" and site.street2 == "1 Harbor Rd" and site.city == "Harbor"


def test_f12_a_replay_removes_a_site_street_an_earlier_run_leaked_into_the_company():
    partners, markers = _AddressPartners(), contract._MarkerModel()
    company = partners.create({"name": "Synthetic Recycling", "is_company": True})
    remit, site_row = _f12_rows()
    _f12_run(partners, markers, company, [remit, site_row])
    company.street2 = "1 Harbor Rd"  # what the pre-F12 importer wrote

    _f12_run(partners, markers, company, [remit, site_row])

    assert company.street2 is False
    assert company.street == "P.O. Box 100"


def test_f12_a_company_street2_that_is_no_site_street_is_kept():
    partners, markers = _AddressPartners(), contract._MarkerModel()
    company = partners.create({"name": "Synthetic Recycling", "is_company": True})
    remit, site_row = _f12_rows()
    _f12_run(partners, markers, company, [remit, site_row])
    company.street2 = "Suite 4"

    _f12_run(partners, markers, company, [remit, site_row])

    assert company.street2 == "Suite 4"


def test_f12_a_same_address_row_still_folds_into_the_company():
    partners, markers = _AddressPartners(), contract._MarkerModel()
    company = partners.create({"name": "Synthetic Recycling", "is_company": True})
    remit, _site_row = _f12_rows()
    same = {**remit, "AddressID": "B2", "InvoiceAddr": "N", "Type": "MAIN", "Addr3": "Dock 2"}

    by_address = _f12_run(partners, markers, company, [remit, same])

    assert by_address["B2"] == company.id, "same street: the company itself"
    assert company.street2 == "Dock 2", "a blank company value is still filled from its own address"
