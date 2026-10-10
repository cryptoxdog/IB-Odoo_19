#!/usr/bin/env python3
"""
Business Logic Anti-Pattern Detector
Catches common Odoo coding mistakes.
"""

import io
import re
import tokenize
from pathlib import Path

from path_filters import skip_path

# Same-line placement is repo law: .cursor/rules/71-plasticos-security-model.mdc
# and .cursor/rules/00-plasticos-master-context.mdc ("inline comment on the same
# line"). The accepted markers are the two spellings already used in models/.
_SUDO_JUSTIFICATION = re.compile(r"^#\s*(?:sudo|cron-sudo-justification)\s*:\s*(?P<why>.*)$")
_TRIVIA = frozenset({tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENCODING})
_PLACEHOLDER_WORDS = frozenset(
    {"todo", "tbd", "fixme", "xxx", "n/a", "na", "none", "needed", "required", "justified", "ok"}
)


def _is_sudo_justification(comment: str) -> bool:
    """True for ``# sudo: <reason>`` with a substantive reason.

    A generic comment (``# noqa``), an empty marker, or a one-word placeholder
    is not a justification. This checks documentation only; it never proves
    that the caller is authorized to perform the elevated operation.
    """
    match = _SUDO_JUSTIFICATION.match(comment.strip())
    if not match:
        return False
    words = re.findall(r"[A-Za-z][A-Za-z/'-]*", match.group("why"))
    return len(words) >= 2 and not all(word.lower() in _PLACEHOLDER_WORDS for word in words)


def _sudo_call_lines(source: str) -> dict[int, bool] | None:
    """Map each line holding an executable ``.sudo()`` call to its justification state.

    Uses the Python tokenizer, so ``.sudo()`` or ``#`` inside a string or a
    comment is not mistaken for code or for a comment. Returns ``None`` when the
    source cannot be tokenized, so the caller can fail closed.
    """
    try:
        tokens = [t for t in tokenize.generate_tokens(io.StringIO(source).readline) if t.type not in _TRIVIA]
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return None
    comments = {t.start[0]: t.string for t in tokens if t.type == tokenize.COMMENT}
    code = [t for t in tokens if t.type != tokenize.COMMENT]
    calls: dict[int, bool] = {}
    for i in range(1, len(code) - 2):
        dot, name, lpar, rpar = code[i - 1], code[i], code[i + 1], code[i + 2]
        if (
            name.type == tokenize.NAME
            and name.string == "sudo"
            and dot.string == "."
            and lpar.string == "("
            and rpar.string == ")"
        ):
            line = name.start[0]
            calls[line] = _is_sudo_justification(comments.get(line, ""))
    return calls


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

        for py_file in self.root_dir.rglob("models/*.py"):
            if skip_path(py_file):
                continue
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

        for py_file in self.root_dir.rglob("models/*.py"):
            if skip_path(py_file):
                continue
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
        """Find executable ``.sudo()`` calls without a same-line justification.

        Repo law requires a ``# sudo: <reason>`` comment on the same line as
        ``.sudo()``. A comment on an earlier line does not count. Passing this
        check means the justification is documented; it is not proof that the
        caller is authorized, which only the code before the elevation can give.
        """
        errors = []

        for py_file in self.root_dir.rglob("models/*.py"):
            if skip_path(py_file):
                continue
            source = py_file.read_text(encoding="utf-8")
            lines = source.splitlines()
            calls = _sudo_call_lines(source)
            if calls is None:
                # Untokenizable source: fail closed on every textual occurrence.
                calls = {i: False for i, line in enumerate(lines, 1) if ".sudo()" in line}

            for i, justified in sorted(calls.items()):
                if justified:
                    continue
                errors.append(
                    {
                        "type": "UNJUSTIFIED_SUDO",
                        "severity": "MODERATE",
                        "file": str(py_file.relative_to(self.root_dir)),
                        "line": i,
                        "code": lines[i - 1].strip(),
                        "message": "sudo() lacks a same-line justification comment",
                        "fix": (
                            "Keep the elevation only when the caller is authorized before it, and state "
                            "why on this line as '# sudo: <reason>'. A preceding comment is not accepted, "
                            "and a comment is never proof of authorization."
                        ),
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

        for py_file in self.root_dir.rglob("models/*.py"):
            if skip_path(py_file):
                continue
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
