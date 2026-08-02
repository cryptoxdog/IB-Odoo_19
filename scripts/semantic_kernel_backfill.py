#!/usr/bin/env python3
"""Explicit semantic-kernel backfill CLI (TASK-026).

Usage examples:
  python3 scripts/semantic_kernel_backfill.py --dry-run --family specification --report-path /tmp/report.json
  python3 scripts/semantic_kernel_backfill.py --dry-run --family supply  # reports blocked

No install-hook backfill. No Gate/CEG/EIE calls.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from semantic_kernel_backfill_engine import FAMILIES, BackfillEngine, SourceRow  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="PlasticOS semantic kernel backfill/reconciliation")
    p.add_argument("--dry-run", action="store_true", default=False, help="Plan only; do not write")
    p.add_argument("--family", required=True, choices=list(FAMILIES))
    p.add_argument("--batch-size", type=int, default=100)
    p.add_argument("--after-id", default=None)
    p.add_argument("--company-id", type=int, default=None)
    p.add_argument("--migration-batch-id", default="")
    p.add_argument("--report-path", required=True)
    p.add_argument("--stop-on-conflict", action="store_true", default=False)
    p.add_argument(
        "--fixture-path",
        default=None,
        help="Optional JSON list of source rows for offline/dry-run tests",
    )
    p.add_argument("--code-sha", default="unknown")
    return p


def load_fixture_rows(path: Path | None) -> list[SourceRow]:
    if path is None:
        return []
    data = json.loads(path.read_text())
    rows: list[SourceRow] = []
    for item in data:
        rows.append(
            SourceRow(
                source_model=item["source_model"],
                source_record_id=str(item["source_record_id"]),
                payload=item.get("payload") or {},
                company_id=item.get("company_id"),
            )
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rows = load_fixture_rows(Path(args.fixture_path) if args.fixture_path else None)
    # TASK-026 ships dry-run + report/checkpoint contract. Execute adapter is a later slice.
    dry_run = True
    if not args.dry_run:
        print("execute mode not enabled in this slice; forcing --dry-run", file=sys.stderr)
        dry_run = True
    else:
        dry_run = True
    engine = BackfillEngine(
        family=args.family,
        source_rows=rows,
        dry_run=dry_run,
        batch_size=args.batch_size,
        after_id=args.after_id,
        company_id=args.company_id,
        migration_batch_id=args.migration_batch_id,
        stop_on_conflict=args.stop_on_conflict,
        code_sha=args.code_sha,
    )
    report = engine.run()
    out = Path(args.report_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report.to_dict(), indent=2) + "\n")
    print(json.dumps({"ok": True, "report_path": str(out), "checksum": report.checksum, "family": report.family}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
