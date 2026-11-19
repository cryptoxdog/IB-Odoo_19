"""ci/check_constraint_patterns.py: only a raw _sql_constraints unique is a gap.

models.Constraint and models.UniqueIndex enforce uniqueness through the ORM and
raise ValidationError, so they need no create() pre-check. The checker must
stay silent on them and keep warning on a _sql_constraints unique that has no
create() search.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ci"))

from check_constraint_patterns import check_sql_constraints_without_create_override  # noqa: E402


def _scan(tmp_path: Path, source: str) -> list[str]:
    path = tmp_path / "sample_module" / "models" / "model.py"
    path.parent.mkdir(parents=True)
    path.write_text(source, encoding="utf-8")
    return check_sql_constraints_without_create_override(path)


def test_models_constraint_unique_is_silent(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("check_constraint_patterns.WORKSPACE", tmp_path)
    issues = _scan(
        tmp_path,
        """
        from odoo import fields, models

        class SampleRule(models.Model):
            _name = "sample.rule"

            code = fields.Char()
            _constraints = [
                models.Constraint("unique(code)", "Code must be unique."),
            ]
        """,
    )
    assert issues == []


def test_models_unique_index_is_silent(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("check_constraint_patterns.WORKSPACE", tmp_path)
    issues = _scan(
        tmp_path,
        """
        from odoo import fields, models

        class SampleRule(models.Model):
            _name = "sample.rule"

            sales_rep_id = fields.Many2one("res.users")
            _unique_active_sales_rep = models.UniqueIndex(
                "(sales_rep_id) WHERE (active IS TRUE)",
                "A sales representative may have only one active rule.",
            )
        """,
    )
    assert issues == []


def test_sql_constraints_unique_without_create_search_is_reported(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("check_constraint_patterns.WORKSPACE", tmp_path)
    issues = _scan(
        tmp_path,
        """
        from odoo import fields, models

        class SampleRule(models.Model):
            _name = "sample.rule"

            code = fields.Char()
            _sql_constraints = [("code_uniq", "unique(code)", "Code must be unique!")]
        """,
    )
    assert len(issues) == 1
    assert "sample_module/models/model.py:code - SQL unique constraint without create() pre-check" in issues[0]


def test_sql_constraints_unique_with_a_create_search_is_clean(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("check_constraint_patterns.WORKSPACE", tmp_path)
    issues = _scan(
        tmp_path,
        """
        from odoo import api, fields, models
        from odoo.exceptions import ValidationError

        class SampleRule(models.Model):
            _name = "sample.rule"

            code = fields.Char()
            _sql_constraints = [("code_uniq", "unique(code)", "Code must be unique!")]

            @api.model_create_multi
            def create(self, vals_list):
                for vals in vals_list:
                    if vals.get("code") and self.search([("code", "=", vals["code"])], limit=1):
                        raise ValidationError("Code already exists.")
                return super().create(vals_list)
        """,
    )
    assert issues == []
