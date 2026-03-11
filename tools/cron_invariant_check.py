#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Violation:
    path: str
    line: int
    code: str
    message: str

    def format(self) -> str:
        return f"{self.path}:{self.line}: {self.code} {self.message}"


def _is_cron_method(node: ast.FunctionDef) -> bool:
    return node.name.startswith(("cron_", "_cron_", "action_cron_")) or node.name in {"run_monthly_audit"}


def _attr_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _string_literals(node: ast.AST) -> list[str]:
    out: list[str] = []
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        out.append(node.value)
    elif isinstance(node, ast.JoinedStr):
        for val in node.values:
            if isinstance(val, ast.Constant) and isinstance(val.value, str):
                out.append(val.value)
    return out


def _walk_calls(node: ast.AST):
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            yield child


def _calls_with_attr(node: ast.AST, attr: str) -> list[ast.Call]:
    return [c for c in _walk_calls(node) if _attr_name(c) == attr]


def _call_has_kw(call: ast.Call, kw: str) -> bool:
    return any(k.arg == kw for k in call.keywords if k.arg)


def _is_self_model_call(call: ast.Call) -> bool:
    if not isinstance(call.func, ast.Attribute):
        return False
    owner = call.func.value
    return isinstance(owner, ast.Name) and owner.id == "self"


def analyze_python_file(path: Path) -> list[Violation]:
    violations: list[Violation] = []
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [Violation(str(path), exc.lineno or 1, "CRON001", f"Python parse error: {exc.msg}")]

    lines = source.splitlines()

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or not _is_cron_method(node):
            continue

        # Search/search_read invariants
        for call in _walk_calls(node):
            attr = _attr_name(call)
            if attr not in {"search", "search_read"}:
                continue

            has_order = _call_has_kw(call, "order")
            has_limit = _call_has_kw(call, "limit")

            if not has_order:
                violations.append(
                    Violation(
                        str(path),
                        call.lineno,
                        "CRON101",
                        f"{node.name}: {attr}() missing explicit order=",
                    )
                )
            if has_limit and not has_order:
                violations.append(
                    Violation(
                        str(path),
                        call.lineno,
                        "CRON102",
                        f"{node.name}: {attr}() uses limit without order",
                    )
                )
            if _is_self_model_call(call) and not has_limit:
                violations.append(
                    Violation(
                        str(path),
                        call.lineno,
                        "CRON103",
                        f"{node.name}: {attr}() missing limit (unbounded cron query)",
                    )
                )

        # browse loops
        for for_node in [n for n in ast.walk(node) if isinstance(n, ast.For)]:
            iter_expr = for_node.iter
            if isinstance(iter_expr, ast.Call) and _attr_name(iter_expr) == "browse":
                violations.append(
                    Violation(
                        str(path),
                        for_node.lineno,
                        "CRON104",
                        f"{node.name}: loop over browse() detected; require deterministic ordered source",
                    )
                )

        # sudo checks
        for sudo_call in _calls_with_attr(node, "sudo"):
            line = lines[sudo_call.lineno - 1] if 0 < sudo_call.lineno <= len(lines) else ""
            if "cron-sudo-justification:" not in line:
                violations.append(
                    Violation(
                        str(path),
                        sudo_call.lineno,
                        "CRON105",
                        f"{node.name}: sudo() used without inline '# cron-sudo-justification:'",
                    )
                )

        # advisory lock lifecycle checks
        execute_calls = _calls_with_attr(node, "execute")
        lock_calls: list[ast.Call] = []
        unlock_calls: list[ast.Call] = []
        for call in execute_calls:
            if not call.args:
                continue
            sql_text = " ".join(_string_literals(call.args[0]))
            if "pg_advisory_unlock" in sql_text:
                unlock_calls.append(call)
            elif "pg_try_advisory_lock" in sql_text or "pg_advisory_lock" in sql_text:
                lock_calls.append(call)

        if lock_calls or unlock_calls:
            if not lock_calls and unlock_calls:
                violations.append(
                    Violation(
                        str(path), unlock_calls[0].lineno, "CRON201", f"{node.name}: unlock without lock acquisition"
                    )
                )
            if len(lock_calls) > 1:
                violations.append(
                    Violation(
                        str(path), lock_calls[1].lineno, "CRON202", f"{node.name}: multiple advisory lock acquisitions"
                    )
                )
            if len(unlock_calls) > 1:
                violations.append(
                    Violation(
                        str(path), unlock_calls[1].lineno, "CRON203", f"{node.name}: multiple advisory unlock calls"
                    )
                )
            if lock_calls and unlock_calls and unlock_calls[0].lineno < lock_calls[0].lineno:
                violations.append(
                    Violation(str(path), unlock_calls[0].lineno, "CRON204", f"{node.name}: unlock occurs before lock")
                )

            # unlock must be in finally block
            finally_unlock_lines = set()
            for try_node in [n for n in ast.walk(node) if isinstance(n, ast.Try)]:
                for fnode in try_node.finalbody:
                    for c in _walk_calls(fnode):
                        if c in unlock_calls:
                            finally_unlock_lines.add(c.lineno)

            for u in unlock_calls:
                if u.lineno not in finally_unlock_lines:
                    violations.append(
                        Violation(
                            str(path), u.lineno, "CRON205", f"{node.name}: advisory unlock must be inside finally"
                        )
                    )

            if lock_calls and not unlock_calls:
                violations.append(
                    Violation(str(path), lock_calls[0].lineno, "CRON206", f"{node.name}: lock acquired without unlock")
                )

    return violations


def analyze_xml_file(path: Path) -> list[Violation]:
    violations: list[Violation] = []
    try:
        root = ET.parse(path).getroot()  # nosec B314 — repo tooling parsing trusted repo XML files
    except ET.ParseError as exc:
        return [Violation(str(path), 1, "CRON301", f"XML parse error: {exc}")]

    for rec in root.findall(".//record"):
        if rec.get("model") != "ir.cron":
            continue
        rec_id = rec.get("id", "<unknown>")
        user_fields = [f for f in rec.findall("field") if f.get("name") == "user_id"]
        if not user_fields:
            violations.append(Violation(str(path), 1, "CRON302", f"{rec_id}: ir.cron missing user_id field"))
            continue
        ref = user_fields[0].get("ref", "")
        if ref == "base.user_root":
            violations.append(Violation(str(path), 1, "CRON303", f"{rec_id}: base.user_root is forbidden"))
        if ref != "plasticos_base.user_system_cron":
            violations.append(
                Violation(
                    str(path),
                    1,
                    "CRON304",
                    f"{rec_id}: user_id must reference plasticos_base.user_system_cron (found: {ref or '<none>'})",
                )
            )

    return violations


def collect_files(root: Path) -> tuple[list[Path], list[Path]]:
    py_files = [
        p
        for p in root.rglob("*.py")
        if ".git" not in p.parts
        and "__pycache__" not in p.parts
        and p.parts[0] != ".venv"
        and "plasticos_graph_" not in str(p)
        and "docs" not in p.parts
        and ".cursor" not in p.parts
        and "tests-odoo" not in p.parts
        and "odoo-enterprise" not in p.parts
    ]
    xml_files = [
        p
        for p in root.rglob("*.xml")
        if ".git" not in p.parts
        and "__pycache__" not in p.parts
        and p.parts[0] != ".venv"
        and "plasticos_graph_" not in str(p)
        and "docs" not in p.parts
        and ".cursor" not in p.parts
        and "tests-odoo" not in p.parts
        and "odoo-enterprise" not in p.parts
    ]
    return py_files, xml_files


def run(root: Path) -> list[Violation]:
    py_files, xml_files = collect_files(root)
    violations: list[Violation] = []
    for path in py_files:
        violations.extend(analyze_python_file(path))
    for path in xml_files:
        violations.extend(analyze_xml_file(path))
    return sorted(violations, key=lambda v: (v.path, v.line, v.code))


def main() -> int:
    parser = argparse.ArgumentParser(description="Cron invariant checker")
    parser.add_argument("--root", default=".", help="Repository root")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    violations = run(root)
    if violations:
        print(f"CRON_INVARIANT_VIOLATIONS: {len(violations)}")
        for v in violations:
            print(v.format())
        return 1

    print("CRON_INVARIANTS_OK: 0 violations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
