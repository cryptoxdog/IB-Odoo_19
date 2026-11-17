"""Machine gate between partner import layers.

``import_erp_shell.py`` runs the database check before anything writes, the
previous layer's check before a single layer opens its table, and each layer's
own check after it is written and **before** it commits. A failed check rolls
the stage back. Exit 0 is the only permission to keep going. Exit 1 prints the
failing row.

Every check reads the source the import actually read: the same
``erp.reader`` seam, the same ``ERP_PAYLOAD_ROOT`` / direct-database
selection, or the very payload the import passed to the hook. Dataset facts
that only hold for one extract are guarded by whether that extract's company
is in the active payload.
"""

from __future__ import annotations

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
REQUIRED_MODULES = ("plasticos_partner_import",)
COMMERCIAL_MODULES = ("sale", "purchase", "account")
XMLID_MODULE = "plasticos_transaction"
# A full run realizes native documents through plasticos_transaction and posts
# them to the accounts plasticos_accounting seeds; without either the base
# importer commits partners and silently reports no transaction outcome.
FULL_RUN_PROVIDER_MODULES = (XMLID_MODULE, "plasticos_accounting")
FULL_RUN_MODULES = (*COMMERCIAL_MODULES, *FULL_RUN_PROVIDER_MODULES)

# The import names the disposable database it may write. The check refuses
# any other database, and any database that identifies as production.
TARGET_DB_ENV = "ERP_TARGET_DB"
# Odoo.sh sets this to production / staging / dev on its containers.
ODOO_STAGE_ENV = "ODOO_STAGE"
PRODUCTION_STAGE = "production"
PRODUCTION_NAME_MARKERS = ("production", "prod")
# The check that must pass before any stage writes.
DATABASE_CHECK = "database"
# The one database a verified one-use Production permit admitted in this
# process (``erp/production_permit.py``). Only ``import_erp_shell.py`` sets it.
_PRODUCTION_ADMISSION: dict[str, str | None] = {"database": None}


def admit_production(database_name: str) -> None:
    """Lift the production refusal for exactly ``database_name``, after the shell verified a permit for it."""
    _PRODUCTION_ADMISSION["database"] = database_name


class LayerRejected(RuntimeError):
    """A layer's validator did not pass. The caller rolls the stage back."""


def _setting(name: str) -> str:
    return os.environ.get(f"ERP_{name}") or ""


def _full_run() -> bool:
    """True unless the run is ``ERP_PARTNERS_ONLY`` or one partner ``ERP_LAYER`` (the driver's own scope rule).

    ``ERP_LAYER=database`` (a standalone preflight) names a check, not a partner
    layer, so it keeps the full-run requirement.
    """
    partners_only = _setting("PARTNERS_ONLY").strip().lower() in {"1", "true", "yes", "y"}
    return not partners_only and _setting("LAYER").strip().lower() not in LAYER_BEFORE


def required_modules() -> tuple[str, ...]:
    """Import modules the database check requires for the run this environment selects."""
    return REQUIRED_MODULES


def _addon_root() -> Path:
    import odoo.addons.plasticos_partner_import as addon

    return Path(addon.__file__).resolve().parent


def _erp():
    from odoo.addons.plasticos_partner_import.erp import mapping, reader

    return mapping, reader


@cache
def _expect() -> dict:
    """Dataset facts the checks assert, kept out of the code."""
    path = _addon_root() / "scripts" / "partner_layer_expectations.json"
    return json.loads(path.read_text(encoding="utf-8"))


_ACTIVE_PAYLOAD = {"payload": None}


def _payload():
    """The partner source this import reads: same seam, same selection as the import."""
    if _ACTIVE_PAYLOAD["payload"] is None:
        _mapping, reader = _erp()
        root = _setting("PAYLOAD_ROOT").strip() or None
        database = reader.database_source_from_env(os.environ)
        _ACTIVE_PAYLOAD["payload"] = reader.load_payload(root, only=reader.PARTNER_SOURCE_TABLES, database=database)
    return _ACTIVE_PAYLOAD["payload"]


def _rows(table: str) -> list[dict[str, str | None]]:
    """Rows of one source table, or ``[]`` when the active payload does not carry it."""
    payload = _payload()
    if table not in payload.tables:
        return []
    return payload.rows(table)


def _cell(row: dict, column: str) -> str:
    return (row.get(column) or "").strip()


def _payload_cp_ids() -> frozenset[str]:
    """CpIDs present in the active payload's CounterParty table."""
    return frozenset(_cell(row, "CpID") for row in _rows("CounterParty"))


def _covers(cp_id: str) -> bool:
    """A named sample is checked only when its company is in this payload."""
    return cp_id in _payload_cp_ids()


def _expected_company_count() -> int:
    """Companies the active source carries: every CounterParty row with a name."""
    return sum(1 for row in _rows("CounterParty") if _cell(row, "CompanyNm"))


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


def _replaying(env) -> bool:
    """True once a contacts stage has completed on this database.

    The sequencing checks ("no children before addresses", "no people before
    contacts", "no role tags before roles") describe the first load of an empty
    partner table. On a replay the later stages' records already exist, so
    those three checks are skipped; every identity, linkage, duplicate and
    count check still runs.
    """
    return bool(env["ir.config_parameter"].get_param("plasticos_partner_import.partner_count_after_contacts"))


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


def check_full_run_extension(env, failures: list[str], installed: set[str] | None = None) -> None:
    """A full run realizes sale orders, purchase orders, and invoices.

    ``installed`` is the module set the caller already loaded; when absent, the
    installed set is read from ``env``. Partner-only and single-layer runs do
    not call this.
    """
    if installed is None:
        installed = set(
            env["ir.module.module"]
            .search([("name", "in", list(FULL_RUN_MODULES)), ("state", "=", "installed")])
            .mapped("name")
        )
    missing = [name for name in FULL_RUN_MODULES if name not in installed]
    if missing:
        _fail(failures, "full import needs installed modules: " + ", ".join(missing))


def check_database(env, failures: list[str]) -> None:
    """The target is the declared database, not production unless a permit admitted it, with the modules needed."""
    # Direct SQL justification: the connected database's own name is the identity being verified.
    env.cr.execute("SELECT current_database()")
    name = env.cr.fetchone()[0]
    target = _setting("TARGET_DB").strip()
    if not target:
        _fail(failures, f"{TARGET_DB_ENV} is not set; name the disposable database this import may write")
    elif name != target:
        _fail(failures, f"database is {name}, expected the declared target {target}")
    stage = (os.environ.get(ODOO_STAGE_ENV) or "").strip().lower()
    admitted = bool(name) and stage == PRODUCTION_STAGE and _PRODUCTION_ADMISSION["database"] == name
    if stage == PRODUCTION_STAGE and not admitted:
        _fail(
            failures,
            f"{ODOO_STAGE_ENV}=production: the ERP import writes production only under a verified one-use permit",
        )
    lowered = (name or "").lower()
    if any(marker in lowered for marker in PRODUCTION_NAME_MARKERS) and not admitted:
        _fail(failures, f"database {name} identifies as production")
    required = required_modules()
    wanted = list(USA_MODULES) + list(required)
    if _full_run():
        wanted.extend(FULL_RUN_MODULES)
    installed = set(
        env["ir.module.module"].search([("name", "in", wanted), ("state", "=", "installed")]).mapped("name")
    )
    missing = [module for module in USA_MODULES if module not in installed]
    if missing:
        _fail(failures, f"USA modules not installed: {', '.join(missing)}")
    missing = [module for module in required if module not in installed]
    if missing:
        _fail(failures, f"import modules not installed: {', '.join(missing)}")
    if _full_run():
        check_full_run_extension(env, failures, installed=installed)
    form = env.ref("base.view_partner_form", raise_if_not_found=False)
    if not form:
        _fail(failures, "contact form view is missing")
        return
    arch = form.get_combined_arch() if hasattr(form, "get_combined_arch") else ""
    text = str(arch)
    if "phone_line_ids" not in text:
        _fail(failures, "contact form does not show phone_line_ids")
    if "not is_company" not in text:
        _fail(failures, "contact form does not hide company-only tabs with not is_company")


def check_counterparties(env, failures: list[str]) -> None:
    companies = _imported_companies(env)
    expected = _expected_company_count()
    if len(companies) != expected:
        _fail(failures, f"imported companies {len(companies)}, expected {expected}")
    children = env["res.partner"].with_context(active_test=False).search([("parent_id", "in", companies.ids)])
    if children and not _replaying(env):
        _fail(failures, f"child partners exist before addresses: {children[:5].mapped('name')}")
    people = companies.filtered(lambda partner: not partner.is_company)
    if people:
        _fail(failures, f"imported company is a person: {people[:5].mapped('name')}")
    streets = {_digits(_cell(row, "Addr2")) for row in _rows("Address") if _cell(row, "Addr2")}
    for company in companies:
        if company.name and _digits(company.name) in streets and len(_digits(company.name)) >= 6:
            _fail(failures, f"company name equals a street: {company.id} {company.name}")
            return


def check_addresses(env, failures: list[str]) -> None:
    mapping, _reader = _erp()

    people = (
        env["res.partner"]
        .with_context(active_test=False)
        .search([("company_type", "=", "person"), ("parent_id", "!=", False)])
    )
    imported_people = people.filtered(lambda partner: partner.parent_id.id in _imported_companies(env).ids)
    if imported_people and not _replaying(env):
        _fail(failures, f"people exist before contacts: {imported_people[:5].mapped('name')}")
    for row in _rows("Address"):
        address_id = _cell(row, "AddressID")
        cp_id = _cell(row, "CpID")
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
            street = _cell(row, column)
            if street and street.upper() != "NULL" and street.casefold() in (location.name or "").casefold():
                _fail(failures, f"partner {location.id} name {location.name!r} contains street {street!r}")
                return
        if mapping.real_phone(row.get("Fax")):
            fax_digits = _digits(row.get("Fax") or "")
            numbers = [_digits(line.number) for line in location.phone_line_ids if line.label == "fax"]
            if fax_digits not in numbers:
                _fail(failures, f"location {location.id} missing fax {row.get('Fax')}")
                return
    # A CpID that has Address and Contact rows but no CounterParty row stays
    # unimported. A company is never invented for it. Checked only while the
    # active source still lacks that company.
    missing = _expect()["missing_counterparty"]
    if not _covers(missing["cp_id"]):
        if _partner(env, f"legacy_erp_cp_{missing['cp_id']}"):
            _fail(failures, f"CpID {missing['cp_id']} has no CounterParty row and must not be a company")
        for address_id in missing["address_ids"]:
            if _partner(env, f"legacy_erp_address_{address_id}"):
                _fail(failures, f"Address {address_id} for missing CpID {missing['cp_id']} was imported")
    want = _expect()["abbott"]
    if not _covers(want["cp_id"]):
        return
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


def _is_person(partner) -> bool:
    """A person: neither a company nor a site (either shape, ADR-131 predicate)."""
    return not partner.is_company and not partner._plasticos_is_site()


def _people_under(env, cp_id: str, name: str):
    company = _partner(env, f"legacy_erp_cp_{cp_id}")
    if not company:
        return env["res.partner"]
    return company.child_ids.filtered(lambda partner: _is_person(partner) and partner.name == name)


def _check_contact_sites(env, expect: dict, failures: list[str]) -> None:
    want = expect["eddie"]
    if not _covers(want["cp_id"]):
        return
    eddie = _people_under(env, want["cp_id"], want["name"])
    if len(eddie) != 1:
        _fail(failures, f"{want['name']} under {want['cp_id']} count {len(eddie)}")
    else:
        linked = eddie.location_partner_ids.mapped("name")
        if want["site"] not in linked:
            _fail(failures, f"{want['name']} sites are {linked}")
        if any(want["excluded_site_word"] in name for name in linked):
            _fail(failures, f"{want['name']} is linked to {want['excluded_site_word']}: {linked}")
    address_types = {_cell(row, "Type") for row in _rows("Address") if _cell(row, "CpID") == want["cp_id"]}
    eddie_locations = {
        _cell(row, "Location")
        for row in _rows("Contact")
        if _cell(row, "CpID") == want["cp_id"] and _cell(row, "ContactNm") == want["name"]
    }
    unmatched = eddie_locations - address_types
    if want["unmatched_site"] not in unmatched:
        _fail(failures, f"{want['unmatched_site']} not unmatched: {sorted(unmatched)}")
    want = expect["joshua"]
    joshua_rows = [
        row
        for row in _rows("Contact")
        if _cell(row, "CpID") == want["cp_id"] and _cell(row, "ContactNm") == want["name"]
    ]
    joshua = _people_under(env, want["cp_id"], want["name"])
    if len(joshua) != 1:
        _fail(failures, f"{want['name']} under {want['cp_id']} count {len(joshua)}")
    else:
        linked = set(joshua.location_partner_ids.mapped("name"))
        expected = {_cell(row, "Location") for row in joshua_rows} & address_types
        if linked != expected:
            _fail(failures, f"{want['name']} sites {sorted(linked)} expected {sorted(expected)}")


def check_contacts(env, failures: list[str]) -> None:
    mapping, _reader = _erp()

    companies = _imported_companies(env)
    grouped = defaultdict(list)
    for person in (
        env["res.partner"]
        .with_context(active_test=False)
        .search([("company_type", "=", "person"), ("parent_id", "in", companies.ids)])
    ):
        if person.name and not mapping.is_person_name(person.name):
            _fail(failures, f"partner {person.id} name is only digits: {person.name}")
            return
        if not person.active:
            # A retired person (identity migration, mailbox reconciliation) is not a visible duplicate.
            continue
        grouped[(person.parent_id.id, mapping.person_key(person.name))].append(person)
    for (parent_id, key), rows in grouped.items():
        if len(rows) > 1:
            _fail(failures, f"duplicate {key} under partner {parent_id}: {[row.id for row in rows]}")
            return
    expect = _expect()
    missing = expect["missing_counterparty"]
    if not _covers(missing["cp_id"]) and env["res.partner"].with_context(active_test=False).search_count(
        [("name", "=", missing["contact_name"])]
    ):
        _fail(
            failures,
            f"{missing['contact_name']} was imported without a CounterParty row for CpID {missing['cp_id']}",
        )
    _check_contact_sites(env, expect, failures)
    for forbidden in expect["forbidden_partner_names"]:
        if env["res.partner"].search_count([("name", "=", forbidden)]):
            _fail(failures, f"a partner is named {forbidden}")
    root = _by_xmlid(env, "res.partner.category", "legacy_erp_contact_role_root")
    tags = env["res.partner.category"].search([("parent_id", "=", root.id)]) if root else root
    if tags and not _replaying(env) and env["res.partner"].search_count([("category_id", "in", tags.ids)]):
        _fail(failures, f"{root.name} tags exist before the role file")
    want = expect["eli"]
    eli = _people_under(env, want["cp_id"], want["name"])
    if _covers(want["cp_id"]) and len(eli) != 1:
        _fail(failures, f"{want['name']} count {len(eli)}")
    elif len(eli) == 1:
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
    if not _covers(want["cp_id"]):
        return
    if not tuckahoe or tuckahoe.name != want["name"]:
        _fail(failures, f"CpID {want['cp_id']} name is {tuckahoe.name if tuckahoe else 'missing'}")
    elif want["phone"] not in _digits(tuckahoe.phone or ""):
        _fail(failures, f"{want['name']} phone is {tuckahoe.phone}")
    elif tuckahoe.child_ids.filtered(_is_person):
        _fail(failures, f"{want['name']} has a person child")


def _has_tag(partner, tag_name: str) -> bool:
    return tag_name in partner.category_id.mapped("name")


def check_roles(env, failures: list[str]) -> None:
    expect = _expect()
    tag = expect["decision_maker_tag"]
    for want in expect["decision_makers"]:
        person = _people_under(env, want["cp_id"], want["name"])
        if _covers(want["cp_id"]) and (len(person) != 1 or not _has_tag(person, tag)):
            _fail(failures, f"{want['name']} is missing the {tag} tag")
    want = expect["accounting"]
    accounting = _people_under(env, want["cp_id"], want["name"])
    if _covers(want["cp_id"]) and (len(accounting) != 1 or not _has_tag(accounting, want["tag"])):
        _fail(failures, f"{want['name']} contact under {want['cp_id']} is missing {want['tag']}")
    want = expect["unresolved_rr"]
    rr_rows = [
        row
        for row in _rows("Contact")
        if _cell(row, "ContactNm") == want["name"] and _cell(row, "CpID") == want["cp_id"]
    ]
    if _covers(want["cp_id"]) and not rr_rows:
        _fail(failures, f"{want['name']} is missing from the Contact source")
    elif rr_rows:
        contact_id = _cell(rr_rows[0], "CT_ID")
        person = _partner(env, f"legacy_erp_contact_{contact_id}")
        guessed = set(want["guessed_tags"])
        if person and guessed & set(person.category_id.mapped("name")):
            _fail(failures, f"{want['name']} has a guessed tag: {person.category_id.mapped('name')}")
        stored = env["ir.config_parameter"].get_param("plasticos_partner_import.unresolved_rr") or ""
        if contact_id not in stored.split(","):
            _fail(failures, f"{want['name']} CT_ID {contact_id} is not in the unresolved RR list")
    stamped = env["ir.config_parameter"].get_param("plasticos_partner_import.partner_count_after_contacts")
    # Direct SQL justification: a whole-table count across archived rows, after a bulk load.
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


def check_sales_reps(env, failures: list[str]) -> None:
    """Each imported company carries the user whose login its assigned rep maps to."""
    mapping, _reader = _erp()

    rows_by_cp = defaultdict(list)
    for row in _rows("SalesReps"):
        rows_by_cp[_cell(row, "CpID")].append(row)
    data = env["ir.model.data"].search(
        [("module", "=", XMLID_MODULE), ("model", "=", "res.partner"), ("name", "=like", "legacy_erp_cp_%")]
    )
    for marker in data:
        cp_id = marker.name.removeprefix("legacy_erp_cp_")
        company = env["res.partner"].with_context(active_test=False).browse(marker.res_id).exists()
        if not company:
            continue
        code, _anomaly = mapping.default_sales_rep(rows_by_cp.get(cp_id, []))
        login = mapping.sales_rep_login(code)
        users = env["res.users"].search([("login", "=ilike", login)], limit=2) if login else env["res.users"]
        if login and len(users) != 1:
            # No single Odoo user carries that login: the import reports the row
            # and leaves the Salesperson untouched. Not a validator failure.
            continue
        expected = users if len(users) == 1 else env["res.users"]
        if company.user_id != expected:
            _fail(
                failures,
                f"CpID {cp_id} Salesperson is {company.user_id.login or 'empty'}, expected {expected.login or 'empty'}",
            )
            return


CHECKS = {
    DATABASE_CHECK: check_database,
    "counterparties": check_counterparties,
    "addresses": check_addresses,
    "contacts": check_contacts,
    "roles": check_roles,
    "salesreps": check_sales_reps,
}

# The check that must pass before each import layer may open its table.
LAYER_BEFORE = {
    "counterparties": DATABASE_CHECK,
    "addresses": "counterparties",
    "contacts": "addresses",
    "roles": "contacts",
    "salesreps": "roles",
}


def validate(env, layer: str, payload=None) -> int:
    """Run one check. ``payload`` binds the checks to the rows the import read."""
    if layer not in CHECKS:
        raise SystemExit(f"ERP_LAYER must be one of {', '.join(CHECKS)}")
    if payload is not None:
        _ACTIVE_PAYLOAD["payload"] = payload
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
