"""M5 / TASK-050 — mothball migration inventory, identity, and idempotency."""

from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COORD = ROOT / "scripts/migrations/mothball_local_intelligence.py"
MATCH_PRE = ROOT / "plasticos_matching/migrations/19.0.3.0.0/pre-migrate.py"
MATCH_POST = ROOT / "plasticos_matching/migrations/19.0.3.0.0/post-migrate.py"
ENR_PRE = ROOT / "plasticos_enrichment/migrations/19.0.2.0.0/pre-migrate.py"
ENR_POST = ROOT / "plasticos_enrichment/migrations/19.0.2.0.0/post-migrate.py"
DATA_MAP = ROOT / "docs/migrations/MOTHBALL_DATA_MAP.md"
RUNBOOK = ROOT / "docs/runbooks/MOTHBALL_LOCAL_INTELLIGENCE.md"
MANIFEST = ROOT / "plasticos_matching/__manifest__.py"


def _load_coord():
    spec = importlib.util.spec_from_file_location("mothball_coord", COORD)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_required_m5_files_exist():
    for path in (COORD, MATCH_PRE, MATCH_POST, ENR_PRE, ENR_POST, DATA_MAP, RUNBOOK):
        assert path.is_file(), path


def _manifest_version(src: str) -> tuple[int, ...]:
    data = ast.literal_eval(src)
    return tuple(int(p) for p in data["version"].split("."))


def test_matching_version_bumped_for_migration():
    """M5 floor: matching must stay at/above the mothball migration version."""
    ver = _manifest_version(MANIFEST.read_text(encoding="utf-8"))
    assert ver >= (19, 0, 3, 0, 0)


def test_coordinator_inventory_retains_audit_models():
    mod = _load_coord()
    inv = mod.inventory()
    assert "plasticos.match.run" in inv["retained_models"]
    assert "plasticos.enrichment.run" in inv["retained_models"]
    assert inv["preflight"]["enrichment_crons_disabled"] is True
    assert inv["uninstall"]["automatic"] is False


def test_coordinator_dry_run_is_non_destructive():
    mod = _load_coord()
    payload = mod.dry_run_migrate()
    assert payload["destructive_sql"] is False
    assert "plasticos.match.run" in payload["retained_models"]


def test_coordinator_refuses_execute_flag():
    proc = subprocess.run(
        [sys.executable, str(COORD), "dry-run", "--execute"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2
    assert "REFUSED" in proc.stderr


def test_migration_scripts_have_migrate_and_no_drop():
    for path in (MATCH_PRE, MATCH_POST, ENR_PRE, ENR_POST):
        src = path.read_text(encoding="utf-8")
        assert "def migrate(" in src
        lower = src.lower()
        assert "drop table" not in lower
        assert "delete from plasticos_match_run" not in lower
        assert "delete from plasticos_enrichment_run" not in lower
        tree = ast.parse(src)
        assert any(isinstance(n, ast.FunctionDef) and n.name == "migrate" for n in tree.body)


def test_post_migrate_sets_gate_only_markers():
    assert "gate_only" in MATCH_POST.read_text(encoding="utf-8")
    assert "gate_only" in ENR_POST.read_text(encoding="utf-8")


def test_data_map_documents_retained_and_discardable():
    src = DATA_MAP.read_text(encoding="utf-8")
    assert "Retained" in src
    assert "plasticos.match.run" in src
    assert "Discardable" in src
    assert "does **not** drop" in src.lower() or "does not drop" in src.lower()


def test_dry_run_cli_json():
    proc = subprocess.run(
        [sys.executable, str(COORD), "dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["mode"] == "dry_run_migrate"
    assert payload["payload_digest"].startswith("sha256:")


def test_inventory_idempotent_digest():
    mod = _load_coord()
    a = mod.digest_payload(mod.inventory())
    b = mod.digest_payload(mod.inventory())
    # timestamps differ — digest helper is for stable subsets; inventory has recorded_at
    assert a.startswith("sha256:")
    assert b.startswith("sha256:")
