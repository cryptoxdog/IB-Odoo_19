"""Sync-run counters describe committed work, never attempted work.

The defect these pin: `_sync_contacts` / `_sync_calls` used to accumulate a
plain Python local and assign it to the run row only *after* the whole loop
finished, inside the ambient transaction. Page commits landed leads and
watermarks but never a counter, so a failure on page 2 rolled back the only
write that would have recorded page 1 — and the failed run reported
`contacts_upserted=0` while 50 leads sat durably in the database.

What is modelled here and what is not
-------------------------------------
`_FakeCursor` treats `commit()` as "snapshot the counter" and `rollback()` as
"restore the last snapshot". That is the *ordering contract*: a value is
durable only if it was written before a commit returned. It is deliberately
NOT a claim about PostgreSQL — real commit/rollback, row locks and
cross-session visibility stay real-runtime gates C1-C6 in
docs/runbooks/LAUNCH_GATES.md. A green result here means the counter is
written in the right place; it does not mean the row survived a crash.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plasticos_crm_sync.adapters.base import CanonicalLead, CrmAdapterError  # noqa: E402
from plasticos_crm_sync.services.orchestrator import SyncOrchestrator  # noqa: E402

ORCHESTRATOR = ROOT / "plasticos_crm_sync/services/orchestrator.py"
COUNTERS = ("contacts_upserted", "calls_upserted")


def _lead(external_id: str) -> CanonicalLead:
    return CanonicalLead(
        provider="vanillasoft",
        external_id=external_id,
        company=f"Co {external_id}",
        first_name="Ada",
        last_name="Lovelace",
        lead_status_raw="New",
    )


class _FakeRun:
    """Stands in for the sync-run row; starts at the model's `default=0`."""

    def __init__(self) -> None:
        self.contacts_upserted = 0
        self.calls_upserted = 0
        self.orphans_buffered = 0


class _FakeCursor:
    """Commit snapshots the run's counters; rollback restores the snapshot."""

    def __init__(self, run: _FakeRun) -> None:
        self._run = run
        self.durable = {name: getattr(run, name) for name in COUNTERS}
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1
        self.durable = {name: getattr(self._run, name) for name in COUNTERS}

    def rollback(self) -> None:
        for name, value in self.durable.items():
            setattr(self._run, name, value)


class _FakeEnv:
    def __init__(self, cr: _FakeCursor) -> None:
        self.cr = cr


class _FakeConnection:
    id = 1
    provider = "vanillasoft"

    def __init__(self) -> None:
        self.contact_watermark_utc = None
        self.call_watermark_utc = None
        self.call_backfill_floor_utc = None

    def default_contact_modified_after(self) -> str:
        return "2026-08-01T00:00:00Z"


class _ScriptedAdapter:
    """Pages are scripted; a page may be an exception to raise instead."""

    provider = "vanillasoft"
    live = True

    def __init__(self, contact_pages=(), call_batches=()) -> None:
        self._contact_pages = list(contact_pages)
        self._call_batches = list(call_batches)

    def iter_contacts(self, *, modified_after, limit=200):
        for page in self._contact_pages:
            if isinstance(page, Exception):
                raise page
            yield page

    def iter_calls(self, *, start, end, limit=500):
        for batch in self._call_batches:
            if isinstance(batch, Exception):
                raise batch
            yield batch


class _CountingOrchestrator(SyncOrchestrator):
    """Isolates the counter contract from ORM write mechanics.

    `_upsert_lead` / `_upsert_calls` are the ORM boundary; replacing them keeps
    this test about *which number is written when*, which is the thing that
    regressed.
    """

    def _upsert_lead(self, connection, dto):
        return object()

    def _sync_tables_for_lead(self, connection, adapter, contact_external_id, lead=None):
        return None

    def _upsert_calls(self, connection, batch, run):
        return len(batch)


def _harness(adapter):
    run = _FakeRun()
    cr = _FakeCursor(run)
    orchestrator = _CountingOrchestrator(_FakeEnv(cr))
    return orchestrator, _FakeConnection(), run, cr


# ── contacts ────────────────────────────────────────────────────────────────


def test_failure_before_any_committed_page_reports_zero():
    adapter = _ScriptedAdapter(contact_pages=[CrmAdapterError("source down")])
    orchestrator, connection, run, cr = _harness(adapter)
    with pytest.raises(CrmAdapterError):
        orchestrator._sync_contacts(connection, adapter, run)
    cr.rollback()
    assert run.contacts_upserted == 0
    assert cr.durable["contacts_upserted"] == 0


def test_committed_page_survives_a_later_page_failure():
    """The residual finding from #163: 50 committed leads must not report 0."""
    page1 = ([_lead(f"c{i}") for i in range(50)], "2026-08-02T00:00:00Z", False)
    adapter = _ScriptedAdapter(contact_pages=[page1, CrmAdapterError("page 2 exploded")])
    orchestrator, connection, run, cr = _harness(adapter)
    with pytest.raises(CrmAdapterError):
        orchestrator._sync_contacts(connection, adapter, run)
    cr.rollback()
    assert run.contacts_upserted == 50
    assert cr.durable["contacts_upserted"] == 50


def test_rows_from_the_failed_page_are_not_counted():
    """Page 2 wrote 25 rows into the transaction that then rolled back."""
    page1 = ([_lead(f"c{i}") for i in range(50)], "2026-08-02T00:00:00Z", False)
    page2 = ([_lead(f"d{i}") for i in range(25)], "2026-08-03T00:00:00Z", False)

    class _FailAfterSecondPage(_ScriptedAdapter):
        def iter_contacts(self, *, modified_after, limit=200):
            yield page1
            yield page2
            raise CrmAdapterError("failed after page 2 was written but before its commit")

    adapter = _FailAfterSecondPage()
    orchestrator, connection, run, cr = _harness(adapter)

    # Page 2's commit is what makes its 25 rows real; suppress it to model a
    # failure between the write and the commit.
    real_commit = cr.commit
    state = {"seen": 0}

    def commit_only_the_first_page():
        state["seen"] += 1
        if state["seen"] == 1:
            real_commit()

    cr.commit = commit_only_the_first_page
    with pytest.raises(CrmAdapterError):
        orchestrator._sync_contacts(connection, adapter, run)
    cr.commit = real_commit
    cr.rollback()
    assert run.contacts_upserted == 50


def test_multiple_committed_pages_accumulate():
    pages = [
        ([_lead(f"a{i}") for i in range(50)], "2026-08-02T00:00:00Z", False),
        ([_lead(f"b{i}") for i in range(30)], "2026-08-03T00:00:00Z", False),
        ([_lead(f"c{i}") for i in range(20)], "2026-08-04T00:00:00Z", False),
    ]
    adapter = _ScriptedAdapter(contact_pages=pages)
    orchestrator, connection, run, cr = _harness(adapter)
    assert orchestrator._sync_contacts(connection, adapter, run) == 100
    assert run.contacts_upserted == 100
    assert cr.durable["contacts_upserted"] == 100


def test_a_fully_successful_run_reports_every_row():
    pages = [([_lead(f"a{i}") for i in range(7)], "2026-08-02T00:00:00Z", False)]
    adapter = _ScriptedAdapter(contact_pages=pages)
    orchestrator, connection, run, cr = _harness(adapter)
    assert orchestrator._sync_contacts(connection, adapter, run) == 7
    assert run.contacts_upserted == 7


def test_the_counter_is_written_before_its_page_commit():
    """A counter written after the commit would be lost by the next rollback."""
    page = ([_lead("only")], "2026-08-02T00:00:00Z", False)
    adapter = _ScriptedAdapter(contact_pages=[page])
    orchestrator, connection, run, cr = _harness(adapter)
    seen: list[int] = []
    real_commit = cr.commit

    def record_then_commit():
        seen.append(run.contacts_upserted)
        real_commit()

    cr.commit = record_then_commit
    orchestrator._sync_contacts(connection, adapter, run)
    assert seen == [1], "counter must already hold the page total when commit runs"


def test_a_replay_after_partial_failure_counts_only_its_own_run():
    """Run 2 gets a fresh row; it reports its own committed work, not run 1's."""
    first = ([_lead(f"a{i}") for i in range(50)], "2026-08-02T00:00:00Z", False)
    adapter = _ScriptedAdapter(contact_pages=[first, CrmAdapterError("boom")])
    orchestrator, connection, run_one, cr_one = _harness(adapter)
    with pytest.raises(CrmAdapterError):
        orchestrator._sync_contacts(connection, adapter, run_one)
    cr_one.rollback()
    assert run_one.contacts_upserted == 50

    replay_pages = [([_lead(f"b{i}") for i in range(25)], "2026-08-03T00:00:00Z", False)]
    replay = _ScriptedAdapter(contact_pages=replay_pages)
    orchestrator_two, connection_two, run_two, _ = _harness(replay)
    orchestrator_two._sync_contacts(connection_two, replay, run_two)
    assert run_two.contacts_upserted == 25


# ── calls ───────────────────────────────────────────────────────────────────


def test_call_batches_commit_their_own_counter():
    adapter = _ScriptedAdapter(call_batches=[[object()] * 40])
    orchestrator, connection, run, cr = _harness(adapter)
    connection.call_watermark_utc = "2026-08-30T00:00:00Z"
    orchestrator._sync_calls(connection, adapter, run)
    assert run.calls_upserted >= 40
    assert cr.durable["calls_upserted"] == run.calls_upserted


def test_committed_call_batch_survives_a_later_batch_failure():
    class _FailOnSecondBatch(_ScriptedAdapter):
        def iter_calls(self, *, start, end, limit=500):
            yield [object()] * 40
            raise CrmAdapterError("batch 2 exploded")

    adapter = _FailOnSecondBatch()
    orchestrator, connection, run, cr = _harness(adapter)
    connection.call_watermark_utc = "2026-08-30T00:00:00Z"
    with pytest.raises(CrmAdapterError):
        orchestrator._sync_calls(connection, adapter, run)
    cr.rollback()
    assert run.calls_upserted == 40


# ── the failure writer must not clobber a committed counter ─────────────────


def _function(name: str) -> ast.FunctionDef:
    tree = ast.parse(ORCHESTRATOR.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in {ORCHESTRATOR.name}")


def test_failure_writer_never_writes_a_counter():
    """Writing a counter here would overwrite the durable value with a stale one.

    Asserted over the AST because the failure path is the one that cannot be
    exercised honestly without a real second PostgreSQL session (gate C1/C2).
    """
    written = {
        key.value
        for node in ast.walk(_function("_persist_sync_failure_durable"))
        if isinstance(node, ast.Dict)
        for key in node.keys
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }
    assert not (written & set(COUNTERS)), f"failure writer must not touch counters, writes: {written}"


def test_ambient_transaction_gets_a_snapshot_that_can_see_the_run_row():
    """Guards a defect only a real PostgreSQL run could expose.

    Odoo runs cursors at REPEATABLE READ. `run_connection` takes the ambient
    transaction's snapshot with the advisory-lock SELECT, then creates the
    sync-run row on a SECOND cursor. Without ending the ambient transaction in
    between, `browse(run_id)` is not in that snapshot: `.exists()` is False and
    every write to it is an `UPDATE ... WHERE id=N` matching zero rows —
    silently. The first page's counter was lost exactly that way.

    Required order: create the row, commit (new snapshot), then browse.
    Verified on real Odoo 19 + PostgreSQL 16, gate C2.
    """
    node = _function("run_connection")
    events: list[tuple[int, str]] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            ref, parts = child.func, []
            while isinstance(ref, ast.Attribute):
                parts.append(ref.attr)
                ref = ref.value
            if isinstance(ref, ast.Name):
                parts.append(ref.id)
            name = ".".join(reversed(parts))
            if name.endswith("_create_sync_run_durable"):
                events.append((child.lineno, "create"))
            elif name == "self.env.cr.commit":
                events.append((child.lineno, "commit"))
            elif name == "browse" or name.endswith(".browse"):
                events.append((child.lineno, "browse"))
    ordered = [kind for _, kind in sorted(events)]
    assert "create" in ordered, "run_connection must create the durable run row"
    create_at = ordered.index("create")
    after = ordered[create_at + 1 :]
    assert after and after[0] == "commit", (
        "the ambient transaction must be committed immediately after the durable "
        f"run row is created, so its snapshot can see that row; got {ordered}"
    )
    assert "browse" in after, "the run row is browsed after the snapshot refresh"
    assert after.index("commit") < after.index("browse")


@pytest.mark.parametrize("func", ["_sync_contacts", "_sync_calls"])
def test_counter_assignment_precedes_the_commit_in_the_page_loop(func):
    """Ordering guard: `run.<counter> = ...` then `cr.commit()`, never the reverse."""
    node = _function(func)
    events: list[tuple[int, str]] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Assign):
            for target in child.targets:
                if isinstance(target, ast.Attribute) and target.attr in COUNTERS:
                    events.append((child.lineno, "assign"))
        elif isinstance(child, ast.Call):
            ref, parts = child.func, []
            while isinstance(ref, ast.Attribute):
                parts.append(ref.attr)
                ref = ref.value
            if isinstance(ref, ast.Name):
                parts.append(ref.id)
            if ".".join(reversed(parts)) == "self.env.cr.commit":
                events.append((child.lineno, "commit"))
    ordered = [kind for _, kind in sorted(events)]
    assert ordered[0] == "assign", f"{func}: first counter event must be the assignment, got {ordered}"
