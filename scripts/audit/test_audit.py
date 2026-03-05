#!/usr/bin/env python3
"""
Test Coverage & Quality Audit
Ensures comprehensive, reliable test suite.
"""

import ast
import re
import subprocess
from pathlib import Path


class TestAudit:
    def __init__(self, root_dir="."):
        self.root_dir = Path(root_dir)

    def get_models_without_tests(self):
        """Find models with no test coverage"""
        errors = []

        # Find all models
        all_models = set()
        for py_file in self.root_dir.rglob("models/*.py"):
            with open(py_file, encoding="utf-8") as f:
                content = f.read()
                for match in re.finditer(r'_name\s*=\s*["\']([^"\']+)["\']', content):
                    all_models.add(match.group(1))

        # Find tested models
        tested_models = set()
        for test_file in self.root_dir.rglob("tests/*.py"):
            with open(test_file, encoding="utf-8") as f:
                content = f.read()
                for match in re.finditer(r'self\.env\[["\']([^"\']+)["\']\]', content):
                    tested_models.add(match.group(1))

        # Find untested
        untested = all_models - tested_models
        for model in untested:
            errors.append(
                {
                    "type": "NO_TEST_COVERAGE",
                    "severity": "MODERATE",
                    "model": model,
                    "message": f"Model '{model}' has no test coverage",
                    "fix": "Create test class in tests/test_*.py",
                }
            )

        return errors

    def check_weak_tests(self):
        """Find test methods with no assertions"""
        errors = []

        for test_file in self.root_dir.rglob("tests/test_*.py"):
            with open(test_file, encoding="utf-8") as f:
                try:
                    tree = ast.parse(f.read())
                except Exception:
                    continue

                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                        # Count assertions
                        assertions = sum(
                            1
                            for n in ast.walk(node)
                            if isinstance(n, ast.Call)
                            and isinstance(n.func, ast.Attribute)
                            and n.func.attr.startswith("assert")
                        )

                        if assertions == 0:
                            errors.append(
                                {
                                    "type": "WEAK_TEST",
                                    "severity": "MODERATE",
                                    "file": str(test_file.relative_to(self.root_dir)),
                                    "test": node.name,
                                    "line": node.lineno,
                                    "message": f"Test '{node.name}' has no assertions",
                                    "fix": "Add self.assertEqual/assertTrue/etc",
                                }
                            )

        return errors

    def run_pytest_coverage(self):
        """Run pytest with coverage reporting"""
        result = subprocess.run(
            ["pytest", "--cov=.", "--cov-report=json", "tests/"], capture_output=True, text=True, cwd=self.root_dir
        )

        # Parse coverage.json
        import json

        try:
            with open(self.root_dir / "coverage.json") as f:
                coverage_data = json.load(f)

            errors = []
            for file, data in coverage_data["files"].items():
                if data["summary"]["percent_covered"] < 70:
                    errors.append(
                        {
                            "type": "LOW_COVERAGE",
                            "severity": "MODERATE",
                            "file": file,
                            "coverage": f"{data['summary']['percent_covered']:.1f}%",
                            "message": "Test coverage below 70%",
                        }
                    )

            return errors
        except Exception:
            return []
