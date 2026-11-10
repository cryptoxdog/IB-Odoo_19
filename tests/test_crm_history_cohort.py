"""VanillaSoft 4,876-ContactID history mode: census, ledger, resume, fencing, permit.

Pure-Python tier. ``services/historical_cohort.py`` is exercised directly; the
history mode of ``scripts/import_vanillasoft_shell.py`` runs against an
in-memory transactional database (commit, rollback, savepoint), a fake
orchestrator with the real per-ID seam's contract, and a shared advisory-lock
table. The census is synthetic: ContactIDs only, the approved 763/18/4,095
partition, and the four real omitted duplicate ids.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import types
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "plasticos_partner_import"))

from erp import production_permit as erp_permit  # noqa: E402

from plasticos_crm_sync.scripts import import_vanillasoft_shell as shell  # noqa: E402
from plasticos_crm_sync.services import historical_cohort as cohort  # noqa: E402

_REAL_VERIFY_PERMIT = cohort.verify_permit

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)
DB_UUID = "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0"
RELEASE = "a" * 40
OMITTED = sorted(cohort.OMITTED_DUPLICATE_VS_IDS)
BOUND = [str(2_000_000 + i) for i in range(759)]
NO_IDS = [str(3_000_000 + i) for i in range(18)]
PENDING_IDS = [str(4_000_000 + i) for i in range(4095)]
CROSSWALK = {vs_id: str(100_000_001 + i) for i, vs_id in enumerate(BOUND)}


def _census_text(rows=None) -> str:
    rows = rows or (
        [(i, "YES") for i in BOUND + OMITTED] + [(i, "NO") for i in NO_IDS] + [(i, "PENDING") for i in PENDING_IDS]
    )
    return "vanillasoft_contact_id,decision\n" + "".join(f"{i},{d}\n" for i, d in rows)


CENSUS_TEXT = _census_text()
CENSUS_SHA = cohort.sha256_text(CENSUS_TEXT)
CENSUS = cohort.load_census(CENSUS_TEXT, expected_sha256=CENSUS_SHA)


# ── census and identity ─────────────────────────────────────────────────────


def test_census_loads_the_exact_partition():
    assert len(CENSUS) == cohort.COHORT
    assert sum(1 for d in CENSUS.values() if d == "YES") == 763


@pytest.mark.parametrize(
    ("text", "sha", "needle"),
    [
        (CENSUS_TEXT, "", "must be declared"),
        (CENSUS_TEXT, "0" * 64, "!= declared"),
        (CENSUS_TEXT.replace("vanillasoft_contact_id,decision", "id,decision,email"), None, "header"),
        (CENSUS_TEXT + f"{BOUND[0]},YES\n", None, "repeats"),
        (CENSUS_TEXT.replace(f"{NO_IDS[0]},NO", f"{NO_IDS[0]},PENDING"), None, "partition"),
        (CENSUS_TEXT.replace(f"{NO_IDS[0]},NO", "abc,NO"), None, "not a ContactID"),
        (CENSUS_TEXT.replace(f"{NO_IDS[0]},NO\n", ""), None, "not 4876"),
    ],
)
def test_census_refuses_every_defect(text, sha, needle):
    with pytest.raises(cohort.CohortError, match=needle):
        cohort.load_census(text, expected_sha256=cohort.sha256_text(text) if sha is None else sha)


def test_identity_is_crosswalk_plus_omitted_duplicates():
    assert cohort.verify_identity(CENSUS, CROSSWALK, OMITTED) is None


@pytest.mark.parametrize(
    ("crosswalk", "needle"),
    [
        ({**CROSSWALK, PENDING_IDS[0]: "1"}, "not YES"),
        ({k: v for k, v in CROSSWALK.items() if k != BOUND[0]}, "neither in the crosswalk"),
        ({**CROSSWALK, OMITTED[0]: "1"}, "also in the crosswalk"),
    ],
)
def test_identity_refuses_pending_binding_missing_yes_and_overlap(crosswalk, needle):
    with pytest.raises(cohort.CohortError, match=needle):
        cohort.verify_identity(CENSUS, crosswalk, OMITTED)


def test_packaged_crosswalk_excludes_the_omitted_duplicates():
    text = (ROOT / "plasticos_crm_sync" / "data" / "approved_contact_crosswalk.csv").read_text(encoding="utf-8")
    ids = {line.split(",")[1] for line in text.splitlines()[1:] if line}
    assert not ids & cohort.OMITTED_DUPLICATE_VS_IDS
    assert len(ids) == 759


# ── plan, classification, redaction ─────────────────────────────────────────


def test_plan_skips_durable_ids_and_records_each_duplicate_once():
    imported = set(BOUND[:10])
    ledger = {OMITTED[0]: {"class": cohort.DUPLICATE_SKIPPED}}
    steps = cohort.plan(CENSUS, OMITTED, imported, ledger)
    ids = [cid for cid, _ in steps]
    assert not imported & set(ids)
    assert [cid for cid, action in steps if action == "skip_duplicate"] == sorted(OMITTED[1:], key=int)
    assert ids == sorted(ids, key=int)
    assert len(steps) == cohort.COHORT - 10 - 1


def test_plan_retries_held_and_failed_ids():
    ledger = {NO_IDS[0]: {"class": cohort.HELD}, NO_IDS[1]: {"class": cohort.GENUINE_FAILED}}
    ids = {cid for cid, _ in cohort.plan(CENSUS, OMITTED, set(), ledger)}
    assert {NO_IDS[0], NO_IDS[1]} <= ids


@pytest.mark.parametrize(
    ("raw", "messages", "durable", "expected"),
    [
        ("created", [], True, cohort.IMPORTED),
        ("unchanged", [], True, cohort.IMPORTED),
        ("created", [], False, cohort.GENUINE_FAILED),
        ("failed", ["ERP marker missing"], False, cohort.HELD),
        ("duplicate_rejected", ["multiple leads"], False, cohort.GENUINE_FAILED),
        ("RuntimeError", [], False, cohort.GENUINE_FAILED),
    ],
)
def test_classification_uses_durable_state(raw, messages, durable, expected):
    assert cohort.classify(raw, messages, durable=durable) == expected


def test_signals_never_leave_a_failure_without_a_reason():
    assert cohort.signals("none", [], "", [], cohort.GENUINE_FAILED)[0]["level"] == "UNKNOWN"
    reasons = [s["reason"] for s in cohort.signals("created", [], "", [], cohort.GENUINE_FAILED)]
    assert any("no durable external ref" in r for r in reasons)
    assert cohort.signals("created", [], "", [], cohort.IMPORTED) == []


@pytest.mark.parametrize(
    "text",
    [
        "contact jane.doe+x@example.com refused",
        "api_key=sk-123456 rejected",
        "Authorization: Bearer abc.def",
        "phone (555) 123-4567 invalid",
        "phone +1 555.123.4567 invalid",
    ],
)
def test_redaction_removes_email_secret_and_phone(text):
    cleaned = cohort.redact(text)
    for needle in ("@example.com", "sk-123456", "abc.def", "123-4567", "123.4567"):
        assert needle not in cleaned


# ── ledger ───────────────────────────────────────────────────────────────────


def _row(cid, cls=cohort.GENUINE_FAILED, reason="HTTP 500"):
    return {
        "vanillasoft_contact_id": cid,
        "decision": CENSUS[cid],
        "class": cls,
        "signals": [{"level": "ERROR", "reason": reason}],
    }


def test_ledger_binds_census_and_database(tmp_path):
    path = tmp_path / "ledger.jsonl"
    cohort.Ledger(path, census_sha256=CENSUS_SHA, database_uuid=DB_UUID).append(_row(NO_IDS[0]))
    with pytest.raises(cohort.CohortError, match="another census"):
        cohort.Ledger(path, census_sha256="b" * 64, database_uuid=DB_UUID)
    with pytest.raises(cohort.CohortError, match="another database"):
        cohort.Ledger(path, census_sha256=CENSUS_SHA, database_uuid="other")
    assert NO_IDS[0] in cohort.Ledger(path, census_sha256=CENSUS_SHA, database_uuid=DB_UUID).rows


def test_ledger_tolerates_a_torn_last_line_and_keeps_the_latest_row(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = cohort.Ledger(path, census_sha256=CENSUS_SHA, database_uuid=DB_UUID)
    ledger.append(_row(NO_IDS[0], reason="first"))
    ledger.append(_row(NO_IDS[0], cls=cohort.HELD, reason="second"))
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"vanillasoft_contact_id": "30')
    again = cohort.Ledger(path, census_sha256=CENSUS_SHA, database_uuid=DB_UUID)
    assert again.torn_tail
    assert again.rows[NO_IDS[0]]["class"] == cohort.HELD
    again.append(_row(NO_IDS[1]))
    final = cohort.Ledger(path, census_sha256=CENSUS_SHA, database_uuid=DB_UUID)
    assert not final.torn_tail and NO_IDS[1] in final.rows


def test_ledger_refuses_a_corrupt_middle_line(tmp_path):
    path = tmp_path / "ledger.jsonl"
    cohort.Ledger(path, census_sha256=CENSUS_SHA, database_uuid=DB_UUID).append(_row(NO_IDS[0]))
    with path.open("a", encoding="utf-8") as handle:
        handle.write("not json\n" + json.dumps(_row(NO_IDS[1])) + "\n")
    with pytest.raises(cohort.CohortError, match="not JSON"):
        cohort.Ledger(path, census_sha256=CENSUS_SHA, database_uuid=DB_UUID)


# ── report ───────────────────────────────────────────────────────────────────


def test_report_sums_to_the_cohort_and_trusts_only_durable_refs():
    durable = set(BOUND + NO_IDS + PENDING_IDS[:-2])
    ledger = {i: _row(i, cls=cohort.DUPLICATE_SKIPPED, reason="dup") for i in OMITTED}
    ledger[PENDING_IDS[-2]] = {**_row(PENDING_IDS[-2]), "class": cohort.IMPORTED, "signals": []}
    ledger[PENDING_IDS[-1]] = _row(PENDING_IDS[-1], cls=cohort.HELD, reason="ERP marker")
    verdict = cohort.report(CENSUS, durable, ledger)
    assert sum(verdict["classes"].values()) == cohort.COHORT
    assert verdict["HISTORICAL_SNAPSHOT_COMPLETE"]
    assert not verdict["historical_data_complete"]
    assert verdict["classes"][cohort.GENUINE_FAILED] == 1
    assert verdict["dispositions_without_a_source_reason"] == 1
    assert verdict["LIVE_DELTA_COMPLETENESS"] == "NOT_RUN"
    assert verdict["FULL_CURRENT_CONTACT_COVERAGE"] == "UNKNOWN"


def test_report_stamps_the_length_of_the_census_it_was_given():
    census = {"1": "YES", "2": "PENDING"}
    ledger = {
        "2": {
            "vanillasoft_contact_id": "2",
            "decision": "PENDING",
            "class": cohort.HELD,
            "signals": [{"level": "ERROR", "reason": "waiting"}],
        }
    }
    verdict = cohort.report(census, {"1"}, ledger)
    assert verdict["cohort"] == 2
    assert verdict["dispositioned"] + verdict["undispositioned"] == 2
    assert verdict["HISTORICAL_SNAPSHOT_COMPLETE"]


def test_report_counts_undispositioned_and_unknown_reasons():
    ledger = {NO_IDS[0]: {**_row(NO_IDS[0]), "signals": [{"level": "UNKNOWN", "reason": "outcome none"}]}}
    verdict = cohort.report(CENSUS, set(), ledger)
    assert verdict["undispositioned"] == cohort.COHORT - 1
    assert not verdict["HISTORICAL_SNAPSHOT_COMPLETE"]
    assert verdict["dispositions_without_a_source_reason"] == 1


# ── permit parity with the ERP verifier ──────────────────────────────────────


def _permit_doc(**overrides):
    doc = {
        "permit_id": "crm-history-0001",
        "phase": cohort.PERMIT_PHASE,
        "database_name": "plasticos-main-1",
        "database_uuid": DB_UUID,
        "odoo_stage": "production",
        "release_sha": RELEASE,
        "source_fingerprint": CENSUS_SHA,
        "expires_at": (NOW + timedelta(hours=4)).isoformat(),
        "approved_by": "operator",
    }
    doc.update(overrides)
    return doc


def _observed(module, **overrides):
    values = {
        "database_name": "plasticos-main-1",
        "database_uuid": DB_UUID,
        "odoo_stage": "production",
        "release_sha": RELEASE,
        "release_clean": True,
    }
    values.update(overrides)
    return module.Observed(**values)


PARITY_CASES = [
    ({}, {}),
    ({}, {"odoo_stage": "staging"}),
    ({"odoo_stage": "staging"}, {}),
    ({"database_name": "other"}, {}),
    ({"database_uuid": "1" * 8 + DB_UUID[8:]}, {}),
    ({}, {"release_sha": None}),
    ({}, {"release_clean": False}),
    ({"release_sha": "b" * 40}, {}),
    ({"expires_at": (NOW - timedelta(minutes=1)).isoformat()}, {}),
    ({"expires_at": (NOW + timedelta(hours=25)).isoformat()}, {}),
]


@pytest.mark.parametrize(("permit_over", "observed_over"), PARITY_CASES)
def test_crm_permit_decides_exactly_like_the_erp_permit(tmp_path, permit_over, observed_over):
    crm_path = tmp_path / "crm.json"
    crm_path.write_text(json.dumps(_permit_doc(**permit_over)), encoding="utf-8")
    erp_path = tmp_path / "erp.json"
    erp_path.write_text(json.dumps(_permit_doc(phase=erp_permit.PHASE_PARTNERS, **permit_over)), encoding="utf-8")

    def decide(fn):
        try:
            fn()
        except (cohort.PermitRefused, erp_permit.PermitRefused) as refused:
            return len(refused.reasons)
        return 0

    crm = decide(
        lambda: cohort.verify_permit(
            cohort.load_permit(crm_path), _observed(cohort, **observed_over), fingerprint=CENSUS_SHA, now=NOW
        )
    )
    erp = decide(
        lambda: erp_permit.verify_permit(
            erp_permit.load_permit(erp_path),
            _observed(erp_permit, **observed_over),
            phase=erp_permit.PHASE_PARTNERS,
            now=NOW,
        )
    )
    assert crm == erp


@pytest.mark.parametrize(
    ("override", "needle"),
    [
        ({"phase": "erp_partners"}, "phase must be"),
        ({"database_uuid": "nope"}, "not a UUID"),
        ({"release_sha": "abc"}, "40-character"),
        ({"source_fingerprint": "abc"}, "SHA-256"),
        ({"extra": "x"}, "unknown fields"),
        ({"approved_by": ""}, "missing or empty"),
        ({"expires_at": "2026-10-30T12:00:00"}, "UTC offset"),
    ],
)
def test_crm_permit_shape_refusals(tmp_path, override, needle):
    path = tmp_path / "permit.json"
    path.write_text(json.dumps(_permit_doc(**override)), encoding="utf-8")
    with pytest.raises(cohort.PermitRefused, match=needle):
        cohort.load_permit(path)


def test_crm_permit_binds_the_census_digest(tmp_path):
    path = tmp_path / "permit.json"
    path.write_text(json.dumps(_permit_doc(source_fingerprint="c" * 64)), encoding="utf-8")
    with pytest.raises(cohort.PermitRefused, match="census"):
        cohort.verify_permit(cohort.load_permit(path), _observed(cohort), fingerprint=CENSUS_SHA, now=NOW)


@pytest.mark.parametrize(
    ("raw", "needle"),
    [
        (None, "no committed erp_commercial"),
        ("{", "readable"),
        (json.dumps({"phase": "erp_partners", "database_uuid": DB_UUID}), "another phase"),
        (json.dumps({"phase": "erp_commercial", "database_uuid": "x"}), "another database"),
        (json.dumps({"phase": "erp_commercial", "database_uuid": DB_UUID, "final_status": "failed"}), "failed"),
    ],
)
def test_crm_history_on_production_needs_a_committed_erp_commercial_phase(raw, needle):
    with pytest.raises(cohort.PermitRefused, match=needle):
        cohort.check_erp_completion(raw, _observed(cohort))


def test_witness_keys_match_the_erp_owner():
    assert cohort.ERP_PHASE2_WITNESS_PARAM == erp_permit.PHASE2_WITNESS_PARAM


# ── shell harness ────────────────────────────────────────────────────────────

LOCKS: set[str] = set()


class _Db:
    """Committed rows plus a pending-write log: commit applies it, rollback drops it, a savepoint truncates it."""

    def __init__(self, name="plasticos_scratch"):
        self.name = name
        self.committed = {"params": {"database.uuid": DB_UUID, cohort.ERP_READY_PARAM: "1200"}, "refs": {}}
        self.pending: list[tuple] = []
        self.commits = 0
        self.fail_on_commit: int | None = None

    def param(self, key):
        for kind, name, value in reversed(self.pending):
            if kind == "param" and name == key:
                return value
        return self.committed["params"].get(key)

    def models(self, external_id) -> set[str]:
        found = set(self.committed["refs"].get(external_id, ()))
        found.update(model for kind, name, model in self.pending if kind == "ref" and name == external_id)
        return found

    def committed_refs(self) -> set[tuple[str, str]]:
        return {(e, m) for e, models in self.committed["refs"].items() for m in models}


class _Cr:
    def __init__(self, db: _Db):
        self.db = db
        self._row = None

    def execute(self, sql, params=()):
        text = " ".join(sql.split())
        params = tuple(params or ())
        if text.startswith("SELECT value FROM ir_config_parameter"):
            value = self.db.param(params[0])
            self._row = (value,) if value is not None else None
        elif text.startswith("SELECT current_database()"):
            self._row = (self.db.name,)
        elif text.startswith("INSERT INTO ir_config_parameter"):
            key, value = params[0], params[1]
            if self.db.param(key) is not None:
                self._row = None
            else:
                self.db.pending.append(("param", key, value))
                self._row = (1,)
        else:
            raise AssertionError(f"unexpected SQL: {text}")

    def fetchone(self):
        return self._row

    def commit(self):
        if self.db.fail_on_commit == self.db.commits + 1:
            self.db.fail_on_commit = None
            raise RuntimeError("worker killed before commit")
        for kind, name, value in self.db.pending:
            if kind == "param":
                self.db.committed["params"][name] = value
            else:
                self.db.committed["refs"].setdefault(name, set()).add(value)
        self.db.pending = []
        self.db.commits += 1

    def rollback(self):
        self.db.pending = []

    @contextmanager
    def savepoint(self):
        mark = len(self.db.pending)
        try:
            yield
        except Exception:
            del self.db.pending[mark:]
            raise


class _Params:
    def __init__(self, db):
        self.db = db

    def sudo(self):
        return self

    def get_param(self, key, default=None):
        value = self.db.param(key)
        return default if value is None else value

    def set_param(self, key, value):
        self.db.pending.append(("param", key, value))


class _Refs:
    def __init__(self, db):
        self.db = db

    def sudo(self):
        return self

    def search_read(self, domain, fields):
        wanted = set(dict((d[0], d[2]) for d in domain)["external_id"])
        return [{"external_id": e, "res_model": m} for e in wanted for m in self.db.models(e)]


class _Connection:
    id = 7


class _Connections:
    def get_or_create_vanillasoft_connection(self):
        return _Connection()


class _Cron:
    active = False


class _Env:
    uid = 1

    def __init__(self, db, context=None, cron=None):
        self.db = db
        self.cr = _Cr(db) if not hasattr(db, "cr") else db.cr
        db.cr = self.cr
        self.context = dict(context or {})
        self.cron = cron or _Cron()

    def __call__(self, context=None):
        return _Env(self.db, context=context, cron=self.cron)

    def __getitem__(self, model):
        return {
            "ir.config_parameter": _Params(self.db),
            "plasticos.crm.external.ref": _Refs(self.db),
            "plasticos.crm.connection": _Connections(),
        }[model]

    def ref(self, xmlid, raise_if_not_found=True):
        assert xmlid == shell.CRM_CRON_XMLID
        return self.cron


class _Orchestrator:
    behaviour: dict[str, str] = {}
    calls: list[str] = []
    contexts: list[dict] = []

    def __init__(self, env):
        self.env = env
        self.error_rows = []
        self.last_lead_outcome = None
        _Orchestrator.contexts.append(dict(env.context))

    def _try_advisory_lock(self, key):
        if key in LOCKS:
            return False
        LOCKS.add(key)
        return True

    def _advisory_unlock(self, key):
        LOCKS.discard(key)

    def upsert_contact_external_id(self, connection, contact_id):
        _Orchestrator.calls.append(contact_id)
        behaviour = _Orchestrator.behaviour.get(contact_id, "created")
        if behaviour == "auth":
            raise RuntimeError("VanillaSoft auth failed HTTP 401")
        if behaviour == "boom":
            raise RuntimeError("VanillaSoft HTTP 500: contact jane@example.com phone 555-123-4567")
        if behaviour == "held":
            self.error_rows.append({"message": "ERP marker missing for the approved person"})
            self.last_lead_outcome = "failed"
            return
        if behaviour == "phantom":
            self.last_lead_outcome = "created"
            return
        model = "res.partner" if CENSUS.get(contact_id) == "YES" else "crm.lead"
        db = self.env.db
        self.last_lead_outcome = "unchanged" if model in db.models(contact_id) else "created"
        db.pending.append(("ref", contact_id, model))


@pytest.fixture
def harness(tmp_path, monkeypatch):
    LOCKS.clear()
    _Orchestrator.behaviour = {}
    _Orchestrator.calls = []
    _Orchestrator.contexts = []
    census_path = tmp_path / "census.csv"
    census_path.write_text(CENSUS_TEXT, encoding="utf-8")
    approved = types.ModuleType("approved_identity")
    approved.load_crosswalk_map = lambda env: dict(CROSSWALK)
    orchestrator = types.ModuleType("orchestrator")
    orchestrator.SyncOrchestrator = _Orchestrator
    orchestrator.advisory_lock_key = lambda connection_id: f"crm_sync:{connection_id}"
    connection = types.ModuleType("crm_connection")
    connection.ICP_ROOT = "plasticos_crm_sync.vs_root"
    connection.ICP_VS_KEY_PARAM = "plasticos_crm_sync.vs_key"
    addon = types.ModuleType("odoo.addons.plasticos_crm_sync")
    addon.__file__ = str(ROOT / "plasticos_crm_sync" / "__init__.py")
    services = types.ModuleType("odoo.addons.plasticos_crm_sync.services")
    services.historical_cohort = cohort
    odoo = types.ModuleType("odoo")
    addons = types.ModuleType("odoo.addons")
    odoo.addons = addons
    addons.plasticos_crm_sync = addon
    addon.services = services
    for name, module in {
        "odoo": odoo,
        "odoo.addons": addons,
        "odoo.addons.plasticos_crm_sync": addon,
        "odoo.addons.plasticos_crm_sync.services": services,
        "odoo.addons.plasticos_crm_sync.services.historical_cohort": cohort,
        "odoo.addons.plasticos_crm_sync.services.approved_identity": approved,
        "odoo.addons.plasticos_crm_sync.services.orchestrator": orchestrator,
        "odoo.addons.plasticos_crm_sync.models.crm_connection": connection,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(cohort, "release_identity", lambda path: (RELEASE, True))
    real_verify = cohort.verify_permit
    monkeypatch.setattr(
        cohort,
        "verify_permit",
        lambda permit, observed, *, fingerprint, now=None: real_verify(
            permit, observed, fingerprint=fingerprint, now=now or NOW
        ),
    )
    for name in (
        "ODOO_STAGE",
        "VANILLASOFT_PRODUCTION_PERMIT",
        "VANILLASOFT_HISTORY_MAX_IDS",
        "VANILLASOFT_HISTORY_FAILURE_BUDGET",
        "VANILLASOFT_REPORT_PATH",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("VANILLASOFT_HISTORY_CENSUS", str(census_path))
    monkeypatch.setenv("VANILLASOFT_HISTORY_CENSUS_SHA256", CENSUS_SHA)
    monkeypatch.setenv("VANILLASOFT_HISTORY_CHECKPOINT", str(tmp_path / "durable" / "ledger.jsonl"))
    db = _Db()
    db.committed["params"].update({connection.ICP_VS_KEY_PARAM: "k", connection.ICP_ROOT: "https://vanillasoft.net"})
    env = _Env(db)
    return types.SimpleNamespace(env=env, db=db, tmp=tmp_path, ledger=tmp_path / "durable" / "ledger.jsonl")


def _verdict(capsys) -> dict:
    out = capsys.readouterr().out
    line = next(line for line in out.splitlines() if line.startswith("HISTORY VERDICT "))
    return json.loads(line[len("HISTORY VERDICT ") :])


def test_full_history_run_dispositions_every_id_once_and_sends_nothing(harness, capsys):
    assert shell.history(harness.env) == 0
    verdict = _verdict(capsys)
    assert verdict["HISTORICAL_SNAPSHOT_COMPLETE"] and verdict["historical_data_complete"]
    assert verdict["classes"] == {
        cohort.IMPORTED: cohort.COHORT - 4,
        cohort.HELD: 0,
        cohort.DUPLICATE_SKIPPED: 4,
        cohort.GENUINE_FAILED: 0,
    }
    assert len(_Orchestrator.calls) == len(set(_Orchestrator.calls)) == cohort.COHORT - 4
    assert not set(_Orchestrator.calls) & cohort.OMITTED_DUPLICATE_VS_IDS
    assert all(
        ctx.get("tracking_disable") and ctx.get("mail_auto_subscribe_no_notify") for ctx in _Orchestrator.contexts
    )
    assert not LOCKS
    yes_refs = {e for e, m in harness.db.committed_refs() if m == "res.partner"}
    assert yes_refs == set(BOUND)
    assert Path(f"{harness.ledger}.report.json").is_file()


def test_bounded_sessions_resume_without_refetching(harness, monkeypatch, capsys):
    monkeypatch.setenv("VANILLASOFT_HISTORY_MAX_IDS", "100")
    assert shell.history(harness.env) == 0
    first = _verdict(capsys)
    assert first["stopped"] == "max_ids" and not first["HISTORICAL_SNAPSHOT_COMPLETE"]
    monkeypatch.delenv("VANILLASOFT_HISTORY_MAX_IDS")
    assert shell.history(harness.env) == 0
    assert _verdict(capsys)["HISTORICAL_SNAPSHOT_COMPLETE"]
    assert len(_Orchestrator.calls) == len(set(_Orchestrator.calls)) == cohort.COHORT - 4


def test_crash_after_commit_before_ledger_write_is_not_refetched(harness, monkeypatch, capsys):
    real_append = cohort.Ledger.append
    target = NO_IDS[0]

    def crash(self, record):
        if record["vanillasoft_contact_id"] == target:
            raise KeyboardInterrupt("session dropped")
        return real_append(self, record)

    monkeypatch.setattr(cohort.Ledger, "append", crash)
    with pytest.raises(KeyboardInterrupt):
        shell.history(harness.env)
    assert (target, "crm.lead") in harness.db.committed_refs()
    assert not LOCKS
    monkeypatch.setattr(cohort.Ledger, "append", real_append)
    assert shell.history(harness.env) == 0
    assert _verdict(capsys)["HISTORICAL_SNAPSHOT_COMPLETE"]
    assert _Orchestrator.calls.count(target) == 1


def test_crash_before_commit_is_refetched_once_and_duplicate_safe(harness, capsys):
    harness.db.fail_on_commit = 2  # commit 1 is the admission commit; 2 is the first ContactID
    assert shell.history(harness.env) == 0
    first = _verdict(capsys)
    assert first["classes"][cohort.GENUINE_FAILED] == 1
    assert shell.history(harness.env) == 0
    second = _verdict(capsys)
    assert second["historical_data_complete"]
    assert len(harness.db.committed_refs()) == cohort.COHORT - 4


def test_ledger_imported_row_without_a_durable_ref_is_fetched_again(harness, capsys):
    _Orchestrator.behaviour = {PENDING_IDS[0]: "phantom"}
    assert shell.history(harness.env) == 0
    verdict = _verdict(capsys)
    assert verdict["classes"][cohort.GENUINE_FAILED] == 1
    _Orchestrator.behaviour = {}
    assert shell.history(harness.env) == 0
    assert _verdict(capsys)["historical_data_complete"]
    assert _Orchestrator.calls.count(PENDING_IDS[0]) == 2


def test_rejected_credential_stops_without_a_disposition(harness, capsys):
    _Orchestrator.behaviour = {NO_IDS[0]: "auth"}
    assert shell.history(harness.env) == 2
    verdict = _verdict(capsys)
    assert verdict["stopped"] == "auth"
    ledger = cohort.Ledger(harness.ledger, census_sha256=CENSUS_SHA, database_uuid=DB_UUID)
    assert NO_IDS[0] not in ledger.rows
    assert NO_IDS[1] not in _Orchestrator.calls


def test_consecutive_failures_stop_on_the_budget(harness, monkeypatch, capsys):
    monkeypatch.setenv("VANILLASOFT_HISTORY_FAILURE_BUDGET", "3")
    _Orchestrator.behaviour = {i: "boom" for i in BOUND[:3]}
    assert shell.history(harness.env) == 1
    assert _verdict(capsys)["stopped"] == "budget"
    assert len(_Orchestrator.calls) == 3


def test_held_and_failed_reasons_are_kept_redacted_and_retried(harness, capsys):
    _Orchestrator.behaviour = {BOUND[0]: "held", NO_IDS[0]: "boom"}
    assert shell.history(harness.env) == 0
    verdict = _verdict(capsys)
    assert verdict["classes"][cohort.HELD] == 1 and verdict["classes"][cohort.GENUINE_FAILED] == 1
    assert verdict["dispositions_without_a_source_reason"] == 0
    text = harness.ledger.read_text(encoding="utf-8")
    assert "ERP marker" in text and "HTTP 500" in text
    assert "@example.com" not in text and "555-123-4567" not in text
    _Orchestrator.behaviour = {}
    assert shell.history(harness.env) == 0
    assert _verdict(capsys)["historical_data_complete"]


@pytest.mark.parametrize(
    ("mutate", "needle"),
    [
        (lambda h, mp: setattr(h.env.cron, "active", True), "cron is active"),
        (lambda h, mp: LOCKS.add("crm_sync:7"), "holds this connection's lock"),
        (lambda h, mp: h.db.committed["params"].pop(cohort.ERP_READY_PARAM), "ERP contacts are not imported"),
        (lambda h, mp: mp.delenv("VANILLASOFT_HISTORY_CHECKPOINT"), "CHECKPOINT is not set"),
        (lambda h, mp: mp.setenv("VANILLASOFT_HISTORY_CENSUS_SHA256", "0" * 64), "!= declared"),
        (lambda h, mp: h.db.committed["params"].pop("plasticos_crm_sync.vs_key"), "API key"),
    ],
)
def test_history_refusals_fetch_nothing(harness, monkeypatch, capsys, mutate, needle):
    mutate(harness, monkeypatch)
    assert shell.history(harness.env) == 2
    assert needle in capsys.readouterr().out
    assert _Orchestrator.calls == []


def test_overlapping_history_runs_are_fenced_by_the_owner_lock(harness, capsys):
    """A second run, or the cron's run_connection, cannot take the lock the history run holds."""
    seen: list[bool] = []
    real = _Orchestrator.upsert_contact_external_id

    def overlap(self, connection, contact_id):
        if not seen:
            seen.append(self._try_advisory_lock("crm_sync:7"))
        return real(self, connection, contact_id)

    _Orchestrator.upsert_contact_external_id = overlap
    try:
        assert shell.history(harness.env) == 0
    finally:
        _Orchestrator.upsert_contact_external_id = real
    assert seen == [False]


def test_a_ledger_from_another_database_is_refused(harness, capsys):
    cohort.Ledger(harness.ledger, census_sha256=CENSUS_SHA, database_uuid="other-db")
    assert shell.history(harness.env) == 2
    assert "another database" in capsys.readouterr().out


# ── production permit through the shell ─────────────────────────────────────


def _production(harness, monkeypatch, *, witness=True, **permit):
    harness.db.name = "plasticos-main-1"
    monkeypatch.setenv("ODOO_STAGE", "production")
    if witness:
        harness.db.committed["params"][cohort.ERP_PHASE2_WITNESS_PARAM] = json.dumps(
            {"phase": "erp_commercial", "database_uuid": DB_UUID, "final_status": "success"}
        )
    path = harness.tmp / "permit.json"
    path.write_text(json.dumps(_permit_doc(**permit)), encoding="utf-8")
    monkeypatch.setenv("VANILLASOFT_PRODUCTION_PERMIT", str(path))
    return path


def test_production_runs_once_under_a_consumed_permit(harness, monkeypatch, capsys):
    _production(harness, monkeypatch)
    monkeypatch.setenv("VANILLASOFT_HISTORY_MAX_IDS", "5")
    assert shell.history(harness.env) == 0
    assert cohort.consumed_key("crm-history-0001") in harness.db.committed["params"]
    capsys.readouterr()
    assert shell.history(harness.env) == 2
    assert "already consumed" in capsys.readouterr().out
    assert len(_Orchestrator.calls) == 5


def test_production_without_a_permit_is_refused(harness, monkeypatch, capsys):
    harness.db.name = "plasticos-main-1"
    monkeypatch.setenv("ODOO_STAGE", "production")
    assert shell.history(harness.env) == 2
    assert "must name a one-use permit" in capsys.readouterr().out
    assert _Orchestrator.calls == []


def test_production_named_database_off_the_production_stage_is_refused(harness, monkeypatch, capsys):
    _production(harness, monkeypatch)
    harness.db.name = "plasticos-prod-copy"
    monkeypatch.setenv("ODOO_STAGE", "staging")
    assert shell.history(harness.env) == 2
    assert "only valid on the production stage" in capsys.readouterr().out
    assert _Orchestrator.calls == []


def test_production_before_the_erp_commercial_phase_is_refused(harness, monkeypatch, capsys):
    _production(harness, monkeypatch, witness=False)
    assert shell.history(harness.env) == 2
    assert "no committed erp_commercial" in capsys.readouterr().out
    assert cohort.consumed_key("crm-history-0001") not in harness.db.committed["params"]


def test_production_permit_for_another_census_is_refused(harness, monkeypatch, capsys):
    _production(harness, monkeypatch, source_fingerprint="d" * 64)
    assert shell.history(harness.env) == 2
    assert "census" in capsys.readouterr().out
    assert _Orchestrator.calls == []


def test_full_import_mode_is_unchanged_without_the_census(monkeypatch, capsys):
    monkeypatch.delenv("VANILLASOFT_HISTORY_CENSUS", raising=False)
    monkeypatch.delenv("VANILLASOFT_CALL_FLOOR", raising=False)
    assert shell.main() == 2
    assert "VANILLASOFT_CALL_FLOOR" in capsys.readouterr().out


# ── command dispatch (2026-11-07): make import-vanillasoft is the history path ─

MAKEFILE = ROOT / "Makefile"
SHELL_DRIVER = ROOT / "plasticos_crm_sync" / "scripts" / "import_vanillasoft_shell.py"
HISTORY_VARS = (
    "VANILLASOFT_HISTORY_CENSUS",
    "VANILLASOFT_HISTORY_CENSUS_SHA256",
    "VANILLASOFT_HISTORY_CHECKPOINT",
    "VANILLASOFT_HISTORY_MAX_IDS",
    "VANILLASOFT_HISTORY_FAILURE_BUDGET",
    "VANILLASOFT_PRODUCTION_PERMIT",
)


def test_make_import_vanillasoft_forwards_the_history_inputs_and_pipes_the_history_driver():
    text = MAKEFILE.read_text(encoding="utf-8")
    recipe = text.split("\nimport-vanillasoft:\n", 1)[1].split("\n\n", 1)[0]
    assert recipe.count("< plasticos_crm_sync/scripts/import_vanillasoft_shell.py") == 1, "one production SSH runtime"
    for var in HISTORY_VARS:
        assert recipe.count(f"{var}=") == 1, f"{var} must reach the production SSH runtime"
    assert "$(vanillasoft_mode_guard)" in recipe
    guard = text.split("\nvanillasoft_mode_guard = ", 1)[1].split("\n\n", 1)[0]
    assert "cannot be combined" in guard, "a floor beside the census is refused"
    assert "nothing falls back to the rolling window" in guard
    assert "VANILLASOFT_PRODUCTION_CONFIRM=1 is required" in guard
    assert "does not accept a history census" in guard
    assert "does not accept VANILLASOFT_HISTORY_MAX_IDS" in guard
    assert 'mkdir -p "$$ledger_dir"' in guard
    assert "printf 'VANILLASOFT_API_KEY=%q\\n'" in recipe
    key_lines = [line for line in recipe.splitlines() if "VANILLASOFT_API_KEY" in line]
    assert key_lines == ["\t\tprintf 'VANILLASOFT_API_KEY=%q\\n' \"$${VANILLASOFT_API_KEY:-}\"; \\"]
    assert 'env["ir.module.module"]' in recipe
    assert "button_immediate_install" in recipe
    assert 'scp_opts="-O -o BatchMode=yes -o ConnectTimeout=25"' in recipe
    assert 'scp $$scp_opts "$$export_path"' in recipe
    for retired in ("run_import.py", "run_csv_import", "partner_import_service", "transaction_import"):
        assert retired not in recipe


def test_shell_main_dispatches_history_before_any_floor_and_fetches_through_the_orchestrator_seam():
    import ast  # noqa: PLC0415

    tree = ast.parse(SHELL_DRIVER.read_text(encoding="utf-8"))
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    first = functions["main"].body[0]
    assert isinstance(first, ast.If) and ast.unparse(first.test) == (
        "_env_flag(HISTORY_CENSUS_ENV) or _env_flag(CONTACT_EXPORT_ENV)"
    )
    assert ast.unparse(first.body[0]) == "return history(_odoo_env())"
    calls = {ast.unparse(n.func) for n in ast.walk(functions["_fetch_one"]) if isinstance(n, ast.Call)}
    assert "orchestrator.upsert_contact_external_id" in calls
    history_src = ast.unparse(functions["history"]) + ast.unparse(functions["_history_loop"])
    assert "run_full_import" not in history_src
    assert "SyncOrchestrator" in ast.unparse(functions["history"])
    assert "load_census" not in ast.unparse(functions["_repository_inputs"])
    assert "load_census" in ast.unparse(functions["_history_inputs"])


# ── repository cohort: the tracked export plus the packaged crosswalk ────────

EXPORT = ROOT / "plasticos_crm_sync" / "Vanillasoft-Scrap-Management.csv"
CROSSWALK_FILE = ROOT / "plasticos_crm_sync" / "data" / "approved_contact_crosswalk.csv"
_API_KEY_PARAM = "plasticos_crm_sync.vs_key"


def _contact_ids(path: Path, column: str) -> set[str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = csv.DictReader(handle)
        return {row[column].strip() for row in rows if (row.get(column) or "").strip()}


def _write_export(path: Path, contact_ids) -> None:
    path.write_text(
        "ContactID,Name\n" + "\n".join(f"{contact_id},site" for contact_id in contact_ids) + "\n",
        encoding="utf-8",
    )


def _partners_witness(status: str) -> str:
    return json.dumps({"phase": "erp_partners", "database_uuid": DB_UUID, "final_status": status})


def _repository(harness, monkeypatch, export_ids, crosswalk):
    monkeypatch.delenv("VANILLASOFT_HISTORY_CENSUS", raising=False)
    monkeypatch.delenv("VANILLASOFT_HISTORY_CENSUS_SHA256", raising=False)
    monkeypatch.delenv("VANILLASOFT_PRODUCTION_PERMIT", raising=False)
    monkeypatch.delenv("VANILLASOFT_PRODUCTION_CONFIRM", raising=False)
    monkeypatch.delenv("ODOO_STAGE", raising=False)
    export = harness.tmp / "export.csv"
    _write_export(export, export_ids)
    monkeypatch.setenv(shell.CONTACT_EXPORT_ENV, str(export))
    approved = sys.modules["odoo.addons.plasticos_crm_sync.services.approved_identity"]
    mapping = dict(crosswalk)
    approved.load_crosswalk_map = lambda env, bound=mapping: bound
    return export


@pytest.mark.skipif(not EXPORT.is_file(), reason="the customer VanillaSoft export stays on the operator machine")
def test_repository_cohort_is_the_export_plus_the_missing_crosswalk_ids():
    export_ids = _contact_ids(EXPORT, "ContactID")
    crosswalk_ids = _contact_ids(CROSSWALK_FILE, "vanillasoft_contact_id")
    omitted = set(cohort.OMITTED_DUPLICATE_VS_IDS)
    assert len(export_ids) == 4818
    assert len(crosswalk_ids) == 759
    missing = crosswalk_ids - export_ids
    assert len(missing) == 2
    assert omitted <= export_ids
    assert not (omitted & crosswalk_ids)
    census = shell.repository_census(export_ids, crosswalk_ids, omitted)
    assert len(census) == 4820
    yes = {contact_id for contact_id, decision in census.items() if decision == "YES"}
    assert yes == crosswalk_ids | omitted
    assert all(decision == "PENDING" for contact_id, decision in census.items() if contact_id not in yes)
    cohort.verify_identity(census, {contact_id: "person" for contact_id in crosswalk_ids}, omitted)
    steps = cohort.plan(census, omitted, (), {})
    skipped = {contact_id for contact_id, action in steps if action == cohort.SKIP_DUPLICATE}
    fetched = {contact_id for contact_id, action in steps if action == cohort.FETCH}
    assert skipped == omitted
    assert missing <= fetched
    assert not (omitted & fetched)


def test_repository_shell_refuses_a_failed_erp_partners_witness(harness, monkeypatch, capsys):
    omitted = sorted(cohort.OMITTED_DUPLICATE_VS_IDS)
    _repository(harness, monkeypatch, ["10", "11", *omitted], {"10": "person", "99": "person"})
    harness.db.committed["params"][shell.PARTNERS_WITNESS_PARAM] = _partners_witness("failed")
    harness.env.cron.active = True
    assert shell.history(harness.env) == 2
    assert "the erp_partners phase failed" in capsys.readouterr().out
    assert _Orchestrator.calls == []
    assert harness.env.cron.active is True


def test_repository_shell_accepts_a_partial_erp_partners_witness(harness, monkeypatch, capsys):
    omitted = sorted(cohort.OMITTED_DUPLICATE_VS_IDS)
    _repository(harness, monkeypatch, ["10", "11", *omitted], {"10": "person", "99": "person"})
    harness.db.committed["params"][shell.PARTNERS_WITNESS_PARAM] = _partners_witness("partial")
    del harness.db.committed["params"][_API_KEY_PARAM]
    secret = "vs-test-key-not-for-logs"
    monkeypatch.setenv("VANILLASOFT_API_KEY", secret)
    harness.env.cron.active = True
    assert shell.history(harness.env) == 0
    out = capsys.readouterr().out
    assert secret not in out
    assert "crm_history.admitted" in out
    assert harness.db.committed["params"][_API_KEY_PARAM] == secret
    assert harness.env.cron.active is False
    assert set(_Orchestrator.calls) == {"10", "11", "99"}
    assert not (set(_Orchestrator.calls) & cohort.OMITTED_DUPLICATE_VS_IDS)


def test_repository_confirm_without_a_provable_release_does_not_mint_a_permit(harness, monkeypatch, capsys):
    omitted = sorted(cohort.OMITTED_DUPLICATE_VS_IDS)
    _repository(harness, monkeypatch, ["10", "11", *omitted], {"10": "person", "99": "person"})
    harness.db.committed["params"][shell.PARTNERS_WITNESS_PARAM] = _partners_witness("partial")
    monkeypatch.setenv("ODOO_STAGE", "production")
    monkeypatch.setenv("VANILLASOFT_PRODUCTION_CONFIRM", "1")
    monkeypatch.setattr(cohort, "release_identity", lambda path: (None, False))
    assert shell.history(harness.env) == 2
    out = capsys.readouterr().out
    assert "production confirm does not mint a matching permit" in out
    assert "crm_history.admitted" not in out
    assert _Orchestrator.calls == []
    assert not list(harness.tmp.glob("durable/crmhist-*.json"))


def test_repository_confirm_mints_and_consumes_a_permit_for_the_generated_census(harness, monkeypatch, capsys):
    omitted = sorted(cohort.OMITTED_DUPLICATE_VS_IDS)
    export_ids = {"10", "11", *omitted}
    crosswalk = {"10": "person", "99": "person"}
    _repository(harness, monkeypatch, sorted(export_ids), crosswalk)
    harness.db.committed["params"][shell.PARTNERS_WITNESS_PARAM] = _partners_witness("partial")
    monkeypatch.setenv("ODOO_STAGE", "production")
    monkeypatch.setenv("VANILLASOFT_PRODUCTION_CONFIRM", "1")
    monkeypatch.setattr(cohort, "verify_permit", _REAL_VERIFY_PERMIT)
    assert shell.history(harness.env) == 0
    out = capsys.readouterr().out
    assert "crm_history.admitted" in out
    census = shell.repository_census(export_ids, set(crosswalk), set(cohort.OMITTED_DUPLICATE_VS_IDS))
    fingerprint = cohort.sha256_text(shell.census_text(census))
    permit_path = Path(os.environ["VANILLASOFT_PRODUCTION_PERMIT"])
    permit = json.loads(permit_path.read_text(encoding="utf-8"))
    assert permit["source_fingerprint"] == fingerprint
    assert permit["phase"] == "crm_history"
    assert permit["database_uuid"] == DB_UUID
    assert harness.db.committed["params"][cohort.consumed_key(permit["permit_id"])]
    assert not (set(_Orchestrator.calls) & cohort.OMITTED_DUPLICATE_VS_IDS)
