"""Rehearsal kit proof checks (common.py): every fail-closed branch.

Pure-python tier. Fixtures are built here; no Docker, SQL, HTTP or secret.
Finding ids (RK-03 … RK-08) refer to the 2026-11-06 kit hardening contract.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

KIT = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("rehearsal_kit_common", KIT / "common.py")
lib = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(lib)

RUN_STARTED = "2026-11-06T20:00:00Z"


def _summary(source: str, **overrides) -> dict:
    base = {
        "source": source,
        "start_time": "2026-11-06T20:01:00Z",
        "completion_time": "2026-11-06T20:05:00Z",
        "records_seen": 10,
        "records_valid": 10,
        "records_rejected": 0,
        "records_created": 8,
        "records_updated": 0,
        "records_unchanged": 2,
        "duplicates": 0,
        "errors": [],
        "final_status": "success",
    }
    base.update(overrides)
    return base


def _write(path: Path, value) -> Path:
    path.write_text(value if isinstance(value, str) else json.dumps(value), encoding="utf-8")
    return path


# ── RK-03: counts never default to zero ─────────────────────────────────────


@pytest.mark.parametrize("text, expected", [("0\n", 0), ("1\n", 1), ("  42  \n\n", 42)])
def test_parse_count_accepts_one_integer(text, expected):
    assert lib.parse_count(text) == expected


@pytest.mark.parametrize("text", ["", "\n", "abc", "-1", "1\n2\n", "ERROR: relation does not exist", "1.5"])
def test_parse_count_refuses_anything_else(text):
    with pytest.raises(lib.ProofError):
        lib.parse_count(text)


# ── RK-05: ERP slice ────────────────────────────────────────────────────────

LAYERS = {"counterparties": 3, "addresses": 2, "contacts": 4}
CENSUS = {"payload_kind": "database", "source_origin": "erp-host/erp_db", "census": {}, "unresolved": []}


def _erp(tmp_path, summary=None, census=None, layers=LAYERS, import_exit=0):
    s = tmp_path / "05-erp-summary.json"
    c = tmp_path / "05-erp-summary-census.json"
    if summary is not None:
        _write(s, summary)
    if census is not None:
        _write(c, census)
    return lib.check_erp(s, c, import_exit=import_exit, layers=layers, run_started=RUN_STARTED)


def test_erp_complete_database_run_passes(tmp_path):
    result = _erp(tmp_path, _summary("erp"), CENSUS)
    assert result["state"] == "PASS"
    assert result["facts"]["layers"] == LAYERS


def test_erp_partial_with_attributed_unresolved_rows_passes_with_disposition(tmp_path):
    census = {**CENSUS, "unresolved": [{"table": "Address", "kind": "parent_not_imported", "key": "7", "detail": "x"}]}
    summary = _summary(
        "erp",
        records_rejected=1,
        records_unchanged=1,
        final_status="partial",
        errors=[{"record_ref": "7", "message": "Address parent_not_imported: x"}],
    )
    result = _erp(tmp_path, summary, census)
    assert result["state"] == "PASS"
    assert result["facts"]["disposition"] == "partial-source-explained"


@pytest.mark.parametrize(
    "summary, census, layers, import_exit, reason",
    [
        (None, CENSUS, LAYERS, 0, "erp-summary-unreadable"),
        ("{not json", CENSUS, LAYERS, 0, "erp-summary-unreadable"),
        (_summary("erp"), None, LAYERS, 0, "erp-census-unreadable"),
        (_summary("erp"), "[]", LAYERS, 0, "erp-census-unreadable"),
        (_summary("erp"), {**CENSUS, "payload_kind": "grid"}, LAYERS, 0, "erp-source-not-database"),
        (_summary("erp"), {**CENSUS, "payload_kind": "statements"}, LAYERS, 0, "erp-source-not-database"),
        (
            _summary("erp"),
            {k: v for k, v in CENSUS.items() if k != "payload_kind"},
            LAYERS,
            0,
            "erp-source-not-database",
        ),
        (_summary("erp"), {**CENSUS, "source_origin": ""}, LAYERS, 0, "erp-source-unattributed"),
        (_summary("vanillasoft"), CENSUS, LAYERS, 0, "erp-summary-wrong-source"),
        (_summary("erp", records_seen=11), CENSUS, LAYERS, 0, "erp-summary-census-mismatch"),
        (_summary("erp", duplicates=1), CENSUS, LAYERS, 0, "erp-summary-duplicates"),
        (
            _summary("erp", records_seen=0, records_valid=0, records_created=0, records_unchanged=0),
            CENSUS,
            LAYERS,
            0,
            "erp-summary-empty",
        ),
        (_summary("erp", final_status="failed"), CENSUS, LAYERS, 0, "erp-final-status-failed"),
        (_summary("erp", final_status="partial"), CENSUS, LAYERS, 0, "erp-unexpected-partial"),
        (_summary("erp", start_time="2026-11-01T00:00:00Z"), CENSUS, LAYERS, 0, "erp-summary-stale"),
        (_summary("erp", records_seen="10"), CENSUS, LAYERS, 0, "erp-summary-schema-invalid"),
        (_summary("erp"), CENSUS, {**LAYERS, "addresses": 0}, 0, "erp-layer-missing-addresses"),
        (_summary("erp"), CENSUS, {"counterparties": 1, "contacts": 1}, 0, "erp-layer-census-invalid"),
        (_summary("erp"), CENSUS, None, 0, "erp-layer-census-unavailable"),
        (_summary("erp"), CENSUS, LAYERS, 1, "erp-import-exit"),
    ],
)
def test_erp_fails_closed(tmp_path, summary, census, layers, import_exit, reason):
    result = _erp(tmp_path, summary, census, layers, import_exit)
    assert result["state"] == "FAIL"
    assert reason in result["facts"].get("failure_codes", [result["reason"]])


def test_erp_sql_login_failure_is_a_fail_not_a_pass(tmp_path):
    # SQL Server 18456 surfaces as a nonzero import with no summary.
    result = _erp(tmp_path, None, None, None, import_exit=2)
    assert (result["state"], result["reason"]) == ("FAIL", "erp-import-exit")


# ── RK-06: VanillaSoft ──────────────────────────────────────────────────────


def _vs(tmp_path, summary=None, import_exit=0, contacts=3):
    path = tmp_path / "06-crm-result.json"
    if summary is not None:
        _write(path, summary)
    return lib.check_vanillasoft(path, import_exit=import_exit, contacts_landed=contacts, run_started=RUN_STARTED)


def test_vanillasoft_success_with_landed_contacts_passes(tmp_path):
    assert _vs(tmp_path, _summary("vanillasoft"))["state"] == "PASS"


@pytest.mark.parametrize(
    "summary, import_exit, contacts, state, reason",
    [
        (None, 0, 3, "FAIL", "vanillasoft-summary-unreadable"),
        (_summary("vanillasoft", final_status="failed"), 0, 3, "FAIL", "vanillasoft-business-acceptance"),
        (
            _summary(
                "vanillasoft",
                final_status="partial",
                records_rejected=1,
                records_unchanged=1,
                errors=[{"record_ref": "c1", "message": "identity conflict"}],
            ),
            0,
            3,
            "FAIL",
            "vanillasoft-business-acceptance",
        ),
        (
            _summary(
                "vanillasoft",
                final_status="success",
                errors=[{"record_ref": "c1", "message": "material", "category": "required_mapping"}],
            ),
            0,
            3,
            "FAIL",
            "vanillasoft-business-acceptance",
        ),
        (
            _summary(
                "vanillasoft",
                final_status="partial",
                errors=[{"record_ref": "scope", "message": "watermark clamped", "informational": True}],
            ),
            0,
            3,
            "BLOCKED",
            "vanillasoft-scope-notice-partial",
        ),
        ({"source": "vanillasoft"}, 0, 3, "FAIL", "vanillasoft-summary-schema-invalid"),
        (_summary("erp"), 0, 3, "FAIL", "vanillasoft-summary-wrong-source"),
        (_summary("vanillasoft", duplicates=2), 0, 3, "FAIL", "vanillasoft-summary-duplicates"),
        (
            _summary("vanillasoft", records_seen=0, records_valid=0, records_created=0, records_unchanged=0),
            0,
            0,
            "BLOCKED",
            "vanillasoft-empty-window",
        ),
        (_summary("vanillasoft"), 0, 0, "BLOCKED", "vanillasoft-empty-window"),
        (_summary("vanillasoft"), 0, None, "FAIL", "vanillasoft-contact-census-unavailable"),
        (_summary("vanillasoft"), 2, 3, "FAIL", "vanillasoft-preflight-failed"),
        (_summary("vanillasoft"), 1, 3, "FAIL", "vanillasoft-import-exit"),
    ],
)
def test_vanillasoft_never_passes_on_exit_code_alone(tmp_path, summary, import_exit, contacts, state, reason):
    result = _vs(tmp_path, summary, import_exit, contacts)
    assert (result["state"], result["reason"]) == (state, reason)


# ── RK-04: web lead persistence and idempotency ─────────────────────────────

RECEIPT = {"status": "ok", "decision": "hot", "state": "intake_created", "intake_id": 11, "web_lead_id": 5}
BEFORE = {"web_leads": 2, "intakes": 4, "crm_leads": 7, "partners": 50}
AFTER = {"web_leads": 3, "intakes": 5, "crm_leads": 8, "partners": 50}
ROW = {
    "web_lead": {"id": 5, "lead_id": "cognito-1", "state": "intake_created", "intake_id": 11, "crm_lead_id": 90},
    "same_lead_id_rows": 1,
    "intake_exists": 1,
    "crm_for_intake": 1,
    "crm": {
        "id": 90,
        "type": "opportunity",
        "user_id": None,
        "partner_id": None,
        "active": True,
        "source_intake_id": 11,
        "is_won": False,
    },
}


def _wl(receipt=RECEIPT, replay=RECEIPT, before=BEFORE, after_first=AFTER, after_replay=AFTER, row=ROW):
    return [
        code for code, _text in lib.check_weblead_persistence(receipt, replay, before, after_first, after_replay, row)
    ]


def test_weblead_full_chain_passes():
    assert _wl() == []


def _row(**changes):
    row = json.loads(json.dumps(ROW))
    for dotted, value in changes.items():
        target = row
        *path, key = dotted.split("__")
        for part in path:
            target = target[part]
        target[key] = value
    return row


@pytest.mark.parametrize(
    "kwargs, code",
    [
        ({"row": _row(crm=None, crm_for_intake=0, web_lead__crm_lead_id=None)}, "weblead-crm-link-missing"),
        ({"after_first": {**AFTER, "crm_leads": 7}}, "weblead-delta-crm_leads"),
        ({"row": _row(crm_for_intake=2)}, "weblead-crm-cardinality"),
        ({"row": _row(same_lead_id_rows=2)}, "weblead-duplicate-rows"),
        ({"row": _row(crm__source_intake_id=12)}, "weblead-crm-intake"),
        ({"row": _row(web_lead__intake_id=12)}, "weblead-row-intake"),
        ({"row": _row(crm__id=91)}, "weblead-crm-identity"),
        ({"row": _row(web_lead__state="error")}, "weblead-row-state"),
        ({"receipt": {**RECEIPT, "state": "error"}}, "weblead-state"),
        ({"receipt": {**RECEIPT, "decision": "HOT"}}, "weblead-decision"),
        ({"after_replay": {**AFTER, "web_leads": 4}}, "weblead-replay-web_leads"),
        ({"after_replay": {**AFTER, "crm_leads": 9}}, "weblead-replay-crm_leads"),
        ({"replay": {**RECEIPT, "web_lead_id": 6}}, "weblead-replay-identity"),
        ({"after_first": {**AFTER, "partners": 51}}, "weblead-delta-partners"),
        ({"row": _row(crm__partner_id=3)}, "weblead-crm-partner"),
        ({"row": _row(web_lead__partner_id=3)}, "weblead-partner-created"),
        ({"row": _row(crm__user_id=2)}, "weblead-crm-assigned"),
        ({"row": _row(crm__is_won=True)}, "weblead-crm-won"),
        ({"row": _row(crm__type="lead")}, "weblead-crm-type"),
        ({"row": {"web_lead": None}}, "weblead-row-missing"),
        ({"before": {"web_leads": 1}}, "weblead-snapshot-invalid"),
    ],
)
def test_weblead_superficial_success_cannot_pass(kwargs, code):
    assert code in _wl(**kwargs)


# ── RK-07: evidence never keeps a credential value ──────────────────────────


def test_scan_secrets_redacts_named_values_without_printing(tmp_path, monkeypatch, capsys):
    secret = "fake-rehearsal-secret-0001"
    monkeypatch.setenv("REHEARSAL_TEST_SECRET", secret)
    _write(tmp_path / "log.txt", f"line\nAuthorization: Bearer {secret}\n")
    _write(tmp_path / "clean.txt", "nothing here\n")
    hits = lib.scan_secrets(tmp_path, ["REHEARSAL_TEST_SECRET", "UNSET_NAME"])
    assert hits == ["log.txt"]
    assert secret not in (tmp_path / "log.txt").read_text()
    assert lib.REDACTED in (tmp_path / "log.txt").read_text()
    assert secret not in capsys.readouterr().out


def test_scan_secrets_ignores_short_or_empty_values(tmp_path, monkeypatch):
    monkeypatch.setenv("REHEARSAL_TEST_SECRET", "")
    _write(tmp_path / "a.txt", "x")
    assert lib.scan_secrets(tmp_path, ["REHEARSAL_TEST_SECRET"]) == []


def test_receipt_detail_is_redacted_and_private(tmp_path):
    lib.write_gate(tmp_path, 5, "FAIL", "x", "Authorization: Bearer abcdef123456 password=hunter22")
    path = lib.receipt_path(tmp_path, 5)
    text = path.read_text()
    assert "abcdef123456" not in text and "hunter22" not in text
    assert (path.stat().st_mode & 0o777) == 0o600


def test_receipt_is_written_once(tmp_path):
    lib.write_gate(tmp_path, 3, "PASS", "ok")
    with pytest.raises(lib.ProofError):
        lib.write_gate(tmp_path, 3, "FAIL", "late overwrite")


# ── RK-08: verdict completeness ─────────────────────────────────────────────

BLOCKERS = frozenset({"vanillasoft-key-unbound"})


def _gates(**states):
    out = []
    for gate, name in lib.GATES:
        state, reason = states.get(f"g{gate}", ("PASS", "ok"))
        out.append({"gate": gate, "name": name, "state": state, "reason": reason})
    return out


@pytest.mark.parametrize(
    "states, run_failures, verdict",
    [
        ({}, [], "ready"),
        ({}, ["production-ref-drifted"], "failed"),
        ({"g7": ("BLOCKED", "vanillasoft-key-unbound")}, [], "blocked"),
        ({"g7": ("BLOCKED", "undocumented")}, [], "failed"),
        ({"g7": ("SKIPPED", "gate6-not-passed")}, [], "failed"),
        ({"g6": ("FAIL", "erp-import-exit"), "g7": ("SKIPPED", "gate6-not-passed")}, [], "failed"),
        ({"g5": ("UNKNOWN", "no-receipt")}, [], "failed"),
        ({"g1": ("FAIL", "head-not-origin-staging")}, [], "failed"),
    ],
)
def test_compute_verdict(states, run_failures, verdict):
    assert lib.compute_verdict(_gates(**states), run_failures, BLOCKERS)[0] == verdict


def test_finalize_without_receipts_is_never_ready(tmp_path):
    record = lib.finalize(tmp_path, {"run_ts": "t"}, [])
    assert record["verdict"] == "failed"
    assert all(g["state"] == "UNKNOWN" for g in record["gates"])
    text = (tmp_path / "verdict.txt").read_text()
    assert "verdict=failed" in text


def test_finalize_all_pass_is_ready(tmp_path):
    for gate, _name in lib.GATES:
        lib.write_gate(tmp_path, gate, "PASS", "ok")
    record = lib.finalize(tmp_path, {"run_ts": "t", "staging_sha": "a" * 40}, [])
    assert record["verdict"] == "ready"
    assert json.loads((tmp_path / "verdict.json").read_text())["verdict"] == "ready"


def test_blockers_file_names_the_verdict_blockers():
    ids = lib.verdict_blocker_ids()
    assert {"vanillasoft-key-unbound", "erp-proof-files-missing", "vanillasoft-empty-window"} <= ids
    entries = lib.load_blockers()
    # Design-scope notes never turn a failure into a block.
    assert entries["web-lead-no-partner-creation"].get("verdict_effect") != "blocked"


def test_blockers_record_pr_385_as_merged():
    entry = lib.load_blockers()["web-lead-crm-lead-http-context"]
    assert entry.get("status") == "fix-merged-not-proven"
    assert entry.get("verdict_effect") != "blocked"


def test_link_latest_is_an_atomic_relative_symlink(tmp_path):
    run = tmp_path / "2026-11-06_000000"
    run.mkdir()
    (tmp_path / "latest").symlink_to("old")
    lib.link_latest(tmp_path, run)
    assert os.readlink(tmp_path / "latest") == run.name
