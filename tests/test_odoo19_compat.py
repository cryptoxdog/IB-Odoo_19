"""Odoo 19 API and XML compatibility tests.

Covers:
    - group_ids vs groups_id field naming (Odoo 19 uses group_ids)
    - XML category_id removal (deprecated in Odoo 19)
    - @api.depends("id") prohibition
    - Deprecated API usage detection
"""

import glob
import os
import re
import unittest

# Modules to scan
_PLASTICOS_MODULES = [
    "plasticos_base",
    "plasticos_intake",
    "plasticos_offer",
    "plasticos_transaction",
    "plasticos_logistics",
    "plasticos_automation",
    "plasticos_crm_bridge",
    "plasticos_documents",
    "plasticos_documents_native",
    "plasticos_facility_profile",
    "plasticos_partner_import",
    "plasticos_security_base",
    "plasticos_buyer_match_engine",
    "plasticos_claims",
    "plasticos_commission",
    "plasticos_enrichment",
    "plasticos_enrichment_bridge",
    "plasticos_geolocalize",
    "plasticos_intake_normalizer",
    "plasticos_matching",
    "plasticos_material_profile",
    "plasticos_order_lines",
    "plasticos_product",
    "plasticos_web_leads",
]


def _find_py_files():
    files = []
    for mod in _PLASTICOS_MODULES:
        if os.path.isdir(mod):
            for py in glob.glob(f"{mod}/**/*.py", recursive=True):
                files.append(py)
    return files


def _find_xml_files():
    files = []
    for mod in _PLASTICOS_MODULES:
        if os.path.isdir(mod):
            for xml in glob.glob(f"{mod}/**/*.xml", recursive=True):
                files.append(xml)
    return files


class TestOdoo19APICompat(unittest.TestCase):
    """Verify Python code uses Odoo 19 API patterns."""

    def test_no_groups_id_singular(self):
        """Odoo 19 renamed groups_id → group_ids on ir.model.access CSV files.

        NOTE: groups_id on res.users is still valid (user.groups_id |= group).
        This test only checks for deprecated usage in ir.model.access contexts.
        """
        violations = []
        for py_file in _find_py_files():
            # Skip test files - they legitimately use groups_id for user manipulation
            if "/tests/" in py_file:
                continue
            with open(py_file) as f:
                content = f.read()
            # Match 'groups_id' in ir.model.access context only
            for i, line in enumerate(content.split("\n"), 1):
                if "groups_id" in line and "group_ids" not in line:
                    stripped = line.strip()
                    # Allow comments, docstrings, and explanatory text
                    if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                        continue
                    # Allow if it's inside a multi-line docstring (check previous lines)
                    if '"""' in content[: content.find(line)] and content[: content.find(line)].count('"""') % 2 == 1:
                        continue
                    # Allow user.groups_id manipulation (valid in Odoo 19)
                    if ".groups_id" in line or "['groups_id']" in line or '["groups_id"]' in line:
                        continue
                    violations.append(f"{py_file}:{i}: {stripped}")
        self.assertEqual(violations, [], "Found deprecated groups_id usage:\n" + "\n".join(violations))

    def test_no_api_depends_id(self):
        """@api.depends('id') is prohibited in Odoo 19."""
        violations = []
        pattern = re.compile(r"@api\.depends\(['\"]id['\"]\)")
        for py_file in _find_py_files():
            with open(py_file) as f:
                for i, line in enumerate(f, 1):
                    if pattern.search(line):
                        violations.append(f"{py_file}:{i}: {line.strip()}")
        self.assertEqual(violations, [], "Found @api.depends('id'):\n" + "\n".join(violations))

    def test_no_deprecated_api_multi(self):
        """@api.multi was removed in Odoo 13+."""
        violations = []
        for py_file in _find_py_files():
            with open(py_file) as f:
                for i, line in enumerate(f, 1):
                    if "@api.multi" in line and not line.strip().startswith("#"):
                        violations.append(f"{py_file}:{i}: {line.strip()}")
        self.assertEqual(violations, [], "Found deprecated @api.multi:\n" + "\n".join(violations))

    def test_no_deprecated_api_one(self):
        """@api.one was removed in Odoo 13+."""
        violations = []
        for py_file in _find_py_files():
            with open(py_file) as f:
                for i, line in enumerate(f, 1):
                    if "@api.one" in line and not line.strip().startswith("#"):
                        violations.append(f"{py_file}:{i}: {line.strip()}")
        self.assertEqual(violations, [], "Found deprecated @api.one:\n" + "\n".join(violations))

    def test_no_old_style_constraints(self):
        """_constraints list is deprecated — use models.Constraint or _check_ methods."""
        violations = []
        for py_file in _find_py_files():
            with open(py_file) as f:
                content = f.read()
            if "_constraints = [" in content and not content.strip().startswith("#"):
                violations.append(py_file)
        self.assertEqual(violations, [], "Found old-style _constraints:\n" + "\n".join(violations))

    def test_no_direct_sql_without_justification(self):
        """Direct SQL (env.cr.execute) should have a comment justification."""
        violations = []
        for py_file in _find_py_files():
            with open(py_file) as f:
                lines = f.readlines()
            for i, line in enumerate(lines, 1):
                if "env.cr.execute" in line or "self.env.cr.execute" in line:
                    # Check for justification comment on same or previous line
                    context = lines[max(0, i - 2) : i]
                    context_text = " ".join(context)
                    if "justification" not in context_text.lower() and "advisory" not in context_text.lower():
                        violations.append(f"{py_file}:{i}: {line.strip()}")
        # Soft check — warning only
        if violations:
            import warnings

            warnings.warn("SQL without justification:\n" + "\n".join(violations[:5]), stacklevel=2)


class TestOdoo19XMLCompat(unittest.TestCase):
    """Verify XML files use Odoo 19 patterns."""

    def test_no_category_id_in_groups(self):
        """category_id directly on res.groups is deprecated in Odoo 19.

        Odoo 19 pattern: ir.module.category → res.groups.privilege → res.groups
        - category_id on res.groups.privilege is CORRECT
        - category_id directly on res.groups is DEPRECATED
        """
        violations = []
        category_pattern = re.compile(r'<field\s+name=["\']category_id["\']')
        for xml_file in _find_xml_files():
            if "security" not in xml_file.lower():
                continue
            with open(xml_file) as f:
                content = f.read()
                lines = content.split("\n")

            in_groups_record = False
            in_privilege_record = False
            for i, line in enumerate(lines, 1):
                # Track which record type we're in
                if 'model="res.groups"' in line and 'model="res.groups.privilege"' not in line:
                    in_groups_record = True
                    in_privilege_record = False
                elif 'model="res.groups.privilege"' in line:
                    in_privilege_record = True
                    in_groups_record = False
                elif "</record>" in line:
                    in_groups_record = False
                    in_privilege_record = False

                # Only flag category_id if we're inside a res.groups record (not res.groups.privilege)
                if in_groups_record and category_pattern.search(line):
                    violations.append(f"{xml_file}:{i}: {line.strip()}")

        self.assertEqual(violations, [], "Found deprecated category_id on res.groups:\n" + "\n".join(violations))

    def test_no_tree_view_type(self):
        """<tree> view type is now <list> in Odoo 17+."""
        violations = []
        for xml_file in _find_xml_files():
            with open(xml_file) as f:
                for i, line in enumerate(f, 1):
                    if "<tree " in line or "<tree>" in line:
                        # Allow if it's in a comment
                        if "<!--" in line:
                            continue
                        violations.append(f"{xml_file}:{i}: {line.strip()}")
        # Soft check — Odoo still supports <tree> but <list> is preferred
        if violations:
            import warnings

            warnings.warn("Found <tree> (prefer <list>):\n" + "\n".join(violations[:5]), stacklevel=2)

    def test_xml_well_formed(self):
        """All XML files should be well-formed."""
        import xml.etree.ElementTree as ET

        violations = []
        for xml_file in _find_xml_files():
            try:
                ET.parse(xml_file)
            except ET.ParseError as e:
                violations.append(f"{xml_file}: {e}")
        self.assertEqual(violations, [], "Malformed XML:\n" + "\n".join(violations))

    def test_no_duplicate_xml_ids(self):
        """No duplicate XML IDs within a single file."""
        pattern = re.compile(r'id=["\']([^"\']+)["\']')
        violations = []
        for xml_file in _find_xml_files():
            ids_seen = {}
            with open(xml_file) as f:
                for i, line in enumerate(f, 1):
                    for match in pattern.finditer(line):
                        xml_id = match.group(1)
                        if xml_id in ids_seen:
                            msg = f"{xml_file}:{i}: duplicate id='{xml_id}'"
                            violations.append(msg)
                        ids_seen[xml_id] = i
        self.assertEqual(violations, [], "Duplicate XML IDs:\n" + "\n".join(violations))
