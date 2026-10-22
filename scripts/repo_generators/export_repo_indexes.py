#!/usr/bin/env python3
"""
Repo Index Exporter (l9-repo-index skill — repo-local generator)

Regenerates the fast-lookup index files under reports/repo-index/*.txt:
  class_definitions, function_signatures, method_catalog, imports,
  inheritance_graph, test_catalog, route_handlers, pydantic_models,
  readme_manifest, and (when the repo contains Odoo modules)
  odoo_model_registry, odoo_module_dependencies, odoo_xml_data_files,
  odoo_views, odoo_security_groups, odoo_email_templates, odoo_cron_jobs,
  odoo_automations.

Run: python3 scripts/repo_generators/export_repo_indexes.py [repo_root]
     (defaults to the current working directory)

Exit codes:
  0 = indexes written successfully
  1 = repo root invalid
"""

import ast
import re
import sys
from pathlib import Path

EXCLUDE_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "odoo-enterprise",
    ".semgrep",
}
INDEX_SUBDIR = ("reports", "repo-index")

CLASS_RE = re.compile(r"^\s*class\s+\w+")
FUNCTION_RE = re.compile(r"^\s*(async\s+)?def\s+\w+")
METHOD_RE = re.compile(r"^\s{4,}(async\s+)?def\s+\w+")
IMPORT_RE = re.compile(r"^\s*(import\s+\S+|from\s+\S+\s+import)")
ROUTE_RE = re.compile(r"@http\.route|@route\(")
TEST_RE = re.compile(r"^\s*(class Test\w+|def test_\w+)")
INHERIT_RE = re.compile(r"_(name|inherit|inherits)\s*=")
PYDANTIC_RE = re.compile(r"class\s+\w+\(.*BaseModel")
ODOO_MODEL_RE = re.compile(r"_name\s*=\s*['\"]")
HEADING_RE = re.compile(r"^#\s+")


def iter_files(root: Path, suffix: str):
    """Yield files under root matching suffix, skipping excluded dirs and the index output dir."""
    for path in root.rglob(f"*{suffix}"):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(root).parts
        if any(part in EXCLUDE_DIR_NAMES for part in rel_parts):
            continue
        if rel_parts[: len(INDEX_SUBDIR)] == INDEX_SUBDIR:
            continue
        yield path


def rel(root: Path, path: Path) -> str:
    return f"./{path.relative_to(root).as_posix()}"


def grep_lines(root: Path, suffix: str, pattern: re.Pattern) -> list[str]:
    out: list[str] = []
    for path in sorted(iter_files(root, suffix)):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                out.append(f"{rel(root, path)}:{lineno}:{line}")
    return out


def readme_manifest(root: Path) -> list[str]:
    out: list[str] = []
    for path in sorted(root.rglob("README*.md")):
        rel_parts = path.relative_to(root).parts
        if any(part in EXCLUDE_DIR_NAMES for part in rel_parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if HEADING_RE.search(line):
                out.append(f"{rel(root, path)}:{lineno}:{line}")
    return out


def xml_matching(root: Path, needle: str) -> list[str]:
    out: list[str] = []
    for path in sorted(iter_files(root, ".xml")):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if needle in line:
                out.append(f"{rel(root, path)}:{lineno}:{line}")
    return out


def xml_paths_under(root: Path, dir_name: str) -> list[str]:
    return sorted(rel(root, path) for path in iter_files(root, ".xml") if dir_name in path.relative_to(root).parts)


def odoo_module_dependencies(root: Path) -> list[str]:
    out: list[str] = []
    for path in sorted(root.glob("*/__manifest__.py")):
        try:
            manifest = ast.literal_eval(path.read_text(encoding="utf-8", errors="ignore"))
        except (SyntaxError, ValueError):
            out.append(f"{rel(root, path)}: <unparsable manifest>")
            continue
        depends = manifest.get("depends", []) if isinstance(manifest, dict) else []
        out.append(f"{path.parent.name}\t{rel(root, path)}\tdepends={depends}")
    return out


def is_odoo_repo(root: Path) -> bool:
    return any(root.glob("*/__manifest__.py"))


def write_index(root: Path, name: str, lines: list[str]) -> int:
    out_dir = root.joinpath(*INDEX_SUBDIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{name}.txt"
    out_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return len(lines)


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    if not root.is_dir():
        print(f"ERROR: repo root not found: {root}", file=sys.stderr)
        return 1

    counts: dict[str, int] = {}
    counts["class_definitions"] = write_index(root, "class_definitions", grep_lines(root, ".py", CLASS_RE))
    counts["function_signatures"] = write_index(root, "function_signatures", grep_lines(root, ".py", FUNCTION_RE))
    counts["method_catalog"] = write_index(root, "method_catalog", grep_lines(root, ".py", METHOD_RE))
    counts["imports"] = write_index(root, "imports", grep_lines(root, ".py", IMPORT_RE))
    counts["route_handlers"] = write_index(root, "route_handlers", grep_lines(root, ".py", ROUTE_RE))
    counts["test_catalog"] = write_index(root, "test_catalog", grep_lines(root, ".py", TEST_RE))
    counts["inheritance_graph"] = write_index(root, "inheritance_graph", grep_lines(root, ".py", INHERIT_RE))
    counts["pydantic_models"] = write_index(root, "pydantic_models", grep_lines(root, ".py", PYDANTIC_RE))
    counts["readme_manifest"] = write_index(root, "readme_manifest", readme_manifest(root))

    if is_odoo_repo(root):
        counts["odoo_model_registry"] = write_index(root, "odoo_model_registry", grep_lines(root, ".py", ODOO_MODEL_RE))
        counts["odoo_module_dependencies"] = write_index(
            root, "odoo_module_dependencies", odoo_module_dependencies(root)
        )
        counts["odoo_xml_data_files"] = write_index(
            root,
            "odoo_xml_data_files",
            sorted(set(xml_paths_under(root, "data") + xml_paths_under(root, "security"))),
        )
        counts["odoo_views"] = write_index(root, "odoo_views", xml_paths_under(root, "views"))
        counts["odoo_security_groups"] = write_index(
            root, "odoo_security_groups", xml_matching(root, 'model="res.groups"')
        )
        counts["odoo_email_templates"] = write_index(
            root, "odoo_email_templates", xml_matching(root, 'model="mail.template"')
        )
        counts["odoo_cron_jobs"] = write_index(root, "odoo_cron_jobs", xml_matching(root, 'model="ir.cron"'))
        counts["odoo_automations"] = write_index(
            root, "odoo_automations", xml_matching(root, 'model="base.automation"')
        )

    print("## INDEX UPDATED\n")
    print("| Index | Entries |")
    print("|---|---|")
    for name, count in counts.items():
        print(f"| {name} | {count} |")
    print(f"\nLocation: {root.joinpath(*INDEX_SUBDIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
