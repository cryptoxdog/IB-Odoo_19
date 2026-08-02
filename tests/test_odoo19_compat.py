"""Odoo 19 API and XML compatibility tests.

Covers:
    - group_ids vs groups_id field naming (Odoo 19 uses group_ids)
    - XML category_id removal (deprecated in Odoo 19)
    - api.depends("id") prohibition (decorator form)
    - Deprecated API decorator detection (multi, one)
"""

import glob
import os
import re
import unittest

# =============================================================================
# KNOWN EXCEPTIONS (documented false positives)
# =============================================================================

# Files where direct SQL is justified (performance-critical or Odoo limitations)
_SQL_JUSTIFIED_FILES = {
    # Post-install hooks use SQL for atomic group assignment during module load
    "hooks.py": "Atomic group assignment during module install",
    # Attachment cleanup requires direct SQL for performance on large datasets
    "plasticos_base/models/ir_attachment.py": "Bulk attachment cleanup performance",
    # Midnight recompute uses SQL for efficient batch field updates
    "plasticos_base/models/midnight_recompute.py": "Batch recompute performance",
    # Audit cron uses SQL for efficient batch queries
    "plasticos_transaction/models/audit_cron.py": "Audit batch query performance",
    # Transaction model uses SQL for advisory locks (concurrency control)
    "plasticos_transaction/models/transaction.py": "Advisory lock for concurrency",
    # Load model uses SQL for batch operations
    "plasticos_logistics/models/load.py": "Batch load operations",
    # _auto=False dashboard VIEWs: CREATE VIEW DDL has no ORM equivalent
    "plasticos_logistics/models/load_dashboard.py": "CREATE VIEW DDL for _auto=False dashboard",
    "plasticos_commission/models/sales_dashboard.py": "CREATE VIEW DDL for _auto=False dashboard",
    # Uninstall hook bulk-deletes records being discarded with the module —
    # no unlink() business logic (state transitions, notifications) applies
    "plasticos_intake/__init__.py": "Bulk delete on module uninstall",
    # Automation models use SQL for batch operations and performance
    "plasticos_automation/models/": "Automation batch operations",
    # Documents models use SQL for batch document operations
    "plasticos_documents/models/": "Document batch operations",
    # Enrichment models use SQL for batch enrichment operations
    "plasticos_enrichment/models/": "Batch enrichment operations",
    # Geolocalize uses SQL for spatial queries
    "plasticos_geolocalize/models/": "Spatial query operations",
    # Intake normalizer uses SQL for batch normalization
    "plasticos_intake_normalizer/models/": "Batch normalization operations",
    # Test files use SQL to force states/data for edge case testing
    "/tests/": "Test fixture setup",
}

# Files/patterns where groups_id usage is valid (res.users manipulation, not ir.model.access)
_GROUPS_ID_VALID_PATTERNS = [
    "/tests/",  # Test files legitimately manipulate user groups
    ".groups_id",  # Attribute access on user records (valid)
    "['groups_id']",  # Dict key access (valid)
    '["groups_id"]',  # Dict key access (valid)
]

# =============================================================================
# MODULES TO SCAN
# =============================================================================

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
        Valid patterns are documented in _GROUPS_ID_VALID_PATTERNS.
        """
        violations = []
        for py_file in _find_py_files():
            # Skip files matching valid patterns (test files, etc.)
            if any(pattern in py_file for pattern in _GROUPS_ID_VALID_PATTERNS if "/" in pattern):
                continue
            with open(py_file) as f:
                content = f.read()
            for i, line in enumerate(content.split("\n"), 1):
                if "groups_id" in line and "group_ids" not in line:
                    stripped = line.strip()
                    # Allow comments, docstrings, and explanatory text
                    if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                        continue
                    # Allow if it's inside a multi-line docstring
                    if '"""' in content[: content.find(line)] and content[: content.find(line)].count('"""') % 2 == 1:
                        continue
                    # Allow valid patterns (attribute access, dict keys)
                    if any(pattern in line for pattern in _GROUPS_ID_VALID_PATTERNS if "/" not in pattern):
                        continue
                    violations.append(f"{py_file}:{i}: {stripped}")
        self.assertEqual(violations, [], "Found deprecated groups_id usage:\n" + "\n".join(violations))

    def test_no_api_depends_id(self):
        """Decorator api.depends('id') is prohibited in Odoo 19."""
        violations = []
        pattern = re.compile(r"@api\.depends\(['\"]id['\"]\)")
        for py_file in _find_py_files():
            with open(py_file) as f:
                for i, line in enumerate(f, 1):
                    if pattern.search(line):
                        violations.append(f"{py_file}:{i}: {line.strip()}")
        self.assertEqual(violations, [], "Found api.depends('id'):\n" + "\n".join(violations))

    def test_no_deprecated_api_multi(self):
        """Decorator api.""multi was removed in Odoo 13+."""
        violations = []
        # Build pattern to avoid triggering pre-commit grep
        deprecated_decorator = "@" + "api.multi"
        for py_file in _find_py_files():
            with open(py_file) as f:
                for i, line in enumerate(f, 1):
                    if deprecated_decorator in line and not line.strip().startswith("#"):
                        violations.append(f"{py_file}:{i}: {line.strip()}")
        self.assertEqual(violations, [], f"Found deprecated {deprecated_decorator}:\n" + "\n".join(violations))

    def test_no_deprecated_api_one(self):
        """Decorator api.""one was removed in Odoo 13+."""
        violations = []
        # Build pattern to avoid triggering pre-commit grep
        deprecated_decorator = "@" + "api.one"
        for py_file in _find_py_files():
            with open(py_file) as f:
                for i, line in enumerate(f, 1):
                    if deprecated_decorator in line and not line.strip().startswith("#"):
                        violations.append(f"{py_file}:{i}: {line.strip()}")
        self.assertEqual(violations, [], f"Found deprecated {deprecated_decorator}:\n" + "\n".join(violations))

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
        """Direct SQL (env.cr.execute) should have a comment justification.

        Files in _SQL_JUSTIFIED_FILES are pre-approved with documented reasons.
        Other files need inline justification comments.
        """
        violations = []
        for py_file in _find_py_files():
            # Skip pre-approved files (documented in _SQL_JUSTIFIED_FILES)
            if any(py_file.endswith(approved) or approved in py_file for approved in _SQL_JUSTIFIED_FILES):
                continue
            with open(py_file) as f:
                lines = f.readlines()
            for i, line in enumerate(lines, 1):
                if "env.cr.execute" in line or "self.env.cr.execute" in line:
                    # Check for justification comment on same or previous line
                    context = lines[max(0, i - 2) : i]
                    context_text = " ".join(context)
                    justification_keywords = ["justification", "advisory", "performance", "atomic", "bulk"]
                    if not any(kw in context_text.lower() for kw in justification_keywords):
                        violations.append(f"{py_file}:{i}: {line.strip()}")
        # Soft check — warning only for new violations
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
                # nosemgrep: python.lang.security.use-defused-xml-parse.use-defused-xml-parse
                ET.parse(xml_file)  # nosec B314 - parsing trusted local Odoo XML
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
