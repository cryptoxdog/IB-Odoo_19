#!/usr/bin/env python3
"""CI check for Python anti-patterns that should use Odoo ORM patterns.

Odoo is NOT standard Python. This checker enforces Odoo-native patterns
and blocks common Python idioms that cause bugs, crashes, or performance issues.

FORBIDDEN PATTERNS (with fixes):
================================

1. Direct attribute assignment on recordsets
   ❌ self.field = value
   ✅ self.write({'field': value}) OR self.field = value (only in @api.onchange)

2. Using len() for truthiness (not for counting - counting is fine)
   ❌ if len(records) > 0:
   ✅ if records:  (recordsets are falsy when empty)
   ✅ count = len(records)  (this is fine for counting)

3. Dictionary-style access on records
   ❌ record['field_name']
   ✅ record.field_name (dot notation)

5. Using __init__ in models
   ❌ def __init__(self, ...):
   ✅ Use @api.model def create() or field defaults

6. Raw SQL without ORM
   ❌ cursor.execute("SELECT * FROM res_partner")
   ✅ self.env['res.partner'].search([])

7. Using id in @api.depends
   ❌ @api.depends('id')
   ✅ Remove 'id' from depends (disallowed in Odoo 19)

8. Checking None instead of empty recordset
   ❌ if record is None:
   ✅ if not record:  (empty recordset is falsy)

9. Using append/extend on recordsets
   ❌ records.append(new_record)
   ✅ records |= new_record OR records += new_record

10. Iterating recordset fields with index
    ❌ for i in range(len(self.line_ids)):
    ✅ for line in self.line_ids:

11. Using dict() on record
    ❌ dict(record)
    ✅ record.read()[0] or record._read_format()

12. Comparing recordsets with ==
    ❌ if record == other_record:
    ✅ if record.id == other_record.id: OR if record == other_record: (works but be explicit)

WHITELISTED (valid patterns, NOT flagged):
==========================================
- models.Constraint: Valid in Odoo 19+ (odoo.orm.table_objects)
- len(recordset): Valid for counting (only bad for truthiness checks like `if len(x) > 0`)
- list(recordset): Can be valid in some contexts
- record['field']: Valid for dynamic access, Neo4j records, dicts - too many false positives
- for i in range(len(python_list)): Valid for Python lists, only bad for self.field_ids
- python_list.append(): Valid for Python lists (e.g., missing_ids.append(id))

Run: python3 ci/check_odoo_antipatterns.py
"""

import ast
import re
import sys
from pathlib import Path

# Modules to scan (plasticos_* only, not odoo-enterprise or odoo-source)
SCAN_DIRS = [
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
    "ai_account",
]


class AntiPatternIssue:
    """Represents a detected anti-pattern."""

    def __init__(
        self,
        file: str,
        line: int,
        code: str,
        pattern: str,
        message: str,
        fix: str,
        severity: str = "HIGH",
    ):
        self.file = file
        self.line = line
        self.code = code
        self.pattern = pattern
        self.message = message
        self.fix = fix
        self.severity = severity

    def __str__(self) -> str:
        return f"{self.file}:{self.line} [{self.code}] {self.message}"


class OdooAntiPatternChecker(ast.NodeVisitor):
    """AST visitor to detect Python anti-patterns in Odoo code."""

    def __init__(self, filepath: str, source_lines: list[str]):
        self.filepath = filepath
        self.source_lines = source_lines
        self.issues: list[AntiPatternIssue] = []
        self.in_model_class = False
        self.in_onchange = False
        self.current_decorators: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Track if we're inside an Odoo model class."""
        # Check if this looks like an Odoo model (has _name or _inherit)
        is_model = False
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id in ("_name", "_inherit"):
                        is_model = True
                        break

        old_in_model = self.in_model_class
        self.in_model_class = is_model
        self.generic_visit(node)
        self.in_model_class = old_in_model

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Check function definitions for anti-patterns."""
        # Track decorators
        self.current_decorators = []
        for dec in node.decorator_list:
            if isinstance(dec, ast.Attribute):
                self.current_decorators.append(dec.attr)
            elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                self.current_decorators.append(dec.func.attr)

        self.in_onchange = "onchange" in self.current_decorators

        # Check for __init__ in model classes
        if self.in_model_class and node.name == "__init__":
            self.issues.append(
                AntiPatternIssue(
                    file=self.filepath,
                    line=node.lineno,
                    code="ODOO001",
                    pattern="__init__ in model",
                    message="Don't use __init__ in Odoo models",
                    fix="Use @api.model def create() or field defaults instead",
                    severity="CRITICAL",
                )
            )

        # Check for @api.depends('id')
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                if dec.func.attr == "depends":
                    for arg in dec.args:
                        if isinstance(arg, ast.Constant) and arg.value == "id":
                            self.issues.append(
                                AntiPatternIssue(
                                    file=self.filepath,
                                    line=dec.lineno,
                                    code="ODOO002",
                                    pattern="@api.depends('id')",
                                    message="@api.depends('id') is disallowed in Odoo 19",
                                    fix="Remove 'id' from the depends list",
                                    severity="CRITICAL",
                                )
                            )

        self.generic_visit(node)
        self.in_onchange = False
        self.current_decorators = []

    def visit_Call(self, node: ast.Call) -> None:
        """Check function calls for anti-patterns."""
        # Note: len(recordset) is actually FINE in Odoo for counting.
        # The anti-pattern is using len() for truthiness: `if len(records) > 0:`
        # Instead of: `if records:`
        # We don't flag len() usage anymore as it causes too many false positives.

        # Note: list(recordset) can be valid in some contexts.
        # The preferred pattern is recordset.ids but list() isn't always wrong.
        # Disabled to reduce false positives.

        # Check for dict(record)
        if isinstance(node.func, ast.Name) and node.func.id == "dict":
            if node.args and self._looks_like_record(node.args[0]):
                self.issues.append(
                    AntiPatternIssue(
                        file=self.filepath,
                        line=node.lineno,
                        code="ODOO005",
                        pattern="dict(record)",
                        message="Don't use dict() on records",
                        fix="Use record.read()[0] or record.read(['field1', 'field2'])[0]",
                        severity="MEDIUM",
                    )
                )

        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        """Check comparisons for anti-patterns."""
        # Check for 'record is None' or 'record is not None'
        for op, comparator in zip(node.ops, node.comparators):
            if isinstance(op, (ast.Is, ast.IsNot)):
                if isinstance(comparator, ast.Constant) and comparator.value is None:
                    if self._looks_like_recordset(node.left):
                        self.issues.append(
                            AntiPatternIssue(
                                file=self.filepath,
                                line=node.lineno,
                                code="ODOO006",
                                pattern="record is None",
                                message="Don't compare recordsets with 'is None'",
                                fix="Use 'if not record:' (empty recordset is falsy)",
                                severity="HIGH",
                            )
                        )

        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        """Check for dictionary-style access on records."""
        # Disabled: record['field'] check has too many false positives
        # (Neo4j records, dict results, dynamic field access are all valid)
        # Odoo does support both record.field and record['field'] syntax
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        """Check for anti-pattern iteration."""
        # Check for 'for i in range(len(self.field_ids)):' - iterating recordset fields by index
        # Only flag if it's clearly a recordset field (self.something_ids)
        if isinstance(node.iter, ast.Call):
            if isinstance(node.iter.func, ast.Name) and node.iter.func.id == "range":
                if node.iter.args:
                    arg = node.iter.args[0]
                    if isinstance(arg, ast.Call):
                        if isinstance(arg.func, ast.Name) and arg.func.id == "len":
                            if arg.args:
                                len_arg = arg.args[0]
                                # Only flag self.field_ids patterns, not local variables
                                if (
                                    isinstance(len_arg, ast.Attribute)
                                    and isinstance(len_arg.value, ast.Name)
                                    and len_arg.value.id == "self"
                                    and len_arg.attr.endswith("_ids")
                                ):
                                    self.issues.append(
                                        AntiPatternIssue(
                                            file=self.filepath,
                                            line=node.lineno,
                                            code="ODOO008",
                                            pattern=f"for i in range(len(self.{len_arg.attr}))",
                                            message=f"Don't iterate self.{len_arg.attr} by index",
                                            fix=f"Use 'for record in self.{len_arg.attr}:' instead",
                                            severity="MEDIUM",
                                        )
                                    )

        self.generic_visit(node)

    def _looks_like_recordset(self, node: ast.expr) -> bool:
        """Heuristic to detect if a node is likely a recordset."""
        if isinstance(node, ast.Attribute):
            # self.field_ids, self.line_ids, etc.
            if node.attr.endswith("_ids") or node.attr.endswith("_id"):
                return True
            # Common recordset names
            if node.attr in ("records", "partners", "users", "lines", "moves", "orders"):
                return True
        if isinstance(node, ast.Name):
            # Variable names that suggest recordsets
            name = node.id.lower()
            if name.endswith("_ids") or name.endswith("_id"):
                return True
            if name in ("records", "partners", "users", "lines", "moves", "orders", "self"):
                return True
        if isinstance(node, ast.Call):
            # search(), browse(), filtered(), etc.
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in ("search", "browse", "filtered", "mapped", "sorted"):
                    return True
        return False

    def _looks_like_record(self, node: ast.expr) -> bool:
        """Heuristic to detect if a node is likely a single record."""
        if isinstance(node, ast.Name):
            name = node.id.lower()
            if name in ("record", "rec", "partner", "user", "line", "move", "order", "self"):
                return True
        if isinstance(node, ast.Attribute):
            if node.attr.endswith("_id") and not node.attr.endswith("_ids"):
                return True
        return False


def check_regex_patterns(filepath: str, content: str) -> list[AntiPatternIssue]:
    """Regex-based checks for patterns hard to detect via AST."""
    issues = []
    lines = content.split("\n")

    for i, line in enumerate(lines, 1):
        # Skip comments
        stripped = line.strip()
        if stripped.startswith("#"):
            continue

        # Check for .append() on what looks like recordsets
        # Be careful: _ids suffix often means a list of IDs (Python list), not a recordset
        # Recordsets are usually: self.field_ids, partner_ids (Many2many/One2many fields)
        # But variables like missing_ids, created_ids are usually Python lists
        # Only flag if it's clearly a recordset field access (self.something_ids)
        match = re.search(r"\bself\.(\w+_ids)\b\.append\(", line)
        if match:
            issues.append(
                AntiPatternIssue(
                    file=filepath,
                    line=i,
                    code="ODOO009",
                    pattern=".append() on recordset field",
                    message=f"Don't use .append() on recordset field self.{match.group(1)}",
                    fix="Use self.field_ids |= new_record or self.field_ids += new_record",
                    severity="HIGH",
                )
            )

        # Check for .extend() on recordset fields
        match = re.search(r"\bself\.(\w+_ids)\b\.extend\(", line)
        if match:
            issues.append(
                AntiPatternIssue(
                    file=filepath,
                    line=i,
                    code="ODOO010",
                    pattern=".extend() on recordset field",
                    message=f"Don't use .extend() on recordset field self.{match.group(1)}",
                    fix="Use self.field_ids |= other_recordset",
                    severity="HIGH",
                )
            )

        # Check for raw SQL that could use ORM
        # Only flag SELECT/INSERT/UPDATE/DELETE on known Odoo tables
        if re.search(r'execute\s*\(\s*["\']SELECT\s+\*\s+FROM\s+(res_|ir_|mail_)', line, re.I):
            issues.append(
                AntiPatternIssue(
                    file=filepath,
                    line=i,
                    code="ODOO011",
                    pattern="Raw SQL on Odoo tables",
                    message="Avoid raw SQL on Odoo core tables",
                    fix="Use self.env['model.name'].search([]) instead",
                    severity="MEDIUM",
                )
            )

        # Check for direct attribute assignment outside @api.onchange
        # Pattern: record.field = value (but NOT self.env, self._context, etc.)
        # This is tricky because we need context (are we in @api.onchange?)
        # For now, flag obvious cases in XML server action code blocks
        # XML server actions should always use .write()
        if "force_send=" in line or "send_mail(" in line:
            # Check for direct assignment in same context (likely server action)
            # Pattern: record.field = value where field is not a method call
            direct_assign = re.search(
                r"\b(\w+)\.([a-z_]+)\s*=\s*(?!.*\()",  # var.field = (not a call)
                line,
            )
            if direct_assign:
                var_name = direct_assign.group(1)
                field_name = direct_assign.group(2)
                # Skip known safe patterns
                if var_name not in ("self", "env", "context", "cr", "uid") and field_name not in (
                    "env",
                    "context",
                    "cr",
                    "uid",
                    "id",
                    "ids",
                ):
                    issues.append(
                        AntiPatternIssue(
                            file=filepath,
                            line=i,
                            code="ODOO015",
                            pattern="Direct attribute assignment",
                            message=f"Use .write() instead of direct assignment: {var_name}.{field_name} = ...",
                            fix=f"Use {var_name}.write({{'{field_name}': value}}) instead",
                            severity="HIGH",
                        )
                    )

        # Check for deprecated decorators (removed in Odoo 13+)
        # Pattern: @api DOT one or @api DOT multi
        if re.search(r"@api\.(one|multi)\b", line):
            issues.append(
                AntiPatternIssue(
                    file=filepath,
                    line=i,
                    code="ODOO012",
                    pattern="@api." + "one/@api." + "multi",  # split to avoid self-detection
                    message="@api." + "one and @api." + "multi were removed in Odoo 13",
                    fix="Remove the decorator and update method to handle recordsets",
                    severity="CRITICAL",
                )
            )

        # Note: models.Constraint DOES exist in Odoo 19 (new feature)
        # It's in odoo.orm.table_objects and exported via odoo.models
        # Previously this was flagged as invalid but it's actually correct for Odoo 19+

        # Check for == None instead of is None (general Python, but extra bad in Odoo)
        if re.search(r"==\s*None\b", line) and not stripped.startswith("#"):
            issues.append(
                AntiPatternIssue(
                    file=filepath,
                    line=i,
                    code="ODOO014",
                    pattern="== None",
                    message="Use 'is None' not '== None' (or 'if not record:' for recordsets)",
                    fix="Use 'is None' for None checks, 'if not record:' for empty recordsets",
                    severity="LOW",
                )
            )

    return issues


def scan_file(filepath: str) -> list[AntiPatternIssue]:
    """Scan a single Python file for anti-patterns."""
    issues: list[AntiPatternIssue] = []

    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError):
        return issues

    source_lines = content.split("\n")

    # AST-based checks
    try:
        tree = ast.parse(content)
        checker = OdooAntiPatternChecker(filepath, source_lines)
        checker.visit(tree)
        issues.extend(checker.issues)
    except SyntaxError:
        pass

    # Regex-based checks
    issues.extend(check_regex_patterns(filepath, content))

    return issues


def find_python_files() -> list[str]:
    """Find all Python files to scan."""
    files = []

    for scan_dir in SCAN_DIRS:
        path = Path(scan_dir)
        if path.is_dir():
            for py_file in path.rglob("*.py"):
                # Skip __pycache__, migrations, and test files (lower severity for tests)
                if "__pycache__" in str(py_file):
                    continue
                if "/migrations/" in str(py_file):
                    continue
                files.append(str(py_file))

    return sorted(files)


def main() -> int:
    """Run anti-pattern checks."""
    print("🔍 Checking for Python anti-patterns in Odoo code...")
    print("=" * 70)
    print()

    all_issues: list[AntiPatternIssue] = []
    files = find_python_files()

    for filepath in files:
        issues = scan_file(filepath)
        all_issues.extend(issues)

    # Group by severity
    critical = [i for i in all_issues if i.severity == "CRITICAL"]
    high = [i for i in all_issues if i.severity == "HIGH"]
    medium = [i for i in all_issues if i.severity == "MEDIUM"]
    low = [i for i in all_issues if i.severity == "LOW"]

    # Report
    if critical:
        print(f"❌ CRITICAL ({len(critical)}) - These WILL cause runtime errors:")
        print("-" * 70)
        for issue in critical:
            print(f"  {issue.file}:{issue.line}")
            print(f"    [{issue.code}] {issue.message}")
            print(f"    Fix: {issue.fix}")
            print()
        print()

    if high:
        print(f"⚠️  HIGH ({len(high)}) - These are likely bugs:")
        print("-" * 70)
        for issue in high[:15]:
            print(f"  {issue.file}:{issue.line}")
            print(f"    [{issue.code}] {issue.message}")
            print(f"    Fix: {issue.fix}")
            print()
        if len(high) > 15:
            print(f"  ... and {len(high) - 15} more HIGH issues")
        print()

    if medium:
        print(f"ℹ️  MEDIUM ({len(medium)}) - Code smell, consider fixing:")
        print("-" * 70)
        for issue in medium[:10]:
            print(f"  {issue.file}:{issue.line}: [{issue.code}] {issue.message}")
        if len(medium) > 10:
            print(f"  ... and {len(medium) - 10} more MEDIUM issues")
        print()

    if low:
        print(f"📝 LOW ({len(low)}) - Style suggestions:")
        print("-" * 70)
        for issue in low[:10]:
            print(f"  {issue.file}:{issue.line}: [{issue.code}] {issue.message}")
        if len(low) > 10:
            print(f"  ... and {len(low) - 10} more LOW issues")
        print()

    # Summary
    total = len(all_issues)
    print("=" * 70)
    print(f"SUMMARY: {total} total issues")
    print(f"  CRITICAL: {len(critical)}")
    print(f"  HIGH:     {len(high)}")
    print(f"  MEDIUM:   {len(medium)}")
    print(f"  LOW:      {len(low)}")
    print()

    # Exit code based on severity
    if critical:
        print("❌ FAILED: Critical anti-patterns found (will cause runtime errors)")
        return 1

    if high:
        print("⚠️  WARNING: High-severity anti-patterns found (likely bugs)")
        # Don't fail on HIGH for now to allow gradual adoption
        # Change to 'return 1' once baseline is clean
        return 0

    if medium or low:
        print("✅ PASSED with suggestions")
        return 0

    print("✅ All checks passed - no anti-patterns detected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
