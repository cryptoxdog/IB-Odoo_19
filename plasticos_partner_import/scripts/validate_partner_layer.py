"""Machine gate between partner import layers.

``import_erp_shell.py`` runs the previous layer's check before a layer opens its
file, and the layer's own check after it commits. Run alone inside
``odoo shell``, ``ERP_LAYER`` selects the checks. Exit 0 is the only permission
to open the next file. Exit 1 prints the failing row.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict
from functools import cache
from pathlib import Path

USA_MODULES = (
    "l10n_us",
    "l10n_us_account",
    "l10n_us_1099",
    "l10n_us_reports",
    "l10n_us_check_printing",
    "l10n_us_payment_nacha",
)
XMLID_MODULE = "plasticos_transaction"


def _setting(name: str) -> str:
    return os.environ.get(f"ERP_{name}") or ""


def _addon_root() -> Path:
    import odoo.addons.plasticos_partner_import as addon

    return Path(addon.__file__).resolve().parent


def _bulk() -> Path:
    return _addon_root() / "erp_extracted_data" / "bulk"


@cache
def _expect() -> dict:
    """Dataset facts the checks assert, kept out of the code."""
    path = _addon_root() / "scripts" / "partner_layer_expectations.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _rows(name: str) -> list[dict[str, str]]:
    path = _bulk() / name
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _digits(value: str) -> str:
    return "".join(char for char in (value or "") if char.isdigit())


def _by_xmlid(env, model: str, xml_name: str):
    data = env["ir.model.data"].search(
        [("module", "=", XMLID_MODULE), ("name", "=", xml_name), ("model", "=", model)],
        limit=1,
    )
    if not data or not data.res_id:
        return env[model]
    return env[model].with_context(active_test=False).browse(data.res_id).exists()


def _partner(env, xml_name: str):
    return _by_xmlid(env, "res.partner", xml_name)


def _fail(failures: list[str], message: str) -> None:
    failures.append(message)


def _imported_companies(env):
    data = env["ir.model.data"].search(
        [
            ("module", "=", XMLID_MODULE),
            ("model", "=", "res.partner"),
            ("name", "=like", "legacy_erp_cp_%"),
        ]
    )
    partners = env["res.partner"].with_context(active_test=False).browse(data.mapped("res_id")).exists()
    return partners


def check_database(env, failures: list[str]) -> None:
    env.cr.execute("SELECT current_database()")
    name = env.cr.fetchone()[0]
    expected = _expect()["database"]
    if name != expected:
        _fail(failures, f"database is {name}, expected {expected}")
    installed = set(
        env["ir.module.module"].search([("name", "in", list(USA_MODULES)), ("state", "=", "installed")]).mapped("name")
    )
    missing = [module for module in USA_MODULES if module not in installed]
    if missing:
        _fail(failures, f"USA modules not installed: {', '.join(missing)}")
    form = env.ref("base.view_partner_form")
    arch = form.get_combined_arch() if hasattr(form, "get_combined_arch") else ""
    text = str(arch)
    if "phone_line_ids" not in text:
        _fail(failures, "contact form does not show phone_line_ids")
    if "not is_company" not in text:
        _fail(failures, "contact form does not hide company-only tabs with not is_company")


def check_counterparties(env, failures: list[str]) -> None:
    companies = _imported_companies(env)
    expected = _expect()["company_count"]
    if len(companies) != expected:
        _fail(failures, f"imported companies {len(companies)}, expected {expected}")
    children = env["res.partner"].with_context(active_test=False).search([("parent_id", "in", companies.ids)])
    if children:
        _fail(failures, f"child partners exist before addresses: {children[:5].mapped('name')}")
    people = companies.filtered(lambda partner: not partner.is_company)
    if people:
        _fail(failures, f"imported company is a person: {people[:5].mapped('name')}")
    streets = {_digits(row.get("Addr2") or "") for row in _rows("Address.csv") if (row.get("Addr2") or "").strip()}
    for company in companies:
        if company.name and _digits(company.name) in streets and len(_digits(company.name)) >= 6:
            _fail(failures, f"company name equals a street: {company.id} {company.name}")
            return


def check_addresses(env, failures: list[str]) -> None:
    from odoo.addons.plasticos_partner_import.erp import mapping

    people = (
        env["res.partner"]
        .with_context(active_test=False)
        .search([("is_company", "=", False), ("parent_id", "!=", False)])
    )
    imported_people = people.filtered(lambda partner: partner.parent_id.id in _imported_companies(env).ids)
    if imported_people:
        _fail(failures, f"people exist before contacts: {imported_people[:5].mapped('name')}")
    for row in _rows("Address.csv"):
        address_id = (row.get("AddressID") or "").strip()
        cp_id = (row.get("CpID") or "").strip()
        company = _partner(env, f"legacy_erp_cp_{cp_id}")
        location = _partner(env, f"legacy_erp_address_{address_id}")
        if not company or not location:
            continue
        if location.id != company.id and location.parent_id.id != company.id:
            _fail(failures, f"location {location.id} parent is not company {company.id} for CpID {cp_id}")
            return
        if location.id == company.id:
            continue
        for column in ("Addr2", "Addr3"):
            street = (row.get(column) or "").strip()
            if street and street.upper() != "NULL" and street.casefold() in (location.name or "").casefold():
                _fail(failures, f"partner {location.id} name {location.name!r} contains street {street!r}")
                return
        if mapping.real_phone(row.get("Fax")):
            fax_digits = _digits(row.get("Fax") or "")
            numbers = [_digits(line.number) for line in location.phone_line_ids if line.label == "fax"]
            if fax_digits not in numbers:
                _fail(failures, f"location {location.id} missing fax {row.get('Fax')}")
                return
    # This CpID is in Address.csv and Contact.csv and is absent from CounterParty.csv.
    # Those rows stay unimported. A company is never invented for them.
    missing = _expect()["missing_counterparty"]
    if _partner(env, f"legacy_erp_cp_{missing['cp_id']}"):
        _fail(failures, f"CpID {missing['cp_id']} has no CounterParty row and must not be a company")
    for address_id in missing["address_ids"]:
        if _partner(env, f"legacy_erp_address_{address_id}"):
            _fail(failures, f"Address {address_id} for missing CpID {missing['cp_id']} was imported")
    want = _expect()["abbott"]
    abbott = _partner(env, f"legacy_erp_cp_{want['cp_id']}")
    if not abbott or abbott.name != want["name"] or want["street"] not in (abbott.street or ""):
        _fail(
            failures,
            f"{want['name']} is {abbott.name if abbott else 'missing'} street {abbott.street if abbott else ''}",
        )
    park = (
        abbott.location_child_ids.filtered(lambda partner: partner.name == want["park_name"])
        if abbott
        else env["res.partner"]
    )
    if not park or want["park_street"] not in (park[:1].street or ""):
        _fail(failures, f"{want['park_name']} child with street {want['park_street']} is missing")


def _people_under(env, cp_id: str, name: str):
    company = _partner(env, f"legacy_erp_cp_{cp_id}")
    if not company:
        return env["res.partner"]
    return company.child_ids.filtered(lambda partner: not partner.is_company and partner.name == name)


def check_contacts(env, failures: list[str]) -> None:
    from odoo.addons.plasticos_partner_import.erp import mapping

    companies = _imported_companies(env)
    grouped = defaultdict(list)
    for person in (
        env["res.partner"]
        .with_context(active_test=False)
        .search([("is_company", "=", False), ("parent_id", "in", companies.ids)])
    ):
        if person.name and not mapping.is_person_name(person.name):
            _fail(failures, f"partner {person.id} name is only digits: {person.name}")
            return
        grouped[(person.parent_id.id, mapping.person_key(person.name))].append(person)
    for (parent_id, key), rows in grouped.items():
        if len(rows) > 1:
            _fail(failures, f"duplicate {key} under partner {parent_id}: {[row.id for row in rows]}")
            return
    expect = _expect()
    missing = expect["missing_counterparty"]
    if env["res.partner"].with_context(active_test=False).search_count([("name", "=", missing["contact_name"])]):
        _fail(
            failures,
            f"{missing['contact_name']} was imported without a CounterParty row for CpID {missing['cp_id']}",
        )
    want = expect["eddie"]
    eddie = _people_under(env, want["cp_id"], want["name"])
    if len(eddie) != 1:
        _fail(failures, f"{want['name']} under {want['cp_id']} count {len(eddie)}")
    else:
        linked = eddie.location_partner_ids.mapped("name")
        if want["site"] not in linked:
            _fail(failures, f"{want['name']} sites are {linked}")
        if any(want["excluded_site_word"] in name for name in linked):
            _fail(failures, f"{want['name']} is linked to {want['excluded_site_word']}: {linked}")
    address_types = {
        (row.get("Type") or "").strip()
        for row in _rows("Address.csv")
        if (row.get("CpID") or "").strip() == want["cp_id"]
    }
    eddie_locations = {
        (row.get("Location") or "").strip()
        for row in _rows("Contact.csv")
        if (row.get("CpID") or "").strip() == want["cp_id"] and (row.get("ContactNm") or "").strip() == want["name"]
    }
    unmatched = eddie_locations - address_types
    if want["unmatched_site"] not in unmatched:
        _fail(failures, f"{want['unmatched_site']} not unmatched: {sorted(unmatched)}")
    want = expect["joshua"]
    joshua_rows = [
        row
        for row in _rows("Contact.csv")
        if (row.get("CpID") or "").strip() == want["cp_id"] and (row.get("ContactNm") or "").strip() == want["name"]
    ]
    joshua = _people_under(env, want["cp_id"], want["name"])
    if len(joshua) != 1:
        _fail(failures, f"{want['name']} under {want['cp_id']} count {len(joshua)}")
    else:
        linked = set(joshua.location_partner_ids.mapped("name"))
        expected = {(row.get("Location") or "").strip() for row in joshua_rows} & address_types
        if linked != expected:
            _fail(failures, f"{want['name']} sites {sorted(linked)} expected {sorted(expected)}")
    for forbidden in expect["forbidden_partner_names"]:
        if env["res.partner"].with_context(active_test=False).search_count([("name", "=", forbidden)]):
            _fail(failures, f"a partner is named {forbidden}")
    root = _by_xmlid(env, "res.partner.category", "legacy_erp_contact_role_root")
    tags = env["res.partner.category"].search([("parent_id", "=", root.id)]) if root else root
    if tags and env["res.partner"].search_count([("category_id", "in", tags.ids)]):
        _fail(failures, f"{root.name} tags exist before the role file")
    want = expect["eli"]
    eli = _people_under(env, want["cp_id"], want["name"])
    if len(eli) != 1:
        _fail(failures, f"{want['name']} count {len(eli)}")
    else:
        if want["phone"] not in _digits(eli.phone or ""):
            _fail(failures, f"{want['name']} phone is {eli.phone}")
        mobiles = {_digits(line.number) for line in eli.phone_line_ids if line.label == "mobile"}
        others = {_digits(line.number) for line in eli.phone_line_ids if line.label == "other"}
        if want["mobile"] not in mobiles:
            _fail(failures, f"{want['name']} mobile lines {sorted(mobiles)}")
        if want["other"] not in others:
            _fail(failures, f"{want['name']} other lines {sorted(others)}")
        if eli.comment and want["mobile"] in _digits(eli.comment) and want["mobile"] not in mobiles:
            _fail(failures, f"{want['name']} mobile exists only in notes")
    want = expect["tuckahoe"]
    tuckahoe = _partner(env, f"legacy_erp_cp_{want['cp_id']}")
    if not tuckahoe or tuckahoe.name != want["name"]:
        _fail(failures, f"CpID {want['cp_id']} name is {tuckahoe.name if tuckahoe else 'missing'}")
    elif want["phone"] not in _digits(tuckahoe.phone or ""):
        _fail(failures, f"{want['name']} phone is {tuckahoe.phone}")
    elif tuckahoe.child_ids.filtered(lambda partner: not partner.is_company):
        _fail(failures, f"{want['name']} has a person child")


def _has_tag(partner, tag_name: str) -> bool:
    return tag_name in partner.category_id.mapped("name")


def check_roles(env, failures: list[str]) -> None:
    expect = _expect()
    tag = expect["decision_maker_tag"]
    for want in expect["decision_makers"]:
        person = _people_under(env, want["cp_id"], want["name"])
        if len(person) != 1 or not _has_tag(person, tag):
            _fail(failures, f"{want['name']} is missing the {tag} tag")
    want = expect["accounting"]
    accounting = _people_under(env, want["cp_id"], want["name"])
    if len(accounting) != 1 or not _has_tag(accounting, want["tag"]):
        _fail(failures, f"{want['name']} contact under {want['cp_id']} is missing {want['tag']}")
    want = expect["unresolved_rr"]
    rr_rows = [
        row
        for row in _rows("Contact.csv")
        if (row.get("ContactNm") or "").strip() == want["name"] and (row.get("CpID") or "").strip() == want["cp_id"]
    ]
    if not rr_rows:
        _fail(failures, f"{want['name']} is missing from Contact.csv")
    else:
        contact_id = (rr_rows[0].get("CT_ID") or "").strip()
        person = _partner(env, f"legacy_erp_contact_{contact_id}")
        guessed = set(want["guessed_tags"])
        if person and guessed & set(person.category_id.mapped("name")):
            _fail(failures, f"{want['name']} has a guessed tag: {person.category_id.mapped('name')}")
        stored = env["ir.config_parameter"].get_param("plasticos_partner_import.unresolved_rr") or ""
        if contact_id not in stored.split(","):
            _fail(failures, f"{want['name']} CT_ID {contact_id} is not in the unresolved RR list")
    stamped = env["ir.config_parameter"].get_param("plasticos_partner_import.partner_count_after_contacts")
    env.cr.execute("SELECT count(*) FROM res_partner")
    current = int(env.cr.fetchone()[0])
    if not stamped or int(stamped) != current:
        _fail(failures, f"partner count changed from {stamped} to {current}")
    forbidden = expect["tuckahoe"]["forbidden_partner_name"]
    if env["res.partner"].with_context(active_test=False).search_count([("name", "=", forbidden)]):
        _fail(failures, f"a partner is named {forbidden}")
    want = expect["eddie"]
    eddie = _people_under(env, want["cp_id"], want["name"])
    if len(eddie) == 1 and not failures:
        print(f"{want['name']} partner id {eddie.id}")
        print(f"http://localhost:8069/odoo/contacts/{eddie.id}")
        print(f"{expect['tuckahoe']['name']} has no partner named {forbidden}")


CHECKS = {
    "database": check_database,
    "counterparties": check_counterparties,
    "addresses": check_addresses,
    "contacts": check_contacts,
    "roles": check_roles,
}

# The check that must pass before each import layer may open its file.
LAYER_BEFORE = {
    "counterparties": "database",
    "addresses": "counterparties",
    "contacts": "addresses",
    "roles": "contacts",
}


def validate(env, layer: str) -> int:
    if layer not in CHECKS:
        raise SystemExit(f"ERP_LAYER must be one of {', '.join(CHECKS)}")
    failures: list[str] = []
    CHECKS[layer](env, failures)
    if failures:
        print(f"VALIDATOR FAILED ({layer})")
        for message in failures:
            print(f"  - {message}")
        return 1
    print(f"VALIDATOR PASSED ({layer})")
    return 0


def main() -> int:
    env = globals().get("env")
    if env is None:
        raise SystemExit("no Odoo environment (run inside `odoo shell`)")
    return validate(env, _setting("LAYER").strip().lower())


if __name__ == "__main__":
    sys.exit(main())
