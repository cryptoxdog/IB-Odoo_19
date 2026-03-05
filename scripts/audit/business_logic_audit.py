#!/usr/bin/env python3
"""
Business Logic Anti-Pattern Detector
Catches common Odoo coding mistakes.
"""

import re
from pathlib import Path


class BusinessLogicAudit:
    def __init__(self, root_dir="."):
        self.root_dir = Path(root_dir)

    def check_unsafe_recordset_ops(self):
        """Find operations on recordsets without ensure_one()"""
        errors = []

        DANGEROUS_OPS = [
            r"self\.id\s*[=!<>]",
            r"self\.name\s*=",
            r"self\.write\(",
            r"self\.unlink\(",
        ]

        for py_file in self.root_dir.rglob("models/*.py"):
            with open(py_file, encoding="utf-8") as f:
                content = f.read()
                lines = content.split("\n")

                for i, line in enumerate(lines, 1):
                    for pattern in DANGEROUS_OPS:
                        if re.search(pattern, line):
                            # Look back for ensure_one() in same method
                            method_start = max(0, i - 20)
                            method_lines = "\n".join(lines[method_start:i])

                            if "ensure_one()" not in method_lines:
                                errors.append(
                                    {
                                        "type": "MISSING_ENSURE_ONE",
                                        "severity": "HIGH",
                                        "file": str(py_file.relative_to(self.root_dir)),
                                        "line": i,
                                        "code": line.strip(),
                                        "message": "Recordset operation without ensure_one()",
                                        "fix": "Add self.ensure_one() at method start",
                                    }
                                )

        return errors

    def check_sql_injection_risks(self):
        """Find SQL queries with string formatting"""
        errors = []

        SQL_PATTERNS = [
            r"self\.env\.cr\.execute\([^)]*%\s*[({]",  # execute("... % {}
            r"self\._cr\.execute\([^)]*\.format\(",  # execute("...".format(
            r"self\.env\.cr\.execute\([^)]*\+",  # execute("..." +
        ]

        for py_file in self.root_dir.rglob("models/*.py"):
            with open(py_file, encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    for pattern in SQL_PATTERNS:
                        if re.search(pattern, line):
                            errors.append(
                                {
                                    "type": "SQL_INJECTION_RISK",
                                    "severity": "CRITICAL",
                                    "file": str(py_file.relative_to(self.root_dir)),
                                    "line": line_num,
                                    "code": line.strip(),
                                    "message": "Unsafe SQL query with string formatting",
                                    "fix": "Use parameterized queries: execute(query, (param1, param2))",
                                }
                            )

        return errors

    def check_missing_access_checks(self):
        """Find sudo() calls without justification"""
        errors = []

        for py_file in self.root_dir.rglob("models/*.py"):
            with open(py_file, encoding="utf-8") as f:
                lines = f.readlines()

                for i, line in enumerate(lines, 1):
                    if ".sudo()" in line:
                        # Check for comment justification in surrounding lines
                        context_start = max(0, i - 3)
                        context_lines = lines[context_start:i]

                        has_justification = any("sudo" in ctx_line and "#" in ctx_line for ctx_line in context_lines)

                        if not has_justification:
                            errors.append(
                                {
                                    "type": "UNJUSTIFIED_SUDO",
                                    "severity": "MODERATE",
                                    "file": str(py_file.relative_to(self.root_dir)),
                                    "line": i,
                                    "code": line.strip(),
                                    "message": "sudo() call without comment justification",
                                    "fix": "Add comment explaining why elevated privileges needed",
                                }
                            )

        return errors

    def check_state_machine_bypasses(self):
        """Find direct state writes bypassing validation"""
        errors = []

        for py_file in self.root_dir.rglob("models/*.py"):
            with open(py_file, encoding="utf-8") as f:
                content = f.read()
                lines = content.split("\n")

                # Find models with state/status fields
                has_state = re.search(r"(state|status)\s*=\s*fields\.Selection", content)
                if not has_state:
                    continue

                for i, line in enumerate(lines, 1):
                    # Look for direct writes to state
                    if re.search(r'self\.write\(\{["\']state["\']:', line):
                        # Check if inside an action_* method
                        method_start = max(0, i - 30)
                        method_context = "\n".join(lines[method_start:i])

                        if "def action_" not in method_context:
                            errors.append(
                                {
                                    "type": "STATE_BYPASS",
                                    "severity": "MODERATE",
                                    "file": str(py_file.relative_to(self.root_dir)),
                                    "line": i,
                                    "message": "Direct state write outside action method",
                                    "fix": "Use action_* methods for state transitions",
                                }
                            )

        return errors
