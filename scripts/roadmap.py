#!/usr/bin/env python3
"""
PlasticOS roadmap registry — sync and validate planning docs.

Single source of truth: docs/roadmap/registry.yaml

Usage:
  python3 scripts/roadmap.py check
  python3 scripts/roadmap.py sync
  python3 scripts/roadmap.py list [--domain gate-autonomy] [--phase 1]
  python3 scripts/roadmap.py add --domain gate-autonomy --phase 1 --kind backlog --title "..."

Exit codes: 0 = pass, 1 = validation/sync failure
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "docs" / "roadmap" / "registry.yaml"
ROADMAP_INDEX = ROOT / "ROADMAP.md"
README_INDEX = ROOT / "docs" / "README_INDEX.md"

STATUS_CHECK = {"pending": "[ ]", "in_progress": "[~]", "done": "[x]", "deferred": "[ ]"}


def _load_registry() -> dict:
    if yaml is None:
        print("❌ PyYAML required — pip install pyyaml", file=sys.stderr)
        sys.exit(1)
    if not REGISTRY_PATH.is_file():
        print(f"❌ Missing registry: {REGISTRY_PATH}", file=sys.stderr)
        sys.exit(1)
    data = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        print("❌ registry.yaml root must be a mapping", file=sys.stderr)
        sys.exit(1)
    return data


def _items_for(reg: dict, domain: str, phase: int | None = None, kind: str | None = None) -> list[dict]:
    out = []
    for item in reg.get("items") or []:
        if item.get("domain") != domain:
            continue
        if phase is not None and item.get("phase") != phase:
            continue
        if kind is not None and item.get("kind") != kind:
            continue
        out.append(item)
    return out


def _next_id(reg: dict, domain: str) -> str:
    domain_slug = domain.upper().replace("-", "")[:8]
    nums = []
    for item in reg.get("items") or []:
        iid = item.get("id") or ""
        if iid.startswith(f"ROAD-{domain_slug}-") or iid.startswith("ROAD-GATE-"):
            tail = iid.rsplit("-", 1)[-1]
            if tail.isdigit():
                nums.append(int(tail))
    n = max(nums, default=0) + 1
    if domain == "gate-autonomy":
        return f"ROAD-GATE-{n:03d}"
    return f"ROAD-{domain_slug}-{n:03d}"


def _render_backlog(items: list[dict]) -> str:
    lines = []
    for item in items:
        mark = "[x]" if item.get("status") == "done" else STATUS_CHECK.get(item.get("status", "pending"), "[ ]")
        lines.append(f"- {mark} {item['title']} `({item['id']})`")
    return "\n".join(lines) + ("\n" if lines else "")


def _render_scope_column(items: list[dict]) -> str:
    lines = [f"- {item['title']} `({item['id']})`" for item in items]
    return "\n".join(lines) + ("\n" if lines else "")


def _render_scope_table(in_items: list[dict], out_items: list[dict]) -> str:
    rows = []
    count = max(len(in_items), len(out_items), 1)
    for i in range(count):
        left = ""
        if i < len(in_items):
            item = in_items[i]
            left = f"- {item['title']} `({item['id']})`"
        right = ""
        if i < len(out_items):
            item = out_items[i]
            right = f"- {item['title']} `({item['id']})`"
        rows.append(f"| {left} | {right} |")
    header = "| In scope | Out of scope (defer) |\n|----------|----------------------|\n"
    return header + "\n".join(rows) + "\n"


def _render_observability(items: list[dict]) -> str:
    lines = [f"- {item['title']} `({item['id']})`" for item in items]
    return "\n".join(lines) + ("\n" if lines else "")


def _render_capabilities(items: list[dict], notes_header: str = "Human gate remaining / Notes") -> str:
    rows = []
    for item in items:
        notes = item.get("notes") or ""
        rows.append(f"| {item['title']} | {notes} | `{item['id']}` |")
    header = f"| Capability | {notes_header} | ID |\n|------------|{'-' * len(notes_header)}|-----|\n"
    return header + "\n".join(rows) + ("\n" if rows else "")


def _render_domain_index(domains: dict) -> str:
    lines = []
    for _dom_id, meta in domains.items():
        roadmap = meta.get("roadmap", "")
        adr = meta.get("adr", "")
        summary = meta.get("index_summary", meta.get("title", ""))
        lines.append(f"| [{roadmap}]({roadmap}) | {summary} |")
        adr_summary = meta.get("adr_index_summary")
        if adr and adr_summary:
            lines.append(f"| [{adr}]({adr}) | {adr_summary} |")
    return "\n".join(lines) + "\n"


def _render_readme_architecture(domains: dict) -> str:
    lines = []
    for _dom_id, meta in domains.items():
        adr = meta.get("adr", "")
        roadmap = meta.get("roadmap", "")
        adr_summary = meta.get("adr_index_summary", "Architecture decision")
        idx_summary = meta.get("index_summary", meta.get("title", ""))
        if adr:
            lines.append(f"| [{Path(adr).name}]({Path(adr).name}) | {adr_summary} |")
        if roadmap:
            name = Path(roadmap).name
            lines.append(f"| [{name}]({name}) | {idx_summary} |")
    return "\n".join(lines) + "\n"


def _replace_marker(content: str, key: str, section: str, body: str) -> str:
    start = f"<!-- roadmap:{key}:{section}:start -->"
    end = f"<!-- roadmap:{key}:{section}:end -->"
    pattern = re.compile(re.escape(start) + r"\n.*?" + re.escape(end), re.DOTALL)
    replacement = f"{start}\n{body.rstrip()}\n{end}"
    if not pattern.search(content):
        raise ValueError(f"Missing sync marker: {key}:{section}")
    return pattern.sub(replacement, content, count=1)


def _update_last_updated(content: str) -> str:
    today = date.today().isoformat()
    return re.sub(
        r"(\*\*Last updated:\*\*)\s*\d{4}-\d{2}-\d{2}",
        rf"\1 {today}",
        content,
        count=1,
    )


def _extract_marker_body(content: str, key: str, section: str) -> str | None:
    start = f"<!-- roadmap:{key}:{section}:start -->"
    end = f"<!-- roadmap:{key}:{section}:end -->"
    pattern = re.compile(re.escape(start) + r"\n(.*?)" + re.escape(end), re.DOTALL)
    match = pattern.search(content)
    return match.group(1) if match else None


def cmd_sync() -> int:
    reg = _load_registry()
    domains = reg.get("domains") or {}
    errors: list[str] = []

    for dom_id, meta in domains.items():
        roadmap_path = ROOT / meta.get("roadmap", "")
        if not roadmap_path.is_file():
            errors.append(f"Missing roadmap file: {roadmap_path}")
            continue
        content = roadmap_path.read_text(encoding="utf-8")
        try:
            content = _replace_marker(
                content,
                dom_id,
                "phase1-backlog",
                _render_backlog(_items_for(reg, dom_id, phase=1, kind="backlog")),
            )
            content = _replace_marker(
                content,
                dom_id,
                "phase1-scope",
                _render_scope_table(
                    _items_for(reg, dom_id, phase=1, kind="scope_in"),
                    _items_for(reg, dom_id, phase=1, kind="scope_out"),
                ),
            )
            content = _replace_marker(
                content,
                dom_id,
                "phase1-observability",
                _render_observability(_items_for(reg, dom_id, phase=1, kind="observability")),
            )
            content = _replace_marker(
                content,
                dom_id,
                "phase2-capabilities",
                _render_capabilities(_items_for(reg, dom_id, phase=2, kind="capability")),
            )
            content = _replace_marker(
                content,
                dom_id,
                "phase3-capabilities",
                _render_capabilities(
                    _items_for(reg, dom_id, phase=3, kind="capability"),
                    notes_header="Notes",
                ),
            )
            content = _update_last_updated(content)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        roadmap_path.write_text(content, encoding="utf-8")
        print(f"  ✅ synced {roadmap_path.relative_to(ROOT)}")

    if ROADMAP_INDEX.is_file():
        idx = ROADMAP_INDEX.read_text(encoding="utf-8")
        try:
            idx = _replace_marker(idx, "index", "domains", _render_domain_index(domains))
            ROADMAP_INDEX.write_text(idx, encoding="utf-8")
            print(f"  ✅ synced {ROADMAP_INDEX.relative_to(ROOT)}")
        except ValueError as exc:
            errors.append(str(exc))

    if README_INDEX.is_file():
        ri = README_INDEX.read_text(encoding="utf-8")
        try:
            ri = _replace_marker(ri, "index", "architecture", _render_readme_architecture(domains))
            README_INDEX.write_text(ri, encoding="utf-8")
            print(f"  ✅ synced {README_INDEX.relative_to(ROOT)}")
        except ValueError as exc:
            errors.append(str(exc))

    if errors:
        for err in errors:
            print(f"  ❌ {err}")
        return 1
    print("✅ Roadmap sync complete")
    return 0


def cmd_check() -> int:
    reg = _load_registry()
    domains = reg.get("domains") or {}
    failures = 0

    print("→ Roadmap registry check...")

    for _dom_id, meta in domains.items():
        for rel in (meta.get("roadmap"), meta.get("adr")):
            if rel and not (ROOT / rel).is_file():
                print(f"  ❌ missing file: {rel}")
                failures += 1

    required_markers = [
        "phase1-backlog",
        "phase1-scope",
        "phase1-observability",
        "phase2-capabilities",
        "phase3-capabilities",
    ]
    for dom_id, meta in domains.items():
        roadmap_path = ROOT / meta.get("roadmap", "")
        if not roadmap_path.is_file():
            continue
        content = roadmap_path.read_text(encoding="utf-8")
        for section in required_markers:
            if _extract_marker_body(content, dom_id, section) is None:
                print(f"  ❌ missing marker {dom_id}:{section} in {meta.get('roadmap')}")
                failures += 1

    for dom_id, meta in domains.items():
        roadmap_path = ROOT / meta.get("roadmap", "")
        if not roadmap_path.is_file():
            continue
        content = roadmap_path.read_text(encoding="utf-8")
        for item in _items_for(reg, dom_id):
            iid = item.get("id", "")
            if iid and iid not in content:
                print(f"  ❌ item {iid} not in synced doc — run: make roadmap")
                failures += 1

    adr = domains.get("gate-autonomy", {}).get("adr")
    if adr:
        adr_text = (ROOT / adr).read_text(encoding="utf-8")
        for link in ("GATE_AUTONOMY_ROADMAP.md", "ARCHITECTURE.md"):
            if link not in adr_text:
                print(f"  ❌ ADR missing link to {link}")
                failures += 1

    arch = ROOT / "ARCHITECTURE.md"
    if arch.is_file() and "External Intelligence Boundary" not in arch.read_text(encoding="utf-8"):
        print("  ❌ ARCHITECTURE.md missing External Intelligence Boundary section")
        failures += 1

    for path, key, section in (
        (ROADMAP_INDEX, "index", "domains"),
        (README_INDEX, "index", "architecture"),
    ):
        if path.is_file() and _extract_marker_body(path.read_text(encoding="utf-8"), key, section) is None:
            print(f"  ❌ missing marker {key}:{section} in {path.relative_to(ROOT)}")
            failures += 1

    if failures:
        print(f"\n❌ Roadmap check FAILED ({failures} issue(s))")
        return 1
    print(f"\n✅ Roadmap check passed ({len(reg.get('items') or [])} items, {len(domains)} domain(s))")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    reg = _load_registry()
    items = reg.get("items") or []
    if args.domain:
        items = [i for i in items if i.get("domain") == args.domain]
    if args.phase is not None:
        items = [i for i in items if i.get("phase") == args.phase]
    for item in items:
        print(
            f"{item.get('id')}\tphase={item.get('phase')}\t{item.get('kind')}\t"
            f"[{item.get('status')}]\t{item.get('title')}"
        )
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    reg = _load_registry()
    domains = reg.get("domains") or {}
    if args.domain not in domains:
        print(f"❌ Unknown domain '{args.domain}'. Known: {', '.join(domains)}", file=sys.stderr)
        return 1
    items = reg.setdefault("items", [])
    new_item = {
        "id": _next_id(reg, args.domain),
        "domain": args.domain,
        "phase": args.phase,
        "kind": args.kind,
        "title": args.title.strip(),
        "status": args.status or "pending",
    }
    if args.notes:
        new_item["notes"] = args.notes.strip()
    items.append(new_item)
    REGISTRY_PATH.write_text(
        yaml.dump(reg, sort_keys=False, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )
    print(f"  ✅ added {new_item['id']} to registry")
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    """Optional add → sync → check (default make roadmap pipeline)."""
    if args.title:
        if not args.domain or args.phase is None or not args.kind:
            print(
                "❌ Adding an item requires: domain= phase= kind= title=\n"
                '   Example: make roadmap domain=gate-autonomy phase=1 kind=backlog title="..."',
                file=sys.stderr,
            )
            return 1
        rc = cmd_add(args)
        if rc != 0:
            return rc
    print("→ Syncing roadmap docs from registry.yaml...")
    if cmd_sync() != 0:
        return 1
    return cmd_check()


def main() -> int:
    parser = argparse.ArgumentParser(description="PlasticOS roadmap registry tooling")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("check", help="Validate registry and synced docs")
    sub.add_parser("sync", help="Regenerate sync blocks from registry.yaml")

    update_p = sub.add_parser("update", help="Optional add, then sync, then check (make roadmap)")
    update_p.add_argument("--domain", default=None)
    update_p.add_argument("--phase", type=int, default=None)
    update_p.add_argument(
        "--kind",
        default=None,
        choices=["backlog", "scope_in", "scope_out", "observability", "capability"],
    )
    update_p.add_argument("--title", default=None)
    update_p.add_argument("--notes", default=None)
    update_p.add_argument(
        "--status",
        default="pending",
        choices=["pending", "in_progress", "done", "deferred"],
    )

    list_p = sub.add_parser("list", help="List registry items")
    list_p.add_argument("--domain", default=None)
    list_p.add_argument("--phase", type=int, default=None)

    add_p = sub.add_parser("add", help="Append item to registry.yaml only")
    add_p.add_argument("--domain", required=True)
    add_p.add_argument("--phase", type=int, required=True)
    add_p.add_argument(
        "--kind",
        required=True,
        choices=["backlog", "scope_in", "scope_out", "observability", "capability"],
    )
    add_p.add_argument("--title", required=True)
    add_p.add_argument("--notes", default=None, help="Second column for capability rows")
    add_p.add_argument(
        "--status",
        default="pending",
        choices=["pending", "in_progress", "done", "deferred"],
    )

    args = parser.parse_args()
    cmd = args.command or "update"

    if cmd == "check":
        return cmd_check()
    if cmd == "sync":
        print("→ Syncing roadmap docs from registry.yaml...")
        return cmd_sync()
    if cmd == "list":
        return cmd_list(args)
    if cmd == "add":
        return cmd_add(args)
    if cmd == "update":
        return cmd_update(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
