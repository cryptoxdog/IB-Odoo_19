#!/usr/bin/env python3
"""CI check for ORM integrity patterns that can cause runtime crashes.

Detects:
1. Unprotected env.ref() calls - crash if XML ID missing
2. Unguarded search access - crash if recordset empty
3. Missing raise_if_not_found parameter in test files

Run: python3 ci/check_orm_integrity.py
"""

import ast
import os
import re
import sys
from pathlib import Path

# Modules to scan
PLASTICOS_MODULES = [
    "plasticos_automation",
    "plasticos_base",
    "plasticos_buyer_match_engine",
    "plasticos_claims",
    "plasticos_commission",
    "plasticos_crm_bridge",
    "plasticos_dev_tools",
    "plasticos_documents",
    "plasticos_documents_native",
    "plasticos_enrichment",
    "plasticos_enrichment_bridge",
    "plasticos_facility_profile",
    "plasticos_geolocalize",
    "plasticos_graph_intelligence",
    "plasticos_inference_engine",
    "plasticos_intake",
    "plasticos_intake_normalizer",
    "plasticos_logistics",
    "plasticos_matching",
    "plasticos_material_profile",
    "plasticos_offer",
    "plasticos_order_lines",
    "plasticos_partner_import",
    "plasticos_product",
    "plasticos_security_base",
    "plasticos_transaction",
    "plasticos_web_leads",
]

# Also scan central tests directory
EXTRA_DIRS = ["tests"]


class OrmIntegrityChecker(ast.NodeVisitor):
    """AST visitor to detect ORM integrity issues."""

    def __init__(self, filename: str):
        self.filename = filename
        self.issues: list[dict] = []
        self.is_test_file = "/tests/" in filename or filename.startswith("tests/")

    def visit_Call(self, node: ast.Call) -> None:
        self._check_env_ref(node)
        self._check_unguarded_search_access(node)
        self.generic_visit(node)

    def _check_env_ref(self, node: ast.Call) -> None:
        """Check for unprotected env.ref() calls."""
        # Match: self.env.ref(...) or env.ref(...)
        if not isinstance(node.func, ast.Attribute):
            return
        if node.func.attr != "ref":
            return

        # Check if it's on env object
        func = node.func
        if isinstance(func.value, ast.Attribute):
            if func.value.attr != "env":
                return
        elif isinstance(func.value, ast.Name):
            if func.value.id != "env":
                return
        else:
            return

        # Check if raise_if_not_found=False is present
        has_protection = False
        for kw in node.keywords:
            if kw.arg == "raise_if_not_found":
                if isinstance(kw.value, ast.Constant) and kw.value.value is False:
                    has_protection = True
                    break

        if not has_protection:
            # Get the XML ID if it's a string literal
            xml_id = ""
            if node.args and isinstance(node.args[0], ast.Constant):
                xml_id = node.args[0].value

            self.issues.append(
                {
                    "type": "UNPROTECTED_ENV_REF",
                    "line": node.lineno,
                    "col": node.col_offset,
                    "message": f"env.ref('{xml_id}') without raise_if_not_found=False",
                    "severity": "HIGH" if self.is_test_file else "CRITICAL",
                    "fix": f"env.ref('{xml_id}', raise_if_not_found=False)",
                }
            )

    def _check_unguarded_search_access(self, node: ast.Call) -> None:
        """Check for unguarded attribute access on search results.

        Pattern: model.search(...).attr where attr is id, name, code, etc.
        This crashes if search returns empty recordset.
        """
        # This is complex to detect via AST because the access happens
        # after the call. We'll use a simpler regex-based approach instead.
        pass


def check_unguarded_search_regex(filepath: str, content: str) -> list[dict]:
    """Regex-based check for unguarded search access patterns."""
    issues = []
    is_test = "/tests/" in filepath or filepath.startswith("tests/")

    # Pattern: .search(...).id or .search(...).name etc without prior check
    # This is a simplified check - looks for direct chained access
    pattern = re.compile(r"\.search\s*\([^)]+\)\s*\.(id|name|code|display_name)\b", re.MULTILINE)

    for i, line in enumerate(content.split("\n"), 1):
        # Skip comments
        stripped = line.strip()
        if stripped.startswith("#"):
            continue

        for match in pattern.finditer(line):
            # Check if there's a truthiness guard nearby (simple heuristic)
            # Look for "if record:" or "if not record:" patterns
            context_start = max(0, i - 5)
            context_lines = content.split("\n")[context_start:i]
            context = "\n".join(context_lines)

            # Skip if there's an obvious guard
            if re.search(r"if\s+\w+:", context) or "limit=1" in line:
                # Has some guard, but still risky - lower severity
                continue

            issues.append(
                {
                    "type": "UNGUARDED_SEARCH_ACCESS",
                    "line": i,
                    "col": match.start(),
                    "message": f"Direct access {match.group()} on search result without guard",
                    "severity": "MEDIUM" if is_test else "HIGH",
                    "fix": "Check recordset truthiness before accessing attributes",
                }
            )

    return issues


def scan_file(filepath: str) -> list[dict]:
    """Scan a single Python file for ORM integrity issues."""
    issues: list[dict] = []

    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError):
        return issues

    # AST-based checks
    try:
        tree = ast.parse(content)
        checker = OrmIntegrityChecker(filepath)
        checker.visit(tree)
        issues.extend(checker.issues)
    except SyntaxError:
        pass

    # Regex-based checks
    issues.extend(check_unguarded_search_regex(filepath, content))

    # Add filepath to all issues
    for issue in issues:
        issue["file"] = filepath

    return issues


def find_python_files() -> list[str]:
    """Find all Python files to scan."""
    files = []

    for module in PLASTICOS_MODULES:
        if os.path.isdir(module):
            for py_file in Path(module).rglob("*.py"):
                files.append(str(py_file))

    for extra_dir in EXTRA_DIRS:
        if os.path.isdir(extra_dir):
            for py_file in Path(extra_dir).rglob("*.py"):
                files.append(str(py_file))

    return files


def main() -> int:
    """Run ORM integrity checks."""
    print("🔍 Checking ORM integrity patterns...")
    print()

    all_issues: list[dict] = []
    files = find_python_files()

    for filepath in files:
        issues = scan_file(filepath)
        all_issues.extend(issues)

    # Group by severity
    critical = [i for i in all_issues if i["severity"] == "CRITICAL"]
    high = [i for i in all_issues if i["severity"] == "HIGH"]
    medium = [i for i in all_issues if i["severity"] == "MEDIUM"]

    # Report
    if critical:
        print(f"❌ CRITICAL ({len(critical)}):")
        for issue in critical[:10]:
            print(f"  {issue['file']}:{issue['line']}: {issue['message']}")
        if len(critical) > 10:
            print(f"  ... and {len(critical) - 10} more")
        print()

    if high:
        print(f"⚠️  HIGH ({len(high)}):")
        for issue in high[:10]:
            print(f"  {issue['file']}:{issue['line']}: {issue['message']}")
        if len(high) > 10:
            print(f"  ... and {len(high) - 10} more")
        print()

    if medium:
        print(f"ℹ️  MEDIUM ({len(medium)}):")
        for issue in medium[:5]:
            print(f"  {issue['file']}:{issue['line']}: {issue['message']}")
        if len(medium) > 5:
            print(f"  ... and {len(medium) - 5} more")
        print()

    # Summary
    total = len(all_issues)
    print(f"Total: {total} issues ({len(critical)} critical, {len(high)} high, {len(medium)} medium)")

    # Fail on critical issues only (production code)
    # High issues in tests are warnings
    if critical:
        print()
        print("❌ FAILED: Critical ORM integrity issues found in production code")
        return 1

    if all_issues:
        print()
        print("⚠️  PASSED with warnings: Review high/medium issues")
        return 0

    print()
    print("✅ All ORM integrity checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
