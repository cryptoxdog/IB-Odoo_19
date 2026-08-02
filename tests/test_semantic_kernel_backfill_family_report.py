"""TASK-031: one-family report identity + blocked-family refusal."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from semantic_kernel_backfill_engine import (  # noqa: E402
    BLOCKED_AUTOMATIC,
    TASK_031_LOCKED_FAMILY,
    BackfillEngine,
    SourceRow,
)


def _rows() -> list[SourceRow]:
    return [
        SourceRow("plasticos.material.profile", "10", {"polymer_id": 1}, company_id=1),
        SourceRow("plasticos.material.profile", "20", {"polymer_id": 2}, company_id=1),
    ]


def test_task_031_locked_family_is_specification() -> None:
    assert TASK_031_LOCKED_FAMILY == "specification"


def test_report_checksum_stable_for_identical_inputs() -> None:
    a = BackfillEngine(
        family="specification",
        source_rows=_rows(),
        dry_run=True,
        batch_size=10,
        migration_batch_id="fixed-batch",
        code_sha="deadbeef",
    ).run()
    b = BackfillEngine(
        family="specification",
        source_rows=_rows(),
        dry_run=True,
        batch_size=10,
        migration_batch_id="fixed-batch",
        code_sha="deadbeef",
    ).run()
    assert a.checksum == b.checksum
    assert a.planned == 2
    assert a.created == 0
    d = a.to_dict()
    for key in ("planned", "created", "reused", "skipped", "conflicted", "failed", "blocked"):
        assert key in d


def test_blocked_family_refusal_in_report() -> None:
    for family in sorted(BLOCKED_AUTOMATIC):
        report = BackfillEngine(family=family, source_rows=_rows(), dry_run=True, batch_size=10).run()
        assert report.blocked == 2
        assert report.planned == 0
        assert all(r.status == "blocked" for r in report.rows)


def test_cli_task_031_lock_refuses_other_family(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "semantic_kernel_backfill.py"),
        "--dry-run",
        "--family",
        "observation",
        "--task-031-lock",
        "--report-path",
        str(report_path),
    ]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False)
    assert proc.returncode == 2
    assert "task_031_family_lock" in proc.stderr
