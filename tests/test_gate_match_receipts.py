"""Pure-source guards for canonical Gate matching receipts and result persistence."""

from __future__ import annotations

import ast
import hashlib
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ORCHESTRATOR = ROOT / "plasticos_matching/models/match_orchestrator.py"
INTAKE_EXTENSION = ROOT / "plasticos_matching/models/intake_extension.py"
RUN = ROOT / "plasticos_matching/models/match_run.py"
WRITER = ROOT / "plasticos_matching/models/match_result_writer.py"
CLIENT = ROOT / "plasticos_gate/services/gate_client.py"


def test_gate_match_run_has_durable_request_and_response_receipt_fields():
    source = RUN.read_text(encoding="utf-8")
    for field_name in (
        "request_attempt",
        "operation_id",
        "request_fingerprint",
        "gate_response_digest",
        "gate_query_id",
        "gate_contract_version",
        "gate_domain_spec_version",
        "gate_model_version",
    ):
        assert field_name in source


def test_orchestrator_records_receipt_before_mapping_and_preserves_zero_match_audit():
    source = ORCHESTRATOR.read_text(encoding="utf-8")
    assert "send_match_action(" in source
    assert "idempotency_key=operation_id" in source
    assert 'extract_audit_metadata(gate_result["packet"])' in source
    assert "gate_response_digest" in source
    assert '"gate_packet_id": audit["gate_packet_id"]' in source
    response_receipt_start = source.index("gate_response_digest")
    assert "if matches:" not in source[response_receipt_start : source.index("return run, matches")]


def test_canonical_result_writer_is_gate_only_and_receipt_bound():
    source = WRITER.read_text(encoding="utf-8")
    assert '_name = "plasticos.match.result.writer"' in source
    assert "match_run.operation_id" in source
    assert "match_run.gate_response_digest" in source
    assert "Result.sudo().create" in source
    assert "_find_matches_local" not in source
    assert "find_matches_for_supplier" not in source


def test_match_client_forwards_business_idempotency_to_single_gate_egress():
    source = CLIENT.read_text(encoding="utf-8")
    send_match_start = source.index("def send_match_action")
    send_converge_start = source.index("def send_converge_action")
    section = source[send_match_start:send_converge_start]
    assert "idempotency_key: str | None = None" in section
    assert "idempotency_key=idempotency_key" in section


# ── F192-01 — failure receipts survive the request rollback (ordering contract) ──
#
# Asserted structurally over the AST, exactly as I2/I3 are for crm_sync and
# enrichment: rollback precedes the owned cursor, no flush in between, every
# failure path goes through the one durable helper. Real cross-session
# durability is a runtime gate (C9/C10 in docs/runbooks/LAUNCH_GATES.md).


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


def test_orchestrator_rolls_back_before_persisting_the_failure_receipt():
    calls = _calls(_function(ORCHESTRATOR, "_rollback_then_persist_failed_run_durable"))
    assert calls.index("self.env.cr.rollback") < calls.index("self._persist_failed_run_durable")


def test_durable_failure_write_uses_an_owned_committed_cursor_and_never_flushes():
    source = ORCHESTRATOR.read_text(encoding="utf-8")
    for forbidden in ("flush_recordset", "flush_model", "flush_all"):
        assert forbidden not in source, f"{forbidden} re-creates the row lock the rollback just released"
    fn = _function(ORCHESTRATOR, "_persist_failed_run_durable")
    assert [a.arg for a in fn.args.args] == ["self", "run_id", "vals"], "primitives only across the rollback"
    calls = _calls(fn)
    assert "self.pool.cursor" in calls
    assert "cr.commit" in calls
    assert "message_post" in " ".join(calls), "the operator note must ride the committed cursor"


def test_every_failure_path_persists_durably_with_its_cause():
    tree = ast.parse(ORCHESTRATOR.read_text(encoding="utf-8"))
    durable_writes = [
        node.args[1]
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_rollback_then_persist_failed_run_durable"
    ]
    # disabled, GateIntegrationError, UserError/ValidationError, unexpected, result persistence
    assert len(durable_writes) == 5, "every failure path must persist durably"
    for vals in durable_writes:
        assert isinstance(vals, ast.Dict)
        keys = {k.value for k in vals.keys if isinstance(k, ast.Constant)}
        assert {"state", "failure_class", "error_message"} <= keys, sorted(keys)
        # identity, availability status and captured receipt ride in through **base_vals / **receipt / **snapshot
        assert None in vals.keys, "durable record must carry the run identity and availability status"


def test_intake_action_writes_nothing_before_re_raising():
    """A chatter post inside the except branch rides the transaction the re-raise rolls back."""
    fn = _function(INTAKE_EXTENSION, "action_match_to_buyers")
    handlers = [node for node in ast.walk(fn) if isinstance(node, ast.ExceptHandler)]
    assert len(handlers) == 1
    body = handlers[0].body
    assert len(body) == 1 and isinstance(body[0], ast.Raise) and body[0].exc is None
    assert "message_post" not in _calls(handlers[0])


# ── F192-04 — receipt metadata is server-owned, write-once evidence ──


def _receipt_fields_declared() -> tuple[str, ...]:
    tree = ast.parse(RUN.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "RECEIPT_FIELDS" for t in node.targets
        ):
            assert isinstance(node.value, ast.Tuple)
            return tuple(elt.value for elt in node.value.elts if isinstance(elt, ast.Constant))
    raise AssertionError("RECEIPT_FIELDS not declared")


def test_match_run_receipt_fields_are_guarded_readonly_and_never_copied():
    source = RUN.read_text(encoding="utf-8")
    fields_declared = _receipt_fields_declared()
    assert set(fields_declared) == {
        "request_attempt",
        "operation_id",
        "request_fingerprint",
        "gate_packet_id",
        "gate_correlation_id",
        "gate_query_id",
        "gate_contract_version",
        "gate_domain_spec_version",
        "gate_model_version",
        "gate_response_digest",
    }
    tree = ast.parse(source)
    declarations = {}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and isinstance(node.value.func.value, ast.Name)
            and node.value.func.value.id == "fields"
        ):
            declarations[node.targets[0].id] = {
                kw.arg: kw.value.value for kw in node.value.keywords if isinstance(kw.value, ast.Constant)
            }
    for name in fields_declared:
        assert declarations[name].get("readonly") is True, name
        assert declarations[name].get("copy") is False, name
    assert "RECEIPT_WRITE_CONTEXT" in source
    assert "AccessError" in source
    for method in ("create", "write"):
        assert "self.browse()._check_receipt_write" in ast.unparse(_function(RUN, method)) or (
            "self._check_receipt_write" in ast.unparse(_function(RUN, method))
        ), method


def test_orchestrator_is_the_only_receipt_writer():
    """The door is opened in exactly one addon file: the orchestrator."""
    matching_models = ROOT / "plasticos_matching/models"
    openers = [
        path.name
        for path in matching_models.glob("*.py")
        if "RECEIPT_WRITE_CONTEXT: True" in path.read_text(encoding="utf-8")
    ]
    assert openers == ["match_orchestrator.py"], openers


# ── U192-01 — digest determinism evidence (float rounding review concern) ──


def _load_canonical_digest():
    tree = ast.parse(ORCHESTRATOR.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_canonical_digest")
    namespace: dict[str, object] = {"hashlib": hashlib, "json": json}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(ORCHESTRATOR), "exec"), namespace)  # noqa: S102
    return namespace["_canonical_digest"]


def test_canonical_digest_is_stable_over_normalized_input_and_rejects_nan():
    digest = _load_canonical_digest()
    payload = {"candidates": [{"score": 0.85, "entity_ref": "res.partner:7", "eligible": True}], "query_id": "q-1"}
    reordered = {
        "query_id": "q-1",
        "candidates": [{"eligible": True, "entity_ref": "res.partner:7", "score": 85 / 100}],
    }
    assert digest(payload) == digest(reordered)
    # A stored-and-replayed payload (JSON round trip) is the same evidence.
    assert digest(json.loads(json.dumps(payload))) == digest(payload)
    assert digest({**payload, "query_id": "q-2"}) != digest(payload)
    with pytest.raises(ValueError):
        digest({"score": math.nan})
