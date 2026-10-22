"""The lookup index lives under docs/reports, and root reports/ stays gone."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_repo_index_is_generated_under_docs_reports() -> None:
    generator = (ROOT / "scripts/repo_generators/export_repo_indexes.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/repo-index.yml").read_text(encoding="utf-8")
    gmp_writer = (ROOT / "scripts/generate_gmp_report.py").read_text(encoding="utf-8")
    xml_audit = (ROOT / "scripts/audit/xml_field_audit.py").read_text(encoding="utf-8")

    assert 'INDEX_SUBDIR = ("docs", "reports", "repo-index")' in generator
    assert "docs/reports/repo-index" in workflow
    assert "reports/repo-index" not in workflow.replace("docs/reports/repo-index", "")
    assert 'Path("docs") / "reports" / "gmp-reports"' in gmp_writer
    assert 'Path("reports")' not in gmp_writer
    assert 'repo_root / "docs" / "reports" / "gmp-reports"' in xml_audit
    assert 'repo_root / "reports"' not in xml_audit
    assert (ROOT / "docs/reports/gmp-reports/README.md").is_file()
    assert (ROOT / "docs/reports/repo-index/class_definitions.txt").is_file()
    assert not (ROOT / "reports").exists()
    assert list(ROOT.glob("reports/**")) == []
