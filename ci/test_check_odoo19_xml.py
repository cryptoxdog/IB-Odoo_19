"""
Unit tests for ci/check_odoo19_xml.py
======================================

Tests call the actual CI functions directly and assert on the exact dict
structure they return. No parallel reimplementation — every test exercises
the real code path.

Coverage:
    - _check_view_xml_file(): all 4 patterns + clean file + edge cases
    - _check_data_xml_file(): view_mode tree detection
    - check_xml_patterns(): integration path (no git, uses glob fallback)
    - Output dict structure: file, line, pattern, message — all 4 fields
"""

import sys
import textwrap
from pathlib import Path

import pytest

# Add ci/ to path so we can import the script directly
sys.path.insert(0, str(Path(__file__).parent))
from check_odoo19_xml import _check_data_xml_file, _check_view_xml_file, check_xml_patterns


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_xml(tmp_path: Path, filename: str, content: str) -> Path:
    """Write an XML file and return its Path."""
    p = tmp_path / filename
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Pattern 1: <tree> tag
# ---------------------------------------------------------------------------


class TestTreePattern:
    def test_detects_tree_tag(self, tmp_path):
        f = write_xml(tmp_path, "view.xml", """\
            <odoo>
                <tree string="Records">
                    <field name="name"/>
                </tree>
            </odoo>
        """)
        errors = _check_view_xml_file(f)
        assert len(errors) == 1
        err = errors[0]
        assert err["file"] == str(f)
        assert err["line"] == 2
        assert err["pattern"] == "<tree>"
        assert err["message"] == "Use <list> instead of <tree> (Odoo 19)"

    def test_detects_tree_with_attributes(self, tmp_path):
        f = write_xml(tmp_path, "view.xml", """\
            <odoo>
                <tree editable="bottom" multi_edit="1">
                </tree>
            </odoo>
        """)
        errors = _check_view_xml_file(f)
        assert any(e["pattern"] == "<tree>" for e in errors)

    def test_no_false_positive_list_tag(self, tmp_path):
        f = write_xml(tmp_path, "view.xml", """\
            <odoo>
                <list string="Records">
                    <field name="name"/>
                </list>
            </odoo>
        """)
        errors = _check_view_xml_file(f)
        assert not any(e["pattern"] == "<tree>" for e in errors)

    def test_excludes_tree_txt_reference(self, tmp_path):
        """Lines referencing tree.txt should not be flagged."""
        f = write_xml(tmp_path, "view.xml", """\
            <odoo>
                <!-- see tree.txt for details -->
                <list string="Records"/>
            </odoo>
        """)
        errors = _check_view_xml_file(f)
        assert not any(e["pattern"] == "<tree>" for e in errors)

    def test_word_boundary_no_false_positive_on_treeview(self, tmp_path):
        """'treeview' should not match <tree\\b."""
        f = write_xml(tmp_path, "view.xml", """\
            <odoo>
                <field name="treeview_ids"/>
            </odoo>
        """)
        errors = _check_view_xml_file(f)
        assert not any(e["pattern"] == "<tree>" for e in errors)

    def test_line_number_is_1_indexed(self, tmp_path):
        f = write_xml(tmp_path, "view.xml", """\
            <odoo>
                <list/>
                <tree/>
            </odoo>
        """)
        errors = _check_view_xml_file(f)
        tree_errors = [e for e in errors if e["pattern"] == "<tree>"]
        assert len(tree_errors) == 1
        assert tree_errors[0]["line"] == 3


# ---------------------------------------------------------------------------
# Pattern 2: alert-* class without role
# ---------------------------------------------------------------------------


class TestAlertPattern:
    def test_detects_alert_class_without_role(self, tmp_path):
        f = write_xml(tmp_path, "view.xml", """\
            <odoo>
                <div class="alert alert-warning">No role here</div>
            </odoo>
        """)
        errors = _check_view_xml_file(f)
        assert len(errors) == 1
        err = errors[0]
        assert err["file"] == str(f)
        assert err["line"] == 2
        assert err["pattern"] == "alert without role"
        assert 'role="alert"' in err["message"] or 'role="status"' in err["message"]

    def test_no_error_when_role_present_on_same_line(self, tmp_path):
        f = write_xml(tmp_path, "view.xml", """\
            <odoo>
                <div class="alert alert-warning" role="alert">Has role</div>
            </odoo>
        """)
        errors = _check_view_xml_file(f)
        assert not any(e["pattern"] == "alert without role" for e in errors)

    def test_no_error_when_role_in_context_window(self, tmp_path):
        """role= within 3-line context window should suppress the error."""
        f = write_xml(tmp_path, "view.xml", """\
            <odoo>
                <div class="alert alert-info"
                     role="status">Context role</div>
            </odoo>
        """)
        errors = _check_view_xml_file(f)
        assert not any(e["pattern"] == "alert without role" for e in errors)

    def test_no_false_positive_non_alert_class(self, tmp_path):
        f = write_xml(tmp_path, "view.xml", """\
            <odoo>
                <div class="o_form_view">Fine</div>
            </odoo>
        """)
        errors = _check_view_xml_file(f)
        assert not any(e["pattern"] == "alert without role" for e in errors)

    def test_all_four_fields_present(self, tmp_path):
        f = write_xml(tmp_path, "view.xml", """\
            <odoo>
                <div class="alert alert-danger">Missing role</div>
            </odoo>
        """)
        errors = _check_view_xml_file(f)
        alert_errors = [e for e in errors if e["pattern"] == "alert without role"]
        assert len(alert_errors) == 1
        err = alert_errors[0]
        assert set(err.keys()) == {"file", "line", "pattern", "message"}


# ---------------------------------------------------------------------------
# Pattern 3: active_id in context
# ---------------------------------------------------------------------------


class TestActiveIdPattern:
    def test_detects_active_id_in_context(self, tmp_path):
        f = write_xml(tmp_path, "view.xml", """\
            <odoo>
                <button context="{'default_parent_id': active_id}"/>
            </odoo>
        """)
        errors = _check_view_xml_file(f)
        assert len(errors) == 1
        err = errors[0]
        assert err["file"] == str(f)
        assert err["line"] == 2
        assert err["pattern"] == "active_id in context"
        assert "id" in err["message"].lower()

    def test_no_false_positive_without_context(self, tmp_path):
        f = write_xml(tmp_path, "view.xml", """\
            <odoo>
                <field name="active_id"/>
            </odoo>
        """)
        errors = _check_view_xml_file(f)
        assert not any(e["pattern"] == "active_id in context" for e in errors)

    def test_all_four_fields_present(self, tmp_path):
        f = write_xml(tmp_path, "view.xml", """\
            <odoo>
                <button context="{'x': active_id}"/>
            </odoo>
        """)
        errors = _check_view_xml_file(f)
        active_errors = [e for e in errors if e["pattern"] == "active_id in context"]
        assert len(active_errors) == 1
        assert set(active_errors[0].keys()) == {"file", "line", "pattern", "message"}


# ---------------------------------------------------------------------------
# Pattern 4: view_mode with 'tree'
# ---------------------------------------------------------------------------


class TestViewModePattern:
    def test_detects_view_mode_tree_in_view_file(self, tmp_path):
        f = write_xml(tmp_path, "view.xml", """\
            <odoo>
                <field name="view_mode">tree,form</field>
            </odoo>
        """)
        errors = _check_view_xml_file(f)
        assert len(errors) == 1
        err = errors[0]
        assert err["file"] == str(f)
        assert err["line"] == 2
        assert err["pattern"] == "view_mode tree"
        assert err["message"] == "Use 'list' instead of 'tree' in view_mode (Odoo 19)"

    def test_detects_view_mode_tree_in_data_file(self, tmp_path):
        f = write_xml(tmp_path, "data.xml", """\
            <odoo>
                <field name="view_mode">tree,form</field>
            </odoo>
        """)
        errors = _check_data_xml_file(f)
        assert len(errors) == 1
        err = errors[0]
        assert err["file"] == str(f)
        assert err["line"] == 2
        assert err["pattern"] == "view_mode tree"

    def test_no_error_when_view_mode_is_list(self, tmp_path):
        f = write_xml(tmp_path, "view.xml", """\
            <odoo>
                <field name="view_mode">list,form</field>
            </odoo>
        """)
        errors = _check_view_xml_file(f)
        assert not any(e["pattern"] == "view_mode tree" for e in errors)

    def test_all_four_fields_present(self, tmp_path):
        f = write_xml(tmp_path, "view.xml", """\
            <odoo>
                <field name="view_mode">tree</field>
            </odoo>
        """)
        errors = _check_view_xml_file(f)
        vm_errors = [e for e in errors if e["pattern"] == "view_mode tree"]
        assert len(vm_errors) == 1
        assert set(vm_errors[0].keys()) == {"file", "line", "pattern", "message"}


# ---------------------------------------------------------------------------
# Clean file — no false positives
# ---------------------------------------------------------------------------


class TestCleanFile:
    def test_compliant_view_produces_no_errors(self, tmp_path):
        f = write_xml(tmp_path, "view.xml", """\
            <?xml version="1.0" encoding="utf-8"?>
            <odoo>
                <record id="view_partner_list" model="ir.ui.view">
                    <field name="name">res.partner.list</field>
                    <field name="model">res.partner</field>
                    <field name="arch" type="xml">
                        <list string="Partners">
                            <field name="name"/>
                            <field name="email"/>
                        </list>
                    </field>
                </record>
            </odoo>
        """)
        assert _check_view_xml_file(f) == []


# ---------------------------------------------------------------------------
# Multiple errors in one file
# ---------------------------------------------------------------------------


class TestMultipleErrors:
    def test_multiple_patterns_in_one_file(self, tmp_path):
        f = write_xml(tmp_path, "view.xml", """\
            <odoo>
                <tree string="Bad view"/>
                <button context="{'x': active_id}"/>
                <field name="view_mode">tree,form</field>
            </odoo>
        """)
        errors = _check_view_xml_file(f)
        patterns = [e["pattern"] for e in errors]
        assert "<tree>" in patterns
        assert "active_id in context" in patterns
        assert "view_mode tree" in patterns
        assert len(errors) == 3

    def test_each_error_has_correct_line_number(self, tmp_path):
        f = write_xml(tmp_path, "view.xml", """\
            <odoo>
                <tree/>
                <list/>
                <tree/>
            </odoo>
        """)
        errors = _check_view_xml_file(f)
        tree_lines = sorted(e["line"] for e in errors if e["pattern"] == "<tree>")
        assert tree_lines == [2, 4]


# ---------------------------------------------------------------------------
# File path in error dict
# ---------------------------------------------------------------------------


class TestFileField:
    def test_file_field_is_string_not_path(self, tmp_path):
        f = write_xml(tmp_path, "view.xml", "<odoo><tree/></odoo>")
        errors = _check_view_xml_file(f)
        assert errors
        assert isinstance(errors[0]["file"], str)

    def test_file_field_matches_input_path(self, tmp_path):
        f = write_xml(tmp_path, "my_view.xml", "<odoo><tree/></odoo>")
        errors = _check_view_xml_file(f)
        assert errors[0]["file"] == str(f)


# ---------------------------------------------------------------------------
# check_xml_patterns() integration (glob fallback, no git)
# ---------------------------------------------------------------------------


class TestCheckXmlPatterns:
    def test_finds_errors_via_glob_fallback(self, tmp_path, monkeypatch):
        """When git returns no files, glob fallback finds and checks files."""
        import check_odoo19_xml as mod

        # Force git to return nothing so glob fallback activates
        monkeypatch.setattr(mod, "get_git_tracked_files", lambda _: [])

        views_dir = tmp_path / "my_module" / "views"
        views_dir.mkdir(parents=True)
        (views_dir / "bad.xml").write_text("<odoo><tree/></odoo>", encoding="utf-8")

        errors = check_xml_patterns(tmp_path)
        assert any(e["pattern"] == "<tree>" for e in errors)

    def test_returns_empty_list_for_clean_tree(self, tmp_path, monkeypatch):
        import check_odoo19_xml as mod

        monkeypatch.setattr(mod, "get_git_tracked_files", lambda _: [])

        views_dir = tmp_path / "my_module" / "views"
        views_dir.mkdir(parents=True)
        (views_dir / "good.xml").write_text(
            "<odoo><list/></odoo>",
            encoding="utf-8",
        )
        errors = check_xml_patterns(tmp_path)
        assert errors == []
