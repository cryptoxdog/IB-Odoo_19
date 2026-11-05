"""One-use Production permit for the ERP import (amendment v1.2 D2), with no Odoo runtime.

The permit decisions are pure functions in ``erp/production_permit.py``. The
shell driver is loaded from its repo file against stubbed ``odoo.addons``
modules and an in-memory ``ir_config_parameter`` table, so these tests prove
the refusal order: every refused permit leaves zero import calls, zero commits
of import data and no consumed record, and an admitted permit is consumed once,
atomically, before the first write.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import types
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plasticos_partner_import"))

from erp import production_permit as permits  # noqa: E402
from erp import reader as real_reader  # noqa: E402
from erp import summary as real_summary  # noqa: E402

SCRIPTS = ROOT / "plasticos_partner_import" / "scripts"
DRIVER = SCRIPTS / "import_erp_shell.py"
VALIDATOR = SCRIPTS / "validate_partner_layer.py"
PACKAGE = "odoo.addons.plasticos_partner_import.scripts"
ERP_PACKAGE = "odoo.addons.plasticos_partner_import.erp"
PARTNER_LAYERS = ("counterparties", "addresses", "contacts", "roles", "salesreps")

DB_NAME = "plasticos-prod-main-1234567"
DB_UUID = "0b1c2d3e-4f50-6172-8394-a5b6c7d8e9f0"
RELEASE = "a" * 40
NOW = datetime(2026, 10, 31, 3, 0, tzinfo=UTC)


def _tables(phase: str, *, drift: str = "") -> dict[str, list[dict]]:
    names = permits.phase_tables(phase)
    return {name: [{"Id": f"{name}-1", "Value": f"v{drift}"}, {"Id": f"{name}-2", "Value": None}] for name in names}


def _permit_doc(phase: str = permits.PHASE_PARTNERS, **overrides) -> dict:
    doc = {
        "permit_id": "cutover-20261031-p1",
        "phase": phase,
        "database_name": DB_NAME,
        "database_uuid": DB_UUID,
        "odoo_stage": "production",
        "release_sha": RELEASE,
        "source_fingerprint": permits.source_fingerprint(_tables(phase), permits.phase_tables(phase))["sha256"],
        "expires_at": (NOW + timedelta(hours=6)).isoformat().replace("+00:00", "Z"),
        "approved_by": "operator",
    }
    doc.update(overrides)
    return doc


def _write_permit(tmp_path: Path, doc: dict) -> Path:
    path = tmp_path / f"{doc.get('permit_id', 'permit')}.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def _observed(**overrides) -> permits.Observed:
    values = {
        "database_name": DB_NAME,
        "database_uuid": DB_UUID,
        "odoo_stage": "production",
        "release_sha": RELEASE,
        "release_clean": True,
    }
    values.update(overrides)
    return permits.Observed(**values)


# ---------------------------------------------------------------------------
# Pure permit decisions
# ---------------------------------------------------------------------------


def test_a_complete_permit_on_the_bound_target_is_admitted(tmp_path):
    permit = permits.load_permit(_write_permit(tmp_path, _permit_doc()))
    assert permits.verify_permit(permit, _observed(), phase=permits.PHASE_PARTNERS, now=NOW) is None
    assert permit.phase == permits.PHASE_PARTNERS


@pytest.mark.parametrize(
    ("override", "fragment"),
    [
        ({"permit_id": ""}, "permit_id is missing"),
        ({"permit_id": "short"}, "permit_id must be"),
        ({"phase": "erp_everything"}, "phase must be one of"),
        ({"database_uuid": "not-a-uuid"}, "database_uuid is not a UUID"),
        ({"release_sha": "main"}, "release_sha is not a 40-character git SHA"),
        ({"source_fingerprint": "abc"}, "source_fingerprint is not a SHA-256"),
        ({"expires_at": "2026-10-31T09:00:00"}, "UTC offset"),
        ({"approved_by": " "}, "approved_by is missing"),
        ({"allow_prod": "1"}, "unknown fields: allow_prod"),
    ],
)
def test_a_malformed_permit_is_refused(tmp_path, override, fragment):
    doc = {**_permit_doc(), **override}
    with pytest.raises(permits.PermitRefused, match=fragment):
        permits.load_permit(_write_permit(tmp_path, doc))


def test_an_unreadable_permit_is_refused(tmp_path):
    with pytest.raises(permits.PermitRefused, match="unreadable"):
        permits.load_permit(tmp_path / "absent.json")
    (tmp_path / "list.json").write_text("[]", encoding="utf-8")
    with pytest.raises(permits.PermitRefused, match="not a JSON object"):
        permits.load_permit(tmp_path / "list.json")


@pytest.mark.parametrize(
    ("observed", "phase", "now", "fragment"),
    [
        ({"odoo_stage": ""}, permits.PHASE_PARTNERS, NOW, "only valid on the production stage"),
        ({"odoo_stage": "staging"}, permits.PHASE_PARTNERS, NOW, "only valid on the production stage"),
        ({"database_name": "plasticos-prod-copy"}, permits.PHASE_PARTNERS, NOW, "connected to plasticos-prod-copy"),
        ({"database_uuid": "ffffffff-4f50-6172-8394-a5b6c7d8e9f0"}, permits.PHASE_PARTNERS, NOW, "database_uuid"),
        ({"release_sha": None, "release_clean": False}, permits.PHASE_PARTNERS, NOW, "not provable"),
        ({"release_clean": False}, permits.PHASE_PARTNERS, NOW, "modified tracked files"),
        ({"release_sha": "b" * 40}, permits.PHASE_PARTNERS, NOW, "release_sha"),
        ({}, permits.PHASE_COMMERCIAL, NOW, "is for phase erp_partners"),
        ({}, permits.PHASE_PARTNERS, NOW + timedelta(hours=7), "expired"),
    ],
)
def test_every_binding_mismatch_is_refused(tmp_path, observed, phase, now, fragment):
    permit = permits.load_permit(_write_permit(tmp_path, _permit_doc()))
    with pytest.raises(permits.PermitRefused, match=fragment):
        permits.verify_permit(permit, _observed(**observed), phase=phase, now=now)


def test_a_permit_valid_for_more_than_a_day_is_refused(tmp_path):
    doc = _permit_doc(expires_at=(NOW + timedelta(hours=25)).isoformat())
    permit = permits.load_permit(_write_permit(tmp_path, doc))
    with pytest.raises(permits.PermitRefused, match="exceeds 24 hours"):
        permits.verify_permit(permit, _observed(), phase=permits.PHASE_PARTNERS, now=NOW)


def test_a_permit_written_for_staging_is_refused(tmp_path):
    permit = permits.load_permit(_write_permit(tmp_path, _permit_doc(odoo_stage="staging")))
    with pytest.raises(permits.PermitRefused, match="permit odoo_stage is staging"):
        permits.verify_permit(permit, _observed(), phase=permits.PHASE_PARTNERS, now=NOW)


def test_fingerprint_is_order_independent_and_detects_drift():
    names = permits.phase_tables(permits.PHASE_PARTNERS)
    tables = _tables(permits.PHASE_PARTNERS)
    reordered = {name: list(reversed(rows)) for name, rows in reversed(list(tables.items()))}
    assert permits.source_fingerprint(tables, names) == permits.source_fingerprint(reordered, names)
    drifted = _tables(permits.PHASE_PARTNERS, drift="x")
    assert permits.source_fingerprint(drifted, names)["sha256"] != permits.source_fingerprint(tables, names)["sha256"]
    with pytest.raises(permits.PermitRefused, match="lacks tables: SalesReps"):
        permits.source_fingerprint({k: v for k, v in tables.items() if k != "SalesReps"}, names)


def test_phase_tables_match_what_the_service_reads():
    assert permits.phase_tables(permits.PHASE_PARTNERS) == real_reader.PARTNER_SOURCE_TABLES
    assert (
        permits.phase_tables(permits.PHASE_COMMERCIAL)
        == real_reader.REQUIRED_TABLES | real_reader.COMMERCIAL_SQL_TABLES
    )


def test_partner_fingerprint_from_a_commercial_payload_equals_the_partner_phase():
    partner = permits.source_fingerprint(_tables(permits.PHASE_PARTNERS), permits.phase_tables(permits.PHASE_PARTNERS))
    commercial = permits.source_fingerprint(
        _tables(permits.PHASE_COMMERCIAL), permits.phase_tables(permits.PHASE_COMMERCIAL)
    )
    assert permits.partner_fingerprint(commercial) == partner["sha256"] == permits.partner_fingerprint(partner)


def _phase1_witness(**overrides) -> str:
    fingerprint = permits.source_fingerprint(
        _tables(permits.PHASE_PARTNERS), permits.phase_tables(permits.PHASE_PARTNERS)
    )
    permit = permits.Permit(**{**_permit_doc(), "expires_at": NOW + timedelta(hours=1)})
    verdict = {"final_status": "success", "data_complete": True, "exceptions_digest": "e" * 64}
    witness = permits.witness_record(permit, _observed(), fingerprint, verdict, now=NOW)
    witness.update(overrides)
    return json.dumps(witness)


def _commercial(tmp_path, **overrides) -> tuple[permits.Permit, dict]:
    permit = permits.load_permit(_write_permit(tmp_path, _permit_doc(permits.PHASE_COMMERCIAL, **overrides)))
    fingerprint = permits.source_fingerprint(
        _tables(permits.PHASE_COMMERCIAL), permits.phase_tables(permits.PHASE_COMMERCIAL)
    )
    return permit, fingerprint


def test_commercial_phase_requires_the_committed_partner_phase(tmp_path):
    permit, fingerprint = _commercial(tmp_path)
    permits.check_phase1_witness(_phase1_witness(), permit, _observed(), fingerprint)
    with pytest.raises(permits.PermitRefused, match="no committed erp_partners phase"):
        permits.check_phase1_witness(None, permit, _observed(), fingerprint)
    with pytest.raises(permits.PermitRefused, match="another database"):
        permits.check_phase1_witness(
            _phase1_witness(database_uuid="ffffffff-4f50-6172-8394-a5b6c7d8e9f0"), permit, _observed(), fingerprint
        )
    with pytest.raises(permits.PermitRefused, match="partner source changed"):
        permits.check_phase1_witness(_phase1_witness(partner_fingerprint="0" * 64), permit, _observed(), fingerprint)


def test_a_partial_partner_phase_needs_the_exact_exception_digest_accepted(tmp_path):
    open_witness = _phase1_witness(data_complete=False, exceptions_digest="d" * 64)
    permit, fingerprint = _commercial(tmp_path)
    with pytest.raises(permits.PermitRefused, match="must carry accept_phase1_exceptions_digest"):
        permits.check_phase1_witness(open_witness, permit, _observed(), fingerprint)
    wrong, _ = _commercial(tmp_path, accept_phase1_exceptions_digest="c" * 64)
    with pytest.raises(permits.PermitRefused, match="does not match"):
        permits.check_phase1_witness(open_witness, wrong, _observed(), fingerprint)
    accepted, _ = _commercial(tmp_path, accept_phase1_exceptions_digest="d" * 64)
    permits.check_phase1_witness(open_witness, accepted, _observed(), fingerprint)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)  # noqa: S603, S607


def test_release_identity_is_head_and_tracked_cleanliness(tmp_path):
    assert permits.release_identity(tmp_path) == (None, False)
    _git(tmp_path, "init", "-q")
    _git(
        tmp_path, "-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "x"
    )
    (tmp_path / "tracked.txt").write_text("a", encoding="utf-8")
    _git(tmp_path, "add", "tracked.txt")
    _git(tmp_path, "-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-q", "-m", "y")
    sha, clean = permits.release_identity(tmp_path)
    assert len(sha) == 40 and clean
    (tmp_path / "untracked.txt").write_text("b", encoding="utf-8")
    assert permits.release_identity(tmp_path) == (sha, True)
    (tmp_path / "tracked.txt").write_text("changed", encoding="utf-8")
    assert permits.release_identity(tmp_path) == (sha, False)


# ---------------------------------------------------------------------------
# Data verdict: script completion is not data acceptance
# ---------------------------------------------------------------------------


def test_a_partial_run_exits_zero_but_is_not_data_complete():
    result = {"summary": {"final_status": "partial", "records_rejected": 3, "errors": [{"record_ref": "CP1"}]}}
    assert real_summary.run_exit_status(result) == 0
    verdict = real_summary.data_verdict(result)
    assert verdict["data_complete"] is False
    assert verdict["open_exceptions"] == 3
    assert verdict["accounting_state"] == "draft_unposted"
    assert verdict["accounting_acceptance"] == "BLOCKED_ARCHITECTURE"


def test_only_a_success_without_run_failures_is_data_complete():
    assert real_summary.data_verdict({"summary": {"final_status": "success"}}, partners_only=True) == {
        "final_status": "success",
        "data_complete": True,
        "open_exceptions": 0,
        "run_failures": [],
        "exceptions_digest": real_summary.exceptions_digest({"final_status": "success"}),
    }
    failed = {"summary": {"final_status": "success"}, "failures": [{"check": "payables_reconciliation"}]}
    assert real_summary.data_verdict(failed)["data_complete"] is False
    assert real_summary.data_verdict(failed)["run_failures"] == ["payables_reconciliation"]


def test_exceptions_digest_changes_with_the_open_set():
    base = {"final_status": "partial", "records_rejected": 1, "errors": [{"record_ref": "A", "message": "m"}]}
    same = {"final_status": "partial", "records_rejected": 1, "errors": [{"record_ref": "A", "message": "m"}]}
    other = {"final_status": "partial", "records_rejected": 1, "errors": [{"record_ref": "B", "message": "m"}]}
    assert real_summary.exceptions_digest(base) == real_summary.exceptions_digest(same)
    assert real_summary.exceptions_digest(base) != real_summary.exceptions_digest(other)


# ---------------------------------------------------------------------------
# Shell driver against an in-memory ir_config_parameter table
# ---------------------------------------------------------------------------


class _Cursor:
    def __init__(self, name: str, params: dict, race: bool):
        self.name = name
        self.params = params
        self.race = race
        self.commits = 0
        self.rollbacks = 0
        self.inserts: list[str] = []
        self._last = None

    def execute(self, query, args=None):
        compact = " ".join(query.split())
        if compact == "SELECT current_database()":
            self._last = (self.name,)
        elif compact.startswith("SELECT value FROM ir_config_parameter WHERE key"):
            value = self.params.get(args[0])
            self._last = None if value is None else (value,)
        elif compact.startswith("INSERT INTO ir_config_parameter"):
            key, value = args[0], args[1]
            if self.race or key in self.params:
                self._last = None
            else:
                self.params[key] = value
                self.inserts.append(key)
                self._last = (1,)
        elif "res_users" in compact:
            self._last = (0,)
        else:
            self._last = (28,)

    def fetchone(self):
        return self._last

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class _Params:
    def __init__(self, table: dict):
        self.table = table

    def set_param(self, key, value):
        self.table[key] = value


class _Env:
    uid = 1

    def __init__(self, name=DB_NAME, params=None, race=False):
        self.params = {"database.uuid": DB_UUID, **(params or {})}
        self.cr = _Cursor(name, self.params, race)

    def __getitem__(self, model):
        assert model == "ir.config_parameter"
        return _Params(self.params)


class _Payload:
    def __init__(self, tables):
        self.tables = tables


class _Driver:
    def __init__(self, monkeypatch, env, *, database=True, release=(RELEASE, True), drift=""):
        self.env = env
        self.runs: list[dict] = []
        self.validated: list[str] = []
        self.admitted: list[str] = []
        self.writes_before_consumption = 0
        driver = self
        real_validator_spec = importlib.util.spec_from_file_location("erp_validate_for_permit", VALIDATOR)
        real_validator = importlib.util.module_from_spec(real_validator_spec)
        real_validator_spec.loader.exec_module(real_validator)

        def validate(_env, layer, payload=None):
            driver.validated.append(layer)
            return 0

        def run(env_, **kwargs):
            driver.runs.append(kwargs)
            phase = permits.PHASE_PARTNERS if kwargs["partners_only"] else permits.PHASE_COMMERCIAL
            hook = kwargs.get("on_payload")
            if hook is not None and not kwargs["dry_run"]:
                hook(_Payload(_tables(phase, drift=drift)))
            if not env_.cr.inserts:
                driver.writes_before_consumption += 1
            for stage in PARTNER_LAYERS:
                kwargs["after_stage"](stage, None)
            if kwargs.get("commit"):
                env_.cr.commit()
            return {"summary": {"final_status": "success", "records_rejected": 0, "errors": []}}

        addon = types.ModuleType("odoo.addons.plasticos_partner_import")
        addon.__file__ = str(ROOT / "plasticos_partner_import" / "__init__.py")
        for name in ("odoo", "odoo.addons", PACKAGE, ERP_PACKAGE):
            monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
        monkeypatch.setitem(sys.modules, addon.__name__, addon)
        monkeypatch.setitem(sys.modules, f"{ERP_PACKAGE}.summary", real_summary)
        monkeypatch.setitem(sys.modules, f"{ERP_PACKAGE}.production_permit", permits)
        monkeypatch.setattr(permits, "release_identity", lambda _path: release)
        reader = types.ModuleType(f"{ERP_PACKAGE}.reader")
        reader.database_source_from_env = lambda _environ: types.SimpleNamespace(label="sql/erp") if database else None
        monkeypatch.setitem(sys.modules, reader.__name__, reader)
        limits_spec = importlib.util.spec_from_file_location(
            f"{ERP_PACKAGE}.limits", ROOT / "plasticos_partner_import" / "erp" / "limits.py"
        )
        limits = importlib.util.module_from_spec(limits_spec)
        limits_spec.loader.exec_module(limits)
        monkeypatch.setitem(sys.modules, limits.__name__, limits)
        runner = types.ModuleType(f"{PACKAGE}.run_erp_import")
        runner.run = run
        validator = types.ModuleType(f"{PACKAGE}.validate_partner_layer")
        validator.LAYER_BEFORE = real_validator.LAYER_BEFORE
        validator.DATABASE_CHECK = real_validator.DATABASE_CHECK
        validator.LayerRejected = real_validator.LayerRejected
        validator.validate = validate
        validator.check_full_run_extension = lambda _env, _failures: None
        validator.admit_production = driver.admitted.append
        monkeypatch.setitem(sys.modules, runner.__name__, runner)
        monkeypatch.setitem(sys.modules, validator.__name__, validator)
        for name in ("DRY", "LIMIT", "PAYLOAD_ROOT", "REPORT_PATH", "PARTNERS_ONLY", "LAYER", "REQUIRE_EMPTY", "PROBE"):
            monkeypatch.delenv(f"ERP_{name}", raising=False)
        monkeypatch.setenv("ERP_TARGET_DB", DB_NAME)
        monkeypatch.setenv("ODOO_STAGE", "production")

    def main(self) -> int:
        spec = importlib.util.spec_from_file_location("erp_import_shell_permit", DRIVER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.env = self.env
        return module.main()


@pytest.fixture(autouse=True)
def _frozen_clock(monkeypatch):
    real_verify = permits.verify_permit
    monkeypatch.setattr(
        permits,
        "verify_permit",
        lambda permit, observed, *, phase, now=None: real_verify(permit, observed, phase=phase, now=now or NOW),
    )


def _partners_run(monkeypatch, tmp_path, doc=None, **driver_kwargs):
    env = driver_kwargs.pop("env", None) or _Env()
    driver = _Driver(monkeypatch, env, **driver_kwargs)
    monkeypatch.setenv("ERP_PARTNERS_ONLY", "1")
    monkeypatch.setenv("ERP_PRODUCTION_PERMIT", str(_write_permit(tmp_path, doc or _permit_doc())))
    return driver


def test_admitted_partner_phase_consumes_once_then_commits_rows_with_its_witness(monkeypatch, tmp_path):
    driver = _partners_run(monkeypatch, tmp_path)
    monkeypatch.setenv("ERP_REPORT_PATH", str(tmp_path / "reports" / "erp-partners.json"))

    assert driver.main() == 0
    assert driver.admitted == [DB_NAME]
    assert driver.validated[0] == "database"
    (run,) = driver.runs
    assert run["commit"] is False and run["partners_only"] is True
    assert driver.env.cr.inserts == [permits.consumed_key("cutover-20261031-p1")]
    assert driver.writes_before_consumption == 0
    # Consumption commit, then the witness commit that carries the partner rows.
    assert driver.env.cr.commits == 2
    witness = json.loads(driver.env.params[permits.PHASE1_WITNESS_PARAM])
    assert witness["database_uuid"] == DB_UUID and witness["data_complete"] is True
    receipt = json.loads((tmp_path / "reports" / "erp-partners-permit.json").read_text(encoding="utf-8"))
    assert [event["event"] for event in receipt["audit_events"]] == [
        "erp_production.admitted",
        "erp_production.consumed",
        "erp_production.committed",
    ]
    assert "password" not in json.dumps(receipt).lower()


def _refused(driver, fragment, capsys) -> None:
    assert driver.main() == 1
    assert fragment in capsys.readouterr().out
    assert driver.env.cr.inserts == []
    assert driver.env.cr.commits == 0
    assert permits.PHASE1_WITNESS_PARAM not in driver.env.params


@pytest.mark.parametrize(
    ("env_settings", "fragment"),
    [
        ({"REQUIRE_EMPTY": "0"}, "cannot disable the empty-target guard"),
        ({"LIMIT": "25%"}, "ERP_LIMIT is a diagnostic cap"),
        ({"PAYLOAD_ROOT": "/tmp/grid"}, "unset ERP_PAYLOAD_ROOT"),
        ({"DRY": "1"}, "unset ERP_DRY"),
        ({"LAYER": "counterparties"}, "unset ERP_LAYER"),
    ],
)
def test_a_permit_cannot_widen_the_run(monkeypatch, tmp_path, capsys, env_settings, fragment):
    driver = _partners_run(monkeypatch, tmp_path)
    for name, value in env_settings.items():
        monkeypatch.setenv(f"ERP_{name}", value)
    _refused(driver, fragment, capsys)
    assert driver.runs == []


def test_a_permit_without_the_direct_sql_source_is_refused(monkeypatch, tmp_path, capsys):
    _refused(_partners_run(monkeypatch, tmp_path, database=False), "needs the direct SQL source", capsys)


def test_a_permit_on_a_non_production_stage_is_refused(monkeypatch, tmp_path, capsys):
    driver = _partners_run(monkeypatch, tmp_path)
    monkeypatch.setenv("ODOO_STAGE", "staging")
    _refused(driver, "only valid on the production stage", capsys)
    assert driver.admitted == []


def test_a_production_named_scratch_database_cannot_use_the_permit(monkeypatch, tmp_path, capsys):
    driver = _partners_run(monkeypatch, tmp_path, env=_Env(name="erp_import_gate_prod"))
    monkeypatch.setenv("ERP_TARGET_DB", "erp_import_gate_prod")
    _refused(driver, "connected to erp_import_gate_prod", capsys)


def test_a_dirty_or_unknown_release_is_refused(monkeypatch, tmp_path, capsys):
    _refused(_partners_run(monkeypatch, tmp_path, release=(RELEASE, False)), "modified tracked files", capsys)


def test_a_consumed_permit_is_refused_before_the_import(monkeypatch, tmp_path, capsys):
    env = _Env(params={permits.consumed_key("cutover-20261031-p1"): "{}"})
    driver = _partners_run(monkeypatch, tmp_path, env=env)
    assert driver.main() == 1
    assert "already consumed" in capsys.readouterr().out
    assert driver.runs == []


def test_a_concurrent_consumer_loses_the_atomic_insert_and_writes_nothing(monkeypatch, tmp_path, capsys):
    driver = _partners_run(monkeypatch, tmp_path, env=_Env(race=True))
    assert driver.main() == 1
    assert "already consumed" in capsys.readouterr().out
    assert driver.env.cr.commits == 0
    assert driver.env.cr.rollbacks >= 1
    assert permits.PHASE1_WITNESS_PARAM not in driver.env.params


def test_source_drift_after_the_probe_is_refused_before_consumption(monkeypatch, tmp_path, capsys):
    driver = _partners_run(monkeypatch, tmp_path, drift="changed")
    assert driver.main() == 1
    assert "does not match the permit source_fingerprint" in capsys.readouterr().out
    assert driver.env.cr.inserts == [] and driver.env.cr.commits == 0


def _commercial_run(monkeypatch, tmp_path, *, params=None, **doc_overrides):
    driver = _Driver(monkeypatch, _Env(params=params))
    monkeypatch.setenv("ERP_REQUIRE_EMPTY", "0")
    doc = _permit_doc(permits.PHASE_COMMERCIAL, permit_id="cutover-20261031-p2", **doc_overrides)
    monkeypatch.setenv("ERP_PRODUCTION_PERMIT", str(_write_permit(tmp_path, doc)))
    return driver


def test_commercial_phase_is_refused_without_a_committed_partner_phase(monkeypatch, tmp_path, capsys):
    driver = _commercial_run(monkeypatch, tmp_path)
    assert driver.main() == 1
    assert "no committed erp_partners phase" in capsys.readouterr().out
    assert driver.runs == []


def test_commercial_phase_is_refused_with_the_empty_guard_on(monkeypatch, tmp_path, capsys):
    driver = _commercial_run(monkeypatch, tmp_path, params={permits.PHASE1_WITNESS_PARAM: _phase1_witness()})
    monkeypatch.delenv("ERP_REQUIRE_EMPTY")
    assert driver.main() == 1
    assert "set ERP_REQUIRE_EMPTY=0" in capsys.readouterr().out


def test_commercial_phase_after_partners_writes_the_completion_witness(monkeypatch, tmp_path):
    driver = _commercial_run(monkeypatch, tmp_path, params={permits.PHASE1_WITNESS_PARAM: _phase1_witness()})
    assert driver.main() == 0
    (run,) = driver.runs
    assert run["commit"] is True and run["partners_only"] is False
    assert driver.env.cr.inserts == [permits.consumed_key("cutover-20261031-p2")]
    witness = json.loads(driver.env.params[permits.PHASE2_WITNESS_PARAM])
    assert witness["phase"] == permits.PHASE_COMMERCIAL and witness["final_status"] == "success"


def test_commercial_phase_refuses_a_partner_witness_from_another_database(monkeypatch, tmp_path, capsys):
    other = _phase1_witness(database_uuid="ffffffff-4f50-6172-8394-a5b6c7d8e9f0")
    driver = _commercial_run(monkeypatch, tmp_path, params={permits.PHASE1_WITNESS_PARAM: other})
    assert driver.main() == 1
    assert "another database" in capsys.readouterr().out
    assert driver.env.cr.inserts == []


def test_probe_reports_identity_and_fingerprint_and_writes_nothing(monkeypatch, tmp_path, capsys):
    driver = _Driver(monkeypatch, _Env())
    real_load = real_reader.load_payload
    monkeypatch.setattr(
        sys.modules[f"{ERP_PACKAGE}.reader"],
        "load_payload",
        lambda _root, only, database: types.SimpleNamespace(
            tables=_tables(permits.PHASE_PARTNERS), kind=types.SimpleNamespace(value="database"), origin="sql/erp"
        ),
        raising=False,
    )
    assert real_load is not None
    monkeypatch.setenv("ERP_PROBE", permits.PHASE_PARTNERS)
    assert driver.main() == 0
    line = next(row for row in capsys.readouterr().out.splitlines() if row.startswith("ERP_PRODUCTION_PROBE "))
    probe = json.loads(line.removeprefix("ERP_PRODUCTION_PROBE "))
    assert probe["permit_template"]["source_fingerprint"] == _permit_doc()["source_fingerprint"]
    assert probe["permit_template"]["database_uuid"] == DB_UUID
    assert driver.runs == [] and driver.env.cr.commits == 0 and driver.env.cr.rollbacks == 1


# ---------------------------------------------------------------------------
# Database check: admission lifts the production refusal for one database only
# ---------------------------------------------------------------------------


class _Modules:
    def search(self, domain):
        wanted = next(value for name, _op, value in domain if name == "name")
        return types.SimpleNamespace(mapped=lambda _field: list(wanted))


class _CheckEnv:
    def __init__(self, name):
        self.cr = types.SimpleNamespace(execute=lambda _q: None, fetchone=lambda: (name,))

    def __getitem__(self, model):
        return _Modules()

    def ref(self, _xmlid, raise_if_not_found=True):
        return types.SimpleNamespace(get_combined_arch=lambda: "phone_line_ids not is_company")


def _check(monkeypatch, name, *, stage, admitted=None) -> list[str]:
    spec = importlib.util.spec_from_file_location("erp_validate_admission", VALIDATOR)
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    monkeypatch.setenv("ERP_TARGET_DB", name)
    monkeypatch.setenv("ERP_PARTNERS_ONLY", "1")
    monkeypatch.setenv("ODOO_STAGE", stage)
    if admitted:
        validator.admit_production(admitted)
    failures: list[str] = []
    validator.check_database(_CheckEnv(name), failures)
    return failures


def test_production_stays_refused_without_admission(monkeypatch):
    failures = _check(monkeypatch, DB_NAME, stage="production")
    assert any("verified one-use permit" in failure for failure in failures)
    assert any("identifies as production" in failure for failure in failures)


def test_admission_lifts_the_refusal_only_for_the_admitted_database(monkeypatch):
    assert _check(monkeypatch, DB_NAME, stage="production", admitted=DB_NAME) == []
    other = _check(monkeypatch, DB_NAME, stage="production", admitted="plasticos-prod-other")
    assert any("verified one-use permit" in failure for failure in other)


def test_admission_never_applies_off_the_production_stage(monkeypatch):
    failures = _check(monkeypatch, DB_NAME, stage="", admitted=DB_NAME)
    assert any("identifies as production" in failure for failure in failures)
