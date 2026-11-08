"""The lookup index lives under docs/reports, and root reports/ stays gone.

The generator indexes the tracked tree. A new module and a SKILL.md heading
are included. An ignored Python file is not.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts/repo_generators/export_repo_indexes.py"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def test_generator_indexes_tracked_modules_and_skills_only(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    addon = repo / "plasticos_sample" / "services" / "new_folder"
    addon.mkdir(parents=True)
    (repo / "plasticos_sample" / "__manifest__.py").write_text(
        "{'depends': ['base']}\n",
        encoding="utf-8",
    )
    (addon / "worker.py").write_text("def sample_hook():\n    return 1\n", encoding="utf-8")
    (repo / "plasticos_sample" / "views").mkdir()
    (repo / "plasticos_sample" / "views" / "sample_views.xml").write_text(
        "<odoo/>\n",
        encoding="utf-8",
    )
    skill = repo / "skills" / "plasticos-sample"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Sample skill\n", encoding="utf-8")
    ignored = repo / "Current Work - IGNORE"
    ignored.mkdir()
    (ignored / "scratch.py").write_text("def scratch_hook():\n    return 0\n", encoding="utf-8")
    (repo / ".gitignore").write_text("secret.py\n", encoding="utf-8")
    (repo / "secret.py").write_text("def secret_hook():\n    return 0\n", encoding="utf-8")
    (repo / "docs" / "reports").mkdir(parents=True)
    (repo / "docs" / "reports" / "noise.py").write_text("def report_noise():\n    return 0\n", encoding="utf-8")
    (repo / "docs" / "notes").mkdir(parents=True)
    (repo / "docs" / "notes" / "README.md").write_text("# Kept note\n", encoding="utf-8")

    _git(repo, "init")
    _git(repo, "add", "plasticos_sample", "skills", ".gitignore", "docs")

    completed = subprocess.run(
        [sys.executable, str(GENERATOR), str(repo)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr

    index = repo / "docs" / "reports" / "repo-index"
    dependencies = (index / "odoo_module_dependencies.txt").read_text(encoding="utf-8")
    functions = (index / "function_signatures.txt").read_text(encoding="utf-8")
    views = (index / "odoo_views.txt").read_text(encoding="utf-8")
    headings = (index / "readme_manifest.txt").read_text(encoding="utf-8")

    assert "plasticos_sample" in dependencies
    assert "depends=['base']" in dependencies
    assert "sample_hook" in functions
    assert "services/new_folder/worker.py" in functions
    assert "views/sample_views.xml" in views
    assert "skills/plasticos-sample/SKILL.md" in headings
    assert "Sample skill" in headings
    assert "scratch_hook" not in functions
    assert "secret_hook" not in functions
    assert "report_noise" not in functions
    assert "Kept note" in headings
    assert not (repo / "reports").exists()


def test_repo_index_is_generated_under_docs_reports() -> None:
    generator = GENERATOR.read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/repo-index.yml").read_text(encoding="utf-8")
    gmp_writer = (ROOT / "scripts/generate_gmp_report.py").read_text(encoding="utf-8")
    xml_audit = (ROOT / "scripts/audit/xml_field_audit.py").read_text(encoding="utf-8")

    assert 'INDEX_SUBDIR = ("docs", "reports", "repo-index")' in generator
    assert "docs/reports/repo-index" in workflow
    assert "reports/repo-index" not in workflow.replace("docs/reports/repo-index", "")
    trigger = workflow.split("jobs:", 1)[0]
    assert "workflow_dispatch:" in trigger
    assert "push:" not in trigger
    assert 'Path("docs") / "reports" / "gmp-reports"' in gmp_writer
    assert 'Path("reports")' not in gmp_writer
    assert 'repo_root / "docs" / "reports" / "gmp-reports"' in xml_audit
    assert 'repo_root / "reports"' not in xml_audit
    assert (ROOT / "docs/reports/gmp-reports/README.md").is_file()
    assert (ROOT / "docs/reports/repo-index/class_definitions.txt").is_file()
    assert not (ROOT / "reports").exists()
    assert list(ROOT.glob("reports/**")) == []
