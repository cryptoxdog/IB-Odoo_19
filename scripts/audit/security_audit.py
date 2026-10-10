#!/usr/bin/env python3
"""
Security Vulnerability Audit
Finds common security issues in Odoo code.
"""

import ast
import re
from pathlib import Path

from path_filters import skip_path

_SENSITIVE_NAME = re.compile(r"password|token|secret|api_key|credit_card|ssn", re.IGNORECASE)
_LOG_METHODS = frozenset({"debug", "info", "warning", "error", "exception", "critical", "log"})


def _is_sensitive_name(node):
    """True when an identifier being emitted names a secret."""
    if isinstance(node, ast.Name):
        return bool(_SENSITIVE_NAME.search(node.id))
    if isinstance(node, ast.Attribute):
        return bool(_SENSITIVE_NAME.search(node.attr)) or _is_sensitive_name(node.value)
    if isinstance(node, ast.Subscript):
        key = node.slice
        if isinstance(key, ast.Constant) and isinstance(key.value, str) and _SENSITIVE_NAME.search(key.value):
            return True
        return _is_sensitive_name(node.value)
    return False


def _emitted_values(expr):
    """Values interpolated into a log call. Static text is not a value."""
    if expr is None or isinstance(expr, ast.Constant):
        return []
    if isinstance(expr, ast.JoinedStr):
        values = []
        for part in expr.values:
            if isinstance(part, ast.FormattedValue):
                values.extend(_emitted_values(part.value) or [part.value])
        return values
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Mod):
        return _emitted_values(expr.right) or [expr.right]
    if isinstance(expr, (ast.Tuple, ast.List, ast.Set)):
        values = []
        for elt in expr.elts:
            values.extend(_emitted_values(elt) or [elt])
        return values
    if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute) and expr.func.attr == "format":
        values = []
        for arg in expr.args:
            values.extend(_emitted_values(arg) or [arg])
        for keyword in expr.keywords:
            if keyword.value is not None:
                values.extend(_emitted_values(keyword.value) or [keyword.value])
        return values
    return [expr]


def _is_log_call(node):
    func = node.func
    if isinstance(func, ast.Name) and func.id == "print":
        return True
    if not isinstance(func, ast.Attribute) or func.attr not in _LOG_METHODS:
        return False
    owner = func.value
    if isinstance(owner, ast.Name):
        return "log" in owner.id.lower()
    if isinstance(owner, ast.Attribute):
        return owner.attr in {"logger", "log"} or "log" in owner.attr.lower()
    if isinstance(owner, ast.Call) and isinstance(owner.func, ast.Attribute):
        return owner.func.attr == "getLogger"
    return False


def _call_emits_secret(node):
    emitted = []
    for arg in node.args:
        emitted.extend(_emitted_values(arg))
    for keyword in node.keywords:
        if keyword.value is not None:
            emitted.extend(_emitted_values(keyword.value))
    return any(_is_sensitive_name(value) for value in emitted)


class SecurityAudit:
    def __init__(self, root_dir="."):
        self.root_dir = Path(root_dir)

    def check_controller_security(self):
        """Find controllers without proper auth"""
        errors = []

        for py_file in self.root_dir.rglob("controllers/*.py"):
            if skip_path(py_file):
                continue
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
        """Find log and print calls that emit a secret value.

        A static message that merely contains words such as ``api_key`` is not
        a finding. Interpolation of a sensitive name is.
        """
        errors = []

        for py_file in self.root_dir.rglob("**/*.py"):
            if skip_path(py_file):
                continue
            if ".venv" in str(py_file) or "venv" in str(py_file) or "tests/" in str(py_file):
                continue
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source)
            except (OSError, SyntaxError, UnicodeError):
                continue
            lines = source.splitlines()
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not _is_log_call(node) or not _call_emits_secret(node):
                    continue
                line_num = getattr(node, "lineno", 1)
                code = lines[line_num - 1].strip() if 0 < line_num <= len(lines) else ""
                errors.append(
                    {
                        "type": "SENSITIVE_DATA_LOGGED",
                        "severity": "HIGH",
                        "file": str(py_file.relative_to(self.root_dir)),
                        "line": line_num,
                        "code": code,
                        "message": "Log call emits a sensitive value",
                        "fix": "Mask or remove sensitive fields from logs",
                    }
                )

        return errors
