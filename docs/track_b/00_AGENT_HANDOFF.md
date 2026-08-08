# Track B — Agent Handoff (Gate hub + CEG + EIE)

**Status: OPEN — not fully executed.** Session-load TODO: [`memory-bank/tasks.md`](../../memory-bank/tasks.md) § "OPEN — Track B". Partial proof only (`LIVE_TRANSPORT_ROUNDTRIP_PASS`); full `LIVE_INTEGRATION_PASS` still required — see [`05_external_authority_readiness.md`](05_external_authority_readiness.md).

**One handoff for all three external repos.** Read this first, then execute the per-repo files in numeric order: `01` → `02` → `03`.

> Authority: [`docs/adr/ADR-002-gate-hub-phased-autonomy.md`](../adr/ADR-002-gate-hub-phased-autonomy.md), [`docs/GATE_AUTONOMY_ROADMAP.md`](../GATE_AUTONOMY_ROADMAP.md).
> **Authority model (see [`04_odoo_gate_consumer_wiring.md`](04_odoo_gate_consumer_wiring.md) §0):** the **wire format and worker contracts are owned by Gate_SDK / Constellation.Gate / EIE / CEG**. Odoo (`plasticos_gate`) is a **consumer that adapts** to them — it does not own the transport. The payload shapes below are the shapes Odoo currently **emits/reads as a client**; when a worker's live contract differs, **Odoo adapts** (bump `Gate_SDK` + re-pin all nodes for schema changes).

---

## 1. What already exists (Track A — do not rebuild)

PlasticOS Odoo (`cryptoxdog/IB-Odoo_19`) ships a thin client addon `plasticos_gate` that:

- Imports **only** `constellation_node_sdk` (pip: `constellation-node-sdk`, repo `Quantum-L9/Gate_SDK`).
- Builds a **TransportPacket** via `create_transport_packet(...)` and sends it with `GateClient(config).send_to_gate(packet)` (async, bridged to sync).
- Targets `destination_node="gate"`, `source_node="odoo"`.
- Sends `action="match"` for buyer matching (primary path, enabled by default when URL set).
- Sends `action="converge"` for enrichment (**live by default** — enabled when URL set; results are auto-written to the partner).
- Reads the response **`payload`** dict and **`header.packet_id` / `header.correlation_id`** for audit.
- On Gate unreachable/disabled/error: Odoo **fails closed** with classified run state (retryable/permanent/degraded) — local matcher/enrichment engines were **retired (M7)** and are not architectural fallback. See [`ADR-003-single-external-intelligence-authority.md`](../adr/ADR-003-single-external-intelligence-authority.md) and proposed **ADR-013** in the [architecture convergence backlog](../adr/PROPOSED-ADR-BACKLOG-2026-08-architecture-convergence.md).

**Implication:** Track B is the intelligence path. Without Gate+workers, match/enrichment actions surface operator-visible failure — they do not silently score locally.

> **Stale note:** Older drafts of this handoff said “always falls back to a local engine.” That sentence is **superseded**.

---

## 2. Topology & build order (why this order)

```
Odoo (Track A) ──TransportPacket──► [01] Gate hub ──routes by action──► [02] CEG (action=match)
               ◄──TransportPacket──            ◄──                     └─► [03] EIE (action=converge)
```

| Order | Repo | Why it must come at this position |
|-------|------|-----------------------------------|
| **01** | `Quantum-L9/Constellation.Gate` (Gate hub) | Nothing can be routed until the hub accepts packets and exposes the endpoint Odoo's SDK posts to. CEG/EIE register **to** it. Build + deploy the hub first or you cannot integration-test 02/03 end-to-end. |
| **02** | `Quantum-L9/Cognitive.Engine.Graphs` (CEG) | This is the **Phase-1 critical path** (`action=match`). Track A's matcher already calls it by default. Building CEG second makes Track A's primary match path live and is the milestone that delivers user value. |
| **03** | `Quantum-L9/Enrichment.Inference.Engine` (EIE) | `action=converge` is **live by default in Odoo** (auto-writeback ON). Build last (match is higher business priority), but EIE **must** expose a `converge` handler — Odoo applies the returned fields to the partner immediately. |

**Hard rule (ADR-002):** Odoo → CEG/EIE direct HTTP is forbidden. Everything goes Odoo → Gate → worker. CEG/EIE must only ever be reachable *through* the Gate.

---

## 3. The wire contract (as Odoo emits/reads it — Gate_SDK is the schema owner)

### 3.1 TransportPacket envelope

Track A calls:

```python
create_transport_packet(
    action=<"match"|"converge">,
    payload=<dict, see 3.2/3.3>,
    tenant={                       # ensure_tenant_context input
        "actor": <org_id|db_name>,
        "on_behalf_of": <org_id|db_name>,
        "originator": "odoo",
        "org_id": <org_id|db_name>,
        "user_id": "<odoo uid>",
    },
    source_node="odoo",
    destination_node="gate",
    reply_to="odoo",
    correlation_id=<"model:record_id" or None>,
    classification="internal",
    compliance_tags=("ERP","MATCHING") | ("ERP","ENRICHMENT"),
)
```

The **response packet** Track A reads must expose:
- `response_packet.payload` → dict (the worker result; see 3.2/3.3 response shapes)
- `response_packet.header.packet_id` → str (stored as `gate_packet_id`)
- `response_packet.header.correlation_id` → str (stored as `gate_correlation_id`)

> Keep `correlation_id` stable round-trip so Odoo audit ties request↔response.

### 3.2 `action="match"` (CEG)

**Request `payload`** (from `MatchRequest.to_dict()`):

```jsonc
{
  "query": {
    "polymer_type": "HDPE",          // intake.polymer_id.code (may be name)
    "form": "PELLET",                // intake.form_id.code
    "color": "NAT",                  // intake.color_id.code
    "source_type": "PCR",            // intake.source_type_id.code
    "quantity_per_load_lbs": 40000.0,
    "contamination_pct": 2.5,
    "mfi": 0.8,                       // from intake.mfi_value
    "lat": 35.0, "lon": -80.0,
    "intake_id": 42,
    "supplier_partner_id": 99,
    "mode": "strict"                 // or "relaxed"
  },
  "match_direction": "intake_to_buyer",
  "top_n": 20,
  "odoo": { "model": "plasticos.intake", "record_id": 42,
            "company_id": 1, "user_id": 2, "db_name": "...", "correlation_id": "plasticos.intake:42" }
}
```

Some fields may be absent if the intake lacks them; treat all `query.*` as optional except do your best with what is present. When Odoo has no intake, it sends only `{"supplier_partner_id": <id>, "mode": ...}`.

**Response `payload`** (what `map_match_response` consumes):

```jsonc
{
  "status": "ok",
  "match_direction": "intake_to_buyer",
  "top_n": 20,
  "results": [
    {
      "buyer_partner_id": 7,          // REQUIRED (alias "buyer_id" accepted). Must be an Odoo res.partner id.
      "buyer_name": "Buyer Co",       // optional
      "facility_profile_id": 3,       // optional (Odoo plasticos.facility.profile id)
      "score": 0.85,                  // 0–1 OR 0–100 (Odoo divides by 100 if >1)
      "reason": "Strong polymer+geo fit",  // optional (alias "match_reason")
      "typical_price": 0.42,          // optional (alias "price_anchor")
      "gates_passed": 8,              // optional (int or list)
      "gates_failed": ["gate_3"]      // optional (list)
    }
  ]
}
```

> **Critical:** `buyer_partner_id` MUST be a real Odoo `res.partner` id. CEG must key candidates on the partner id Odoo sent / knows. If CEG works in its own graph id space, it must map back to Odoo partner ids before responding.

### 3.3 `action="converge"` (EIE)

**Request `payload`** (from `ConvergeRequest.to_dict()`):

```jsonc
{
  "entity_id": "res.partner:55",
  "domain": "plasticos",
  "entity_snapshot": {
    "name": "Acme Recycling", "website": "https://acme.example",
    "city": "Charlotte", "zip": "28202", "street": "1 Polymer Way",
    "source_urls": ["https://acme.example/about"]
    // any of: street2, comment, email, phone when present
  },
  "odoo": { "model": "plasticos.enrichment.run", "record_id": 7, ... },
  "max_passes": null
}
```

**Response `payload`** (what `map_converge_response` consumes):

```jsonc
{
  "run_id": "eie-...", "status": "ok", "pass_count": 2,
  "final_fields": { "website": "https://acme-new.example", "city": "Raleigh" },
  "writeback": { "partner_fields": { ... } },   // optional; if present, partner_fields wins
  "total_tokens": 1234, "total_cost_usd": 0.05
}
```

> Odoo **applies the result live** (auto-writeback ON by default) but only for **allowlisted partner fields**: `name, website, city, zip, street, street2, email, phone`. Writeback is **merge-not-overwrite** (existing partner values are never clobbered; only blanks are backfilled). Every write is recorded in `plasticos.enrichment.provenance` (`target_model="res.partner"`). Anything outside the allowlist is ignored on the Odoo side. Setting `plasticos.gate.auto_writeback=0` reverts to review-only (proposal stored, `state="review"`, no writes).

---

## 4. Environment / config Odoo already exposes

Set on the Odoo side once Gate is reachable (`ir.config_parameter`):

| Key | Default | Meaning for Track B |
|-----|---------|---------------------|
| `plasticos.gate.url` | *(empty)* | Where the SDK posts. Must point at the deployed Gate hub. |
| `plasticos.gate.local_node` | `odoo` | `source_node` in packets. |
| `plasticos.gate.matching_enabled` | `1` | Match attempted when URL set. |
| `plasticos.gate.matching_action` | `match` | Action string Gate routes to CEG. |
| `plasticos.gate.enrichment_enabled` | `1` | Converge attempted when URL set (live by default). |
| `plasticos.gate.enrichment_action` | `converge` | Action string Gate routes to EIE. |
| `plasticos.gate.auto_writeback` | `1` | Apply converge fields to the partner live. `0` → review-only. |
| `plasticos.gate.org_id` | *(empty → db name)* | Tenant id. |
| `plasticos.gate.timeout_seconds` | `30` | SDK client timeout — workers should respond within this. |

SDK pinned in Odoo `requirements.txt`:
`constellation-node-sdk @ git+https://github.com/Quantum-L9/Gate_SDK.git@<sha>`. Track B must build against the **same SDK version/packet schema**.

---

## 5. Definition of done (all three)

1. Gate hub deployed and reachable; SDK `send_to_gate` round-trips a signed/validated packet.
2. `action=match` routes to CEG; CEG returns the 3.2 response; Odoo "Match to Buyers" shows `score_breakdown.match_source == "gate"` and `gate_packet_id` populated.
3. `action=converge` routes to EIE; Odoo enrichment run shows `engine_used == "gate"`, `state == "injected"`, `fields_written > 0`, and the allowlisted fields are live on the partner (with `plasticos.enrichment.provenance` rows). With `auto_writeback=0`, `state == "review"` and a `gate_proposal` is stored instead.
4. Worker outage → Gate returns an error/timeout → Odoo **fails closed** with classified run state (`retryable` / `permanent` / `degraded`) — no silent local score substitution (M7).
5. `correlation_id` is preserved request→response for every action.

## 6. Validation snippet (run from Odoo after each milestone)

```bash
# In Odoo shell / staging, set the URL then trigger from UI:
#   plasticos.gate.url = https://<gate-host>
#   Match to Buyers on an intake  -> expect match_source="gate"
#   (EIE) run enrichment (enrichment_enabled=1 by default) -> engine_used="gate", state="injected", partner fields backfilled
```

Per-repo step-by-step build instructions follow in `01`/`02`/`03`.
