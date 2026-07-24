# 01 — Constellation.Gate (Gate hub) — BUILD FIRST

**Repo:** `Quantum-L9/Constellation.Gate`
**Role:** Mandatory transport hub. Accepts TransportPackets from Odoo's `constellation_node_sdk`, validates/signs, and **routes by `action`** to the correct worker (CEG/EIE), then returns the worker's response packet.
**Why first:** CEG (02) and EIE (03) register *to* the hub and are only reachable *through* it. Without a live hub there is no endpoint for Odoo's SDK to post to and nothing to integration-test. This is the single egress/ingress point ADR-002 mandates.

> Read [`00_AGENT_HANDOFF.md`](00_AGENT_HANDOFF.md) §3 for the exact packet contract before step 1.

---

## Execution steps (in order, with rationale)

### Step 1 — Pin the shared packet schema (`Gate_SDK`)
- **Do:** Make the hub depend on the same `Quantum-L9/Gate_SDK` version Odoo pins (`constellation-node-sdk`). Use the SDK's `TransportPacket`, `create_transport_packet`, validation, and signing helpers as the single source of truth.
- **Why first:** Every later step (validation, routing, response) is defined by the packet schema. If the hub and Odoo drift on the schema, nothing round-trips. Lock it before writing handlers.

### Step 2 — Expose the ingress endpoint the SDK posts to
- **Do:** Implement the HTTP server endpoint that `GateClient.send_to_gate(packet)` targets (the path/verb the SDK uses against `gate_url`). Accept the packet body, deserialize via SDK.
- **Why second:** This is the contact surface for `plasticos.gate.url`. Until it answers, Odoo's client times out and falls back to local. Stand it up before routing logic so you can smoke-test connectivity with a stub 200.

### Step 3 — Inbound validation + auth/tenant context
- **Do:** Run SDK inbound validation (`validate_transport_packet` / equivalent) and verify signature. Parse `tenant` (`actor/on_behalf_of/originator/org_id/user_id`) and `source_node="odoo"`. Reject malformed/forbidden packets with a structured error packet (not a bare 500).
- **Why third:** Routing untrusted/garbage packets to workers is unsafe. Validation must gate routing. Tenant context is needed downstream for multi-tenant isolation and audit.

### Step 4 — Action router (`match` → CEG, `converge` → EIE)
- **Do:** Map `header.action` → destination worker. Maintain a registry/config of worker nodes and their addresses. For unknown actions return a structured "unroutable" error packet.
- **Why fourth:** This is the hub's core job and the seam 02/03 plug into. It depends on a validated packet (Step 3) and a known schema (Step 1). Start with `match` only; add `converge` when EIE exists.

### Step 5 — Outbound to worker + response relay (preserve correlation)
- **Do:** Forward the (re-signed if required) packet to the chosen worker, await its response packet, and relay it back to Odoo. **Preserve `correlation_id`** and populate `header.packet_id` on the response. Enforce a timeout ≤ Odoo's `plasticos.gate.timeout_seconds` (default 30s) and return a structured timeout error packet on overrun.
- **Why fifth:** The response shape and correlation/packet ids are exactly what Track A reads for audit (`gate_packet_id`, `gate_correlation_id`). Getting this wrong silently breaks Odoo audit even when matching "works".

### Step 6 — Observability + structured errors
- **Do:** Log per-packet: `correlation_id`, `action`, `source_node`, tenant `org_id`, latency, worker, outcome. Emit metrics (prometheus-client is already a Gate_SDK dep). Ensure **all** failure modes (validation, unroutable, worker down, timeout) return a well-formed error packet so Odoo can catch and fall back.
- **Why sixth:** ADR-002 makes Gate the single observability point. Track A's graceful fallback depends on receiving an error (or timeout) rather than a hang/crash.

### Step 7 — Deploy + connectivity smoke test
- **Do:** Deploy to a reachable host. From Odoo staging set `plasticos.gate.url` and run a packet through with CEG stubbed (or a hub-level echo for `match`). Confirm a valid response packet returns and Odoo records `match_source="gate"`.
- **Why last:** End-to-end reachability is the milestone that unblocks 02 integration. Do it before CEG real logic so failures are isolated to transport.

---

## Acceptance (Gate hub)
- [ ] SDK packet from Odoo is accepted, validated, signature-checked.
- [ ] `action=match` routes to the configured CEG node; `action=converge` routes to EIE.
- [ ] Response packet preserves `correlation_id` and sets `packet_id`.
- [ ] Timeout ≤ 30s; all errors return structured error packets (no hangs).
- [ ] Metrics/logs per packet with correlation id.
- [ ] Odoo staging round-trip green with a stub worker.

## Guardrails
- Never let workers be reachable except through the hub (ADR-002).
- Do not change the packet schema unilaterally — bump `Gate_SDK` and re-pin in Odoo `requirements.txt` together.
