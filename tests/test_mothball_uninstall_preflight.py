"""M5 / TASK-050 — uninstall preflight and active-cron absence."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COORD = ROOT / "scripts/migrations/mothball_local_intelligence.py"
CRON = ROOT / "plasticos_enrichment/data/cron.xml"
RUNBOOK = ROOT / "docs/runbooks/MOTHBALL_LOCAL_INTELLIGENCE.md"


def _load_coord():
    spec = importlib.util.spec_from_file_location("mothball_coord", COORD)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_enrichment_crons_inactive():
    src = CRON.read_text(encoding="utf-8")
    assert 'name="active">False</field>' in src
    assert src.count(">False</field>") >= 2


def test_uninstall_preflight_blocks_without_backup():
    mod = _load_coord()
    result = mod.uninstall_preflight(backup_receipt_digest=None, allow_uninstall=False)
    assert result["would_uninstall"] is False
    assert "missing_verified_backup_receipt" in result["blocked_reasons"]
    assert result["status"] == "BLOCKED"


def test_uninstall_preflight_still_blocks_with_backup_and_allow():
    """Coordinator must never auto-uninstall even when operator flags are set."""
    mod = _load_coord()
    result = mod.uninstall_preflight(
        backup_receipt_digest="sha256:" + ("a" * 64),
        allow_uninstall=True,
    )
    assert result["would_uninstall"] is False
    assert result["backup_receipt_present"] is True
    assert any("refuses_automatic_uninstall" in r for r in result["blocked_reasons"])


def test_uninstall_preflight_cli():
    proc = subprocess.run(
        [
            sys.executable,
            str(COORD),
            "uninstall-preflight",
            "--backup-receipt-digest",
            "sha256:" + ("b" * 64),
            "--allow-uninstall",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["would_uninstall"] is False
    assert payload["status"] == "BLOCKED"


def test_runbook_covers_backup_uninstall_restore():
    src = RUNBOOK.read_text(encoding="utf-8").lower()
    assert "backup" in src
    assert "uninstall" in src
    assert "restore" in src
    assert "automatic production uninstall" in src or "no automatic" in src
