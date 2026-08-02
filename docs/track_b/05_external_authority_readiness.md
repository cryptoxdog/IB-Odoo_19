# External Authority Readiness (M0 / TASK-046)

## Purpose

Prove that PlasticOS Odoo can exercise Gate-routed `match` and `converge`
actions against live constellation services without embedding CEG/EIE semantics
inside Odoo and without silent local substitution on transport failure.

## Invariants

- Gate is the only egress (`GateClient.send_to_gate`).
- Default actions remain `match` and `converge` (Gate routing authority).
- Availability is classified (`classify_gate_availability`) rather than boolean-only.
- Transport failures are classified as `retryable` / `permanent` / `unknown`.
- Owner payload schemas (CEG match request/response, EIE FeatureEvidence) remain
  the checksum authority; Odoo maps consumer contracts to those payloads.

## Validation

```bash
python3 scripts/check_external_intelligence_readiness.py \
  --owner-root "$HOME/l9-constellation-repos/Cognitive.Engine.Graphs" \
  --owner-root "$HOME/l9-constellation-repos/Enrichment.Inference.Engine"

pytest -q tests/contracts/test_external_intelligence_contract_parity.py

# Live five-service stack (Gate :9000 + registered CEG/EIE workers):
PLASTICOS_GATE_LIVE_URL=http://127.0.0.1:9000 \
PLASTICOS_GATE_ALLOW_INSECURE_HTTP=1 \
pytest -q tests/integration/test_gate_external_authority_e2e.py
```

## Evidence artifact

Controller evidence for TASK-046 must record:

- `proof_class: live_integration_proof`
- `live_five_service_stack_exercised: true` only when the live e2e above passes
- Gate/CEG/EIE/Odoo/SDK git SHAs and health endpoints
- TransportPacket correlation ids from match and converge round-trips

Never fabricate `LIVE_INTEGRATION_PASS` without the live e2e exit code 0.
