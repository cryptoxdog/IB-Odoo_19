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

import sys
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plasticos_crm_sync.adapters.base import CrmAdapterError  # noqa: E402
from plasticos_crm_sync.adapters.vanillasoft.adapter import VanillaSoftAdapter  # noqa: E402
from plasticos_crm_sync.services.import_summary import build_run_summary  # noqa: E402
from plasticos_crm_sync.services.orchestrator import INCREMENTAL_CONTACT_LOOKBACK_DAYS  # noqa: E402
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
)


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
