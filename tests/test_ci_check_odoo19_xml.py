"""
Unit tests for ci/check_odoo19_xml.py

Tests the actual CI functions with controlled XML input and asserts on dict output.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ci.check_odoo19_xml import (
    _check_data_xml_file,
    _check_view_xml_file,
    check_xml_patterns,
)


class TestCheckViewXmlFile(unittest.TestCase):
    """Test _check_view_xml_file function with controlled XML input."""

    def _create_temp_xml(self, content: str) -> Path:
        """Create a temporary XML file with given content."""
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False)
        tmp.write(content)
        tmp.close()
        return Path(tmp.name)

    # =========================================================================
    # Pattern 1: <tree> tag detection
    # =========================================================================

    def test_tree_tag_detected(self):
        """<tree> tag should produce error with correct dict fields."""
        xml_content = """<?xml version="1.0"?>
<odoo>
    <record id="view_test" model="ir.ui.view">
        <field name="arch" type="xml">
            <tree string="Test">
                <field name="name"/>
            </tree>
        </field>
    </record>
</odoo>"""
        xml_file = self._create_temp_xml(xml_content)
        try:
            errors = _check_view_xml_file(xml_file)

            # Only opening <tree> tag is detected (regex uses \b word boundary)
            # Closing </tree> doesn't match r"<tree\b" pattern
            self.assertEqual(len(errors), 1)

            err = errors[0]
            self.assertEqual(err["file"], str(xml_file))
            self.assertEqual(err["line"], 5)
            self.assertEqual(err["pattern"], "<tree>")
            self.assertEqual(err["message"], "Use <list> instead of <tree> (Odoo 19)")
        finally:
            xml_file.unlink()

    def test_tree_tag_not_detected_in_comment(self):
        """<tree> in XML content (not as view type) should not trigger."""
        xml_content = """<?xml version="1.0"?>
<odoo>
    <!-- This references tree.txt file -->
    <record id="view_test" model="ir.ui.view">
        <field name="name">tree.txt reference</field>
    </record>
</odoo>"""
        xml_file = self._create_temp_xml(xml_content)
        try:
            errors = _check_view_xml_file(xml_file)
            self.assertEqual(len(errors), 0)
        finally:
            xml_file.unlink()

    def test_list_tag_no_error(self):
        """<list> tag (correct Odoo 19 pattern) should not produce error."""
        xml_content = """<?xml version="1.0"?>
<odoo>
    <record id="view_test" model="ir.ui.view">
        <field name="arch" type="xml">
            <list string="Test">
                <field name="name"/>
            </list>
        </field>
    </record>
</odoo>"""
        xml_file = self._create_temp_xml(xml_content)
        try:
            errors = _check_view_xml_file(xml_file)
            self.assertEqual(len(errors), 0)
        finally:
            xml_file.unlink()

    # =========================================================================
    # Pattern 2: alert-* class without role attribute
    # =========================================================================

    def test_alert_without_role_detected(self):
        """alert class without role attribute should produce error."""
        xml_content = """<?xml version="1.0"?>
<odoo>
    <record id="view_test" model="ir.ui.view">
        <field name="arch" type="xml">
            <form>
                <div class="alert alert-warning">Warning message</div>
            </form>
        </field>
    </record>
</odoo>"""
        xml_file = self._create_temp_xml(xml_content)
        try:
            errors = _check_view_xml_file(xml_file)

            self.assertEqual(len(errors), 1)
            err = errors[0]
            self.assertEqual(err["file"], str(xml_file))
            self.assertEqual(err["line"], 6)
            self.assertEqual(err["pattern"], "alert without role")
            self.assertEqual(
                err["message"],
                'Elements with alert-* class must have role attribute. Add role="alert" or role="status"',
            )
        finally:
            xml_file.unlink()

    def test_alert_with_role_no_error(self):
        """alert class with role attribute should not produce error."""
        xml_content = """<?xml version="1.0"?>
<odoo>
    <record id="view_test" model="ir.ui.view">
        <field name="arch" type="xml">
            <form>
                <div class="alert alert-warning" role="alert">Warning message</div>
            </form>
        </field>
    </record>
</odoo>"""
        xml_file = self._create_temp_xml(xml_content)
        try:
            errors = _check_view_xml_file(xml_file)
            self.assertEqual(len(errors), 0)
        finally:
            xml_file.unlink()

    def test_alert_with_role_in_context_no_error(self):
        """alert class with role on nearby line (within 3-line context) should not error."""
        xml_content = """<?xml version="1.0"?>
<odoo>
    <record id="view_test" model="ir.ui.view">
        <field name="arch" type="xml">
            <form>
                <div class="alert alert-danger"
                     role="alert">
                    Error message
                </div>
            </form>
        </field>
    </record>
</odoo>"""
        xml_file = self._create_temp_xml(xml_content)
        try:
            errors = _check_view_xml_file(xml_file)
            self.assertEqual(len(errors), 0)
        finally:
            xml_file.unlink()

    # =========================================================================
    # Pattern 3: active_id in context
    # =========================================================================

    def test_active_id_in_context_detected(self):
        """active_id in context should produce error.

        NOTE: The regex r"context=.*active_id" requires literal 'context=' as an
        XML attribute assignment (e.g., context="..." on a button), NOT as a
        field name (e.g., <field name="context">).
        """
        # This matches the actual regex pattern: context=.*active_id
        # The pattern appears on buttons, not on <field name="context"> elements
        xml_content = """<?xml version="1.0"?>
<odoo>
    <record id="view_test" model="ir.ui.view">
        <field name="arch" type="xml">
            <form>
                <button name="action" context="{'default_partner_id': active_id}"/>
            </form>
        </field>
    </record>
</odoo>"""
        xml_file = self._create_temp_xml(xml_content)
        try:
            errors = _check_view_xml_file(xml_file)

            # The regex r"context=.*active_id" matches 'context=' as attribute
            self.assertEqual(len(errors), 1)
            err = errors[0]
            self.assertEqual(err["file"], str(xml_file))
            self.assertEqual(err["line"], 6)
            self.assertEqual(err["pattern"], "active_id in context")
            self.assertEqual(
                err["message"],
                "active_id is a client-side variable, not a field. Use 'id' instead in view context",
            )
        finally:
            xml_file.unlink()

    def test_active_id_without_context_equals_not_detected(self):
        """active_id without 'context=' pattern should NOT be detected.

        This tests the actual regex behavior: r"context=.*active_id"
        The regex requires 'context=' literally on the line.
        """
        # This does NOT match because there's no 'context=' on the line
        xml_content = """<?xml version="1.0"?>
<odoo>
    <record id="action_test" model="ir.actions.act_window">
        <field name="context">{'default_partner_id': active_id}</field>
    </record>
</odoo>"""
        xml_file = self._create_temp_xml(xml_content)
        try:
            errors = _check_view_xml_file(xml_file)
            # The line has name="context" not context=, so regex doesn't match
            self.assertEqual(len(errors), 0)
        finally:
            xml_file.unlink()

    def test_id_in_context_no_error(self):
        """Using 'id' instead of 'active_id' should not produce error."""
        xml_content = """<?xml version="1.0"?>
<odoo>
    <record id="action_test" model="ir.actions.act_window">
        <field name="context">{'default_partner_id': id}</field>
    </record>
</odoo>"""
        xml_file = self._create_temp_xml(xml_content)
        try:
            errors = _check_view_xml_file(xml_file)
            self.assertEqual(len(errors), 0)
        finally:
            xml_file.unlink()

    # =========================================================================
    # Pattern 4: view_mode with 'tree'
    # =========================================================================

    def test_view_mode_tree_detected(self):
        """view_mode containing 'tree' should produce error."""
        xml_content = """<?xml version="1.0"?>
<odoo>
    <record id="action_test" model="ir.actions.act_window">
        <field name="view_mode">tree,form</field>
    </record>
</odoo>"""
        xml_file = self._create_temp_xml(xml_content)
        try:
            errors = _check_view_xml_file(xml_file)

            self.assertEqual(len(errors), 1)
            err = errors[0]
            self.assertEqual(err["file"], str(xml_file))
            self.assertEqual(err["line"], 4)
            self.assertEqual(err["pattern"], "view_mode tree")
            self.assertEqual(err["message"], "Use 'list' instead of 'tree' in view_mode (Odoo 19)")
        finally:
            xml_file.unlink()

    def test_view_mode_list_no_error(self):
        """view_mode with 'list' (correct Odoo 19 pattern) should not produce error."""
        xml_content = """<?xml version="1.0"?>
<odoo>
    <record id="action_test" model="ir.actions.act_window">
        <field name="view_mode">list,form</field>
    </record>
</odoo>"""
        xml_file = self._create_temp_xml(xml_content)
        try:
            errors = _check_view_xml_file(xml_file)
            self.assertEqual(len(errors), 0)
        finally:
            xml_file.unlink()

    # =========================================================================
    # Multiple patterns in single file
    # =========================================================================

    def test_multiple_errors_in_single_file(self):
        """Multiple violations should all be detected with correct line numbers."""
        xml_content = """<?xml version="1.0"?>
<odoo>
    <record id="view_test" model="ir.ui.view">
        <field name="arch" type="xml">
            <tree string="Test">
                <field name="name"/>
                <button name="action" context="{'default_id': active_id}"/>
            </tree>
        </field>
    </record>
    <record id="action_test" model="ir.actions.act_window">
        <field name="view_mode">tree,form</field>
    </record>
</odoo>"""
        xml_file = self._create_temp_xml(xml_content)
        try:
            errors = _check_view_xml_file(xml_file)

            # Should detect:
            # - 1x <tree> opening tag (closing </tree> doesn't match r"<tree\b")
            # - 1x view_mode tree
            # - 1x active_id in context (requires context= as attribute)
            self.assertEqual(len(errors), 3)

            patterns_found = [e["pattern"] for e in errors]
            self.assertIn("<tree>", patterns_found)
            self.assertIn("view_mode tree", patterns_found)
            self.assertIn("active_id in context", patterns_found)

            # Verify line numbers are correct
            lines_by_pattern = {e["pattern"]: e["line"] for e in errors}
            self.assertEqual(lines_by_pattern["<tree>"], 5)
            self.assertEqual(lines_by_pattern["active_id in context"], 7)
            self.assertEqual(lines_by_pattern["view_mode tree"], 12)
        finally:
            xml_file.unlink()

    # =========================================================================
    # Error dict structure validation
    # =========================================================================

    def test_error_dict_has_all_required_keys(self):
        """Every error dict must have exactly: file, line, pattern, message."""
        xml_content = """<?xml version="1.0"?>
<odoo>
    <tree>test</tree>
</odoo>"""
        xml_file = self._create_temp_xml(xml_content)
        try:
            errors = _check_view_xml_file(xml_file)

            self.assertGreater(len(errors), 0)
            for err in errors:
                self.assertIn("file", err)
                self.assertIn("line", err)
                self.assertIn("pattern", err)
                self.assertIn("message", err)
                self.assertEqual(len(err), 4)  # Exactly 4 keys
        finally:
            xml_file.unlink()

    def test_error_dict_types(self):
        """Verify correct types for each dict field."""
        xml_content = """<?xml version="1.0"?>
<odoo>
    <tree>test</tree>
</odoo>"""
        xml_file = self._create_temp_xml(xml_content)
        try:
            errors = _check_view_xml_file(xml_file)

            self.assertGreater(len(errors), 0)
            err = errors[0]
            self.assertIsInstance(err["file"], str)
            self.assertIsInstance(err["line"], int)
            self.assertIsInstance(err["pattern"], str)
            self.assertIsInstance(err["message"], str)
        finally:
            xml_file.unlink()


class TestCheckDataXmlFile(unittest.TestCase):
    """Test _check_data_xml_file function."""

    def _create_temp_xml(self, content: str) -> Path:
        """Create a temporary XML file with given content."""
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False)
        tmp.write(content)
        tmp.close()
        return Path(tmp.name)

    def test_view_mode_tree_in_data_file(self):
        """view_mode tree in data XML should be detected."""
        xml_content = """<?xml version="1.0"?>
<odoo>
    <record id="action_test" model="ir.actions.act_window">
        <field name="view_mode">tree,form</field>
    </record>
</odoo>"""
        xml_file = self._create_temp_xml(xml_content)
        try:
            errors = _check_data_xml_file(xml_file)

            self.assertEqual(len(errors), 1)
            err = errors[0]
            self.assertEqual(err["file"], str(xml_file))
            self.assertEqual(err["line"], 4)
            self.assertEqual(err["pattern"], "view_mode tree")
            self.assertEqual(err["message"], "Use 'list' instead of 'tree' in view_mode (Odoo 19)")
        finally:
            xml_file.unlink()

    def test_data_file_only_checks_view_mode(self):
        """Data file checker should ONLY check view_mode, not other patterns."""
        xml_content = """<?xml version="1.0"?>
<odoo>
    <tree>This should NOT be flagged by data checker</tree>
    <div class="alert alert-warning">Also not flagged</div>
    <field name="context">{'id': active_id}</field>
</odoo>"""
        xml_file = self._create_temp_xml(xml_content)
        try:
            errors = _check_data_xml_file(xml_file)
            # Data file checker only looks for view_mode tree
            self.assertEqual(len(errors), 0)
        finally:
            xml_file.unlink()


class TestCheckXmlPatterns(unittest.TestCase):
    """Test check_xml_patterns integration function."""

    def test_empty_directory_returns_empty_list(self):
        """Empty directory should return empty error list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            errors = check_xml_patterns(Path(tmpdir))
            self.assertEqual(errors, [])

    def test_clean_files_return_empty_list(self):
        """Directory with compliant XML should return empty error list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            views_dir = Path(tmpdir) / "test_module" / "views"
            views_dir.mkdir(parents=True)

            xml_file = views_dir / "test_views.xml"
            xml_file.write_text("""<?xml version="1.0"?>
<odoo>
    <record id="view_test" model="ir.ui.view">
        <field name="arch" type="xml">
            <list string="Test">
                <field name="name"/>
            </list>
        </field>
    </record>
</odoo>""")

            errors = check_xml_patterns(Path(tmpdir))
            self.assertEqual(errors, [])


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""

    def _create_temp_xml(self, content: str) -> Path:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False)
        tmp.write(content)
        tmp.close()
        return Path(tmp.name)

    def test_empty_file(self):
        """Empty XML file should return empty error list."""
        xml_file = self._create_temp_xml("")
        try:
            errors = _check_view_xml_file(xml_file)
            self.assertEqual(errors, [])
        finally:
            xml_file.unlink()

    def test_nonexistent_file(self):
        """Nonexistent file should return empty error list (graceful handling)."""
        errors = _check_view_xml_file(Path("/nonexistent/file.xml"))
        self.assertEqual(errors, [])

    def test_line_numbers_are_1_indexed(self):
        """Line numbers should be 1-indexed (first line = 1, not 0)."""
        xml_content = "<tree>test</tree>"  # Single line file
        xml_file = self._create_temp_xml(xml_content)
        try:
            errors = _check_view_xml_file(xml_file)
            self.assertEqual(len(errors), 1)
            self.assertEqual(errors[0]["line"], 1)  # First line is 1, not 0
        finally:
            xml_file.unlink()

    def test_tree_word_boundary(self):
        """<tree> detection should use word boundary (not match 'treeview')."""
        xml_content = """<?xml version="1.0"?>
<odoo>
    <field name="treeview_id">123</field>
    <tree>actual tree tag</tree>
</odoo>"""
        xml_file = self._create_temp_xml(xml_content)
        try:
            errors = _check_view_xml_file(xml_file)
            # Should only detect the actual <tree> tag, not 'treeview_id'
            self.assertEqual(len(errors), 1)
            self.assertEqual(errors[0]["line"], 4)
        finally:
            xml_file.unlink()


if __name__ == "__main__":
    unittest.main()
