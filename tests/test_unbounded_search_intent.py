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
    assert _bounds(tmp_path) == ["unknown"]


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
    assert _bounds(tmp_path) == ["unknown"]


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
    assert _bounds(tmp_path) == ["unknown"]


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
    assert _bounds(tmp_path) == ["unknown"]


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
    assert _bounds(tmp_path) == ["unknown"]


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
    assert _bounds(tmp_path) == ["unknown"]
