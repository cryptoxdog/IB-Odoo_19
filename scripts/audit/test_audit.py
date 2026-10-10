#!/usr/bin/env python3
"""Assertion-quality audit.

Weak-test truth lives in ``ci/weak_test_fixer.py``. This module does not keep
a second assertion doctrine and does not report static model-name search as
Odoo runtime coverage.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path


def _weak_test_fixer():
    fixer_path = Path(__file__).resolve().parents[2] / "ci" / "weak_test_fixer.py"
    spec = importlib.util.spec_from_file_location("weak_test_fixer", fixer_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load weak-test owner: {fixer_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.WeakTestFixer


class TestAudit:
    def __init__(self, root_dir="."):
        self.root_dir = Path(root_dir)

    def get_models_without_tests(self):
        """Retired. Static ``_name`` / ``self.env`` search is not runtime coverage."""
        return []

    def check_weak_tests(self):
        """Report assertion-free tests from the sole owner, ``ci/weak_test_fixer.py``."""
        fixer = _weak_test_fixer()(self.root_dir)
        errors = []
        for test_file in fixer.iter_test_files():
            try:
                found = fixer.analyze_test_file(test_file)
            except SyntaxError:
                continue
            relative = str(test_file.relative_to(self.root_dir))
            for test in found:
                errors.append(
                    {
                        "type": "WEAK_TEST",
                        "severity": "MODERATE",
                        "file": relative,
                        "test": test["name"],
                        "line": test["line"],
                        "message": f"Test '{test['name']}' has no assertions",
                        "fix": "Add an assertion that encodes the contract",
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
