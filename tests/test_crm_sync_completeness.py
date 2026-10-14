"""FX-007 — a CRM sync run must say what it covered, and must not read complete when it was not.

Every assertion here was a counterexample against Staging ``8c09e92`` before
the fix landed. The scenarios:

* a Contacts / GetCallHistory payload with no recognised row list was treated
  as a valid empty page, so an error-shaped or renamed response reported a
  clean run — and, for calls, advanced the window watermark past the calls it
  never read;
* a ``plasticos.crm.sync.run`` row did not say whether it was the rolling
  incremental pass or the operator's full import, nor which bounds it asked
  the provider for, so a ≤30-day run looked exactly like a historical census;
* a contact watermark older than the provider lookback was clamped silently —
  the run said ``success`` while months of modifications were never requested;
* per-record write failures and buffered orphan calls left the run's own
  status at ``success`` even though the shared summary classified the same run
  ``failed`` / ``partial``;
* ``make import-vanillasoft`` defaulted a missing call floor to 30 days and ran
  a "full import" over it, the exact fallback ``_require_utc_bound`` forbids.

The in-memory ORM and the stubbed runtime seams are the ones
``tests/test_crm_sync_full_import.py`` documents; everything the assertions
touch is the production orchestrator and adapter code.
"""

from __future__ import annotations

import ast
import io
import sys
import urllib.error
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plasticos_crm_sync.adapters.base import CrmAdapterError  # noqa: E402
from plasticos_crm_sync.adapters.vanillasoft import client as vs_client  # noqa: E402
from plasticos_crm_sync.adapters.vanillasoft.adapter import VanillaSoftAdapter  # noqa: E402
from plasticos_crm_sync.adapters.vanillasoft.client import VanillaSoftClient  # noqa: E402
from plasticos_crm_sync.services.import_summary import build_run_summary  # noqa: E402
from plasticos_crm_sync.services.orchestrator import (  # noqa: E402
    INCREMENTAL_CONTACT_LOOKBACK_DAYS,
    completion_notice,
)
from tests.test_crm_sync_full_import import (  # noqa: E402
    ANCIENT_Z,
    CALL_FLOOR_Z,
    NOW,
    RECENT_Z,
    _Adapter,
    _call,
    _Connection,
    _harness,
    _iso,
    _lead,
    _one_page,
    _Orchestrator,
)
from tests.test_crm_sync_vanillasoft_client import _FakeResponse  # noqa: E402

ORCHESTRATOR = ROOT / "plasticos_crm_sync" / "services" / "orchestrator.py"
SHELL = ROOT / "plasticos_crm_sync" / "scripts" / "import_vanillasoft_shell.py"


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# ── an unrecognised payload is uncertain coverage, not an empty scope ────────


@pytest.mark.parametrize("payload", [{}, {"status": "ok"}, {"contacts": None}, {"Contact": []}, "garbage", None])
def test_contacts_payload_without_a_recognised_row_list_fails_instead_of_reading_empty(payload):
    client = MagicMock()
    client.get_contacts.return_value = payload
    adapter = VanillaSoftAdapter(client, 139705)
    with pytest.raises(CrmAdapterError, match="unrecognised Contacts payload"):
        list(adapter.iter_contacts(modified_after="2026-07-01T00:00:00Z", limit=50))


def test_contacts_payload_with_an_empty_recognised_list_is_a_valid_empty_scope():
    client = MagicMock()
    client.get_contacts.return_value = {"contacts": [], "partial_fulfillment": False}
    adapter = VanillaSoftAdapter(client, 139705)
    assert list(adapter.iter_contacts(modified_after="2026-07-01T00:00:00Z", limit=50)) == [([], None, False)]


def test_a_bare_list_of_contacts_is_still_accepted():
    client = MagicMock()
    client.get_contacts.return_value = [{"contact_id": 1}]
    adapter = VanillaSoftAdapter(client, 139705)
    pages = list(adapter.iter_contacts(modified_after="2026-07-01T00:00:00Z", limit=50))
    assert [lead.external_id for lead in pages[0][0]] == ["1"]


@pytest.mark.parametrize("payload", [{}, {"error": "throttled"}, {"call_histories": None}, "garbage", None])
def test_calls_payload_without_a_recognised_row_list_fails_the_window(payload):
    """`_sync_calls` advances the whole window watermark when `iter_calls`
    returns normally, so reading this as "no calls" loses every call in the
    window permanently."""
    client = MagicMock()
    client.get_call_history_batch.return_value = payload
    adapter = VanillaSoftAdapter(client, 139705)
    with pytest.raises(CrmAdapterError, match="unrecognised GetCallHistory payload"):
        list(adapter.iter_calls(start="2026-08-01T00:00:00Z", end="2026-08-02T00:00:00Z", limit=500))


def test_calls_payload_with_an_empty_recognised_list_ends_the_window_normally():
    client = MagicMock()
    client.get_call_history_batch.return_value = {"call_histories": []}
    adapter = VanillaSoftAdapter(client, 139705)
    assert list(adapter.iter_calls(start="2026-08-01T00:00:00Z", end="2026-08-02T00:00:00Z", limit=500)) == []


# ── the run names its kind and the bounds it actually asked for ─────────────


def test_an_incremental_run_records_its_kind_and_requested_scope():
    adapter = _Adapter(contact_passes=[_one_page([_lead("c1")], RECENT_Z)], call_passes=[[]])
    orch, connection, env = _harness(adapter)
    run = env["plasticos.crm.sync.run"].browse(orch.run_connection(connection).id)

    assert run.kind == "incremental"
    assert run.contact_scope_from_utc == adapter.contact_calls[0]
    assert run.call_scope_from_utc == adapter.call_windows[0][0]
    assert run.call_scope_to_utc == adapter.call_windows[-1][1]


def test_a_full_import_records_its_kind_and_the_operator_floors():
    adapter = _Adapter(
        contact_passes=[_one_page([_lead("c1", modified=ANCIENT_Z)], ANCIENT_Z), []], call_passes=[[], []]
    )
    orch, connection, env = _harness(adapter)
    run = env["plasticos.crm.sync.run"].browse(
        orch.run_full_import(connection, call_history_floor=CALL_FLOOR_Z, contact_modified_floor=ANCIENT_Z).id
    )

    assert run.kind == "full_import"
    assert run.contact_scope_from_utc == ANCIENT_Z
    assert run.call_scope_from_utc == CALL_FLOOR_Z
    assert _parse(run.call_scope_to_utc) >= NOW - timedelta(minutes=10), "the catch-up closes the window at now"


def test_a_fresh_connection_incremental_run_is_success_for_its_declared_scope_only():
    """Nothing older than the rolling window was requested, so nothing is
    missing from the declared scope — but the row must say that scope."""
    adapter = _Adapter(contact_passes=[_one_page([_lead("c1")], RECENT_Z)], call_passes=[[]])
    orch, connection, env = _harness(adapter)
    run = env["plasticos.crm.sync.run"].browse(orch.run_connection(connection).id)

    assert run.status == "success"
    assert run.kind == "incremental"
    assert _parse(run.contact_scope_from_utc) >= NOW - timedelta(days=INCREMENTAL_CONTACT_LOOKBACK_DAYS, minutes=5)
    assert not run.error_excerpt


# ── a clamped watermark is a scope limitation, never a silent success ───────


def test_a_watermark_older_than_the_lookback_makes_the_run_partial_and_names_the_gap():
    stale = _iso(NOW - timedelta(days=90))
    adapter = _Adapter(contact_passes=[_one_page([_lead("c1")], RECENT_Z)], call_passes=[[]])
    orch, connection, env = _harness(adapter, _Connection(contact_watermark=stale))
    run = env["plasticos.crm.sync.run"].browse(orch.run_connection(connection).id)

    assert run.status == "partial"
    assert stale in run.error_excerpt and "lookback" in run.error_excerpt
    assert run.contact_scope_from_utc == adapter.contact_calls[0], "scope records what was actually requested"
    assert _parse(run.contact_scope_from_utc) > _parse(stale)
    assert connection.last_error == run.error_excerpt
    assert build_run_summary(run)["final_status"] == "partial"


def test_a_watermark_inside_the_lookback_is_not_a_gap():
    adapter = _Adapter(contact_passes=[_one_page([_lead("c1")], RECENT_Z)], call_passes=[[]])
    orch, connection, env = _harness(adapter, _Connection(contact_watermark=RECENT_Z))
    run = env["plasticos.crm.sync.run"].browse(orch.run_connection(connection).id)
    assert run.status == "success"
    assert not run.error_excerpt
    assert connection.last_error is False


# ── per-record outcomes drive the run status, in step with the summary ──────


def test_a_failed_lead_write_makes_the_run_failed_not_success():
    adapter = _Adapter(contact_passes=[_one_page([_lead("boom")], RECENT_Z)], call_passes=[[]])
    orch, connection, env = _harness(adapter)
    record = orch._upsert_lead(connection, _lead("boom"))

    def boom(vals):
        raise RuntimeError("column broken")

    record.write = boom
    adapter._contact_passes = [_one_page([replace(_lead("boom"), company="Renamed")], RECENT_Z)]
    run = env["plasticos.crm.sync.run"].browse(orch.run_connection(connection).id)

    assert run.contacts_failed == 1
    assert run.status == "failed"
    assert "1 contact" in run.error_excerpt and "column broken" in run.error_excerpt
    assert connection.last_error == run.error_excerpt
    assert connection.last_success_at is None, "a run with failed rows is not a success"
    assert build_run_summary(run, error_rows=orch.error_rows)["final_status"] == "failed"


def test_buffered_orphan_calls_make_an_incremental_run_partial():
    adapter = _Adapter(contact_passes=[_one_page([_lead("c1")], RECENT_Z)], call_passes=[[[_call("k1", "ghost")]]])
    orch, connection, env = _harness(adapter)
    run = env["plasticos.crm.sync.run"].browse(orch.run_connection(connection).id)

    assert run.orphans_buffered == 1
    assert run.status == "partial"
    assert "orphan" in run.error_excerpt
    assert build_run_summary(run)["final_status"] == "partial"


def test_a_full_import_with_failed_rows_is_failed_even_when_the_census_is_proven():
    adapter = _Adapter(
        contact_passes=[_one_page([replace(_lead("boom", modified=ANCIENT_Z), company="Renamed")], ANCIENT_Z), []],
        call_passes=[[], []],
    )
    orch, connection, env = _harness(adapter)
    record = orch._upsert_lead(connection, _lead("boom"))

    def boom(vals):
        raise RuntimeError("column broken")

    record.write = boom
    run = env["plasticos.crm.sync.run"].browse(
        orch.run_full_import(connection, call_history_floor=CALL_FLOOR_Z, contact_modified_floor=ANCIENT_Z).id
    )
    assert run.status == "failed"
    assert build_run_summary(run, error_rows=orch.error_rows)["final_status"] == "failed"


# ── a manual caller is told the computed status, never a flat success ──────


def test_a_failed_run_is_not_announced_as_a_success():
    adapter = _Adapter(contact_passes=[_one_page([_lead("boom")], RECENT_Z)], call_passes=[[]])
    orch, connection, env = _harness(adapter)
    record = orch._upsert_lead(connection, _lead("boom"))

    def boom(vals):
        raise RuntimeError("column broken")

    record.write = boom
    adapter._contact_passes = [_one_page([replace(_lead("boom"), company="Renamed")], RECENT_Z)]
    run = env["plasticos.crm.sync.run"].browse(orch.run_connection(connection).id)

    kind, message = completion_notice(run)
    assert kind == "danger"
    assert "failures" in message and "1 contact" in message


def test_a_partial_run_is_announced_as_a_warning_with_its_note():
    stale = _iso(NOW - timedelta(days=90))
    adapter = _Adapter(contact_passes=[_one_page([_lead("c1")], RECENT_Z)], call_passes=[[]])
    orch, connection, env = _harness(adapter, _Connection(contact_watermark=stale))
    run = env["plasticos.crm.sync.run"].browse(orch.run_connection(connection).id)

    kind, message = completion_notice(run)
    assert kind == "warning"
    assert "partial" in message and "lookback" in message


def test_a_clean_run_is_still_announced_as_a_success():
    adapter = _Adapter(contact_passes=[_one_page([_lead("c1")], RECENT_Z)], call_passes=[[]])
    orch, connection, env = _harness(adapter)
    run = env["plasticos.crm.sync.run"].browse(orch.run_connection(connection).id)
    assert completion_notice(run) == ("success", "Sync finished")


# ── the shell driver never defaults the historical floor ────────────────────


def test_shell_import_refuses_to_run_without_an_explicit_call_floor(monkeypatch, capsys):
    """The 30-day default made `make import-vanillasoft` a rolling import under
    the full-import name. The refusal must come before the Odoo environment is
    touched, so this is the pure-python tier's proof."""
    monkeypatch.delenv("VANILLASOFT_CALL_FLOOR", raising=False)
    from plasticos_crm_sync.scripts import import_vanillasoft_shell as shell

    assert shell.main() == 2
    out = capsys.readouterr().out
    assert "VANILLASOFT_CALL_FLOOR" in out
    assert "Nothing was imported." in out


def test_shell_import_refuses_a_blank_call_floor(monkeypatch, capsys):
    monkeypatch.setenv("VANILLASOFT_CALL_FLOOR", "   ")
    from plasticos_crm_sync.scripts import import_vanillasoft_shell as shell

    assert shell.main() == 2
    assert "VANILLASOFT_CALL_FLOOR" in capsys.readouterr().out


def test_shell_driver_imports_through_odoo_addons():
    """Odoo 19 rejects model classes loaded as plasticos_crm_sync.* inside odoo shell."""
    tree = ast.parse(SHELL.read_text(encoding="utf-8"))
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    imports = {
        node.module: tuple(alias.name for alias in node.names)
        for node in main.body
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert imports["odoo.addons.plasticos_crm_sync.models.crm_connection"] == ("ICP_ROOT", "ICP_VS_KEY_PARAM")
    assert imports["odoo.addons.plasticos_crm_sync.services.import_summary"] == ("build_run_summary", "utc_now")
    assert imports["odoo.addons.plasticos_crm_sync.services.orchestrator"] == ("SyncOrchestrator",)
    bare = [module for module in imports if module.startswith("plasticos_crm_sync")]
    assert bare == []


# ── every page of the requested scope is retrieved, through the real adapter ─
#
# The adapter-level pagination tests prove `iter_contacts` follows
# `partial_fulfillment` / `batch_end`; the run-level tests above drive a
# scripted adapter. This drives the REAL `VanillaSoftAdapter` over a mocked
# client through the REAL `run_connection`, so the claim "a multi-page scope
# lands every row and the watermark ends at the last page" is made about the
# two layers together.


def _raw_contact(contact_id: str, modified: str) -> dict:
    return {"contact_id": contact_id, "company": f"Co {contact_id}", "modified_date_time_utc": modified}


def _paged_client(pages: list[dict]) -> MagicMock:
    client = MagicMock()
    client.verify_key.return_value = {"projects": [{"project_id": 139705}]}
    client.get_contacts.side_effect = list(pages)
    client.get_call_history_batch.return_value = {"call_histories": []}
    client.get_custom_tables_list.return_value = {"custom_tables": []}
    client.get_custom_table_data.return_value = {"rows": []}
    return client


def test_an_incremental_run_consumes_every_partial_fulfillment_page():
    t1, t2, t3 = (_iso(NOW - timedelta(days=d)) for d in (6, 5, 4))
    client = _paged_client(
        [
            {"contacts": [_raw_contact("1", t1), _raw_contact("2", t1)], "batch_end": t1, "partial_fulfillment": True},
            {"contacts": [_raw_contact("3", t2)], "batch_end": t2, "partial_fulfillment": True},
            {"contacts": [_raw_contact("4", t3)], "batch_end": t3, "partial_fulfillment": False},
        ]
    )
    orch, connection, env = _harness(VanillaSoftAdapter(client, 139705))
    run = env["plasticos.crm.sync.run"].browse(orch.run_connection(connection).id)

    assert client.get_contacts.call_count == 3, "pagination stops only when the provider says the page is complete"
    # Each follow-up page resumed from the provider's own cursor, never a guess.
    assert [call.args[1] for call in client.get_contacts.call_args_list][1:] == [t1, t2]
    assert run.status == "success" and run.kind == "incremental"
    assert run.contacts_seen == 4 and run.contacts_created == 4
    assert len(env["plasticos.crm.external.ref"].search([])) == 4
    assert connection.contact_watermark_utc == t3, "the watermark ends at the last page actually consumed"


def test_a_page_failure_mid_sequence_fails_the_run_and_keeps_only_the_committed_watermark():
    """Page 1 commits, page 2 raises: the run is `failed`, the watermark stops at
    page 1, no call window is acknowledged, and the summary agrees."""
    t1 = _iso(NOW - timedelta(days=6))
    client = _paged_client(
        [
            {"contacts": [_raw_contact("1", t1)], "batch_end": t1, "partial_fulfillment": True},
            CrmAdapterError("VanillaSoft HTTP 503: upstream unavailable"),
        ]
    )
    orch, connection, env = _harness(VanillaSoftAdapter(client, 139705))
    with pytest.raises(CrmAdapterError, match="503"):
        orch.run_connection(connection)

    run = env["plasticos.crm.sync.run"].browse(1)
    assert run.status == "failed" and "503" in run.error_excerpt
    assert connection.contact_watermark_utc == t1
    assert client.get_call_history_batch.call_count == 0, "no call window is asked for, so none is acknowledged"
    assert connection.call_watermark_utc is None
    assert build_run_summary(run)["final_status"] == "failed"


def test_the_next_run_resumes_from_the_committed_watermark_after_a_failed_page():
    t1 = _iso(NOW - timedelta(days=6))
    failing = _paged_client(
        [
            {"contacts": [_raw_contact("1", t1)], "batch_end": t1, "partial_fulfillment": True},
            CrmAdapterError("VanillaSoft HTTP 429: Too Many Requests"),
        ]
    )
    orch, connection, env = _harness(VanillaSoftAdapter(failing, 139705))
    with pytest.raises(CrmAdapterError, match="429"):
        orch.run_connection(connection)
    first = env["plasticos.crm.sync.run"].browse(1)
    assert first.status == "failed" and "429" in first.error_excerpt

    t2 = _iso(NOW - timedelta(days=5))
    resumed = _paged_client([{"contacts": [_raw_contact("2", t2)], "batch_end": t2, "partial_fulfillment": False}])
    second = _Orchestrator(env, VanillaSoftAdapter(resumed, 139705))
    run = env["plasticos.crm.sync.run"].browse(second.run_connection(connection).id)

    assert resumed.get_contacts.call_args_list[0].args[1] == t1, "the remainder is requested from where page 1 stopped"
    assert run.status == "success" and run.contact_scope_from_utc == t1
    assert {r.external_id for r in env["plasticos.crm.external.ref"].search([])} == {"1", "2"}
    assert connection.contact_watermark_utc == t2


# ── a rate limit is an interruption, never an empty page ────────────────────


def _http_error(status: int, body: bytes = b"slow down"):
    return urllib.error.HTTPError(
        "https://vanillasoft.net/WSPubAPI/Contacts", status, "Too Many Requests", hdrs=None, fp=io.BytesIO(body)
    )


def test_an_exhausted_rate_limit_surfaces_as_a_failure_not_an_empty_page(monkeypatch):
    monkeypatch.setattr(vs_client.time, "sleep", lambda _s: None)
    opener = MagicMock()
    opener.open.side_effect = lambda *_a, **_k: (_ for _ in ()).throw(_http_error(429))
    client = VanillaSoftClient("k", "https://vanillasoft.net", opener=opener)

    with pytest.raises(CrmAdapterError, match="429"):
        client.get_contacts(139705, "2026-07-01T00:00:00Z", limit=200)
    assert opener.open.call_count == vs_client.MAX_RETRIES


def test_a_transient_rate_limit_is_retried_and_the_page_is_still_served(monkeypatch):
    monkeypatch.setattr(vs_client.time, "sleep", lambda _s: None)
    page = {"contacts": [], "partial_fulfillment": False}
    responses = iter([_http_error(429), _FakeResponse(page)])

    def open_(*_a, **_k):
        item = next(responses)
        if isinstance(item, Exception):
            raise item
        return item

    opener = MagicMock()
    opener.open.side_effect = open_
    client = VanillaSoftClient("k", "https://vanillasoft.net", opener=opener)
    assert client.get_contacts(139705, "2026-07-01T00:00:00Z", limit=200) == page
    assert opener.open.call_count == 2


# ── a run interrupted without an exception cannot read as in progress forever ─
#
# A worker kill, an OOM or a deploy restart ends the process between the audit
# row's `running` and any completion write. The connection's session advisory
# lock dies with that backend, so the NEXT run holding the lock is proof that
# nothing is still running: it closes the stale row as `failed` with the
# interruption named. The watermarks already hold exactly what the interrupted
# run committed, so nothing is lost; this makes the ledger say so.


def test_a_run_left_running_by_a_dead_process_is_closed_when_the_next_run_starts():
    adapter = _Adapter(contact_passes=[_one_page([_lead("c1")], RECENT_Z)], call_passes=[[]])
    orch, connection, env = _harness(adapter)
    Run = env["plasticos.crm.sync.run"]
    stale = Run.create({"connection_id": 1, "status": "running", "kind": "incremental"})
    other_connection = Run.create({"connection_id": 2, "status": "running"})

    run = Run.browse(orch.run_connection(connection).id)

    assert stale.status == "failed"
    assert "interrupted" in stale.error_excerpt.lower()
    assert stale.finished_at is not None
    assert other_connection.status == "running", "only the locked connection's rows are proven dead"
    assert run.status == "success"
    assert build_run_summary(stale)["final_status"] == "failed"


def test_the_durable_create_closes_interrupted_runs_before_inserting_the_new_row():
    """The production seam opens its own cursor, so the pure tier reads the
    ordering off the source: the stale-row close must precede the create on
    that same cursor, or the new `running` row would close itself."""
    tree = ast.parse(ORCHESTRATOR.read_text(encoding="utf-8"))
    fn = next(
        node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "_create_sync_run_durable"
    )
    calls = [
        ast.unparse(node.func)
        for node in ast.walk(fn)
        if isinstance(node, ast.Call) and ast.unparse(node.func).endswith(("_close_interrupted_runs", ".create"))
    ]
    assert calls and calls[0].endswith("_close_interrupted_runs"), calls
    assert calls.index(calls[0]) < next(i for i, c in enumerate(calls) if c.endswith(".create"))


# ── repeated execution keeps replay and dedup behaviour ─────────────────────


def test_repeating_an_incremental_run_over_the_same_page_creates_nothing_twice():
    page = _one_page([_lead("r1"), _lead("r2")], RECENT_Z)
    orch, connection, env = _harness(_Adapter(contact_passes=[page], call_passes=[[]]))
    first = env["plasticos.crm.sync.run"].browse(orch.run_connection(connection).id)
    again = _Orchestrator(env, _Adapter(contact_passes=[page], call_passes=[[]]))
    second = env["plasticos.crm.sync.run"].browse(again.run_connection(connection).id)

    assert (first.contacts_created, first.contacts_unchanged) == (2, 0)
    assert (second.contacts_created, second.contacts_unchanged) == (0, 2)
    assert second.status == "success"
    assert len(env["crm.lead"].rows) == 2 and len(env["plasticos.crm.external.ref"].search([])) == 2
