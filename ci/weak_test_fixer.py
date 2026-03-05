#!/usr/bin/env python3
"""
Scan for weak tests and generate fix templates
"""

import ast
from pathlib import Path


class WeakTestFixer:
    def __init__(self, root_dir="."):
        self.root_dir = Path(root_dir)

    def analyze_test_file(self, test_file):
        """Find tests with no assertions and suggest fixes"""
        with open(test_file, encoding="utf-8") as f:
            content = f.read()
            tree = ast.parse(content)

        weak_tests = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                # Count assertions
                assertions = [
                    n
                    for n in ast.walk(node)
                    if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and n.func.attr.startswith("assert")
                ]

                if len(assertions) == 0:
                    # Extract what the test does
                    operations = self._extract_operations(node)
                    weak_tests.append(
                        {
                            "name": node.name,
                            "line": node.lineno,
                            "operations": operations,
                            "suggested_assertions": self._suggest_assertions(operations),
                        }
                    )

        return weak_tests

    def _extract_operations(self, func_node):
        """Identify what operations the test performs"""
        ops = []
        for node in ast.walk(func_node):
            # Record creates
            if isinstance(node, ast.Call):
                if hasattr(node.func, "attr") and node.func.attr == "create":
                    ops.append("create")
                elif hasattr(node.func, "attr") and node.func.attr == "write":
                    ops.append("write")
                elif hasattr(node.func, "attr") and node.func.attr == "search":
                    ops.append("search")
        return ops

    def _suggest_assertions(self, operations):
        """Suggest appropriate assertions based on operations"""
        suggestions = []

        if "create" in operations:
            suggestions.append("self.assertTrue(record.exists())")
            suggestions.append("self.assertEqual(record.state, 'draft')")
            suggestions.append("self.assertRegex(record.name, r'^INT/')")

        if "write" in operations:
            suggestions.append("self.assertEqual(record.field_name, expected_value)")

        if "search" in operations:
            suggestions.append("self.assertEqual(len(results), expected_count)")
            suggestions.append("self.assertIn(expected_record, results)")

        return suggestions


# Run the scanner
fixer = WeakTestFixer(".")
for test_file in Path(".").rglob("tests/test_*.py"):
    weak_tests = fixer.analyze_test_file(test_file)

    if weak_tests:
        print(f"\n📄 {test_file}")
        for test in weak_tests:
            print(f"  ❌ {test['name']} (line {test['line']})")
            print(f"     Operations: {', '.join(test['operations'])}")
            print("     Suggested assertions:")
            for assertion in test["suggested_assertions"]:
                print(f"       • {assertion}")
