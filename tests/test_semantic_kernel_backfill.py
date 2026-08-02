"""TASK-026: explicit backfill engine — dry-run, idempotent, no install hooks."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from semantic_kernel_backfill_engine import (  # noqa: E402
    BLOCKED_AUTOMATIC,
    BackfillEngine,
    SourceRow,
    migration_identity,
    run_twice_idempotent,
)


def _rows() -> list[SourceRow]:
    return [
        SourceRow("plasticos.material.profile", "10", {"polymer_id": 1}, company_id=1),
        SourceRow("plasticos.material.profile", "20", {"polymer_id": 2}, company_id=1),
        SourceRow("plasticos.material.profile", "30", {"polymer_id": 3}, company_id=2),
    ]


def test_migration_identity_stable() -> None:
    a = migration_identity(source_model="plasticos.material.profile", source_record_id="10", family="specification")
    b = migration_identity(source_model="plasticos.material.profile", source_record_id="10", family="specification")
    assert a == b
    assert "specification" in a


def test_dry_run_plans_creates_and_checksum() -> None:
    report = BackfillEngine(family="specification", source_rows=_rows(), dry_run=True, batch_size=10).run()
    assert report.dry_run is True
    assert report.source_count == 3
    assert report.created == 3
    assert report.checksum.startswith("sha256:")
    assert all(r.status == "planned" for r in report.rows)


def test_after_id_and_company_filter() -> None:
    report = BackfillEngine(
        family="specification",
        source_rows=_rows(),
        dry_run=True,
        after_id="10",
        company_id=1,
        batch_size=10,
    ).run()
    assert report.source_count == 1  # only id 20 in company 1 after 10
    assert {r.identity.split("|")[2] for r in report.rows} == {"20"}


def test_blocked_families_not_auto_converted() -> None:
    for family in BLOCKED_AUTOMATIC:
        report = BackfillEngine(family=family, source_rows=_rows(), dry_run=True).run()
        assert report.blocked == min(3, report.batch_size)
        assert all(r.status == "blocked" for r in report.rows)


def test_double_run_idempotent() -> None:
    def factory(*, dry_run=False, existing_identities=None):
        return BackfillEngine(
            family="specification",
            source_rows=_rows(),
            dry_run=dry_run,
            existing_identities=existing_identities,
            batch_size=10,
        )

    first, second = run_twice_idempotent(factory)
    assert first.created == 3
    assert second.reused == 3
    assert second.created == 0


def test_cli_writes_report(tmp_path: Path) -> None:
    fixture = tmp_path / "rows.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "source_model": "plasticos.material.profile",
                    "source_record_id": "1",
                    "payload": {"polymer_id": 1},
                    "company_id": 1,
                }
            ]
        )
    )
    report_path = tmp_path / "report.json"
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "semantic_kernel_backfill.py"),
        "--dry-run",
        "--family",
        "specification",
        "--fixture-path",
        str(fixture),
        "--report-path",
        str(report_path),
    ]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(report_path.read_text())
    assert data["family"] == "specification"
    assert data["dry_run"] is True
    assert data["checksum"].startswith("sha256:")


def test_no_install_hook_backfill() -> None:
    manifest = ast.literal_eval((ROOT / "plasticos_semantic_kernel" / "__manifest__.py").read_text())
    for key in ("post_init_hook", "pre_init_hook", "uninstall_hook"):
        assert key not in manifest
    init_py = (ROOT / "plasticos_semantic_kernel" / "__init__.py").read_text()
    assert "backfill" not in init_py.lower()
