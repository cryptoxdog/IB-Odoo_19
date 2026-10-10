"""GMP-NC-D: UNBOUNDED_SEARCH follows query intent, not spelling."""

from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path

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


def test_caller_supplied_in_set_is_input_bounded(tmp_path: Path):
    _write(
        tmp_path,
        """
        def by_name(self, origins):
            return self.env["sale.order"].search([("name", "in", origins)])
        """,
    )
    assert _findings(tmp_path) == []


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


def test_n_plus_one_method_still_uses_the_line_rule(tmp_path: Path):
    _write(
        tmp_path,
        """
        def walk(self, rows):
            for rec in rows:
                self.env["res.partner"].search([("id", "=", rec.id)])
            Model = self.env["res.partner"]
            for rec in rows:
                Model.search([("id", "=", rec.id)])
        """,
    )
    findings = module.PerformanceAudit(tmp_path).check_n_plus_one_queries()
    assert len(findings) == 1
    assert "self.env" in findings[0]["code"]
