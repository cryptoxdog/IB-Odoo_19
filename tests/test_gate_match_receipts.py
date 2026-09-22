"""Pure-source guards for canonical Gate matching receipts and result persistence."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ORCHESTRATOR = ROOT / "plasticos_matching/models/match_orchestrator.py"
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
