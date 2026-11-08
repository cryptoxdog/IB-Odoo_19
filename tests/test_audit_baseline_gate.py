"""Fail-closed audit baseline: missing, stale, and malformed reports are not a pass.

Scanner exit 1 remains the classified-findings signal. The baseline comparison,
not that exit status, decides whether a fresh findings list is green.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "audit" / "check_baseline.py"
sys.path.insert(0, str(ROOT / "scripts" / "audit"))

from baseline_utils import compute_fingerprint  # noqa: E402

CRITICAL = {
    "type": "FIELD_NOT_FOUND",
    "severity": "CRITICAL",
    "file": "plasticos_transaction/models/transaction.py",
    "message": "arch",
}
HIGH = {
    "type": "N_PLUS_ONE_QUERY",
    "severity": "HIGH",
    "file": "plasticos_logistics/models/load.py",
    "message": "loop",
}


def _baseline(finding: dict) -> dict:
    return {
        "entries": [
            {
                "fingerprint": compute_fingerprint(finding),
                "type": finding["type"],
                "severity": finding["severity"],
                "file": finding["file"],
                "message": finding["message"],
            }
        ]
    }


def _stamp(tmp_path: Path, name: str = "stamp") -> Path:
    path = tmp_path / name
    path.write_text("stamp", encoding="utf-8")
    return path


def _write_report(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _check(
    report: Path,
    baseline: Path,
    *,
    scanner_rc: int | None = 0,
    stamp: Path | None = None,
    severities: str = "CRITICAL,HIGH",
) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        str(CHECKER),
        str(report),
        str(baseline),
        "--severities",
        severities,
        "--label",
        "Comprehensive audit",
    ]
    if scanner_rc is not None:
        cmd.extend(["--scanner-rc", str(scanner_rc)])
    if stamp is not None:
        cmd.extend(["--newer-than", str(stamp)])
    env = {key: value for key, value in os.environ.items() if not key.startswith(("COV_CORE_", "COVERAGE_"))}
    return subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)


def _fresh(tmp_path: Path, payload: object, baseline_doc: dict) -> tuple[Path, Path, Path]:
    stamp = _stamp(tmp_path)
    os.utime(stamp, (1_700_000_000, 1_700_000_000))
    report = tmp_path / "odoo_audit_report.json"
    baseline = tmp_path / "baseline.json"
    _write_report(report, payload)
    baseline.write_text(json.dumps(baseline_doc), encoding="utf-8")
    return report, baseline, stamp


def test_fresh_known_finding_passes_including_scanner_exit_1(tmp_path: Path) -> None:
    report, baseline, stamp = _fresh(tmp_path, [CRITICAL], _baseline(CRITICAL))
    proc = _check(report, baseline, scanner_rc=1, stamp=stamp)
    output = proc.stdout + proc.stderr
    assert proc.returncode == 0, output
    assert "classified findings" in output
    assert "No new Comprehensive audit findings" in output


def test_fresh_unbaselined_finding_fails(tmp_path: Path) -> None:
    report, baseline, stamp = _fresh(tmp_path, [CRITICAL], {"entries": []})
    proc = _check(report, baseline, scanner_rc=0, stamp=stamp)
    output = proc.stdout + proc.stderr
    assert proc.returncode == 1, output
    assert "new" in output.lower()


def test_missing_report_fails_and_is_not_a_skip(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"entries": []}), encoding="utf-8")
    stamp = _stamp(tmp_path)
    proc = _check(tmp_path / "missing.json", baseline, scanner_rc=1, stamp=stamp)
    output = proc.stdout + proc.stderr
    assert proc.returncode == 1, output
    assert "missing" in output
    assert "skipping" not in output.lower()


def test_preexisting_report_plus_scanner_failure_is_not_reused(tmp_path: Path) -> None:
    report, baseline, _old_stamp = _fresh(tmp_path, [CRITICAL], _baseline(CRITICAL))
    os.utime(report, (1_700_000_000, 1_700_000_000))
    stamp = _stamp(tmp_path, "later")
    proc = _check(report, baseline, scanner_rc=1, stamp=stamp)
    output = proc.stdout + proc.stderr
    assert proc.returncode == 1, output
    assert "not newer" in output


def test_malformed_and_wrong_schema_reports_fail(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps(_baseline(CRITICAL)), encoding="utf-8")
    stamp = _stamp(tmp_path)
    os.utime(stamp, (1_700_000_000, 1_700_000_000))
    cases = [
        "{",
        json.dumps({"entries": []}),
        json.dumps([{"severity": "CRITICAL"}]),
        json.dumps([{"type": "FIELD_NOT_FOUND", "severity": 1}]),
    ]
    for raw in cases:
        report = tmp_path / "report.json"
        report.write_text(raw, encoding="utf-8")
        proc = _check(report, baseline, scanner_rc=0, stamp=stamp)
        output = proc.stdout + proc.stderr
        assert proc.returncode == 1, output


def test_scanner_crash_exit_is_not_a_classified_finding(tmp_path: Path) -> None:
    report, baseline, stamp = _fresh(tmp_path, [CRITICAL], _baseline(CRITICAL))
    proc = _check(report, baseline, scanner_rc=2, stamp=stamp)
    output = proc.stdout + proc.stderr
    assert proc.returncode == 1, output
    assert "scanner execution failed" in output


def test_successive_runs_do_not_reuse_the_previous_report(tmp_path: Path) -> None:
    report, baseline, stamp = _fresh(tmp_path, [CRITICAL], _baseline(CRITICAL))
    first = _check(report, baseline, scanner_rc=1, stamp=stamp)
    assert first.returncode == 0, first.stdout + first.stderr
    later = _stamp(tmp_path, "second")
    second = _check(report, baseline, scanner_rc=1, stamp=later)
    output = second.stdout + second.stderr
    assert second.returncode == 1, output
    assert "not newer" in output


def test_unbound_invocation_fails(tmp_path: Path) -> None:
    report, baseline, _stamp_path = _fresh(tmp_path, [], {"entries": []})
    proc = _check(report, baseline, scanner_rc=None, stamp=None)
    output = proc.stdout + proc.stderr
    assert proc.returncode == 1, output
    assert "not bound" in output


def _stub(report_name: str, marker: Path, finding: dict) -> str:
    return (
        "import json, os, sys\n"
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('ran', encoding='utf-8')\n"
        "if os.environ.get('STUB_MODE') == 'crash':\n"
        "    sys.exit(1)\n"
        f"Path({report_name!r}).write_text(json.dumps([{finding!r}]), encoding='utf-8')\n"
        "sys.exit(1)\n"
    )


def _gate_tree(tmp_path: Path) -> Path:
    audit = tmp_path / "scripts" / "audit"
    audit.mkdir(parents=True)
    for name in ("run_baseline_gate.sh", "check_baseline.py", "baseline_utils.py"):
        shutil.copy(ROOT / "scripts" / "audit" / name, audit / name)
    baselines = tmp_path / "ci" / "baselines"
    baselines.mkdir(parents=True)
    (baselines / "odoo_audit_baseline.json").write_text(json.dumps(_baseline(CRITICAL)), encoding="utf-8")
    (baselines / "extended_audit_baseline.json").write_text(json.dumps(_baseline(HIGH)), encoding="utf-8")
    (audit / "odoo_audit.py").write_text(
        _stub("odoo_audit_report.json", tmp_path / "comp.marker", CRITICAL),
        encoding="utf-8",
    )
    (audit / "run_all_audits.py").write_text(
        _stub("extended_audit_report.json", tmp_path / "ext.marker", HIGH),
        encoding="utf-8",
    )
    return audit / "run_baseline_gate.sh"


def _run_gate(script: Path, mode: str) -> subprocess.CompletedProcess[str]:
    env = {key: value for key, value in os.environ.items() if not key.startswith(("COV_CORE_", "COVERAGE_"))}
    env["STUB_MODE"] = mode
    return subprocess.run(["bash", str(script)], capture_output=True, text=True, check=False, env=env, timeout=30)


def test_gate_accepts_fresh_classified_findings_from_both_scanners(tmp_path: Path) -> None:
    script = _gate_tree(tmp_path)
    proc = _run_gate(script, "write")
    output = proc.stdout + proc.stderr
    assert proc.returncode == 0, output
    assert (tmp_path / "comp.marker").is_file()
    assert (tmp_path / "ext.marker").is_file()


def test_gate_runs_both_scanners_and_fails_when_one_crashes(tmp_path: Path) -> None:
    script = _gate_tree(tmp_path)
    ext = script.parent / "run_all_audits.py"
    ext.write_text(
        "import sys\nfrom pathlib import Path\n"
        f"Path({str(tmp_path / 'ext.marker')!r}).write_text('ran', encoding='utf-8')\n"
        "sys.exit(1)\n",
        encoding="utf-8",
    )
    proc = _run_gate(script, "write")
    output = proc.stdout + proc.stderr
    assert proc.returncode == 1, output
    assert (tmp_path / "comp.marker").is_file()
    assert (tmp_path / "ext.marker").is_file()
    assert "missing" in output


def test_gate_second_run_cannot_reuse_a_previous_matching_report(tmp_path: Path) -> None:
    script = _gate_tree(tmp_path)
    first = _run_gate(script, "write")
    assert first.returncode == 0, first.stdout + first.stderr
    second = _run_gate(script, "crash")
    output = second.stdout + second.stderr
    assert second.returncode == 1, output
    assert "missing" in output


def test_makefile_and_ci_share_the_fail_closed_gate() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "bash scripts/audit/run_baseline_gate.sh" in makefile
    assert "bash scripts/audit/run_baseline_gate.sh" in workflow
    assert "odoo_audit.py . || true" not in makefile
    assert "run_all_audits.py . || true" not in makefile
    audit_job = workflow.split("audit-baseline:")[1].split("secret-scan:")[0]
    assert "|| true" not in audit_job
