"""GMP-NC-D: UNBOUNDED_SEARCH follows query intent, not spelling."""

from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "audit"))
spec = importlib.util.spec_from_file_location(
    "performance_audit_under_test",
    ROOT / "scripts" / "audit" / "performance_audit.py",
)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def _write(root: Path, source: str) -> None:
    path = root / "plasticos_sample" / "models" / "sample.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(source), encoding="utf-8")


def _findings(root: Path) -> list[dict]:
    return module.PerformanceAudit(root).check_unbounded_searches()


def _bounds(root: Path) -> list[str]:
    return [finding["bound"] for finding in _findings(root)]


def _tree(root: Path):
    return module.ast.parse((root / "plasticos_sample" / "models" / "sample.py").read_text(encoding="utf-8"))


def _verdicts(root: Path) -> list[str]:
    """Internal verdicts of searches without a proven bound, ``unknown`` included."""
    return [verdict for _call, verdict in module._unbounded_search_calls(_tree(root))]


def _all_verdicts(root: Path) -> list[str]:
    return [verdict for _call, verdict in module._search_calls(_tree(root))]


def _assert_unknown_not_reported(root: Path) -> None:
    """A proof that stopped is visible internally and is never a public finding."""
    assert _verdicts(root) == ["unknown"]
    assert _findings(root) == []


def _assert_one_population_read(root: Path) -> None:
    findings = _findings(root)
    assert [finding["bound"] for finding in findings] == ["unbounded"]
    assert "do not add limit=1" in findings[0]["fix"].lower()


def _function(body: str) -> str:
    return "def probe(self, partner, rows, statuses, ids, config, extra, limit=80):\n" + textwrap.indent(
        textwrap.dedent(body), "    "
    )


def test_multiline_limit_is_a_bound(tmp_path: Path):
    _write(
        tmp_path,
        """
        def read_one(self):
            return self.search(
                [("active", "=", True)],
                limit=1,
            )
        """,
    )
    assert _findings(tmp_path) == []


def test_regex_search_is_not_an_orm_query(tmp_path: Path):
    _write(
        tmp_path,
        """
        def parse(self, text):
            return pattern.search(text)
        """,
    )
    assert _findings(tmp_path) == []


def test_identity_predicate_is_input_bounded(tmp_path: Path):
    _write(
        tmp_path,
        """
        def for_partner(self, partner):
            return self.env["res.partner"].search(
                [("parent_id", "=", partner.id)]
            )
        """,
    )
    assert _findings(tmp_path) == []


def test_caller_supplied_identity_set_is_input_bounded(tmp_path: Path):
    _write(
        tmp_path,
        """
        def by_ids(self, statuses):
            return self.env["sale.order"].search([("id", "in", statuses)])
        """,
    )
    assert _findings(tmp_path) == []


def test_dynamic_in_on_a_non_identity_field_is_unknown(tmp_path: Path):
    _write(
        tmp_path,
        """
        def by_name(self, origins):
            return self.env["sale.order"].search([("name", "in", origins)])
        """,
    )
    _assert_unknown_not_reported(tmp_path)


def test_null_parent_is_not_an_identity_bound(tmp_path: Path):
    _write(
        tmp_path,
        """
        def orphans(self):
            return self.env["res.partner"].search([("parent_id", "=", False)])
        """,
    )
    assert len(_findings(tmp_path)) == 1


def test_state_in_list_is_not_an_identity_bound(tmp_path: Path):
    _write(
        tmp_path,
        """
        def open_rows(self):
            rows = self.search([("state", "in", ("draft", "sent"))])
            return rows
        """,
    )
    findings = _findings(tmp_path)
    assert len(findings) == 1
    assert "Add limit" not in findings[0]["fix"]
    assert "do not add limit=1" in findings[0]["fix"].lower()


def test_spelling_exemptions_do_not_hide_a_search(tmp_path: Path):
    _write(
        tmp_path,
        """
        def load_countries(self):
            # batch lookup of a small table
            country_ids = self.env["res.country"].search([])
            return country_ids
        """,
    )
    assert len(_findings(tmp_path)) == 1


def test_assigned_domain_identity_is_visible(tmp_path: Path):
    _write(
        tmp_path,
        """
        def stale(self, rec):
            domain = [("load_id", "=", rec.id)]
            domain.append(("state", "in", ("draft",)))
            return self.env["plasticos.freight.quote.request"].search(domain)
        """,
    )
    assert _findings(tmp_path) == []


def test_mapped_projection_stays_complete(tmp_path: Path):
    _write(
        tmp_path,
        """
        def codes(self):
            return self.env["plasticos.document.validation.matrix"].search(
                [("doc_category", "=", "supplier"), ("active", "=", True)]
            ).mapped("tag_id.code")
        """,
    )
    assert _findings(tmp_path) == []


def test_search_that_defines_a_returned_domain_stays_complete(tmp_path: Path):
    _write(
        tmp_path,
        """
        def _search_clear(self, value):
            txs = self.env["plasticos.transaction"].search(
                [("compliance_status", "=", value)]
            )
            return [("transaction_id", "in", txs.ids)]
        """,
    )
    assert _findings(tmp_path) == []


def test_query_intent_never_suppresses_a_loop_query(tmp_path: Path):
    """The Moderate intent rule and the High loop rule judge independently.

    An identity-bounded search is not an unbounded search, and it is still a
    query inside a loop. Neither check may consume the other's verdict, so
    this holds for any High scanner that flags a direct ``self.env`` query
    in a loop.
    """
    _write(
        tmp_path,
        """
        def walk(self, rows):
            for rec in rows:
                self.env["res.partner"].search([("id", "=", rec.id)])
        """,
    )
    assert _findings(tmp_path) == []
    loop_findings = module.PerformanceAudit(tmp_path).check_n_plus_one_queries()
    assert [finding["line"] for finding in loop_findings] == [4]


# -- D-01: only a provably positive limit is a bound -------------------------

POSITIVE_LIMITS = [
    'return self.search([("active", "=", True)], limit=5)',
    'return self.search([("active", "=", True)], 0, 10)',
    'size = 50\nreturn self.search([("active", "=", True)], limit=size)',
    'size = max(config.batch_size, 1)\nreturn self.search([("active", "=", True)], limit=size)',
    'return self.search([("active", "=", True)], limit=min(25, 100))',
]

NON_POSITIVE_LIMITS = [
    'return self.search([("active", "=", True)], limit=0)',
    'return self.search([("active", "=", True)], limit=None)',
    'return self.search([("active", "=", True)], limit=False)',
    'return self.search([("active", "=", True)], limit=-1)',
    'return self.search([("active", "=", True)], 0, None)',
    'size = 0\nreturn self.search([("active", "=", True)], limit=size)',
    'size = 10 if rows else 0\nreturn self.search([("active", "=", True)], limit=size)',
    'if rows:\n    size = 10\nelse:\n    size = None\nreturn self.search([("active", "=", True)], limit=size)',
]

UNRESOLVED_LIMITS = [
    # A parameter named ``limit`` with a positive default is not proven positive.
    'return self.search([("active", "=", True)], limit=limit)',
    'return self.search([("active", "=", True)], limit=config.batch_limit)',
    'size = config.batch_limit or 200\nreturn self.search([("active", "=", True)], limit=size)',
    'return self.search([("active", "=", True)], **extra)',
]


@pytest.mark.parametrize("body", POSITIVE_LIMITS)
def test_positive_limit_is_a_bound(tmp_path: Path, body: str):
    _write(tmp_path, _function(body))
    assert _findings(tmp_path) == []


@pytest.mark.parametrize("body", NON_POSITIVE_LIMITS)
def test_non_positive_limit_is_not_a_bound(tmp_path: Path, body: str):
    _write(tmp_path, _function(body))
    assert _bounds(tmp_path) == ["unbounded"]


@pytest.mark.parametrize("body", UNRESOLVED_LIMITS)
def test_unresolved_limit_is_unknown_not_a_bound(tmp_path: Path, body: str):
    _write(tmp_path, _function(body))
    _assert_unknown_not_reported(tmp_path)


def test_unproven_limit_still_yields_to_an_identity_domain(tmp_path: Path):
    _write(tmp_path, _function('return self.search([("partner_id", "=", partner.id)], limit=None)'))
    assert _findings(tmp_path) == []


# -- D-02: every OR branch must be bounded -----------------------------------

BOUNDED_DOMAINS = [
    '[("partner_id", "=", partner.id), ("active", "=", True)]',
    '["|", ("id", "=", partner.id), ("partner_id", "=", partner.id)]',
    '["&", ("partner_id", "=", partner.id), ("active", "=", True)]',
    '[("state", "=", "draft"), "|", ("id", "=", partner.id), ("partner_id", "=", partner.id)]',
    '["|", "|", ("id", "in", ids), ("partner_id", "=", partner.id), ("res_id", "=", partner.id)]',
]

UNBOUNDED_DOMAINS = [
    '["|", ("partner_id", "=", partner.id), ("active", "=", True)]',
    '["|", ("active", "=", True), ("partner_id", "=", partner.id)]',
    '["&", "|", ("id", "=", partner.id), ("active", "=", True), ("state", "=", "draft")]',
    '["|", ("id", "=", partner.id), "&", ("active", "=", True), ("state", "=", "draft")]',
    '["!", ("id", "=", partner.id)]',
    "[]",
]

UNRESOLVED_DOMAINS = [
    '["|", ("id", "=", partner.id)]',
    '["|", ("id", "=", partner.id), *extra]',
    '["|", ("id", "=", partner.id), extra]',
    "extra",
]


@pytest.mark.parametrize("domain", BOUNDED_DOMAINS)
def test_domain_bounded_on_every_branch_is_retained(tmp_path: Path, domain: str):
    _write(tmp_path, _function(f"return self.search({domain})"))
    assert _findings(tmp_path) == []


@pytest.mark.parametrize("domain", UNBOUNDED_DOMAINS)
def test_unbounded_or_branch_is_flagged(tmp_path: Path, domain: str):
    _write(tmp_path, _function(f"return self.search({domain})"))
    assert _bounds(tmp_path) == ["unbounded"]


@pytest.mark.parametrize("domain", UNRESOLVED_DOMAINS)
def test_unresolved_domain_structure_is_unknown(tmp_path: Path, domain: str):
    _write(tmp_path, _function(f"return self.search({domain})"))
    _assert_unknown_not_reported(tmp_path)


# -- D-03: a predicate present on only some paths is not a bound -------------


def test_conditionally_appended_identity_is_not_a_bound(tmp_path: Path):
    _write(
        tmp_path,
        _function(
            """
            domain = [("active", "=", True)]
            if partner:
                domain.append(("partner_id", "=", partner.id))
            return self.search(domain)
            """
        ),
    )
    assert _bounds(tmp_path) == ["unbounded"]


def test_identity_appended_on_both_branches_is_a_bound(tmp_path: Path):
    _write(
        tmp_path,
        _function(
            """
            domain = [("active", "=", True)]
            if partner:
                domain.append(("partner_id", "=", partner.id))
            else:
                domain += [("id", "in", ids)]
            return self.search(domain)
            """
        ),
    )
    assert _findings(tmp_path) == []


def test_identity_after_a_returning_guard_is_unconditional(tmp_path: Path):
    _write(
        tmp_path,
        _function(
            """
            domain = [("active", "=", True)]
            if not partner:
                return self.browse()
            domain.append(("partner_id", "=", partner.id))
            return self.search(domain)
            """
        ),
    )
    assert _findings(tmp_path) == []


def test_identity_assigned_on_both_branches_is_a_bound(tmp_path: Path):
    _write(
        tmp_path,
        _function(
            """
            if partner:
                domain = [("partner_id", "=", partner.id)]
            else:
                domain = [("id", "in", ids)]
            return self.search(domain)
            """
        ),
    )
    assert _findings(tmp_path) == []


def test_unconditional_identity_inside_a_loop_body_is_a_bound(tmp_path: Path):
    _write(
        tmp_path,
        _function(
            """
            Model = self.env["plasticos.freight.quote.request"]
            for rec in rows:
                domain = [("load_id", "=", rec.id), ("state", "in", ("draft", "sent"))]
                if statuses:
                    domain.append(("state", "!=", "cancelled"))
                stale = Model.search(domain)
            """
        ),
    )
    assert _findings(tmp_path) == []


def test_loop_dependent_domain_mutation_is_unknown(tmp_path: Path):
    _write(
        tmp_path,
        _function(
            """
            domain = [("partner_id", "=", partner.id)]
            for rec in rows:
                domain = ["|", *domain, ("state", "=", rec.state)]
            return self.search(domain)
            """
        ),
    )
    _assert_unknown_not_reported(tmp_path)


def test_zero_iteration_path_keeps_an_unbounded_domain(tmp_path: Path):
    _write(
        tmp_path,
        _function(
            """
            domain = [("active", "=", True)]
            for rec in rows:
                domain.append(("partner_id", "=", rec.id))
            return self.search(domain)
            """
        ),
    )
    assert _bounds(tmp_path) == ["unbounded"]


def test_unmodelled_domain_mutation_is_unknown(tmp_path: Path):
    _write(
        tmp_path,
        _function(
            """
            domain = [("partner_id", "=", partner.id)]
            domain.pop()
            return self.search(domain)
            """
        ),
    )
    _assert_unknown_not_reported(tmp_path)


def test_append_after_the_search_does_not_bound_it(tmp_path: Path):
    _write(
        tmp_path,
        _function(
            """
            domain = [("active", "=", True)]
            rows = self.search(domain)
            domain.append(("partner_id", "=", partner.id))
            return rows
            """
        ),
    )
    assert _bounds(tmp_path) == ["unbounded"]


# -- D-04: identity sets versus categorical in-lists -------------------------

IDENTITY_IN = [
    '[("id", "in", statuses)]',
    '[("partner_id", "in", [1, 2])]',
    '[("id", "in", [])]',
    '[("id", "in", partner.child_ids.ids)]',
    '[("res_id", "in", [r.id for r in rows])]',
    '[("id", "=", 7)]',
]

CATEGORICAL_OR_NULL = [
    '[("state", "in", ("draft", "sent"))]',
    '[("active", "in", [True, False])]',
    '[("id", "in", [False])]',
    '[("parent_id", "in", [partner.id, False])]',
    '[("partner_id", "=", None)]',
    '[("partner_id", "=", "Acme")]',
]

DYNAMIC_NON_IDENTITY_IN = [
    '[("state", "in", statuses)]',
    '[("state", "in", ids)]',
    '[("active", "in", partner.flags)]',
]


@pytest.mark.parametrize("domain", IDENTITY_IN)
def test_identity_collection_is_a_bound(tmp_path: Path, domain: str):
    _write(tmp_path, _function(f"return self.search({domain})"))
    assert _findings(tmp_path) == []


@pytest.mark.parametrize("domain", CATEGORICAL_OR_NULL)
def test_categorical_or_null_value_is_not_a_bound(tmp_path: Path, domain: str):
    _write(tmp_path, _function(f"return self.search({domain})"))
    assert _bounds(tmp_path) == ["unbounded"]


@pytest.mark.parametrize("domain", DYNAMIC_NON_IDENTITY_IN)
def test_dynamic_category_is_never_exempt_by_variable_name(tmp_path: Path, domain: str):
    _write(tmp_path, _function(f"return self.search({domain})"))
    _assert_unknown_not_reported(tmp_path)


# -- Public contract: only ``unbounded`` is reported -------------------------


def test_public_findings_never_carry_an_unknown_bound(tmp_path: Path):
    _write(
        tmp_path,
        """
        def known(self):
            return self.env["sale.order"].search([("state", "=", "sale")])

        def unresolved(self, origins):
            return self.env["sale.order"].search([("name", "in", origins)])
        """,
    )
    assert sorted(_verdicts(tmp_path)) == ["unbounded", "unknown"]
    assert [finding["bound"] for finding in _findings(tmp_path)] == ["unbounded"]


# -- Population reads that must keep flagging --------------------------------

POPULATION_READS = [
    'return self.env["sale.order"].search([])',
    'return self.env["sale.order"].search([("active", "=", True)])',
    'return self.env["res.partner"].search([("active", "=", True)])',
    'return self.env["sale.order"].search([("state", "in", ("draft", "sent"))])',
    'return self.env["sale.order"].search([("state", "=", "sale")])',
    'return self.env["res.partner"].search([("ref", "=like", "ERP%")])',
    'return self.env["res.partner"].search([("parent_id", "=", False)])',
]


@pytest.mark.parametrize("body", POPULATION_READS)
def test_population_read_is_one_unbounded_finding(tmp_path: Path, body: str):
    _write(tmp_path, _function(body))
    _assert_one_population_read(tmp_path)


# -- Value predicate ---------------------------------------------------------

KEY_DOMAINS = [
    '[("name", "=", name)]',
    '[("origin", "=", self.origin.strip())]',
    '[("name", "=", f"T-{partner.id}")]',
    '[("name", "in", [rec.origin for rec in self])]',
    '[("name", "in", [partner.name, partner.ref])]',
    '[("login", "=ilike", "ada")]',
    '[("login", "=like", "ada")]',
]

CATEGORY_DOMAINS = [
    '[("name", "in", ["a", "b"])]',
    '[("name", "in", [partner.name, "b"])]',
    '[("login", "=ilike", "a%")]',
    '[("login", "=like", "ada_x")]',
    '[("login", "=ilike", name + "%")]',
    '[("login", "=ilike", False)]',
]

UNRESOLVED_VALUES = [
    '[("name", "in", names)]',
    '[("name", "in", sorted(names))]',
    '[("name", "in", list(names))]',
    '[("name", "in", set(names))]',
    '[("login", "=ilike", name)]',
    '[("login", "=ilike", names[0])]',
]


def _value_function(domain: str) -> str:
    return "def probe(self, name, names, partner):\n    return self.env['res.users'].search(" + domain + ")\n"


@pytest.mark.parametrize("domain", KEY_DOMAINS)
def test_key_value_is_bounded(tmp_path: Path, domain: str):
    _write(tmp_path, _value_function(domain))
    assert _all_verdicts(tmp_path) == ["bounded"]


@pytest.mark.parametrize("domain", CATEGORY_DOMAINS)
def test_category_or_pattern_value_is_a_population_read(tmp_path: Path, domain: str):
    _write(tmp_path, _value_function(domain))
    _assert_one_population_read(tmp_path)


@pytest.mark.parametrize("domain", UNRESOLVED_VALUES)
def test_unresolved_value_is_unknown(tmp_path: Path, domain: str):
    _write(tmp_path, _value_function(domain))
    _assert_unknown_not_reported(tmp_path)


def test_like_of_a_loop_variable_is_unknown(tmp_path: Path):
    _write(
        tmp_path,
        """
        def users(self, logins):
            found = self.env["res.users"]
            for login in logins:
                found |= self.env["res.users"].search([("login", "=ilike", login)])
            return found
        """,
    )
    _assert_unknown_not_reported(tmp_path)


def test_parameter_equality_on_a_category_field_is_the_accepted_key_hole(tmp_path: Path):
    """``("state", "=", status)`` has the AST of ``("name", "=", name)``; it is a key by design."""
    _write(
        tmp_path,
        """
        def by_status(self, status):
            return self.env["sale.order"].search([("state", "=", status)])
        """,
    )
    assert _all_verdicts(tmp_path) == ["bounded"]


# -- Page floor (one helper level) -------------------------------------------

FLOOR_HELPER = """
def _param(self, key, default, cast, minimum):
    raw = self.env["ir.config_parameter"].sudo().get_param(key)
    if not raw:
        return max(default, minimum)
    return max(cast(raw), minimum)

"""


def test_helper_floor_with_a_positive_minimum_is_a_bound(tmp_path: Path):
    _write(
        tmp_path,
        FLOOR_HELPER
        + """
def backfill(self):
    size = self._param("x.batch_size", 25, int, 1)
    return self.search([("active", "=", True)], limit=size)
""",
    )
    assert _all_verdicts(tmp_path) == ["bounded"]


@pytest.mark.parametrize("minimum", ["0", "-1", "None", "True", "floor"])
def test_helper_floor_without_a_positive_minimum_is_unknown(tmp_path: Path, minimum: str):
    _write(
        tmp_path,
        FLOOR_HELPER
        + f"""
def backfill(self, floor):
    size = self._param("x.batch_size", 25, int, {minimum})
    return self.search([("active", "=", True)], limit=size)
""",
    )
    _assert_unknown_not_reported(tmp_path)


def test_helper_with_another_return_shape_is_not_a_floor(tmp_path: Path):
    _write(
        tmp_path,
        """
        def _param(self, key, minimum):
            raw = self.env["ir.config_parameter"].sudo().get_param(key)
            return int(raw) or minimum

        def backfill(self):
            return self.search([("active", "=", True)], limit=self._param("x.batch_size", 1))
        """,
    )
    _assert_unknown_not_reported(tmp_path)


def test_floor_helper_search_without_a_limit_is_a_population_read(tmp_path: Path):
    _write(
        tmp_path,
        FLOOR_HELPER
        + """
def backfill(self):
    return self.search([("active", "=", True)])
""",
    )
    _assert_one_population_read(tmp_path)


# -- Receiver model: the catalog set -----------------------------------------

CATALOG_READS = [
    """
    def polymers(self):
        Polymer = self.env["plasticos.polymer"]
        return Polymer.search([("active", "=", True)])
    """,
    """
    def rules(self):
        return self.env["plasticos.document.rule"].sudo().search([("active", "=", True)])
    """,
    """
    class PlasticosPenaltyRule(models.Model):
        _name = "plasticos.penalty.rule"

        def rules(self):
            return self.search([("active", "=", True)], order="sequence, id")
    """,
    """
    def own_xmlids(self):
        return self.env["ir.model.data"].search([("module", "=", "plasticos_x"), ("model", "=", "res.partner")])
    """,
    """
    XMLID_MODULE = "plasticos_x"

    def by_prefix(self, prefix):
        return self.env["ir.model.data"].search(
            [("module", "=", XMLID_MODULE), ("name", "=like", prefix + "%")]
        )
    """,
]

NON_CATALOG_READS = [
    """
    def rows(self):
        return self.env["sale.order"].search([("active", "=", True)])
    """,
    """
    class PlasticosOffer(models.Model):
        _name = "plasticos.offer"

        def rows(self):
            return self.search([("active", "=", True)])
    """,
    """
    def all_partner_xmlids(self):
        return self.env["ir.model.data"].search([("model", "=", "res.partner")])
    """,
    """
    def either_module(self):
        return self.env["ir.model.data"].search(["|", ("module", "=", "a"), ("model", "=", "res.partner")])
    """,
    """
    def prefixed(self):
        return self.env["ir.model.data"].search([("name", "=like", "legacy_%")])
    """,
]


@pytest.mark.parametrize("source", CATALOG_READS)
def test_catalog_read_is_bounded(tmp_path: Path, source: str):
    _write(tmp_path, source)
    assert _all_verdicts(tmp_path) == ["bounded"]


@pytest.mark.parametrize("source", NON_CATALOG_READS)
def test_non_catalog_read_is_a_population_read(tmp_path: Path, source: str):
    _write(tmp_path, source)
    _assert_one_population_read(tmp_path)


@pytest.mark.parametrize(
    "domain",
    [
        '[("module", "in", ["a", "b"]), ("model", "=", "res.partner")]',
        '["!", ("module", "=", "a"), ("model", "=", "res.partner")]',
        '[("module", "!=", "a"), ("model", "=", "res.partner")]',
    ],
)
def test_xmlid_read_without_one_constant_module_is_a_population_read(tmp_path: Path, domain: str):
    _write(tmp_path, _function(f'return self.env["ir.model.data"].search({domain})'))
    _assert_one_population_read(tmp_path)


# -- Identity field (one level) ----------------------------------------------

SPEC_MODULE = """
from typing import NamedTuple


class Spec(NamedTuple):
    order_model: str
    order_field: str


SPECS = {
    "po": Spec("purchase.order", "purchase_order_id"),
    "so": Spec("sale.order", order_field="sale_order_id"),
}


class PlasticosRequest(models.Model):
    _name = "plasticos.request"

    def by_spec(self, order, purpose):
        spec = SPECS[purpose]
        return self.search([(spec.order_field, "=", order.id), ("state", "=", "queued")])

    def by_subscript(self, order, purpose):
        field = SPECS[purpose].order_field
        return self.search([(field, "=", order.id)])

    def by_model(self, orders):
        field = next(spec.order_field for spec in SPECS.values() if spec.order_model == orders._name)
        return self.search([(field, "in", orders.ids), ("state", "=", "queued")])

    def _owner_links(self, field, bill_ids):
        return self.search([(field, "in", bill_ids)])

    def owners(self, vendor_ids, freight_ids):
        return self._owner_links("vendor_bill_ids", vendor_ids), self._owner_links("freight_bill_ids", freight_ids)

    def queue(self):
        return self.search([("state", "=", "queued")])
"""


def test_identity_field_from_a_constructor_dict_or_literal_call_sites_is_bounded(tmp_path: Path):
    _write(tmp_path, SPEC_MODULE)
    assert _verdicts(tmp_path) == ["unbounded"]
    assert [finding["code"] for finding in _findings(tmp_path)] == ['return self.search([("state", "=", "queued")])']


IDENTITY_BREAKS = [
    # one non-identity literal in the slot
    ('"so": Spec("sale.order", order_field="sale_order_id"),', '"so": Spec("sale.order", order_field="state"),'),
    # one non-literal in the slot
    ('"so": Spec("sale.order", order_field="sale_order_id"),', '"so": Spec("sale.order", order_field=FIELD),'),
]


@pytest.mark.parametrize(("old", "new"), IDENTITY_BREAKS)
def test_one_non_identity_slot_makes_the_dict_field_unknown(tmp_path: Path, old: str, new: str):
    _write(tmp_path, SPEC_MODULE.replace(old, new))
    assert sorted(_verdicts(tmp_path)) == ["unbounded", "unknown", "unknown", "unknown"]
    assert [finding["bound"] for finding in _findings(tmp_path)] == ["unbounded"]


@pytest.mark.parametrize("argument", ['"state"', "field_name"])
def test_one_non_identity_call_site_makes_the_parameter_field_unknown(tmp_path: Path, argument: str):
    _write(tmp_path, SPEC_MODULE.replace('self._owner_links("freight_bill_ids"', f"self._owner_links({argument}"))
    assert sorted(_verdicts(tmp_path)) == ["unbounded", "unknown"]


def test_registry_field_name_is_not_an_identity_field(tmp_path: Path):
    _write(
        tmp_path,
        """
        def rows(self, source, field):
            return self.env[field.model_name].search([(field.name, "=", source.id)])
        """,
    )
    _assert_unknown_not_reported(tmp_path)


# -- Completeness, one callee ------------------------------------------------

PROJECTED_ROWS = """
class PlasticosDocument(models.Model):
    _name = "plasticos.document.native"

    def _projected_rows(self, flag):
        document = self.env["plasticos.document"]
        matched = document.search([("state", "=", "accepted"), ("res_id", "!=", 0)])
        if not matched:
            return document.browse()
        return matched.filtered(flag)

    def _search_verified(self, operator, value):
        rows = self._projected_rows("verified")
        return [("plasticos_doc_id", "in", rows.ids)]

    def _search_flag(self, operator, value):
        domains = []
        domains.append(self._pair_domain(self._projected_rows("override")))
        return domains[0]
"""


def test_helper_search_feeding_a_returned_search_domain_is_complete(tmp_path: Path):
    _write(tmp_path, PROJECTED_ROWS)
    assert _all_verdicts(tmp_path) == ["bounded"]


def test_helper_search_returned_to_a_non_search_caller_is_a_population_read(tmp_path: Path):
    _write(
        tmp_path,
        PROJECTED_ROWS
        + """
    def action_open(self):
        return self._projected_rows("verified")
""",
    )
    _assert_one_population_read(tmp_path)


def test_searching_function_returning_its_recordset_is_a_population_read(tmp_path: Path):
    _write(
        tmp_path,
        """
        def accepted(self):
            matched = self.env["plasticos.document"].search([("state", "=", "accepted")])
            return matched.filtered("attachment_id")
        """,
    )
    _assert_one_population_read(tmp_path)


# -- Partner mismatch report -------------------------------------------------

PARTNER_REPORTS = [
    """
    def validate_graph(self):
        candidates = self.env["res.partner"].search(
            [("company_type", "=", "person"), "|", ("parent_id", "=", False), ("is_company", "=", True)]
        )
        errors = []
        for p in candidates:
            if not p.parent_id:
                errors.append(f"{p.name} missing parent")
        if errors:
            raise ValidationError(f"GRAPH ({len(errors)} errors)")
        _logger.info("%d checked", len(candidates))
        return True
    """,
    """
    def audit(self):
        Partner = self.env["res.partner"]
        missing = Partner.search([("company_type", "=", "person"), ("parent_id", "=", False)])
        report = [{"id": p.id, "name": p.name} for p in missing]
        return {"contacts_missing_parent": report}
    """,
]

NOT_PARTNER_REPORTS = [
    # returns the recordset
    """
    def orphans(self):
        rows = self.env["res.partner"].search([("parent_id", "=", False)])
        return rows
    """,
    # writes
    """
    def repair(self):
        missing = self.env["res.partner"].search([("parent_id", "=", False)])
        report = [p.id for p in missing]
        missing.write({"active": False})
        return report
    """,
    # assigns an attribute
    """
    def repair(self):
        missing = self.env["res.partner"].search([("parent_id", "=", False)])
        report = [p.id for p in missing]
        for p in missing:
            p.active = False
        return report
    """,
    # sliced
    """
    def sample(self):
        missing = self.env["res.partner"].search([("parent_id", "=", False)])
        return [p.id for p in missing[:10]]
    """,
    # rows not folded into the output
    """
    def notify(self):
        missing = self.env["res.partner"].search([("parent_id", "=", False)])
        for p in missing:
            p.message_post(body="x")
        return True
    """,
    # no ``= False`` term
    """
    def audit(self):
        rows = self.env["res.partner"].search([("company_type", "=", "person")])
        report = [p.id for p in rows]
        return {"people": report}
    """,
    # a transactional model is not in the partner-report class
    """
    def audit(self):
        rows = self.env["sale.order"].search([("partner_id", "=", False)])
        report = [o.id for o in rows]
        return {"orphans": report}
    """,
]


@pytest.mark.parametrize("source", PARTNER_REPORTS)
def test_partner_mismatch_report_is_bounded(tmp_path: Path, source: str):
    _write(tmp_path, source)
    assert _all_verdicts(tmp_path) == ["bounded"]


@pytest.mark.parametrize("source", NOT_PARTNER_REPORTS)
def test_not_a_partner_mismatch_report_is_a_population_read(tmp_path: Path, source: str):
    _write(tmp_path, source)
    _assert_one_population_read(tmp_path)
