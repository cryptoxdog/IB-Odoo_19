#!/usr/bin/env python3
"""

Business Logic Anti-Pattern Detector
Catches common Odoo coding mistakes.
"""

MODELS_GLOB = "models/*.py"


import re
from pathlib import Path


class BusinessLogicAudit:
    def __init__(self, root_dir="."):
        self.root_dir = Path(root_dir)

    def check_unsafe_recordset_ops(self):
        """Find operations on recordsets without ensure_one().

        Improved method boundary detection:
        - Finds the actual method start by looking for 'def ' pattern
        - Checks for ensure_one() anywhere in the method up to current line
        - Recognizes multi-record safe patterns (for rec in self, for record in self)
        """
        errors = []

        DANGEROUS_OPS = [
            r"self\.id\s*[=!<>]",
            r"self\.name\s*=",
            r"self\.write\(",
            r"self\.unlink\(",
        ]

        # Patterns that indicate multi-record safe code
        MULTI_RECORD_PATTERNS = [
            r"for\s+\w+\s+in\s+self\b",  # for rec in self
            r"self\.filtered\(",  # self.filtered(...)
            r"self\.mapped\(",  # self.mapped(...)
        ]

        # Short action methods that intentionally work on multiple records
        # These are typically button actions that should apply to all selected records
        MULTI_RECORD_METHOD_PATTERNS = [
            r"def\s+action_\w+\s*\(\s*self\s*\)",  # action_* methods with only self param
        ]

        for py_file in self.root_dir.rglob(MODELS_GLOB):
            # Skip virtual environments and test files
            if ".venv" in str(py_file) or "venv" in str(py_file) or "/tests/" in str(py_file):
                continue

            with open(py_file, encoding="utf-8") as f:
                content = f.read()
                lines = content.split("\n")

                for i, line in enumerate(lines, 1):
                    for pattern in DANGEROUS_OPS:
                        if re.search(pattern, line):
                            # Find the actual method start by looking backwards for 'def '
                            method_start_line = 0
                            for j in range(i - 1, -1, -1):
                                if re.match(r"\s*def\s+\w+\s*\(", lines[j]):
                                    method_start_line = j
                                    break

                            # Get all lines from method start to current line
                            method_lines = "\n".join(lines[method_start_line:i])

                            # Check for ensure_one() in method
                            has_ensure_one = "ensure_one()" in method_lines

                            # Check for multi-record safe patterns in method body
                            is_multi_record_safe = any(re.search(p, method_lines) for p in MULTI_RECORD_PATTERNS)

                            # Check if method signature indicates multi-record action
                            method_def_line = lines[method_start_line] if method_start_line < len(lines) else ""
                            is_multi_record_action = any(
                                re.search(p, method_def_line) for p in MULTI_RECORD_METHOD_PATTERNS
                            )

                            if not has_ensure_one and not is_multi_record_safe and not is_multi_record_action:
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

        for py_file in self.root_dir.rglob(MODELS_GLOB):
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

        for py_file in self.root_dir.rglob(MODELS_GLOB):
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
        """Find direct state writes bypassing validation.

        Legitimate patterns (not flagged):
        - action_* methods (standard Odoo pattern)
        - _*_pipeline methods (documented pipeline methods)
        - Methods with "State transitions" docstring (explicitly documented)
        """
        errors = []

        for py_file in self.root_dir.rglob(MODELS_GLOB):
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
                        # Find the enclosing method by looking for most recent 'def '
                        method_start_line = 0
                        for j in range(i - 2, -1, -1):
                            if re.match(r"\s*def\s+", lines[j]):
                                method_start_line = j
                                break

                        # Get context from method start to current line
                        method_context = "\n".join(lines[method_start_line:i])

                        # Legitimate patterns:
                        # 1. action_* methods (standard Odoo pattern)
                        # 2. _*_pipeline methods (documented pipeline methods)
                        # 3. Methods with "State transitions" in docstring
                        is_action_method = "def action_" in method_context
                        is_pipeline_method = re.search(r"def _\w*pipeline", method_context)
                        has_state_docstring = "State transitions" in method_context

                        if not (is_action_method or is_pipeline_method or has_state_docstring):
                            errors.append(
                                {
                                    "type": "STATE_BYPASS",
                                    "severity": "MODERATE",
                                    "file": str(py_file.relative_to(self.root_dir)),
                                    "line": i,
                                    "message": "Direct state write outside action method",
                                    "fix": "Use action_* methods or document state transitions in docstring",
                                }
                            )

        return errors
