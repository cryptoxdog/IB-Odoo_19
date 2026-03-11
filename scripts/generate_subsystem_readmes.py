#!/usr/bin/env python3
"""




DEPLOYMENT_MD = "DEPLOYMENT.md"
DATA_MODEL_MD = "DATA_MODEL.md"
API_REFERENCE_MD = "API_REFERENCE.md"
ARCHITECTURE_MD = "ARCHITECTURE.md"
Repo-agnostic subsystem README generator.

- AST-heavy parsing: Python modules (ast.parse), Odoo manifests (ast.literal_eval)
- Core docs discovery: reads 18 standard docs when present to enrich READMEs
- Repo types: Odoo (__manifest__.py), Python packages, generic

Usage:
  python scripts/generate_subsystem_readmes.py [--tier TIER] [--subsystem NAME] [--skip-time-verify]
  python scripts/generate_subsystem_readmes.py --list
  python scripts/generate_subsystem_readmes.py --validate
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Core docs catalog (from ai files to harvest)
# ---------------------------------------------------------------------------

CORE_DOCS = [
    ARCHITECTURE_MD,
    API_REFERENCE_MD,
    DATA_MODEL_MD,
    "WORKFLOW_GUIDE.md",
    "TEST_STRATEGY.md",
    DEPLOYMENT_MD,
    "MIGRATION_GUIDE.md",
    "SECURITY_MODEL.md",
    "CHANGELOG.md",
    "ROADMAP.md",
    "ENVIRONMENT_SPEC.yaml",
    "NEO4J_ONTOLOGY.yaml",
    "README.md",
    "QUICK_START.md",
    "CONTRIBUTING.md",
    "GLOSSARY.md",
    "FAQ.md",
    "LICENSE",
]

DOC_SEARCH_PATHS = ["", "docs", "AI Agent Files", "docs/AI Files", "doc", ".cursor/docs"]


def _get_repo_root() -> Path:
    root = Path(__file__).resolve().parent.parent
    env_root = Path.cwd()
    if (env_root / "config" / "subsystems").exists():
        return env_root
    return root


def _get_config_path(repo_root: Path) -> Path:
    import os

    env_path = os.environ.get("README_PIPELINE_CONFIG")
    if env_path:
        return Path(env_path)
    return repo_root / "config" / "subsystems" / "readme_config.yaml"


def _parse_manifest(manifest_path: Path) -> dict | None:
    """Parse __manifest__.py via AST literal_eval."""
    try:
        content = manifest_path.read_text(encoding="utf-8")
        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            return None
        return ast.literal_eval(match.group(0))
    except (SyntaxError, ValueError):
        return None


def _extract_model_attrs_ast(content: str) -> dict:
    """Extract _name, _inherit, _description, fields from model file using AST + regex."""
    attrs: dict[str, Any] = {
        "_name": None,
        "_inherit": None,
        "_description": None,
        "fields": [],
        "class_name": None,
    }
    # Class name
    class_match = re.search(r"class\s+(\w+)\s*\([^)]*models\.Model", content)
    if class_match:
        attrs["class_name"] = class_match.group(1)
    # _name
    m = re.search(r'_name\s*=\s*["\']([^"\']+)["\']', content)
    if m:
        attrs["_name"] = m.group(1)
    # _inherit
    m = re.search(r"_inherit\s*=\s*\[([^\]]+)\]", content)
    if m:
        attrs["_inherit"] = [x.strip().strip("\"'") for x in m.group(1).split(",")]
    else:
        m = re.search(r'_inherit\s*=\s*["\']([^"\']+)["\']', content)
        if m:
            attrs["_inherit"] = [m.group(1)]
    # _description
    m = re.search(r'_description\s*=\s*["\']([^"\']*)["\']', content)
    if m:
        attrs["_description"] = m.group(1)
    # Fields
    for m in re.finditer(r"(\w+)\s*=\s*fields\.(\w+)\s*\(", content):
        attrs["fields"].append((m.group(1), m.group(2)))
    return attrs


class _ModuleVisitor(ast.NodeVisitor):
    """AST visitor to extract classes and top-level functions."""

    def __init__(self) -> None:
        self.classes: list[dict[str, str]] = []
        self.functions: list[dict[str, str]] = []
        self._in_class = False

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        cls_doc = ast.get_docstring(node) or ""
        self.classes.append({"name": node.name, "doc": cls_doc.strip().split("\n")[0][:120]})
        old = self._in_class
        self._in_class = True
        self.generic_visit(node)
        self._in_class = old

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if not self._in_class:
            fn_doc = ast.get_docstring(node) or ""
            self.functions.append({"name": node.name, "doc": fn_doc.strip().split("\n")[0][:80]})
        self.generic_visit(node)


def _ast_parse_python_module(path: Path) -> dict:
    """Parse Python module with AST to extract classes and top-level functions."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return {"classes": [], "functions": [], "docstring": None}
    visitor = _ModuleVisitor()
    visitor.visit(tree)
    doc = ast.get_docstring(tree)
    return {
        "classes": visitor.classes,
        "functions": visitor.functions,
        "docstring": doc.strip().split("\n")[0][:200] if doc else None,
    }


def _discover_core_docs(repo_root: Path, config: dict) -> dict[str, str]:
    """Discover and read core docs when present. Returns {filename: content_snippet}."""
    docs = config.get("core_docs", CORE_DOCS)
    paths = config.get("doc_search_paths", DOC_SEARCH_PATHS)
    found: dict[str, str] = {}
    for name in docs:
        for base in paths:
            p = repo_root / (base or ".").lstrip("/") / name
            if p.exists() and p.is_file():
                try:
                    raw = p.read_text(encoding="utf-8", errors="replace")
                    # First 500 chars as snippet for injection
                    found[name] = raw[:500].strip()
                except OSError:
                    pass
                break
    return found


def _detect_repo_type(repo_root: Path) -> str:
    if list(repo_root.glob("*/__manifest__.py")):
        return "odoo"
    for d in ["", "src", "lib"]:
        base = repo_root / d if d else repo_root
        if base.exists() and list(base.glob("**/__init__.py")):
            return "python"
    return "generic"


def _build_odoo_subsystems(repo_root: Path) -> dict[str, dict]:
    """Build subsystem map from Odoo manifests + AST model extraction."""
    subsystems: dict[str, dict] = {}
    for manifest_path in repo_root.glob("*/__manifest__.py"):
        module = manifest_path.parent.name
        if module.startswith("tests") or module == "scripts":
            continue
        m = _parse_manifest(manifest_path)
        if not m:
            continue
        models: list[str] = []
        models_dir = manifest_path.parent / "models"
        if models_dir.is_dir():
            for py in models_dir.glob("*.py"):
                if py.name.startswith("__"):
                    continue
                attrs = _extract_model_attrs_ast(py.read_text(encoding="utf-8"))
                if attrs.get("_name") or attrs.get("_inherit"):
                    models.append(attrs.get("_name") or attrs.get("class_name") or py.stem)
        depends = m.get("depends", [])
        subsystems[module] = {
            "path": module,
            "tier": "core",
            "purpose": m.get("summary", m.get("name", module)),
            "summary": m.get("summary", ""),
            "version": m.get("version", "1.0.0"),
            "depends": depends,
            "models": models,
        }
    return subsystems


def _load_yaml(path: Path) -> dict | None:
    """Load YAML file. Uses PyYAML if available, else minimal parsing."""
    try:
        import yaml

        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except ImportError:
        pass
    except Exception:
        pass
    return None


def _ensure_config(repo_root: Path, config_path: Path, repo_type: str) -> dict:
    """Load or create minimal config."""
    if config_path.exists():
        loaded = _load_yaml(config_path)
        if loaded:
            return loaded
    # Create minimal config
    config_path.parent.mkdir(parents=True, exist_ok=True)
    subsystems = _build_odoo_subsystems(repo_root) if repo_type == "odoo" else {}
    minimal = {
        "version": "1.0.0",
        "repo_type": repo_type,
        "subsystems": subsystems,
        "core_docs": CORE_DOCS,
        "doc_search_paths": DOC_SEARCH_PATHS,
        "template": """
---
component_id: "{component_id}"
component_name: "{component_name}"
module_version: "{version}"
layer: "{tier}"
purpose: "{purpose}"
summary: "{summary}"
---

# {component_name}

## Purpose
{purpose}

## Summary
{summary}

## Structure
```
{structure}
```

## Dependencies
{dependencies}

## Models
{models}

## Tier
{tier}
""",
    }
    try:
        import yaml

        config_path.write_text(yaml.dump(minimal, default_flow_style=False, sort_keys=False), encoding="utf-8")
    except ImportError:
        config_path.write_text(json.dumps(minimal, indent=2).replace("'", '"'), encoding="utf-8")
    return minimal


def _get_structure(repo_root: Path, path: str) -> str:
    """Produce directory structure for subsystem."""
    p = repo_root / path
    if not p.is_dir():
        return path
    lines: list[str] = []
    for child in sorted(p.iterdir()):
        if child.name.startswith(".") or child.name == "__pycache__":
            continue
        rel = child.relative_to(p)
        if child.is_dir():
            lines.append(f"{rel}/")
        else:
            lines.append(str(rel))
    return "\n".join(lines[:30]) if lines else path


def _enrich_from_manifest(repo_root: Path, path: str) -> dict:
    """Enrich subsystem with manifest data (depends, version, models) for Odoo."""
    manifest_path = repo_root / path / "__manifest__.py"
    if not manifest_path.exists():
        return {}
    m = _parse_manifest(manifest_path)
    if not m:
        return {}
    models: list[str] = []
    models_dir = repo_root / path / "models"
    if models_dir.is_dir():
        for py in models_dir.glob("*.py"):
            if py.name.startswith("__"):
                continue
            attrs = _extract_model_attrs_ast(py.read_text(encoding="utf-8"))
            if attrs.get("_name"):
                models.append(attrs["_name"])
    return {
        "depends": m.get("depends", []),
        "version": m.get("version", "1.0.0"),
        "models": models,
    }


def generate_readme(
    repo_root: Path,
    config: dict,
    subsystem_id: str,
    subsystem: dict,
    core_docs: dict[str, str],
) -> str:
    """Generate README content from template and AST-derived data."""
    template = config.get("template", "{component_name}\n\n{purpose}")
    path = subsystem.get("path", subsystem_id)
    structure = _get_structure(repo_root, path)
    # Enrich from manifest for Odoo (depends, models, version)
    manifest_data = _enrich_from_manifest(repo_root, path)
    if manifest_data:
        subsystem = {**subsystem, **manifest_data}
    depends = subsystem.get("depends", [])
    models = subsystem.get("models", [])
    if not models and (repo_root / path / "models").is_dir():
        models_dir = repo_root / path / "models"
        for py in models_dir.glob("*.py"):
            if py.name.startswith("__"):
                continue
            attrs = _extract_model_attrs_ast(py.read_text(encoding="utf-8"))
            if attrs.get("_name"):
                models.append(attrs["_name"])
    deps_str = ", ".join(depends) if depends else "—"
    models_str = ", ".join(models) if models else "—"
    component_name = subsystem_id.replace("_", " ").title()
    version = subsystem.get("version", "1.0.0")
    purpose = subsystem.get("purpose", "")
    summary = subsystem.get("summary", purpose)
    tier = subsystem.get("tier", "core")
    ctx = {
        "component_id": subsystem_id,
        "component_name": component_name,
        "version": version,
        "purpose": purpose,
        "summary": summary,
        "tier": tier,
        "structure": structure,
        "dependencies": deps_str,
        "models": models_str,
    }
    out = template
    for k, v in ctx.items():
        out = out.replace("{" + k + "}", str(v))
    if core_docs:
        out += "\n\n## Related Documentation\n\n"
        for name in [ARCHITECTURE_MD, API_REFERENCE_MD, DATA_MODEL_MD, DEPLOYMENT_MD]:
            if name in core_docs:
                out += f"- `{name}` — {core_docs[name][:80].replace(chr(10), ' ')}...\n"
        if not any(n in core_docs for n in [ARCHITECTURE_MD, API_REFERENCE_MD, DATA_MODEL_MD, DEPLOYMENT_MD]):
            out += "- *(No core docs found in repo root or docs/)*\n"
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate subsystem READMEs")
    parser.add_argument("--tier", type=str, help="Filter by tier")
    parser.add_argument("--subsystem", type=str, help="Generate single subsystem")
    parser.add_argument("--skip-time-verify", action="store_true", help="Skip timestamp checks")
    parser.add_argument("--list", action="store_true", help="List configured subsystems")
    parser.add_argument("--validate", action="store_true", help="Validate config only")
    args = parser.parse_args()

    repo_root = _get_repo_root()
    config_path = _get_config_path(repo_root)
    repo_type = _detect_repo_type(repo_root)
    config = _ensure_config(repo_root, config_path, repo_type)
    subsystems = config.get("subsystems", {})
    core_docs = _discover_core_docs(repo_root, config)

    if args.list:
        print("## Subsystems")
        for sid, s in subsystems.items():
            print(f"  - {sid} (tier={s.get('tier', '?')})")
        print(f"\nCore docs found: {list(core_docs.keys())}")
        return 0

    if args.validate:
        print("Config valid." if subsystems else "No subsystems in config.")
        return 0

    if args.subsystem:
        subsystems = {k: v for k, v in subsystems.items() if k == args.subsystem}
        if not subsystems:
            print(f"Subsystem '{args.subsystem}' not found.", file=sys.stderr)
            return 1
    if args.tier:
        subsystems = {k: v for k, v in subsystems.items() if v.get("tier") == args.tier}

    written = 0
    for sid, sub in subsystems.items():
        path = sub.get("path", sid)
        readme_path = repo_root / path / "README.md"
        readme_path.parent.mkdir(parents=True, exist_ok=True)
        content = generate_readme(repo_root, config, sid, sub, core_docs)
        readme_path.write_text(content, encoding="utf-8")
        written += 1
        print(f"  Wrote {readme_path.relative_to(repo_root)}")

    print(f"\nGenerated {written} README(s). Core docs used: {len(core_docs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
