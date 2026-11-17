"""Site as a Contact type, in both shapes (C1 lane D1, ADR-131).

A site is a partner with a parent that is either a native delivery/invoice
address or a company parented under a company. The predicate, its search
domain, the stored Contact type and the one address label are pure functions in
``plasticos_facility_profile/address_meaning.py``; the model methods
``_plasticos_is_site`` / ``_plasticos_site_domain`` / ``_compute_company_type`` /
``_inverse_company_type`` delegate to them.
"""

from __future__ import annotations

import importlib.util
import itertools
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "plasticos_facility_profile"


def _load():
    spec = importlib.util.spec_from_file_location("address_meaning_site_core", MODULE / "address_meaning.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AM = _load()
TYPES = ("contact", "delivery", "invoice", "other")


def _evaluate(domain, record):
    """Evaluate the prefix-notation domain shapes ``site_domain`` uses."""

    def leaf(term):
        field, operator, value = term
        actual = record[field]
        if operator == "=":
            return actual == value
        if operator == "!=":
            return actual != value
        if operator == "in":
            return actual in value
        raise AssertionError(f"operator {operator!r} not handled by the test evaluator")

    def parse(tokens):
        head = tokens.pop(0)
        if head == "|":
            left, right = parse(tokens), parse(tokens)
            return left or right
        if head == "&":
            left, right = parse(tokens), parse(tokens)
            return left and right
        return leaf(head)

    tokens = list(domain)
    result = True
    while tokens:
        result = parse(tokens) and result
    return result


@pytest.mark.parametrize(
    ("has_parent", "partner_type", "is_company"),
    [(True, "delivery", True), (True, "delivery", False), (True, "invoice", False), (True, "contact", True)],
)
def test_predicate_true_for_both_site_shapes(has_parent, partner_type, is_company):
    assert AM.is_site(has_parent=has_parent, partner_type=partner_type, is_company=is_company)


@pytest.mark.parametrize(
    ("has_parent", "partner_type", "is_company"),
    [(True, "contact", False), (True, "other", False), (False, "contact", True), (False, "delivery", True)],
)
def test_predicate_false_for_people_and_top_level_companies(has_parent, partner_type, is_company):
    assert not AM.is_site(has_parent=has_parent, partner_type=partner_type, is_company=is_company)


@pytest.mark.parametrize(
    ("has_parent", "partner_type", "is_company"),
    list(itertools.product((True, False), TYPES, (True, False))),
)
def test_domain_matches_the_predicate(has_parent, partner_type, is_company):
    record = {"parent_id": 7 if has_parent else False, "type": partner_type, "is_company": is_company}
    expected = AM.is_site(has_parent=has_parent, partner_type=partner_type, is_company=is_company)
    assert _evaluate(AM.site_domain(), record) is expected


@pytest.mark.parametrize(
    ("has_parent", "partner_type", "is_company", "expected"),
    [
        (True, "delivery", True, "site"),
        (True, "invoice", False, "site"),
        (True, "contact", True, "site"),
        (True, "contact", False, "person"),
        (False, "contact", True, "company"),
        (False, "contact", False, "person"),
    ],
)
def test_contact_type_compute(has_parent, partner_type, is_company, expected):
    assert AM.contact_type(has_parent=has_parent, partner_type=partner_type, is_company=is_company) == expected


def test_inverse_values():
    assert AM.contact_type_inverse("company", "contact") == (True, "contact")
    assert AM.contact_type_inverse("person", "contact") == (False, "contact")
    assert AM.contact_type_inverse("site", "contact") == (False, "delivery")
    assert AM.contact_type_inverse("site", "invoice") == (False, "invoice")
    assert AM.contact_type_inverse("site", "other") == (False, "delivery")
    assert AM.contact_type_inverse("person", "delivery") == (False, "contact")


@pytest.mark.parametrize("partner_type", TYPES)
@pytest.mark.parametrize("chosen", ("site", "person"))
def test_child_choice_round_trips(partner_type, chosen):
    is_company, new_type = AM.contact_type_inverse(chosen, partner_type)
    assert AM.contact_type(has_parent=True, partner_type=new_type, is_company=is_company) == chosen


@pytest.mark.parametrize("partner_type", TYPES)
@pytest.mark.parametrize("chosen", ("company", "person"))
def test_top_level_choice_round_trips(partner_type, chosen):
    is_company, new_type = AM.contact_type_inverse(chosen, partner_type)
    assert AM.contact_type(has_parent=False, partner_type=new_type, is_company=is_company) == chosen


@pytest.mark.parametrize(
    ("role", "label", "expected"),
    [
        ("supplier", None, "Pick-Up Address"),
        ("buyer", None, "Delivery Address"),
        ("buyer", "HOUSTON TX - PICK UP", "Pick-Up Address"),
        ("carrier", "PICK-UP", "Pick-Up Address"),
        ("carrier", None, "Site Address"),
        ("broker", "WAREHOUSE", "Site Address"),
        ("internal", None, "Site Address"),
        ("prospect", None, "Site Address"),
        ("other", None, "Site Address"),
        (None, None, "Site Address"),
    ],
)
@pytest.mark.parametrize("is_company", (True, False))
def test_site_label_per_role(role, label, expected, is_company):
    meaning = AM.address_type_meaning(
        "delivery", is_company=is_company, company_role=role, source_label=label, site=True
    )
    assert meaning == expected


@pytest.mark.parametrize("role", ("supplier", "buyer", "carrier", None))
def test_invoice_site_is_a_mailing_address(role):
    meaning = AM.address_type_meaning("invoice", is_company=False, company_role=role, source_label="PICK UP", site=True)
    assert meaning == "Mailing Address"


def test_company_itself_keeps_its_label():
    meaning = AM.address_type_meaning("contact", is_company=True, company_role="supplier", source_label=None)
    assert meaning == "This record is the company itself."


def test_person_contact_has_no_label():
    assert AM.address_type_meaning("contact", is_company=False, company_role=None, source_label=None) == ""


MODEL = (MODULE / "models" / "res_partner.py").read_text(encoding="utf-8")
FACILITY_VIEWS = (MODULE / "views" / "facility_profile_views.xml").read_text(encoding="utf-8")
PARTNER_UX = (MODULE / "views" / "partner_ux.xml").read_text(encoding="utf-8")


def test_model_exposes_the_predicate_contract():
    assert "def _plasticos_is_site(self):" in MODEL
    assert "def _plasticos_site_domain(self):" in MODEL
    assert 'selection_add=[("site", "Site")]' in MODEL
    assert '@api.depends("is_company", "parent_id", "type")\n    def _compute_company_type' in MODEL


def test_site_uses_are_routed_through_the_predicate():
    assert 'child_ids.filtered("is_company")' not in MODEL
    assert "partner.is_company and partner.parent_id" not in MODEL
    assert "if not self.is_company or not parent:" not in MODEL


def test_views_use_company_type_not_is_company_and_parent():
    for text in (FACILITY_VIEWS, PARTNER_UX):
        assert not re.search(r"is_company (and|or) (not )?parent_id", text)
        assert "not is_company or parent_id" not in text
    assert 'name="type" nolabel="1" readonly="1" invisible="address_type_meaning"' in FACILITY_VIEWS


def test_search_view_has_contact_type_filters():
    for kind in ("company", "person", "site"):
        assert f"domain=\"[('company_type', '=', '{kind}')]\"" in PARTNER_UX


def test_material_profile_section_shows_on_sites():
    assert 'ref="plasticos_material_profile.view_partner_form_material_tab"' in PARTNER_UX
    section = PARTNER_UX[PARTNER_UX.index("partner_form_material_profile_sites") :]
    assert section.count("company_type == 'person'") == 3
