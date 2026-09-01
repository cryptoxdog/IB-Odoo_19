"""Launch invariants I1–I6 / I16 for the VanillaSoft → Gate path.

Every test here runs in the pure-Python CI tier (no Odoo runtime). The
transaction-ordering invariants (I2/I3) are asserted structurally over the AST:
that proves the *ordering contract* — rollback before the second cursor, no
flush between — which is the property that silently regresses when someone
"tidies" the failure handler. It does NOT prove real PostgreSQL row-lock and
cross-session visibility behavior; that stays a real-runtime deployment gate and
is listed in docs/runbooks/LAUNCH_GATES.md.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plasticos_crm_sync.adapters.base import CrmAdapterError  # noqa: E402
from plasticos_crm_sync.adapters.vanillasoft import adapter as vs_adapter  # noqa: E402
from plasticos_crm_sync.adapters.vanillasoft.adapter import (  # noqa: E402
    VanillaSoftAdapter,
    call_to_canonical,
)
from plasticos_crm_sync.adapters.vanillasoft.client import (  # noqa: E402
    VanillaSoftClient,
    normalize_api_base,
    require_secure_endpoint,
)
from plasticos_gate.services.gate_builders import build_converge_request  # noqa: E402

ORCHESTRATOR = ROOT / "plasticos_crm_sync/services/orchestrator.py"
CONNECTION = ROOT / "plasticos_crm_sync/models/crm_connection.py"
ENRICHMENT_RUN = ROOT / "plasticos_enrichment/models/enrichment_run.py"


def _function(path: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in {path.name}")


def _calls(node: ast.AST) -> list[str]:
    """Ordered dotted names of every call in `node`, e.g. 'self.env.cr.rollback'."""
    out = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            parts = []
            ref = child.func
            while isinstance(ref, ast.Attribute):
                parts.append(ref.attr)
                ref = ref.value
            if isinstance(ref, ast.Name):
                parts.append(ref.id)
            if parts:
                out.append(".".join(reversed(parts)))
    return out


# ── I1 — no source acknowledgement without durable consumption ──────────────


def test_malformed_contact_fails_the_page_instead_of_being_skipped():
    """A contact with no id must raise, so the page's watermark never advances."""
    client = MagicMock()
    client.get_contacts.return_value = {
        "contacts": [{"contact_id": 42}, {"company": "No Id Co"}],
        "batch_end": "2026-08-01T10:00:00Z",
        "partial_fulfillment": False,
    }
    adapter = VanillaSoftAdapter(client, 139705)
    with pytest.raises(CrmAdapterError, match="missing contact_id"):
        list(adapter.iter_contacts(modified_after="2026-07-01T00:00:00Z", limit=50))


def test_non_dict_contact_row_fails_the_page():
    client = MagicMock()
    client.get_contacts.return_value = {"contacts": [{"contact_id": 1}, "garbage"]}
    adapter = VanillaSoftAdapter(client, 139705)
    with pytest.raises(CrmAdapterError, match="expected object"):
        list(adapter.iter_contacts(modified_after="2026-07-01T00:00:00Z", limit=50))


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        ({"contact_id": 42}, "missing call_history_id"),
        ({"call_history_id": 9}, "missing contact_id"),
    ],
)
def test_call_without_identity_raises(row, expected):
    """Identity-less calls cannot be de-duplicated, so they fail the window."""
    with pytest.raises(CrmAdapterError, match=expected):
        call_to_canonical(row)


def test_malformed_call_fails_the_whole_window():
    client = MagicMock()
    client.get_call_history_batch.return_value = {
        "call_histories": [
            {"call_history_id": 9, "contact_id": 42},
            {"call_history_id": 10},
        ]
    }
    adapter = VanillaSoftAdapter(client, 139705)
    with pytest.raises(CrmAdapterError, match="missing contact_id"):
        list(adapter.iter_calls(start="2026-08-01T00:00:00Z", end="2026-08-02T00:00:00Z", limit=500))


def test_call_to_canonical_still_maps_a_valid_row():
    call = call_to_canonical({"call_history_id": 9, "contact_id": 42, "duration_seconds": 120})
    assert (call.external_id, call.contact_external_id, call.duration_seconds) == ("9", "42", 120)


# ── I1 — pagination must make progress or fail deterministically ────────────


def test_non_advancing_partial_cursor_raises_instead_of_looping():
    """batch_end == cursor with partial_fulfillment would refetch page 1 forever."""
    client = MagicMock()
    client.get_contacts.return_value = {
        "contacts": [{"contact_id": 1, "modified_date_time_utc": "2026-08-01T10:00:00Z"}],
        "batch_end": "2026-07-01T00:00:00Z",
        "partial_fulfillment": True,
    }
    adapter = VanillaSoftAdapter(client, 139705)
    with pytest.raises(CrmAdapterError, match="failed to advance"):
        list(adapter.iter_contacts(modified_after="2026-07-01T00:00:00Z", limit=50))


def test_backwards_partial_cursor_raises():
    client = MagicMock()
    client.get_contacts.return_value = {
        "contacts": [{"contact_id": 1}],
        "batch_end": "2026-06-01T00:00:00Z",
        "partial_fulfillment": True,
    }
    adapter = VanillaSoftAdapter(client, 139705)
    with pytest.raises(CrmAdapterError, match="failed to advance"):
        list(adapter.iter_contacts(modified_after="2026-07-01T00:00:00Z", limit=50))


def test_advancing_partial_cursor_keeps_paginating():
    client = MagicMock()
    client.get_contacts.side_effect = [
        {
            "contacts": [{"contact_id": 1}],
            "batch_end": "2026-07-02T00:00:00Z",
            "partial_fulfillment": True,
        },
        {
            "contacts": [{"contact_id": 2}],
            "batch_end": "2026-07-03T00:00:00Z",
            "partial_fulfillment": False,
        },
    ]
    adapter = VanillaSoftAdapter(client, 139705)
    pages = list(adapter.iter_contacts(modified_after="2026-07-01T00:00:00Z", limit=50))
    assert [b for _leads, b, _p in pages] == ["2026-07-02T00:00:00Z", "2026-07-03T00:00:00Z"]


# ── I1 — a full call page may end pagination only when progress is proven ───
#
# `_sync_calls` advances the ENTIRE window watermark once `iter_calls` returns
# normally, so "ran out of things to yield" and "the window was fully consumed"
# are the same signal to the caller. A full page that cannot be paginated past
# must therefore raise, never break.


def _full_call_page(rows):
    client = MagicMock()
    client.get_call_history_batch.return_value = {"call_histories": rows}
    return VanillaSoftAdapter(client, 139705)


def _call_row(call_id, contact_id="42", ts="2026-08-01T12:00:00Z"):
    return {"call_history_id": call_id, "contact_id": contact_id, "call_date_time_utc": ts}


def test_full_call_page_without_usable_timestamp_raises():
    """500 calls, none with a timestamp: call 501 would be lost silently."""
    rows = [{"call_history_id": i, "contact_id": "42"} for i in range(1, 501)]
    with pytest.raises(CrmAdapterError, match="no usable pagination timestamp"):
        list(_full_call_page(rows).iter_calls(start="2026-08-01T00:00:00Z", end="2026-08-02T00:00:00Z", limit=500))


def test_full_call_page_with_non_advancing_timestamp_raises():
    """Every call at exactly the cursor instant — the cursor cannot move."""
    rows = [_call_row(i, ts="2026-08-01T00:00:00Z") for i in range(1, 501)]
    with pytest.raises(CrmAdapterError, match="failed to advance"):
        list(_full_call_page(rows).iter_calls(start="2026-08-01T00:00:00Z", end="2026-08-02T00:00:00Z", limit=500))


def test_full_call_page_with_backwards_timestamp_raises():
    rows = [_call_row(i, ts="2026-07-30T00:00:00Z") for i in range(1, 501)]
    with pytest.raises(CrmAdapterError, match="failed to advance"):
        list(_full_call_page(rows).iter_calls(start="2026-08-01T00:00:00Z", end="2026-08-02T00:00:00Z", limit=500))


def test_short_call_page_ends_pagination_normally():
    """The one exit that legitimately lets the caller advance the watermark."""
    adapter = _full_call_page([_call_row(1), _call_row(2)])
    batches = list(adapter.iter_calls(start="2026-08-01T00:00:00Z", end="2026-08-02T00:00:00Z", limit=500))
    assert [c.external_id for c in batches[0]] == ["1", "2"]


def test_full_call_page_with_advancing_timestamp_keeps_paginating():
    client = MagicMock()
    client.get_call_history_batch.side_effect = [
        {"call_histories": [_call_row(i, ts="2026-08-01T06:00:00Z") for i in range(1, 501)]},
        {"call_histories": [_call_row(501, ts="2026-08-01T07:00:00Z")]},
    ]
    adapter = VanillaSoftAdapter(client, 139705)
    batches = list(adapter.iter_calls(start="2026-08-01T00:00:00Z", end="2026-08-02T00:00:00Z", limit=500))
    assert [len(b) for b in batches] == [500, 1]
    # Second request resumed from the first page's last timestamp, not the start.
    assert client.get_call_history_batch.call_args_list[1].args[0] == "2026-08-01T06:00:00Z"


# ── I1 — partial contacts need a real API continuation cursor ───────────────


def test_partial_contacts_without_api_cursor_raises():
    """partial_fulfillment=true with no batch_end is a contract violation."""
    client = MagicMock()
    client.get_contacts.return_value = {
        "contacts": [{"contact_id": 1, "modified_date_time_utc": "2026-08-01T10:00:00Z"}],
        "partial_fulfillment": True,
    }
    adapter = VanillaSoftAdapter(client, 139705)
    with pytest.raises(CrmAdapterError, match="without a batch_end"):
        list(adapter.iter_contacts(modified_after="2026-07-01T00:00:00Z", limit=50))


def test_partial_contacts_never_infer_a_cursor_from_row_timestamps():
    """The refusal must happen before the page is yielded, so nothing is
    acknowledged on the strength of an inferred cursor."""
    client = MagicMock()
    client.get_contacts.return_value = {
        "contacts": [{"contact_id": 1, "modified_date_time_utc": "2026-09-01T10:00:00Z"}],
        "partial_fulfillment": True,
    }
    adapter = VanillaSoftAdapter(client, 139705)
    pages = adapter.iter_contacts(modified_after="2026-07-01T00:00:00Z", limit=50)
    with pytest.raises(CrmAdapterError):
        next(pages)
    assert client.get_contacts.call_count == 1


def test_complete_contact_page_may_still_synthesize_its_watermark():
    """A non-partial page names the last contact persisted — that is a
    watermark, not a continuation cursor, and stays supported."""
    client = MagicMock()
    client.get_contacts.return_value = {
        "contacts": [{"contact_id": 1, "modified_date_time_utc": "2026-08-01T10:00:00Z"}],
        "partial_fulfillment": False,
    }
    adapter = VanillaSoftAdapter(client, 139705)
    pages = list(adapter.iter_contacts(modified_after="2026-07-01T00:00:00Z", limit=50))
    assert pages[0][1] == "2026-08-01T10:00:00Z"
    assert pages[0][2] is False


# ── I15 — optional data may degrade; required data may never be skipped ─────


def test_custom_table_classification_is_explicit_and_optional_for_launch():
    """The launch decision is a named constant, not implicit swallow-and-continue."""
    assert vs_adapter.CUSTOM_TABLES_REQUIRED is False


def test_optional_custom_table_failure_does_not_fail_the_contact():
    client = MagicMock()
    client.get_custom_tables_list.side_effect = CrmAdapterError("custom tables 500")
    adapter = VanillaSoftAdapter(client, 139705)
    assert list(adapter.iter_table_rows("42")) == []


def test_required_custom_table_failure_propagates_when_reclassified(monkeypatch):
    monkeypatch.setattr(vs_adapter, "CUSTOM_TABLES_REQUIRED", True)
    client = MagicMock()
    client.get_custom_tables_list.side_effect = CrmAdapterError("custom tables 500")
    adapter = VanillaSoftAdapter(client, 139705)
    with pytest.raises(CrmAdapterError):
        list(adapter.iter_table_rows("42"))


# ── I2 / I3 — durable audit state and cross-transaction ordering ────────────


def test_sync_run_is_created_on_an_owned_committed_cursor():
    fn = _function(ORCHESTRATOR, "_create_sync_run_durable")
    calls = _calls(fn)
    assert "self.env.registry.cursor" in calls, "audit row must not ride the ambient RPC cursor"
    assert "cr.commit" in calls, "the sync-run must be durable before fallible remote work"


def test_run_connection_creates_the_audit_row_before_the_first_adapter_call():
    calls = _calls(_function(ORCHESTRATOR, "run_connection"))
    assert calls.index("self._create_sync_run_durable") < calls.index("adapter.healthcheck")


def test_run_connection_rolls_back_before_opening_the_failure_cursor():
    """I3: the second cursor must never update a row transaction A still holds."""
    calls = _calls(_function(ORCHESTRATOR, "run_connection"))
    assert "self.env.cr.rollback" in calls
    assert calls.index("self.env.cr.rollback") < calls.index("self._persist_sync_failure_durable")


def test_run_connection_does_not_flush_before_the_failure_cursor():
    src = ast.dump(_function(ORCHESTRATOR, "run_connection"))
    for forbidden in ("flush_recordset", "flush_model", "'flush'"):
        assert forbidden not in src, f"{forbidden} re-creates the row lock the rollback just released"


def test_failure_cursor_commits_and_browses_by_primitive_id():
    fn = _function(ORCHESTRATOR, "_persist_sync_failure_durable")
    assert [a.arg for a in fn.args.args] == ["self", "connection_id", "run_id", "excerpt"]
    calls = _calls(fn)
    assert "self.env.registry.cursor" in calls
    assert "cr.commit" in calls


def test_enrichment_rolls_back_before_persisting_failure_state():
    calls = _calls(_function(ENRICHMENT_RUN, "_rollback_then_persist_operator_state"))
    assert calls.index("self.env.cr.rollback") < calls.index("self._persist_operator_state_durable")


def test_enrichment_durable_write_no_longer_flushes():
    """The flush-then-second-cursor sequence is exactly what hung the RPC."""
    src = ENRICHMENT_RUN.read_text(encoding="utf-8")
    assert "flush_recordset" not in src
    fn = _function(ENRICHMENT_RUN, "_persist_operator_state_durable")
    calls = _calls(fn)
    assert "self.pool.cursor" in calls
    assert "cr.commit" in calls


def test_every_enrichment_failure_path_uses_the_rollback_first_helper():
    src = ENRICHMENT_RUN.read_text(encoding="utf-8")
    assert "_persist_operator_state(" not in src.replace("_rollback_then_persist_operator_state(", "").replace(
        "_persist_operator_state_durable(", ""
    )
    assert src.count("self._rollback_then_persist_operator_state(") == 4


def test_durable_failure_record_keeps_the_availability_state():
    """The ambient write of availability_status is rolled back, so every durable
    record must carry it or the operator sees a failure with no stated cause."""
    fn = _function(ENRICHMENT_RUN, "action_execute")
    durable_writes = [
        node.args[1]
        for node in ast.walk(fn)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_rollback_then_persist_operator_state"
    ]
    assert len(durable_writes) == 4, "every failure path must persist durably"
    for vals in durable_writes:
        keys = {k.value for k in vals.keys if isinstance(k, ast.Constant)}
        assert "state" in keys and "failure_class" in keys
        assert "availability_status" in keys, f"durable record missing cause: {sorted(keys)}"


# ── I5 — concurrency exclusion covers every sync entry point ────────────────


def test_run_connection_owns_the_advisory_lock():
    calls = _calls(_function(ORCHESTRATOR, "run_connection"))
    assert "self._try_advisory_lock" in calls
    assert "self._advisory_unlock" in calls


# ── I2 / I3 / I5 apply to the full import's envelope too ───────────────────
#
# `run_full_import` carries its own copy of the envelope rather than wrapping
# `run_connection`, because the ordering asserted above is the property that
# silently regresses when someone factors the two together. So it is asserted
# on both.


def test_full_import_creates_the_audit_row_before_the_first_adapter_call():
    calls = _calls(_function(ORCHESTRATOR, "run_full_import"))
    assert calls.index("self._create_sync_run_durable") < calls.index("adapter.healthcheck")


def test_full_import_rolls_back_before_opening_the_failure_cursor():
    calls = _calls(_function(ORCHESTRATOR, "run_full_import"))
    assert "self.env.cr.rollback" in calls
    assert calls.index("self.env.cr.rollback") < calls.index("self._persist_sync_failure_durable")


def test_full_import_does_not_flush_before_the_failure_cursor():
    src = ast.dump(_function(ORCHESTRATOR, "run_full_import"))
    for forbidden in ("flush_recordset", "flush_model", "'flush'"):
        assert forbidden not in src, f"{forbidden} re-creates the row lock the rollback just released"


def test_full_import_owns_the_advisory_lock():
    calls = _calls(_function(ORCHESTRATOR, "run_full_import"))
    assert "self._try_advisory_lock" in calls
    assert "self._advisory_unlock" in calls


def test_full_import_validates_every_bound_before_taking_the_lock():
    """An unusable floor must not leave a lock, an audit row or a partial run
    behind for an operator to interpret."""
    calls = _calls(_function(ORCHESTRATOR, "run_full_import"))
    assert calls.index("self._require_utc_bound") < calls.index("self._try_advisory_lock")


def test_full_import_captures_the_boundary_before_enumerating_contacts():
    """A boundary taken after enumeration would leave the bootstrap's own
    duration uncovered by either phase."""
    fn = _function(ORCHESTRATOR, "run_full_import")
    src = ast.unparse(fn)
    assert src.index("boundary = datetime.now(UTC)") < src.index("bootstrap_contacts = self._sync_contacts")


def test_cron_no_longer_carries_its_own_duplicate_lock():
    """One critical section, so cron and the manual button exclude each other."""
    src = CONNECTION.read_text(encoding="utf-8")
    assert "pg_try_advisory_lock" not in src
    assert "CrmSyncLockedError" in src


# ── I6 — canonical cross-service identity ───────────────────────────────────


class _FakeValue:
    def __init__(self, value):
        self._value = value

    def __bool__(self):
        return bool(self._value)


class _FakePartner:
    _fields: dict = {}

    def __init__(self, partner_id):
        self.id = partner_id

    def __getitem__(self, key):
        raise KeyError(key)


class _FakeRun:
    _name = "plasticos.enrichment.run"
    source_ids = ()

    def __init__(self, run_id, partner):
        self.id = run_id
        self.partner_id = partner


class _FakeEnv:
    company = _FakeValue(1)
    user = _FakeValue(2)
    cr = _FakeValue("testdb")

    def __init__(self):
        self.company = type("C", (), {"id": 1})()
        self.user = type("U", (), {"id": 2})()
        self.cr = type("R", (), {"dbname": "testdb"})()


def test_converge_request_carries_canonical_entity_id():
    request = build_converge_request(_FakeEnv(), _FakeRun(7, _FakePartner(123)))
    payload = request.to_dict()
    assert payload["entity"]["id"] == "res.partner:123"
    assert payload["entity"]["_odoo_entity_id"] == "res.partner:123"


def test_converge_request_identity_is_not_a_new_scheme():
    """Compatibility alias and canonical id must never drift apart."""
    request = build_converge_request(_FakeEnv(), _FakeRun(7, _FakePartner(999)))
    entity = request.to_dict()["entity"]
    assert entity["id"] == entity["_odoo_entity_id"]


# ── I16 — credential-bearing endpoints use TLS ──────────────────────────────


def test_https_endpoint_is_accepted():
    assert normalize_api_base("https://vanillasoft.net") == "https://vanillasoft.net/WSPubAPI"
    assert normalize_api_base("vanillasoft.net") == "https://vanillasoft.net/WSPubAPI"


def test_plaintext_production_endpoint_is_rejected():
    with pytest.raises(CrmAdapterError, match="must use https"):
        normalize_api_base("http://vanillasoft.net")


def test_client_construction_rejects_plaintext():
    with pytest.raises(CrmAdapterError, match="must use https"):
        VanillaSoftClient("test-key", "http://vanillasoft.net")


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1"])
def test_loopback_http_stays_available_for_local_stubs(host):
    assert normalize_api_base(f"http://{host}:8099") == f"http://{host}:8099/WSPubAPI"


def test_non_http_scheme_is_rejected():
    with pytest.raises(CrmAdapterError, match="must use https"):
        require_secure_endpoint("ftp://vanillasoft.net/WSPubAPI")
