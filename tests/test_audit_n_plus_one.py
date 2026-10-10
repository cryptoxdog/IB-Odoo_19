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
