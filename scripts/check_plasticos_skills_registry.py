#!/usr/bin/env python3
"""Validate PlasticOS project skills are registered, manifested, and auto-invoke.

SSOT: skills/ (repo root — not Claude Code, not Cursor-Governance).
Discovery adapters: .claude/skills/plasticos-* -> ../../skills/plasticos-*

Checks:
  1. Every skills/plasticos-*/SKILL.md appears in PLASTICOS_SKILLS_MANIFEST.yaml
  2. Manifest entries exist on disk with matching name/
  3. AGENTS.md and .claude/README.md list every skill
  4. disable-model-invocation is not true (auto-invoke law)
  5. Manifest invocation: auto for every entry
  6. No __manifest__.py / __init__.py under skills/ (not an Odoo addon tree)
  7. .claude/skills/plasticos-* are symlinks into skills/ (discovery only)

Exit 0 on success, 1 on failure.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = ROOT / "skills"
MANIFEST = SKILLS_ROOT / "PLASTICOS_SKILLS_MANIFEST.yaml"
DISCOVERY = ROOT / ".claude" / "skills"


def parse_frontmatter(text: str) -> dict[str, str]:
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fm: dict[str, str] = {}
    key: str | None = None
    buf: list[str] = []
    for line in parts[1].splitlines():
        if re.match(r"^[a-zA-Z0-9_-]+:", line):
            if key is not None:
                fm[key] = " ".join(buf).strip().strip('"').strip("'")
            key, _, rest = line.partition(":")
            key = key.strip()
            rest = rest.strip()
            if rest in (">-", ">", "|", "|+", "|-"):
                buf = []
            else:
                buf = [rest.lstrip(">|").lstrip("-").strip()] if rest else []
        elif key is not None and line.startswith((" ", "\t")):
            buf.append(line.strip())
    if key is not None:
        fm[key] = " ".join(buf).strip().strip('"').strip("'")
    return fm


def parse_manifest_names(text: str) -> dict[str, dict[str, str]]:
    skills: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    in_skills = False
    for line in text.splitlines():
        if line.startswith("skills:"):
            in_skills = True
            continue
        if not in_skills:
            continue
        if line.startswith("  - name:"):
            if current and "name" in current:
                skills[current["name"]] = current
            current = {"name": line.split(":", 1)[1].strip()}
        elif current is not None and line.startswith("    "):
            k, _, v = line.strip().partition(":")
            current[k.strip()] = v.strip().strip('"').strip("'")
        elif line and not line.startswith(" ") and in_skills:
            break
    if current and "name" in current:
        skills[current["name"]] = current
    return skills


def main() -> int:
    errors: list[str] = []
    if not MANIFEST.exists():
        print(f"FAIL: missing {MANIFEST.relative_to(ROOT)}")
        return 1

    # Never an Odoo module tree
    for bad in SKILLS_ROOT.rglob("__manifest__.py"):
        errors.append(f"Odoo manifest forbidden under skills/: {bad.relative_to(ROOT)}")
    for bad in SKILLS_ROOT.rglob("__init__.py"):
        errors.append(f"Python package __init__.py forbidden under skills/: {bad.relative_to(ROOT)}")

    disk = sorted(p for p in SKILLS_ROOT.glob("plasticos-*") if p.is_dir() and not p.is_symlink())
    disk_names = {p.name for p in disk}
    manifest = parse_manifest_names(MANIFEST.read_text())
    agents = (ROOT / "AGENTS.md").read_text()
    readme = (ROOT / ".claude" / "README.md").read_text()
    try:
        readme_proj = readme.split("## Project Skills", 1)[1].split("## Adapters", 1)[0]
    except IndexError:
        readme_proj = readme
        errors.append("README.md missing ## Project Skills section")

    for name in sorted(disk_names - set(manifest)):
        errors.append(f"disk skill not in manifest: {name}")
    for name in sorted(set(manifest) - disk_names):
        errors.append(f"manifest skill missing on disk: {name}")

    for d in disk:
        sm = d / "SKILL.md"
        if not sm.exists():
            errors.append(f"missing SKILL.md: {d.name}")
            continue
        fm = parse_frontmatter(sm.read_text())
        if fm.get("name") != d.name:
            errors.append(f"name/dir mismatch: dir={d.name} name={fm.get('name')}")
        dis = fm.get("disable-model-invocation", "false").lower().split("#", 1)[0].strip()
        if dis in ("true", "yes", "1"):
            errors.append(f"explicit-only forbidden for project skill: {d.name}")
        if f"`{d.name}`" not in agents and d.name not in agents:
            errors.append(f"missing AGENTS.md row: {d.name}")
        if d.name not in readme_proj:
            errors.append(f"missing .claude/README.md Project Skills row: {d.name}")
        entry = manifest.get(d.name, {})
        if entry.get("invocation") != "auto":
            errors.append(f"manifest invocation not auto: {d.name}={entry.get('invocation')}")
        path = entry.get("path", "")
        if path and not path.startswith("skills/"):
            errors.append(f"manifest path must be under skills/: {d.name} -> {path}")

        # Discovery symlink
        link = DISCOVERY / d.name
        if not link.exists():
            errors.append(f"missing discovery symlink: .claude/skills/{d.name}")
        elif not link.is_symlink():
            errors.append(f"discovery path must be symlink into skills/: .claude/skills/{d.name}")
        else:
            target = link.resolve()
            if target != d.resolve():
                errors.append(
                    f"discovery symlink target mismatch: {link} -> {target} (expected {d.resolve()})"
                )

    if errors:
        print(f"FAIL: plasticos skills registry ({len(errors)} issue(s))")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"PASS: {len(disk)} plasticos skills in skills/ (SSOT), auto-invoke, not Odoo addons")
    for n in sorted(disk_names):
        inv = manifest[n].get("invocation")
        ver = manifest[n].get("version")
        print(f"  - {n} v{ver} ({inv})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
