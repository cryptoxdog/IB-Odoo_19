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


def test_hash_inside_string_is_not_a_comment(tmp_path: Path):
    _write(
        tmp_path,
        """
        def find(self):
            return self.env["res.partner"].sudo().search([("name", "=", "#internal")])
        """,
    )
    assert [item["line"] for item in _findings(tmp_path)] == [3]


def test_generic_comment_is_not_a_justification(tmp_path: Path):
    _write(
        tmp_path,
        """
        def read_param(self):
            return self.env["ir.config_parameter"].sudo()  # noqa
        """,
    )
    assert [item["line"] for item in _findings(tmp_path)] == [3]


def test_empty_marker_is_not_a_justification(tmp_path: Path):
    _write(
        tmp_path,
        """
        def read_param(self):
            return self.env["ir.config_parameter"].sudo()  # sudo:
        """,
    )
    assert [item["line"] for item in _findings(tmp_path)] == [3]


def test_placeholder_marker_is_not_a_justification(tmp_path: Path):
    _write(
        tmp_path,
        """
        def read_param(self):
            a = self.env["ir.config_parameter"].sudo()  # sudo: justified
            b = self.env["ir.config_parameter"].sudo()  # sudo: TODO
            return a, b
        """,
    )
    assert [item["line"] for item in _findings(tmp_path)] == [3, 4]


def test_debt_marker_with_more_words_is_not_a_justification(tmp_path: Path):
    _write(
        tmp_path,
        """
        def read_param(self):
            a = self.env["ir.config_parameter"].sudo()  # sudo: TODO add authorization
            b = self.env["ir.config_parameter"].sudo()  # sudo: FIXME later
            c = self.env["ir.config_parameter"].sudo()  # sudo: read config, xxx revisit
            return a, b, c
        """,
    )
    assert [item["line"] for item in _findings(tmp_path)] == [3, 4, 5]


def test_substantive_marker_passes_documentation_check(tmp_path: Path):
    _write(
        tmp_path,
        """
        def read_param(self):
            a = self.env["ir.config_parameter"].sudo()  # sudo: narrow documented boundary
            b = self.env["plasticos.x"].sudo().get_config()  # cron-sudo-justification: config read
            return a, b
        """,
    )
    assert _findings(tmp_path) == []


def test_sudo_text_in_string_or_comment_is_not_elevation(tmp_path: Path):
    _write(
        tmp_path,
        """
        def describe(self):
            # call .sudo() only after the guard
            note = "never use .sudo() here"
            doc = '''self.sudo().write({})'''
            return note, doc
        """,
    )
    assert _findings(tmp_path) == []


def test_multiline_chain_with_same_line_justification_passes(tmp_path: Path):
    _write(
        tmp_path,
        """
        def read_param(self):
            return (
                self.env["ir.config_parameter"]
                .sudo()  # sudo: settings-admin parameter store
                .get_param("plasticos.example")
            )
        """,
    )
    assert _findings(tmp_path) == []


def test_justification_on_a_later_chain_line_does_not_count(tmp_path: Path):
    _write(
        tmp_path,
        """
        def read_param(self):
            return (
                self.env["ir.config_parameter"]
                .sudo()
                .get_param("plasticos.example")  # sudo: on the wrong line
            )
        """,
    )
    assert [item["line"] for item in _findings(tmp_path)] == [5]


def test_finding_schema_is_preserved(tmp_path: Path):
    _write(
        tmp_path,
        """
        def read_param(self):
            return self.env["ir.config_parameter"].sudo()
        """,
    )
    (finding,) = _findings(tmp_path)
    assert set(finding) == {"type", "severity", "file", "line", "code", "message", "fix"}
    assert finding["type"] == "UNJUSTIFIED_SUDO"
    assert finding["severity"] == "MODERATE"
    assert finding["file"] == "models/sample.py"
    assert "proof of authorization" in finding["fix"]


def test_untokenizable_source_fails_closed(tmp_path: Path):
    _write(
        tmp_path,
        """
        def broken(self:
            return self.env["x"].sudo()  # sudo: documented but file does not parse
        """,
    )
    assert [item["line"] for item in _findings(tmp_path)] == [3]
