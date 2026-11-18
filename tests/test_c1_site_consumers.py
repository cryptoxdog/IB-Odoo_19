"""Site consumers (campaign C1, lane D2, ADR-131): both site shapes, one owning company.

A site is an address of a company in either shape: a native delivery/invoice
address, or a company record parented under a company (``address_meaning`` from
lane D1). Consumers must never treat a site as the commercial entity and must
find sites in both shapes. Odoo is not imported: the predicate, the owning
company walk and the release parties are pure functions, and field domains and
the record rule are evaluated from their source text. Synthetic names only.
"""

from __future__ import annotations

import ast
import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plasticos_crm_sync.services import orchestrator  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AM = _load("d2_address_meaning", ROOT / "plasticos_facility_profile" / "address_meaning.py")
PS = _load("d2_partner_site", ROOT / "plasticos_intake" / "partner_site.py")
RP = _load("d2_release_parties", ROOT / "plasticos_crm_bridge" / "release_parties.py")


class Partner:
    """Stand-in res.partner: the D1 predicate and the intake owning-company walk."""

    _next = 1

    def __init__(self, name, parent=None, address_type="contact", is_company=False, purchase_order_count=0):
        self.id = Partner._next
        Partner._next += 1
        self.name = self.display_name = name
        self.parent_id = parent
        self.type = address_type
        self.is_company = is_company
        self.purchase_order_count = purchase_order_count
        self.is_facility = False
        self.child_ids = Children()
        if parent is not None:
            parent.child_ids.append(self)

    def __repr__(self):
        return f"<{self.name}>"

    @property
    def company_type(self):
        return AM.contact_type(has_parent=bool(self.parent_id), partner_type=self.type, is_company=self.is_company)

    def _plasticos_is_site(self):
        return AM.is_site(has_parent=bool(self.parent_id), partner_type=self.type, is_company=self.is_company)

    def _plasticos_site_company(self):
        return PS.site_company(self)

    def __getitem__(self, field):
        return getattr(self, field)


class Children(list):
    def filtered(self, predicate):
        return Children(child for child in self if predicate(child))


def _world():
    buyer = Partner("Buyer Co", is_company=True)
    company_site = Partner("Buyer Plant", parent=buyer, is_company=True)  # today's ERP shape
    delivery_site = Partner("Buyer Dock", parent=buyer, address_type="delivery")  # after the data phase
    person = Partner("Pat Doe", parent=buyer)
    person_at_site = Partner("Lee Roe", parent=company_site)
    return buyer, company_site, delivery_site, person, person_at_site


# Owning company ---------------------------------------------------------------
def test_site_company_resolves_both_site_shapes_and_people_to_the_company():
    buyer, company_site, delivery_site, person, person_at_site = _world()
    for partner in (buyer, company_site, delivery_site, person, person_at_site):
        assert partner._plasticos_site_company() is buyer, partner


def test_site_company_of_a_lone_person_is_empty():
    assert Partner("Solo Person")._plasticos_site_company() is None


# Opportunity hand-off -----------------------------------------------------------
@pytest.mark.parametrize("facility_shape", ["company", "delivery"])
@pytest.mark.parametrize("supplier_shape", ["company", "site", "delivery", "person"])
def test_release_customer_is_the_buyer_company_ship_to_the_facility_vendor_the_supplier_company(
    facility_shape, supplier_shape
):
    buyer, company_site, delivery_site, _person, _ = _world()
    facility = company_site if facility_shape == "company" else delivery_site
    supplier_co = Partner("Supplier Co", is_company=True)
    supplier = {
        "company": supplier_co,
        "site": Partner("Supplier Yard", parent=supplier_co, is_company=True),
        "delivery": Partner("Supplier Pickup", parent=supplier_co, address_type="delivery"),
        "person": Partner("Sam Seller", parent=supplier_co),
    }[supplier_shape]
    parties = RP.release_parties(supplier, facility)
    assert parties["customer"] is buyer
    assert parties["ship_to"] is facility
    assert parties["vendor"] is supplier_co
    assert not parties["customer"]._plasticos_is_site() and not parties["vendor"]._plasticos_is_site()


def test_release_refuses_a_facility_or_supplier_with_no_company():
    buyer, company_site, *_ = _world()
    with pytest.raises(RP.ReleasePartyError):
        RP.release_parties(Partner("Solo Seller"), company_site)
    with pytest.raises(RP.ReleasePartyError):
        RP.release_parties(buyer, Partner("Loose Dock", address_type="delivery"))


def _function_source(path, name):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(source, node)


def test_submit_release_issues_the_orders_to_the_release_parties():
    body = _function_source(ROOT / "plasticos_crm_bridge" / "models" / "crm_lead.py", "action_submit_release")
    assert "release_parties(self.partner_id, self.release_buyer_facility_id)" in body
    assert '"partner_id": parties["vendor"].id' in body, "purchase order vendor is the supplier company"
    assert '"partner_id": parties["ship_to"].id' in body, "sale order customer is the facility"
    assert '"partner_shipping_id": parties["ship_to"].id' in body, "the facility is the delivery address"
    assert '"supplier_id": parties["vendor"].id' in body
    assert 'parties["customer"] != self.release_buyer_company_id' in body
    assert '"partner_id": self.release_buyer_facility_id.id' not in body
    assert '"partner_id": self.partner_id.id' not in body


# CRM sync -----------------------------------------------------------------------
class _Lead:
    id = 7

    def __init__(self, partner):
        self.partner_id = partner


@pytest.mark.parametrize("shape", ["company", "delivery"])
def test_verified_company_of_a_site_is_its_parent_company(shape):
    buyer, company_site, delivery_site, *_ = _world()
    site = company_site if shape == "company" else delivery_site
    assert orchestrator._verified_company(_Lead(site), None) is buyer
    assert orchestrator._verified_company(None, site) is buyer
    assert orchestrator._verified_company(_Lead(site), buyer) is buyer, "the same company once"


def test_verified_company_of_two_companies_is_none():
    buyer, *_ = _world()
    other = Partner("Other Co", is_company=True)
    assert orchestrator._verified_company(_Lead(buyer), other) is None


def test_facility_for_material_finds_the_one_site_in_either_shape():
    buyer = Partner("Lone Co", is_company=True)
    dock = Partner("Lone Dock", parent=buyer, address_type="delivery")
    Partner("Lone Person", parent=buyer)
    facility, reason = orchestrator._facility_for_material(_Lead(buyer))
    assert (list(facility), reason) == ([dock], ""), "the one child site, as a one-record set"
    person_at_dock = Partner("Dock Person", parent=dock)
    assert orchestrator._facility_for_material(_Lead(person_at_dock)) == (dock, "")


def test_facility_for_material_with_two_sites_stays_unresolved():
    buyer, *_ = _world()
    facility, reason = orchestrator._facility_for_material(_Lead(buyer))
    assert facility is None and "ambiguous" in reason


# Intake domains -----------------------------------------------------------------
def _field_domain(path, field):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == field for t in node.targets):
            call = node.value
            for keyword in call.keywords:
                if keyword.arg == "domain":
                    return ast.literal_eval(keyword.value)
    raise AssertionError(f"{field} has no domain")


def _evaluate(domain, record, **names):
    """Evaluate a prefix-notation domain; a bare name on the right side is a form value."""

    def value(raw):
        return names[raw] if isinstance(raw, str) and raw in names else raw

    def leaf(term):
        field, operator, right = term
        actual = record[field]
        right = value(right)
        if field == "id" or field.endswith("_id"):
            actual = getattr(actual, "id", actual)
            right = getattr(right, "id", right)
        if operator == "=":
            return actual == right
        if operator == "!=":
            return actual != right
        if operator == "in":
            if isinstance(actual, list):  # a many2many "in" one id: the relation contains it
                return getattr(right, "id", right) in [getattr(item, "id", item) for item in actual]
            return actual in right
        if operator == ">":
            return actual > right
        raise AssertionError(f"operator {operator!r} not handled")

    def parse(tokens):
        head = tokens.pop(0)
        if head in ("|", "&"):
            left, right = parse(tokens), parse(tokens)
            return (left or right) if head == "|" else (left and right)
        return leaf(head)

    tokens = list(domain)
    result = True
    while tokens:
        result = parse(tokens) and result
    return result


def _domain_from_text(text, **names):
    tree = ast.parse(text, mode="eval")

    class Names(ast.NodeTransformer):
        def visit_Name(self, node):
            return ast.copy_location(ast.Constant(node.id), node)

    return ast.literal_eval(Names().visit(tree)), names


INTAKE = ROOT / "plasticos_intake" / "models" / "intake.py"


def test_intake_facility_domain_accepts_the_company_and_both_site_shapes_only():
    buyer, company_site, delivery_site, person, _ = _world()
    domain, _ = _domain_from_text(_field_domain(INTAKE, "facility_id"))
    accepted = [p for p in (buyer, company_site, delivery_site, person) if _evaluate(domain, p, partner_id=buyer)]
    assert accepted == [buyer, company_site, delivery_site]


def test_intake_contact_domain_never_offers_a_site():
    buyer, company_site, delivery_site, person, person_at_site = _world()
    domain, _ = _domain_from_text(_field_domain(INTAKE, "contact_id"))
    for partner in (person, delivery_site, company_site):
        partner.location_partner_ids = []
    offered = [
        p
        for p in (person, delivery_site, company_site)
        if _evaluate(domain, p, partner_id=buyer, facility_id=company_site)
    ]
    assert offered == [person]


def test_intake_facility_onchange_searches_the_site_domain():
    body = _function_source(INTAKE, "_onchange_partner_id")
    assert "_plasticos_site_domain()" in body
    assert '("is_company", "=", True)' not in body


# Logistics record rule ------------------------------------------------------------
def test_logistics_rule_shows_every_site_in_both_shapes():
    xml = (ROOT / "plasticos_web_leads" / "data" / "logistics_ir_rules.xml").read_text(encoding="utf-8")
    record = re.search(r'id="rule_logistics_partner_confirmed_po".*?</record>', xml, re.S).group(0)
    domain_text = re.search(r'<field name="domain_force">(.*?)</field>', record, re.S).group(1)
    domain = ast.literal_eval(domain_text)
    buyer, company_site, delivery_site, person, _ = _world()
    assert _evaluate(domain, company_site), "a company-shaped site without its own purchase orders"
    assert _evaluate(domain, delivery_site)
    assert _evaluate(domain, person)
    assert not _evaluate(domain, buyer), "a company without confirmed purchase orders stays hidden"
    buyer.purchase_order_count = 1
    assert _evaluate(domain, buyer)
