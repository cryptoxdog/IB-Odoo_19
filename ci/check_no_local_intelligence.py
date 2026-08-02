#!/usr/bin/env python3
"""CI Guard: no local intelligence authority drift (M7+ / TASK-051).

Scans the repo for reintroduction of Odoo-local matching/enrichment *authority*.
After M7 physical retirement, legacy addon trees must be ABSENT. Presence of
plasticos_buyer_match_engine / plasticos_inference_engine is blocking.

Exit codes:
  0 = PASS (no consumer-path drift; retired modules absent)
  1 = FAIL (drift or retired modules still present)
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RESIDUE_PREFIXES = (
    "plasticos_buyer_match_engine/",
    "plasticos_inference_engine/",
)

CONSUMER_PREFIXES = (
    "plasticos_matching/",
    "plasticos_enrichment/",
    "plasticos_gate/",
)

CONSTITUTIONAL = (
    "INVARIANTS.md",
    "ARCHITECTURE.md",
    "AGENTS.md",
    "docs/adr/ADR-003-single-external-intelligence-authority.md",
)

CONSUMER_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "local_matcher_env_lookup",
        re.compile(r"""env\[\s*['\"]plasticos\.buyer\.matcher['\"]\s*]"""),
    ),
    (
        "silent_local_fallback_phrase",
        re.compile(r"falling back to local", re.IGNORECASE),
    ),
]


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _is_residue(rel: str) -> bool:
    return any(rel.startswith(p) for p in RESIDUE_PREFIXES)


def _is_consumer(rel: str) -> bool:
    return any(rel.startswith(p) for p in CONSUMER_PREFIXES)


def _iter_py_files() -> list[Path]:
    files: list[Path] = []
    for pattern in ("plasticos_*/**/*.py", "tests/**/*.py", "ci/**/*.py", "scripts/**/*.py"):
        files.extend(ROOT.glob(pattern))
    out: list[Path] = []
    seen: set[str] = set()
    for f in files:
        if not f.is_file():
            continue
        if any(part in {".venv", "__pycache__", "node_modules"} for part in f.parts):
            continue
        rel = _rel(f)
        if rel in seen:
            continue
        seen.add(rel)
        out.append(f)
    return sorted(out)


def check_manifests() -> list[str]:
    violations: list[str] = []
    for path in (
        ROOT / "plasticos_matching" / "__manifest__.py",
        ROOT / "plasticos_enrichment" / "__manifest__.py",
    ):
        data = ast.literal_eval(path.read_text(encoding="utf-8"))
        depends = data.get("depends", [])
        rel = _rel(path)
        if "plasticos_gate" not in depends:
            violations.append(f"{rel}: missing depends plasticos_gate")
        if "plasticos_inference_engine" in depends:
            violations.append(f"{rel}: must not depend on plasticos_inference_engine")
        if "plasticos_buyer_match_engine" in depends:
            violations.append(f"{rel}: must not depend on plasticos_buyer_match_engine")
    return violations


def check_enrichment_crons() -> list[str]:
    cron = ROOT / "plasticos_enrichment" / "data" / "cron.xml"
    text = cron.read_text(encoding="utf-8")
    if text.count('name="active">False</field>') < 2:
        return [f"{_rel(cron)}: enrichment crons must remain active=False"]
    return []


def check_action_execute_gate_only() -> list[str]:
    violations: list[str] = []
    run_path = ROOT / "plasticos_enrichment" / "models" / "enrichment_run.py"
    tree = ast.parse(run_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "action_execute":
            calls = {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)}
            for banned in ("crawl_source", "extract_from_source", "run_inference"):
                if banned in calls:
                    violations.append(f"{_rel(run_path)}:action_execute calls {banned} (local intelligence)")
    orch = ROOT / "plasticos_matching" / "models" / "match_orchestrator.py"
    src = orch.read_text(encoding="utf-8")
    if re.search(r"""env\[\s*['\"]plasticos\.buyer\.matcher['\"]\s*]""", src):
        violations.append(f"{_rel(orch)}: looks up plasticos.buyer.matcher")
    return violations


def scan_consumer_patterns() -> tuple[list[str], list[str]]:
    blocking: list[str] = []
    residue: list[str] = []
    for path in _iter_py_files():
        rel = _rel(path)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for rule_id, pattern in CONSUMER_PATTERNS:
            for i, line in enumerate(text.splitlines(), 1):
                if not pattern.search(line):
                    continue
                hit = f"{rel}:{i}: [{rule_id}] {line.strip()[:120]}"
                if _is_residue(rel):
                    residue.append(hit)
                    continue
                if not _is_consumer(rel):
                    residue.append(hit)
                    continue
                stripped = line.lstrip()
                if stripped.startswith("#") or "No silent fallback" in line:
                    residue.append(hit)
                    continue
                if "mothball" in line.lower() and "not" in line.lower():
                    residue.append(hit)
                    continue
                # Stale log lines under enrichment_run (non-executable messaging)
                if rel.endswith("enrichment_run.py") and "falling back to local" in line.lower():
                    residue.append(hit)
                    continue
                blocking.append(hit)
    return blocking, residue


def check_constitutional() -> list[str]:
    violations: list[str] = []
    for rel in CONSTITUTIONAL:
        path = ROOT / rel
        if not path.is_file():
            violations.append(f"missing constitutional file: {rel}")
            continue
        text = path.read_text(encoding="utf-8")
        if rel.endswith("ADR-003-single-external-intelligence-authority.md"):
            if "Observation criteria" not in text and "observation criteria" not in text.lower():
                violations.append(f"{rel}: missing observation criteria (M6)")
            if "Retirement evidence" not in text and "retirement evidence" not in text.lower():
                violations.append(f"{rel}: missing retirement evidence section (M6)")
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    blocking: list[str] = []
    residue: list[str] = []
    blocking.extend(check_manifests())
    blocking.extend(check_enrichment_crons())
    blocking.extend(check_action_execute_gate_only())
    blocking.extend(check_constitutional())
    b2, r2 = scan_consumer_patterns()
    blocking.extend(b2)
    residue.extend(r2)

    scanned_residue = [_rel(p) for p in _iter_py_files() if _is_residue(_rel(p))]
    # M7 physical retirement: retired addon trees must be gone.
    for prefix in RESIDUE_PREFIXES:
        root_dir = ROOT / prefix.rstrip("/")
        if root_dir.exists():
            blocking.append(f"retired module still present: {prefix.rstrip('/')}")
    if scanned_residue:
        blocking.append(f"legacy local-intelligence residue files still present ({len(scanned_residue)})")

    if args.json:
        print(
            json.dumps(
                {
                    "blocking": blocking,
                    "residue_reports": residue[:50],
                    "residue_files_scanned": len(scanned_residue),
                    "status": "FAIL" if blocking else "PASS",
                },
                indent=2,
            )
        )
    else:
        print(
            f"Local-intelligence drift scan: residue_files={len(scanned_residue)} "
            f"residue_hits={len(residue)} blocking={len(blocking)}"
        )
        if residue:
            print("--- residue (non-blocking; still reported) ---")
            for hit in residue[:30]:
                print(f"  WARN {hit}")
            if len(residue) > 30:
                print(f"  ... {len(residue) - 30} more")
        if blocking:
            print("--- BLOCKING drift ---")
            for hit in blocking:
                print(f"  FAIL {hit}")
            print(
                "\nFix: keep Gate-only authority on matching/enrichment consumers; "
                "do not reintroduce local matcher/inference as design."
            )
            return 1
        print("PASS: no new local-intelligence authority drift on consumer paths")
    return 1 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
