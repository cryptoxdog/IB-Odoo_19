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
# What the real driver prints on an applied direct-SQL run (import_erp_shell.py).
ERP_COUNTS = (
    "{'counterparties': {'created': 3, 'updated': 0, 'skipped': 0, 'rejected': 0}, "
    "'transactions': {'created': 1, 'updated': 0, 'skipped': 9, 'rejected': 0}, "
    "'transaction_lines': {'created': 2, 'updated': 0, 'skipped': 18, 'rejected': 0}}"
)


def _erp_log(scope: str = "", counts: str = ERP_COUNTS) -> str:
    return (
        "ERP source: direct database read (erp-host/erp_db)\nres.partner before import: 3\n"
        f"2026-11-06 20:02:00,000 7 INFO odoo_test_cutover odoo.addons.plasticos_partner_import.models.erp_import_service: "
        f"ERP import finished{scope}: {counts}\nDATA VERDICT {{}}\n"
    )


ERP_LOG = _erp_log()
# The clone's native-document snapshot (fidelity_run.py --print-odoo-sql): one worksheet, both sides.
SNAPSHOT = {
    "evidence": "complete",
    "partners": [],
    "sale_orders": [{"xmlid": "legacy_erp_so_1", "name": "1", "origin": "100"}],
    "purchase_orders": [{"xmlid": "legacy_erp_po_2", "name": "2", "origin": "100"}],
    "sale_lines": [{"xmlid": "legacy_erp_sol_900"}],
    "purchase_lines": [{"xmlid": "legacy_erp_pol_900"}],
    "invoices": [{"xmlid": "legacy_erp_outinv_100", "invoice_origin": "100"}],
    "bills": [{"xmlid": "legacy_erp_ininv_5", "invoice_origin": "100"}],
    "ledger_moves": [],
}


def _fidelity_pass() -> dict:
    return {
        "schema": "l9.plasticos.rehearsal.fidelity.v1",
        "evidence": "complete",
        "status": "PASS",
        "failed": 0,
        "compared": 1,
        "rows": [
            {
                "source_id": "1",
                "source_table": "CounterParty",
                "source_field": "CompanyNm",
                "source_value": "Acme",
                "target_model": "res.partner",
                "target_field": "name",
                "expected": "Acme",
                "actual": "Acme",
                "tolerance": None,
                "result": "PASS",
                "classification": "mapped",
            }
        ],
    }


def _erp(
    tmp_path, summary=None, census=None, layers=LAYERS, import_exit=0, fidelity="pass", log=ERP_LOG, snapshot=SNAPSHOT
):
    s = tmp_path / "05-erp-summary.json"
    c = tmp_path / "05-erp-summary-census.json"
    if summary is not None:
        _write(s, summary)
    if census is not None:
        _write(c, census)
    report = None if fidelity is None else fidelity if isinstance(fidelity, dict) else _fidelity_pass()
    return lib.check_erp(
        s,
        c,
        import_exit=import_exit,
        layers=layers,
        run_started=RUN_STARTED,
        log_text=log,
        database="odoo_test_cutover",
        limit="full",
        release_sha="a" * 40,
        fidelity=report,
        snapshot=snapshot,
    )


def test_erp_complete_database_run_passes(tmp_path):
    result = _erp(tmp_path, _summary("erp"), CENSUS)
    assert result["state"] == "PASS"
    assert result["facts"]["layers"] == LAYERS
    path = result["facts"]["execution_path"]
    assert path["make_target"] == "import-erp"
    assert path["driver"] == "plasticos_partner_import/scripts/import_erp_shell.py"
    assert "plasticos.erp.import" in path["dispatcher"]
    assert "legacy_erp_import_service.py" in path["commercial_extension"]
    assert (path["database"], path["limit"], path["release_sha"]) == ("odoo_test_cutover", "full", "a" * 40)


@pytest.mark.parametrize(
    "log, reason",
    [
        (None, "erp-log-unreadable"),
        ("res.partner before import: 3\nDATA VERDICT {}\n", "erp-dispatcher-unobserved"),
        ("ERP source: direct database read (x)\n", "erp-verdict-unobserved"),
        ("", "erp-dispatcher-unobserved"),
    ],
)
def test_erp_requires_the_drivers_own_trace_in_the_log(tmp_path, log, reason):
    result = _erp(tmp_path, _summary("erp"), CENSUS, log=log)
    assert result["state"] == "FAIL"
    assert reason in result["facts"]["failure_codes"]


def _compact_census(**overrides) -> dict:
    census = {
        "schema": "l9.plasticos.rehearsal.census.v1",
        "payload_kind": "database",
        "origin_sha256": "ab" * 32,
        "census": {},
        "anomaly_counts": {},
        "anomaly_sample": {},
        "anomaly_sample_cap": 5,
        "unresolved_count": 0,
        "attributed_count": 0,
        "unattributed_count": 0,
        "attributed_digest": "cd" * 32,
    }
    census.update(overrides)
    return census


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


def test_erp_native_documents_are_accounted_from_the_importers_own_counts(tmp_path):
    result = _erp(tmp_path, _summary("erp"), CENSUS)
    assert result["state"] == "PASS", result
    native = result["facts"]["native_documents"]
    assert (native["realized_transactions"], native["realized_lines"], native["scope"]) == (1, 2, "")
    assert native["clone"]["worksheets"] == 1 and native["clone"]["sale_lines"] == 1


def _snapshot(**over) -> dict:
    return {**SNAPSHOT, **over}


@pytest.mark.parametrize(
    "kwargs, reason",
    [
        ({"log": _erp_log().replace("ERP import finished", "ERP import ended")}, "erp-run-accounting-unobserved"),
        ({"log": _erp_log(counts="{not a dict")}, "erp-run-accounting-unobserved"),
        ({"log": _erp_log(counts="{'counterparties': {'created': 1, 'updated': 0}}")}, "erp-run-accounting-unobserved"),
        ({"log": _erp_log(scope=" (partners only)")}, "erp-run-not-full"),
        ({"log": _erp_log(scope=" (counterparties)")}, "erp-run-not-full"),
        ({"snapshot": None}, "erp-native-snapshot-unreadable"),
        ({"snapshot": {"evidence": "missing"}}, "erp-native-snapshot-unreadable"),
        ({"log": _erp_log(counts=ERP_COUNTS.replace("'created': 2", "'created': 0"))}, "erp-native-documents-none"),
        ({"snapshot": _snapshot(sale_orders=[], purchase_orders=[])}, "erp-native-class-missing"),
        ({"snapshot": _snapshot(sale_lines=[], purchase_lines=[])}, "erp-native-class-missing"),
        ({"snapshot": _snapshot(purchase_lines=[])}, "erp-native-documents-missing"),
        ({"log": _erp_log(counts=ERP_COUNTS.replace("'created': 1", "'created': 3"))}, "erp-native-documents-missing"),
        (
            {
                "snapshot": _snapshot(
                    sale_orders=[], purchase_orders=[], sale_lines=[], purchase_lines=[], invoices=[], bills=[]
                )
            },
            "erp-native-class-missing",
        ),
    ],
)
def test_erp_silently_omitted_native_documents_fail_the_gate(tmp_path, kwargs, reason):
    """Codex finding on PR #401: a document class the importer never wrote never entered the comparison."""
    result = _erp(tmp_path, _summary("erp"), CENSUS, **kwargs)
    assert result["state"] == "FAIL"
    assert reason in result["facts"]["failure_codes"], result["facts"]["failure_codes"]


def test_compact_census_counts_replace_the_unresolved_list(tmp_path):
    census = _compact_census(unresolved_count=2, attributed_count=1, unattributed_count=1)
    summary = _summary("erp", final_status="partial", records_rejected=2, records_unchanged=0)
    result = _erp(tmp_path, summary, census)
    assert result["state"] == "FAIL"
    assert "erp-unexpected-partial" in result["facts"]["failure_codes"]


def test_compact_census_without_an_origin_digest_is_unattributed(tmp_path):
    result = _erp(tmp_path, _summary("erp"), _compact_census(origin_sha256=""))
    assert result["reason"] == "erp-source-unattributed"


def test_compact_grid_census_is_not_a_database_source(tmp_path):
    result = _erp(tmp_path, _summary("erp"), _compact_census(payload_kind="grid"))
    assert result["reason"] == "erp-source-not-database"


def test_comparison_digest_does_not_cover_a_missing_identity(tmp_path):
    report = _fidelity_pass()
    report["rows_retained"] = "failures"
    report["rows"] = []
    report["failed"] = 0
    report["rejected"] = 0
    report["unmapped"] = 0
    report["coverage"] = [{"source_field": "CompanyNm"}]
    report["source_fingerprint"] = "fp"
    report["comparison_digest"] = "digest"
    report["coverage_ledger"] = {
        "expected_count": 2,
        "expected_digest": "",
        "partition": {"compared": 1, "rejected": 0, "excluded": 0},
    }
    result = _erp(tmp_path, _summary("erp"), CENSUS, fidelity=report)
    assert result["reason"] == "erp-source-coverage"


def test_compact_failed_count_must_match_the_stored_rows(tmp_path):
    report = _fidelity_pass()
    report["rows_retained"] = "failures"
    report["rows"] = []
    report["failed"] = 1
    report["coverage"] = [{"source_field": "CompanyNm"}]
    report["source_fingerprint"] = "fp"
    result = _erp(tmp_path, _summary("erp"), CENSUS, fidelity=report)
    assert result["reason"] == "erp-fidelity-unproven"


def test_compact_identity_ledger_accounts_for_the_realized_documents(tmp_path):
    result = _erp(tmp_path, _summary("erp"), CENSUS, snapshot=lib.identity_ledger(SNAPSHOT))
    assert result["state"] == "PASS", result


def test_missing_identity_ledger_is_unreadable(tmp_path):
    result = _erp(tmp_path, _summary("erp"), CENSUS, snapshot=None)
    assert result["reason"] == "erp-native-snapshot-unreadable"


def test_duplicate_document_identity_fails(tmp_path):
    ledger = lib.identity_ledger(SNAPSHOT)
    ledger["duplicate_count"] = 1
    result = _erp(tmp_path, _summary("erp"), CENSUS, snapshot=ledger)
    assert "erp-native-identity-duplicate" in result["facts"]["failure_codes"]


def test_interrupted_publish_leaves_the_evidence_directory_without_the_full_dumps(tmp_path, monkeypatch):
    evidence = tmp_path / "evidence"
    staging = tmp_path / "isolated"
    evidence.mkdir()
    staging.mkdir()

    def interrupted(*_args, **_kwargs):
        raise OSError("interrupted before rename")

    monkeypatch.setattr(lib.os, "replace", interrupted)
    with pytest.raises(OSError, match="interrupted"):
        lib.publish_json(evidence / "05-erp-fidelity.json", {"rows": [{"result": "FAIL"}]}, staging_dir=staging)
    assert not (evidence / "05-erp-fidelity.json").exists()
    assert not (evidence / "05-erp-fidelity-odoo.json").exists()
    assert not (evidence / "05-erp-summary-census.json").exists()
    assert not any(path.name.endswith("census.json") and "anomaly" in path.read_text() for path in evidence.iterdir())


def test_published_census_omits_the_full_arrays(tmp_path):
    full = {
        "payload_kind": "database",
        "source_origin": "erp-host/erp_db",
        "census": {"payables": 1},
        "anomalies": [{"table": "BuySell", "key": "1", "detail": "purchase link: blank line key"}],
        "unresolved": [{"table": "Address", "kind": "parent_not_imported", "key": "7", "detail": "x"}],
    }
    receipt = lib.compact_census(full)
    assert receipt["origin_sha256"]
    assert "source_origin" not in receipt
    assert "anomalies" not in receipt and "unresolved" not in receipt
    assert receipt["unresolved_count"] == 1
    assert receipt["attributed_count"] == 1
    assert receipt["unattributed_count"] == 0
    assert receipt["anomaly_counts"]["purchase link"] == 1
    lib.publish_json(tmp_path / "evidence" / "05-erp-summary-census.json", receipt, staging_dir=tmp_path / "staging")
    published = json.loads((tmp_path / "evidence" / "05-erp-summary-census.json").read_text(encoding="utf-8"))
    assert published == receipt


def test_erp_without_a_fidelity_report_is_unproven(tmp_path):
    result = _erp(tmp_path, _summary("erp"), CENSUS, fidelity=None)
    assert result["state"] == "FAIL"
    assert result["reason"] == "erp-fidelity-unproven"


def test_erp_fidelity_discrepancy_fails_a_balanced_import(tmp_path):
    report = _fidelity_pass()
    report["rows"][0]["actual"] = "Other"
    report["rows"][0]["result"] = "FAIL"
    report["rows"][0]["classification"] = "defect"
    report["status"] = "FAIL"
    report["failed"] = 1
    result = _erp(tmp_path, _summary("erp"), CENSUS, fidelity=report)
    assert result["state"] == "FAIL"
    assert result["reason"] == "erp-fidelity-discrepancy"


def test_erp_rejected_rows_do_not_pass_without_a_mapped_comparison(tmp_path):
    report = _fidelity_pass()
    report["rows"] = [
        {
            "source_id": "9",
            "source_table": "Address",
            "source_field": "parent_not_imported",
            "source_value": "missing parent",
            "target_model": "",
            "target_field": "",
            "expected": None,
            "actual": None,
            "tolerance": None,
            "result": "PASS",
            "classification": "rejected",
        }
    ]
    report["compared"] = 0
    result = _erp(tmp_path, _summary("erp"), CENSUS, fidelity=report)
    assert result["reason"] == "erp-fidelity-unproven"


# ── RK-06: VanillaSoft historical cohort (bounded) ──────────────────────────

cohort = lib.crm_cohort()
SHA = "f" * 64
DB = "odoo_test_cutover"
DB_UUID = "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0"
ADMITTED = json.dumps({"event": "crm_history.admitted", "database": DB, "permit": False, "census_sha256": SHA})


def _report(**over) -> dict:
    classes = {cohort.IMPORTED: 3, cohort.HELD: 1, cohort.DUPLICATE_SKIPPED: 1, cohort.GENUINE_FAILED: 0}
    classes.update(over.pop("classes", {}))
    dispositioned = sum(classes.values())
    by_decision = {d: dict.fromkeys(cohort.CLASSES, 0) for d in cohort.PARTITION}
    by_decision["YES"].update(classes)
    base = {
        "cohort": cohort.COHORT,
        "dispositioned": dispositioned,
        "undispositioned": cohort.COHORT - dispositioned,
        "classes": classes,
        "by_decision": by_decision,
        "dispositions_without_a_source_reason": 0,
        "imported_with_error_signals": 0,
        "HISTORICAL_SNAPSHOT_COMPLETE": False,
        "historical_data_complete": False,
        "LIVE_DELTA_COMPLETENESS": "NOT_RUN",
        "FULL_CURRENT_CONTACT_COVERAGE": "UNKNOWN",
        "stopped": "max_ids",
        "census_sha256": SHA,
    }
    base.update(over)
    return base


def _ledger(rows=None, *, sha=SHA, header=None) -> str:
    head = header or {"kind": "header", "version": 1, "census_sha256": sha, "database_uuid": DB_UUID, "created_at": "t"}
    if rows is None:
        rows = [
            {"vanillasoft_contact_id": str(i), "class": cohort.IMPORTED, "importer_outcome": "created", "signals": []}
            for i in (1, 2, 3)
        ]
        rows.append({"vanillasoft_contact_id": "4", "class": cohort.HELD, "importer_outcome": "failed", "signals": []})
        rows.append(
            {"vanillasoft_contact_id": "5", "class": cohort.DUPLICATE_SKIPPED, "importer_outcome": "not_fetched"}
        )
    return "\n".join(json.dumps(line) for line in [head, *rows]) + "\n"


def _log(admitted=ADMITTED, verdict=True, rolling=False) -> str:
    lines = []
    if admitted:
        lines.append(lib.VS_AUDIT_PREFIX + admitted)
    if rolling:
        lines.append(lib.VS_ROLLING_BANNER)
    if verdict:
        lines.append(lib.VS_VERDICT_PREFIX + json.dumps(_report()))
    return "\n".join(lines) + "\n"


def _vs(tmp_path, report=_report(), *, import_exit=0, ledger=_ledger(), log=_log(), before=0, after=3, max_ids=100):
    path = tmp_path / "06-crm-result.json"
    if report is not None:
        _write(path, report)
    ledger_path = None
    if ledger is not None:
        ledger_path = _write(tmp_path / "06-crm-history.jsonl", ledger)
    return lib.check_vanillasoft_history(
        path,
        import_exit=import_exit,
        ledger_path=ledger_path,
        log_text=log,
        refs_before=before,
        refs_after=after,
        census_sha256=SHA,
        database=DB,
        max_ids=max_ids,
        run_started=RUN_STARTED,
        release_sha="a" * 40,
    )


def test_vanillasoft_bounded_sample_passes_without_claiming_the_cohort(tmp_path):
    result = _vs(tmp_path)
    assert (result["state"], result["reason"]) == ("PASS", "vanillasoft-history-sample-exercised")
    facts = result["facts"]
    assert facts["full_cohort_claimed"] is False
    assert facts["historical_snapshot_complete"] is False
    assert (facts["fetched"], facts["attempted"], facts["imported"], facts["held"]) == (4, 4, 3, 1)
    assert (facts["duplicate_skipped"], facts["undispositioned"], facts["max_ids"]) == (1, cohort.COHORT - 5, 100)
    assert (facts["durable_refs_landed"], facts["ledger_rows"], facts["admitted"]) == (3, 5, True)
    assert facts["ledger_database_uuid"] == DB_UUID
    path = facts["execution_path"]
    assert path["make_target"] == "import-vanillasoft"
    assert path["driver"] == "plasticos_crm_sync/scripts/import_vanillasoft_shell.py"
    assert "upsert_contact_external_id" in path["dispatcher"]
    assert (path["database"], path["census_sha256"], path["release_sha"]) == (DB, SHA, "a" * 40)
    assert "complete" not in result["reason"]


ROLLING_SUMMARY = _summary("vanillasoft")


@pytest.mark.parametrize(
    "kwargs, reason",
    [
        ({"report": None}, "vanillasoft-history-report-unreadable"),
        ({"report": ROLLING_SUMMARY}, "vanillasoft-history-report-shape"),
        ({"report": _report(cohort=100)}, "vanillasoft-history-report-shape"),
        ({"report": _report(classes={"extra": 1})}, "vanillasoft-history-report-shape"),
        ({"report": _report(stopped="later")}, "vanillasoft-history-report-shape"),
        ({"report": _report(undispositioned=1)}, "vanillasoft-history-report-shape"),
        ({"report": _report(HISTORICAL_SNAPSHOT_COMPLETE="yes")}, "vanillasoft-history-report-shape"),
        ({"report": _report(census_sha256="e" * 64)}, "vanillasoft-history-census-mismatch"),
        ({"report": _report(stopped="auth")}, "vanillasoft-history-credential-rejected"),
        ({"report": _report(stopped="budget")}, "vanillasoft-history-failure-budget"),
        ({"report": _report(dispositions_without_a_source_reason=1)}, "vanillasoft-history-unexplained-dispositions"),
        ({"report": _report(imported_with_error_signals=1)}, "vanillasoft-history-imported-with-errors"),
        ({"report": _report(classes={cohort.GENUINE_FAILED: 1})}, "vanillasoft-history-genuine-failures"),
        ({"ledger": None}, "vanillasoft-history-ledger-invalid"),
        ({"ledger": _ledger(sha="e" * 64)}, "vanillasoft-history-ledger-invalid"),
        ({"ledger": _ledger(header={"kind": "row"})}, "vanillasoft-history-ledger-invalid"),
        (
            {"ledger": _ledger(rows=[{"vanillasoft_contact_id": "1", "class": "maybe"}])},
            "vanillasoft-history-ledger-invalid",
        ),
        ({"ledger": _ledger(rows=[])}, "vanillasoft-history-ledger-mismatch"),
        ({"log": None}, "vanillasoft-history-log-unreadable"),
        ({"log": _log(admitted=None)}, "vanillasoft-history-not-admitted"),
        ({"log": _log(admitted=ADMITTED.replace(DB, "odoo"))}, "vanillasoft-history-wrong-database"),
        ({"log": _log(admitted=ADMITTED.replace("false", "true"))}, "vanillasoft-history-permit-used"),
        ({"log": _log(admitted=ADMITTED.replace(SHA, "e" * 64))}, "vanillasoft-history-admitted-other-census"),
        ({"log": _log(rolling=True)}, "vanillasoft-rolling-mode-observed"),
        ({"log": _log(verdict=False)}, "vanillasoft-history-verdict-unobserved"),
        ({"before": None}, "vanillasoft-history-refs-unavailable"),
        ({"after": None}, "vanillasoft-history-refs-unavailable"),
        ({"after": 2}, "vanillasoft-history-durable-mismatch"),
        ({"import_exit": 2}, "vanillasoft-preflight-failed"),
        ({"import_exit": 1}, "vanillasoft-history-import-exit"),
    ],
)
def test_vanillasoft_history_never_passes_on_exit_code_alone(tmp_path, kwargs, reason):
    result = _vs(tmp_path, **kwargs)
    assert result["state"] == "FAIL"
    assert reason in result["facts"].get("failure_codes", [result["reason"]])


def _nothing_imported():
    rows = [{"vanillasoft_contact_id": "1", "class": cohort.HELD, "importer_outcome": "failed", "signals": []}]
    return {"report": _report(classes={cohort.IMPORTED: 0, cohort.DUPLICATE_SKIPPED: 0}), "ledger": _ledger(rows=rows)}


@pytest.mark.parametrize(
    "kwargs",
    [
        {**_nothing_imported(), "after": 0},
        {
            "report": _report(classes={cohort.IMPORTED: 0, cohort.HELD: 0, cohort.DUPLICATE_SKIPPED: 1}),
            "ledger": _ledger(
                rows=[
                    {
                        "vanillasoft_contact_id": "5",
                        "class": cohort.DUPLICATE_SKIPPED,
                        "importer_outcome": "not_fetched",
                    }
                ]
            ),
            "after": 0,
        },
    ],
)
def test_vanillasoft_history_sample_without_a_durable_import_is_blocked(tmp_path, kwargs):
    result = _vs(tmp_path, **kwargs)
    assert (result["state"], result["reason"]) == ("BLOCKED", "vanillasoft-history-sample-no-import")
    assert result["facts"]["imported"] == 0


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
    assert {
        "vanillasoft-key-unbound",
        "erp-proof-files-missing",
        "vanillasoft-history-sample-no-import",
    } <= ids
    # The rolling-window blockers are gone with the mode.
    assert not {"vanillasoft-empty-window", "vanillasoft-scope-notice-partial"} & ids
    entries = lib.load_blockers()
    # Design-scope notes never turn a failure into a block.
    assert entries["web-lead-no-partner-creation"].get("verdict_effect") != "blocked"
    assert entries["vanillasoft-history-bounded-sample"].get("verdict_effect") != "blocked"
    assert "vanillasoft-seven-day-window" not in entries


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
