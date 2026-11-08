#!/usr/bin/env python3
"""Export idempotent Odoo outcome-replay input artifacts (TASK-057).

Reads offline event fixtures (JSON list or {"events": [...]}) and writes a
deterministic replay document with content_hash. Never calls Gate / network.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from outcome_replay.schema import build_replay_document  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Export Odoo outcome-replay input (offline)")
    p.add_argument(
        "--fixture-path",
        required=True,
        help="JSON file: list of events or object with 'events' array",
    )
    p.add_argument("--output-path", required=True, help="Where to write replay input JSON")
    p.add_argument("--notes", default="", help="Optional operator note (affects hash if set)")
    return p


def load_events(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("events"), list):
        return data["events"]
    raise ValueError("fixture must be a JSON list or an object with an 'events' list")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    events = load_events(Path(args.fixture_path))
    doc = build_replay_document(
        events=events,
        notes=args.notes or None,
    )
    out = Path(args.output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Deterministic file bytes: sorted keys, stable separators, trailing newline.
    text = json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    out.write_text(text, encoding="utf-8")
    print(json.dumps({"output_path": str(out), "content_hash": doc["content_hash"], "event_count": doc["event_count"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
