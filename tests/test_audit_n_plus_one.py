"""Structural N+1 scanner regressions."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "audit"))

from performance_audit import PerformanceAudit  # noqa: E402


def _findings(tmp_path: Path, source: str):
    models = tmp_path / "models"
    models.mkdir()
    (models / "sample.py").write_text(textwrap.dedent(source), encoding="utf-8")
    return PerformanceAudit(tmp_path).check_n_plus_one_queries()


def test_self_search_inside_loop_is_a_finding(tmp_path):
    findings = _findings(
        tmp_path,
        """
        class Model:
            def run(self, xs):
                for x in xs:
                    self.search([("id", "=", x)])
        """,
    )
    assert len(findings) == 1
    assert findings[0]["type"] == "N_PLUS_ONE_QUERY"
    assert "search" in findings[0]["message"]


def test_env_alias_search_inside_loop_is_a_finding(tmp_path):
    findings = _findings(
        tmp_path,
        """
        class Model:
            def run(self, xs):
                Profile = self.env["plasticos.material.profile"]
                for x in xs:
                    Profile.search([("id", "=", x)])
        """,
    )
    assert len(findings) == 1
    assert "search" in findings[0]["message"]


def test_env_subscription_search_inside_loop_is_a_finding(tmp_path):
    findings = _findings(
        tmp_path,
        """
        class Model:
            def run(self, xs):
                for x in xs:
                    self.env["plasticos.transaction"].search([("id", "=", x)])
        """,
    )
    assert len(findings) == 1


def test_browse_alone_inside_loop_is_not_a_query_finding(tmp_path):
    findings = _findings(
        tmp_path,
        """
        class Model:
            def run(self, xs):
                for x in xs:
                    self.env["res.partner"].browse(x)
        """,
    )
    assert findings == []


def test_batch_search_before_loop_is_not_a_finding(tmp_path):
    findings = _findings(
        tmp_path,
        """
        class Model:
            def run(self, xs):
                rows = self.search([("id", "in", xs)])
                found = {row.id: row for row in rows}
                for x in xs:
                    found.get(x)
        """,
    )
    assert findings == []


def test_static_list_work_inside_loop_is_not_a_finding(tmp_path):
    findings = _findings(
        tmp_path,
        """
        class Model:
            def run(self, xs):
                bucket = []
                for x in xs:
                    bucket.append(x)
        """,
    )
    assert findings == []


def test_create_inside_loop_stays_in_the_n_plus_one_family(tmp_path):
    findings = _findings(
        tmp_path,
        """
        class Model:
            def run(self, rows):
                for row in rows:
                    self.env["plasticos.match.result"].create(row)
        """,
    )
    assert len(findings) == 1
    assert findings[0]["type"] == "N_PLUS_ONE_QUERY"
    assert "mutation in loop" in findings[0]["message"]
    assert 'self.env["plasticos.match.result"].create(row)' in findings[0]["code"]


def test_sudo_env_search_inside_loop_is_a_finding(tmp_path):
    findings = _findings(
        tmp_path,
        """
        class Model:
            def run(self, xs):
                for x in xs:
                    self.env["res.partner"].sudo().search([("id", "=", x)])
        """,
    )
    assert len(findings) == 1
    assert findings[0]["type"] == "N_PLUS_ONE_QUERY"
    assert "query in loop" in findings[0]["message"]


def test_sudo_create_inside_loop_stays_a_mutation_finding(tmp_path):
    findings = _findings(
        tmp_path,
        """
        class Model:
            def run(self, rows):
                for row in rows:
                    self.env["plasticos.match.result"].sudo().create(row)
        """,
    )
    assert len(findings) == 1
    assert "mutation in loop" in findings[0]["message"]


def test_sudo_browse_inside_loop_is_not_a_query_finding(tmp_path):
    findings = _findings(
        tmp_path,
        """
        class Model:
            def run(self, xs):
                for x in xs:
                    self.env["res.partner"].sudo().browse(x)
        """,
    )
    assert findings == []


def test_sudo_batch_search_before_loop_is_not_a_finding(tmp_path):
    findings = _findings(
        tmp_path,
        """
        class Model:
            def run(self, xs):
                rows = self.env["res.partner"].sudo().search([("id", "in", xs)])
                for row in rows:
                    row.name
        """,
    )
    assert findings == []


def test_sudo_env_alias_search_inside_loop_is_a_finding(tmp_path):
    findings = _findings(
        tmp_path,
        """
        class Model:
            def run(self, xs):
                Partner = self.env["res.partner"].sudo()
                for x in xs:
                    Partner.search([("id", "=", x)])
        """,
    )
    assert len(findings) == 1
    assert "query in loop" in findings[0]["message"]


# ── Keyset pagination is not a per-record query ─────────────────────────────
#
# ``while True: batch = Model.search([..., ("id", ">", last_id)], limit=N); last_id = batch[-1].id``
# runs one bounded query per page, not one per record. The loop's own cursor
# (derived from the previous page) advances the domain, and ``limit=`` bounds
# each page. Everything else in a loop stays a finding.


def test_keyset_pagination_with_a_bounded_page_is_not_a_finding(tmp_path):
    findings = _findings(
        tmp_path,
        """
        class Model:
            def run(self):
                NativeDoc = self.env["documents.document"]
                domain = [("plasticos_doc_id", "=", False)]
                last_id = 0
                while True:
                    batch = NativeDoc.search(
                        [*domain, ("id", ">", last_id)],
                        order="id ASC",
                        limit=200,
                    )
                    if not batch:
                        break
                    last_id = batch[-1].id
                    for doc in batch:
                        doc.name
        """,
    )
    assert findings == []


def test_per_record_search_with_a_limit_inside_a_for_loop_is_still_a_finding(tmp_path):
    findings = _findings(
        tmp_path,
        """
        class Model:
            def run(self):
                for rec in self:
                    self.search([("code", "=", rec.code), ("id", "!=", rec.id)], limit=1)
        """,
    )
    assert len(findings) == 1
    assert "query in loop" in findings[0]["message"]


def test_a_while_loop_whose_cursor_is_not_derived_from_the_page_is_still_a_finding(tmp_path):
    findings = _findings(
        tmp_path,
        """
        class Model:
            def run(self, ids):
                last_id = 0
                while ids:
                    batch = self.search([("id", ">", last_id)], limit=200)
                    last_id = ids.pop()
                    batch.name
        """,
    )
    assert len(findings) == 1


def test_a_page_search_without_a_limit_is_still_a_finding(tmp_path):
    findings = _findings(
        tmp_path,
        """
        class Model:
            def run(self):
                last_id = 0
                while True:
                    batch = self.search([("id", ">", last_id)])
                    if not batch:
                        break
                    last_id = batch[-1].id
        """,
    )
    assert len(findings) == 1


def test_a_second_query_inside_a_paginated_loop_is_still_a_finding(tmp_path):
    findings = _findings(
        tmp_path,
        """
        class Model:
            def run(self):
                last_id = 0
                while True:
                    batch = self.search([("id", ">", last_id)], limit=200)
                    if not batch:
                        break
                    last_id = batch[-1].id
                    for doc in batch:
                        self.env["plasticos.document"].search([("native_id", "=", doc.id)], limit=1)
        """,
    )
    assert len(findings) == 1
    assert 'self.env["plasticos.document"].search' in findings[0]["code"]
