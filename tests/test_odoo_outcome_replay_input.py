"""TASK-057: idempotent Odoo outcome-replay input exporter."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from outcome_replay.schema import (  # noqa: E402
    SCHEMA_ID,
    build_replay_document,
    content_hash,
)

FIXTURE_EVENTS = [
    {
        "tenant": "plasticos",
        "action": "match",
        "packet_id": "pkt-b",
        "correlation_id": "corr-1",
        "payload": {"score": 0.9},
    },
    {
        "tenant": "plasticos",
        "action": "match",
        "packet_id": "pkt-a",
        "payload": {"score": 0.1},
    },
]


def test_build_document_is_idempotent() -> None:
    a = build_replay_document(events=list(FIXTURE_EVENTS))
    b = build_replay_document(events=list(reversed(FIXTURE_EVENTS)))
    assert a["schema"] == SCHEMA_ID
    assert a["gate_mutation"] is False
    assert a["content_hash"] == b["content_hash"]
    assert a["events"][0]["packet_id"] == "pkt-a"
    assert a == b
    # hash covers body excluding itself
    body = {k: v for k, v in a.items() if k != "content_hash"}
    assert a["content_hash"] == content_hash(body)


def test_exporter_cli_idempotent(tmp_path: Path) -> None:
    fixture = tmp_path / "events.json"
    out1 = tmp_path / "out1.json"
    out2 = tmp_path / "out2.json"
    fixture.write_text(json.dumps(FIXTURE_EVENTS), encoding="utf-8")
    exporter = SCRIPTS / "outcome_replay_export.py"
    for dest in (out1, out2):
        completed = subprocess.run(
            [
                sys.executable,
                str(exporter),
                "--fixture-path",
                str(fixture),
                "--output-path",
                str(dest),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0
    assert out1.read_text(encoding="utf-8") == out2.read_text(encoding="utf-8")
    doc = json.loads(out1.read_text(encoding="utf-8"))
    assert doc["content_hash"].startswith("sha256:")
    assert doc["gate_mutation"] is False


def test_exporter_source_has_no_gate_client_import() -> None:
    export_src = (SCRIPTS / "outcome_replay_export.py").read_text(encoding="utf-8")
    schema_src = (SCRIPTS / "outcome_replay" / "schema.py").read_text(encoding="utf-8")
    for src in (export_src, schema_src):
        assert "gate_client" not in src
        assert "constellation_node_sdk" not in src
        assert "send_to_gate" not in src


def test_adr_and_runbook_document_schema() -> None:
    adr = (ROOT / "docs/adr/ADR-126-odoo-outcome-replay-input.md").read_text(encoding="utf-8")
    rb = (ROOT / "docs/runbooks/ODOO_OUTCOME_REPLAY_INPUT.md").read_text(encoding="utf-8")
    assert SCHEMA_ID in adr and SCHEMA_ID in rb
    assert "content_hash" in adr and "idempotent" in rb.lower() or "Idempotency" in rb
    assert "TASK-033" in adr or "TASK-033" in rb
