"""GMP-NC-B: UNJUSTIFIED_SUDO follows same-line repo law, not nearby comments."""

from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path

AUDIT = Path(__file__).resolve().parents[1] / "scripts" / "audit"
sys.path.insert(0, str(AUDIT))
spec = importlib.util.spec_from_file_location("business_logic_audit_under_test", AUDIT / "business_logic_audit.py")
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def _write(root: Path, source: str) -> None:
    path = root / "models" / "sample.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(source), encoding="utf-8")


def _findings(root: Path) -> list[dict]:
    return module.BusinessLogicAudit(root).check_missing_access_checks()


def test_same_line_boundary_is_not_open_debt(tmp_path: Path):
    _write(
        tmp_path,
        """
        def read_param(self):
            return self.env["ir.config_parameter"].sudo()  # sudo: settings-admin parameter store
        """,
    )
    assert _findings(tmp_path) == []


def test_preceding_comment_is_not_a_boundary(tmp_path: Path):
    _write(
        tmp_path,
        """
        def read_param(self):
            # sudo: this earlier line must not count
            return self.env["ir.config_parameter"].sudo()
        """,
    )
    findings = _findings(tmp_path)
    assert len(findings) == 1
    assert findings[0]["type"] == "UNJUSTIFIED_SUDO"
    assert "preceding comment" in findings[0]["fix"]
    assert "add a comment" not in findings[0]["fix"].lower()


def test_split_line_sudo_without_boundary_is_flagged(tmp_path: Path):
    _write(
        tmp_path,
        """
        def read_param(self):
            return (
                self.env["ir.config_parameter"]
                .sudo()
                .get_param("plasticos.example")
            )
        """,
    )
    findings = _findings(tmp_path)
    assert len(findings) == 1
    assert ".sudo()" in findings[0]["code"]


def test_bare_sudo_is_flagged(tmp_path: Path):
    _write(
        tmp_path,
        """
        def read_param(self):
            return self.env["ir.config_parameter"].sudo()
        """,
    )
    assert [item["line"] for item in _findings(tmp_path)] == [3]
