#!/usr/bin/env python3
"""
Security Vulnerability Audit
Finds common security issues in Odoo code.
"""

import re
from pathlib import Path


class SecurityAudit:
    def __init__(self, root_dir="."):
        self.root_dir = Path(root_dir)

    def check_controller_security(self):
        """Find controllers without proper auth"""
        errors = []

        for py_file in self.root_dir.rglob("controllers/*.py"):
            with open(py_file, encoding="utf-8") as f:
                content = f.read()

                # Find @http.route decorators
                for match in re.finditer(r"@http\.route\((.*?)\)\s*def\s+(\w+)", content, re.DOTALL):
                    route_args = match.group(1)
                    method_name = match.group(2)

                    # Check authentication
                    if "auth=" not in route_args:
                        errors.append(
                            {
                                "type": "NO_AUTH_SPECIFIED",
                                "severity": "HIGH",
                                "file": str(py_file.relative_to(self.root_dir)),
                                "method": method_name,
                                "message": f"Controller '{method_name}' has no auth specified",
                                "fix": "Add auth='user' or auth='public' to @http.route",
                            }
                        )

                    # Check CSRF for POST routes
                    if "'POST'" in route_args and "csrf=False" in route_args:
                        errors.append(
                            {
                                "type": "CSRF_DISABLED",
                                "severity": "HIGH",
                                "file": str(py_file.relative_to(self.root_dir)),
                                "method": method_name,
                                "message": "POST route with CSRF disabled",
                                "fix": "Remove csrf=False unless justified",
                            }
                        )

        return errors

    def check_sensitive_logging(self):
        """Find sensitive data in log statements"""
        errors = []

        SENSITIVE_PATTERNS = [
            r"password",
            r"token",
            r"secret",
            r"api_key",
            r"credit_card",
            r"ssn",
        ]

        for py_file in self.root_dir.rglob("**/*.py"):
            # Skip virtual environments and test files
            if ".venv" in str(py_file) or "venv" in str(py_file) or "tests/" in str(py_file):
                continue

            with open(py_file, encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    if "_logger." in line or "print(" in line:
                        for pattern in SENSITIVE_PATTERNS:
                            if re.search(pattern, line, re.IGNORECASE):
                                errors.append(
                                    {
                                        "type": "SENSITIVE_DATA_LOGGED",
                                        "severity": "HIGH",
                                        "file": str(py_file.relative_to(self.root_dir)),
                                        "line": line_num,
                                        "code": line.strip(),
                                        "message": "Potentially sensitive data in log statement",
                                        "fix": "Mask or remove sensitive fields from logs",
                                    }
                                )

        return errors
