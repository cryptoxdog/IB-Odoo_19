#!/usr/bin/env python3
"""
Performance Anti-Pattern Detector
Finds N+1 queries and other performance issues.
"""

import re
from pathlib import Path

from path_filters import skip_path


class PerformanceAudit:
    def __init__(self, root_dir="."):
        self.root_dir = Path(root_dir)

    def check_n_plus_one_queries(self):
        """Find ORM queries inside loops"""
        errors = []

        ORM_METHODS = ["search", "browse", "read", "write", "create", "unlink"]

        for py_file in self.root_dir.rglob("models/*.py"):
            if skip_path(py_file):
                continue
            # Skip virtual environments
            if ".venv" in str(py_file) or "venv" in str(py_file):
                continue

            with open(py_file, encoding="utf-8") as f:
                lines = f.readlines()
                in_loop = False
                loop_start = 0

                for i, line in enumerate(lines, 1):
                    # Track loop context
                    if re.match(r"\s*for\s+\w+\s+in\s+", line):
                        in_loop = True
                        loop_start = i
                    elif in_loop and not line.startswith(" " * 4):
                        in_loop = False

                    # Look for ORM calls in loop
                    if in_loop:
                        for method in ORM_METHODS:
                            if f".{method}(" in line and "self.env" in line:
                                errors.append(
                                    {
                                        "type": "N_PLUS_ONE_QUERY",
                                        "severity": "HIGH",
                                        "file": str(py_file.relative_to(self.root_dir)),
                                        "line": i,
                                        "loop_start": loop_start,
                                        "code": line.strip(),
                                        "message": f"ORM .{method}() inside loop (N+1 query)",
                                        "fix": "Move query outside loop or use read_group/prefetch",
                                    }
                                )

        return errors

    def check_unbounded_searches(self):
        """Find search() calls without limit that could return huge recordsets.

        Excludes legitimate patterns:
        - Searches with 'in' operator (already bounded by input list)
        - Searches for small reference tables (country, currency, etc.)
        - Searches used for duplicate/validation checking
        - Searches assigned to variables ending in _ids, _by_*, etc. (batch lookups)
        - Searches in batch query context (preceded by comment about batch)
        """
        errors = []

        # Models that typically have small, bounded result sets
        SMALL_TABLES = {
            "res.country",
            "res.currency",
            "res.lang",
            "res.company",
            "uom.uom",
            "uom.category",
            "product.category",
            "ir.model",
            "ir.model.fields",
            "ir.module.module",
            "plasticos.material.form",
            "plasticos.source.type",
            "plasticos.document.tag",
            "plasticos.document.rule",
        }

        for py_file in self.root_dir.rglob("models/*.py"):
            if skip_path(py_file):
                continue
            # Skip virtual environments
            if ".venv" in str(py_file) or "venv" in str(py_file):
                continue

            with open(py_file, encoding="utf-8") as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, 1):
                if ".search(" not in line or "limit=" in line:
                    continue

                # Skip if it's a count or boolean check
                if "len(" in line or "if " in line or "not " in line:
                    continue

                # Skip if using 'in' operator (bounded by input list)
                if '"in"' in line or "'in'" in line or ", in," in line.lower():
                    continue

                # Skip searches on small reference tables
                is_small_table = False
                for table in SMALL_TABLES:
                    if f'["{table}"]' in line or f"['{table}']" in line:
                        is_small_table = True
                        break
                if is_small_table:
                    continue

                # Skip batch lookup patterns (variable names suggest bounded use)
                if re.search(r"(\w+_by_\w+|_ids|_map|_dict)\s*=", line):
                    continue

                # Skip if preceded by batch query comment (within 3 lines)
                context_start = max(0, line_num - 4)
                context = "".join(lines[context_start:line_num])
                if "batch" in context.lower() or "Batch" in context:
                    continue

                # Skip duplicate/validation checks
                if "duplicate" in line.lower() or "existing" in line.lower():
                    continue

                errors.append(
                    {
                        "type": "UNBOUNDED_SEARCH",
                        "severity": "MODERATE",
                        "file": str(py_file.relative_to(self.root_dir)),
                        "line": line_num,
                        "code": line.strip(),
                        "message": "search() without limit may return huge recordset",
                        "fix": "Add limit parameter or use search_count()",
                    }
                )

        return errors
