#!/usr/bin/env python3
"""
Performance Anti-Pattern Detector
Finds N+1 queries and other performance issues.
"""

import re
from pathlib import Path


class PerformanceAudit:
    def __init__(self, root_dir="."):
        self.root_dir = Path(root_dir)

    def check_n_plus_one_queries(self):
        """Find ORM queries inside loops"""
        errors = []

        ORM_METHODS = ["search", "browse", "read", "write", "create", "unlink"]

        for py_file in self.root_dir.rglob("models/*.py"):
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
        """Find search() calls without limit"""
        errors = []

        for py_file in self.root_dir.rglob("models/*.py"):
            # Skip virtual environments
            if ".venv" in str(py_file) or "venv" in str(py_file):
                continue

            with open(py_file, encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    if ".search(" in line and "limit=" not in line:
                        # Check if it's a count or boolean check
                        if "len(" not in line and "if " not in line:
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
