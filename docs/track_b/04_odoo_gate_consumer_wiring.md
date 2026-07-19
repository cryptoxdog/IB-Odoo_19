# 04 — Wire IB-Odoo_19 as a Gate Consumer (Odoo side)

**Target repo:** `cryptoxdog/IB-Odoo_19` · **Branch:** `feat/gate-client-matcher-fallback`
**Audience:** agent with write access to **IB-Odoo_19 only**.
**Companion (other repo, do not edit here):** EIE `action=converge` handler — `Quantum-L9/Enrichment.Inference.Engine` PR #128 (`cursor/odoo-converge-handler-66d5`), served over the SDK `/v1/execute`.

Reference constellation repos (read-only for this agent):
`Quantum-L9/Gate_SDK` (pip `constellation-node-sdk`), `Quantum-L9/Constellation.Gate` (hub), `Quantum-L9/Enrichment.Inference.Engine` (EIE), `Quantum-L9/Cognitive.Engine.Graphs` (CEG).

---

## 0. Authority model (non-negotiable)

```
Gate_SDK + Constellation.Gate + EIE/CEG  =  own transport / runtime / worker contracts
Odoo (plasticos_gate)                    =  CONSUMER that must wire correctly and ADAPT
```

**Odoo owns:** CRM domain models (`res.partner`, enrichment runs, provenance, matcher UI); *when* to call Gate (ICP flags); *how* to map Gate results into Odoo (allowlists, merge-not-overwrite, local fallback); operator UX + audit fields.

**Odoo does NOT own:** the `TransportPacket` schema (Gate_SDK); hub routing / `/v1/execute` semantics (Constellation.Gate); worker action registry + handler payloads (EIE/CEG); any direct HTTP API on EIE/CEG.

### Canonical topology
```
Odoo plasticos_gate
  → constellation_node_sdk.create_transport_packet(...)
  → GateClient.send_to_gate(packet)        # destination_node="gate" ONLY
  → Constellation.Gate  POST /v1/execute
  → route by header.action
        ├─ "match"    → CEG  /v1/execute
        └─ "converge" → EIE  /v1/execute
  ← response TransportPacket (payload + header.packet_id/correlation_id)
  → Odoo applies allowlisted fields / matcher results  OR  falls back local
```

**Hard rule (ADR-002):** never Odoo → EIE/CEG direct HTTP; never import EIE/CEG code into Odoo models.

---

## 1. Mission

Make IB-Odoo_19 a correct Gate **consumer**:
1. `constellation-node-sdk` installed + pinned in the Odoo runtime.
2. `plasticos_gate` is the **sole** SDK import seam and only talks to Constellation.Gate.
3. `converge` (enrichment) and `match` (matching) paths operate when `plasticos.gate.url` is set.
4. Odoo request builders / response mappers **adapt to the live worker contracts** (EIE for converge, CEG for match).
5. Preserve **try-Gate → local-fallback**; never hang; never hard-break ERP flows when Gate is down.

Do **not** redesign Gate_SDK / Constellation.Gate / EIE from this repo.

---

## 2. Current Track A state (audit, don't rebuild)

Addon `plasticos_gate`: `gate_client.py` (sole SDK import + `send_to_gate`), `gate_config.py` (ICP + `GateClientConfig`), `gate_contracts.py`, `gate_builders.py`, `gate_mappers.py`, `gate_allowlists.py`, `data/gate_icp_seed.xml`.

SDK pin (`requirements.txt`): `constellation-node-sdk @ git+https://github.com/Quantum-L9/Gate_SDK.git@ab9df5f15c1ba433c3f072a1ca01052584682758` — keep the SHA in **lockstep** across Odoo / Gate / EIE.

Call sites: enrichment `plasticos.enrichment.run._run_gate_converge()` (`converge` → EIE); matcher (`match` → CEG). Enrichment tries Gate then falls back to local crawl/extract/inject.

### Seeded ICPs
| Key | Default | Meaning |
|-----|---------|---------|
| `plasticos.gate.url` | `""` | Hub base URL; empty ⇒ Gate off |
| `plasticos.gate.local_node` | `odoo` | `source_node`/`reply_to` |
| `plasticos.gate.matching_enabled` | `1` | Match via Gate when URL+SDK ok |
| `plasticos.gate.matching_action` | `match` | header.action for matching |
| `plasticos.gate.enrichment_enabled` | `1` | Converge via Gate when URL+SDK ok |
| `plasticos.gate.enrichment_action` | `converge` | header.action for enrichment |
| `plasticos.gate.auto_writeback` | `1` | Live partner writeback (merge-not-overwrite) |
| `plasticos.gate.timeout_seconds` | `30` | Client timeout |
| `plasticos.gate.org_id` | `""` | Tenant; falls back to `env.cr.dbname` |

---

## 3. Execution checklist (in order)

1. **Confirm runtime has Gate_SDK** — `python -c "import constellation_node_sdk; from constellation_node_sdk import GateClient, create_transport_packet, GateClientConfig"`. Manifest keeps `external_dependencies: {"python": ["constellation_node_sdk"]}`. Do **not** vendor the SDK, add a second import site, or call worker URLs with httpx/requests.
2. **Audit the sole-seam client** (`gate_client.py`) — only SDK import; builds packet with `destination_node="gate"` (never a worker host); sends via `GateClient(config).send_to_gate`; returns `{"packet": response_packet, "payload": dict(response_packet.payload)}`; raises `GateIntegrationError` on transport failure so callers fall back.
3. **Wire ICP + install (staging)** — install/upgrade `plasticos_gate` + `plasticos_enrichment`; set `plasticos.gate.url = https://<gate-host>`; enablement helpers return True only when URL valid + SDK importable + flag truthy.
4. **Align converge with live EIE contract** — see §4.
5. **Align match with CEG** — keep `action=match`, require `buyer_partner_id`/`buyer_id` before writing matcher rows, preserve Gate→local fallback. Don't break the shared `gate_client.py` seam.
6. **Reject forbidden surfaces** — see §6.
7. **Staging e2e (converge)** — see §7.
8. **Docs framing** — Gate_SDK/Gate/EIE own transport; Odoo consumes/adapts. Document the payloads Odoo emits/reads as the **Odoo client contract**, not as ownership of worker internals.

---

## 4. Converge alignment with live EIE (EIE PR #128)

EIE ingress is `POST /v1/execute` with `header.action == "converge"`. Odoo is **not** a direct `/v1/converge` consumer.

**Request Odoo sends** (`ConvergeRequest.to_dict()`): `entity_id="res.partner:<id>"` (required, echoed back), `domain` (default `plasticos`), optional `entity_snapshot.{name,website,city,zip,street,street2,comment,email,phone,source_urls}`, `odoo` audit context, optional `profile_id`, optional `max_passes`. (This is EIE's **partner-snapshot** converge form — never the legacy internal `EnrichRequest` `entity/object_type/objective` form.)

**Response Odoo reads** (`map_converge_response`): `{run_id, status, pass_count, final_fields, writeback{partner_fields?}, total_tokens, total_cost_usd}`.

**Odoo application rules** (`gate_mappers.py` / `enrichment_run.py`):
- `partner_writeback_from_converge`: prefer non-empty `writeback.partner_fields`, else `final_fields`; keep only allowlist (§6); drop `null/false/""`.
- Audit from **header**: `gate_packet_id ← header.packet_id`, `gate_correlation_id ← header.correlation_id`.
- **`status != "ok"` ⇒ failure ⇒ local fallback** (never mark `injected` on junk).
- **No writable allowlisted fields ⇒ fall back** (do not fake `fields_written>0`).
- `auto_writeback=1` ⇒ merge-not-overwrite onto `res.partner` (blank fields only) + provenance rows + `state=injected`, `engine_used=gate`.
- `auto_writeback=0` ⇒ store proposal, `state=review`, no partner writes.
- Transport/SDK/hub failures ⇒ exceptions ⇒ local fallback.

Agent tasks: diff builders/mappers against the above; ensure `_run_gate_converge` uses `send_converge_action` (not raw HTTP) with a stable `correlation_id` (`plasticos.enrichment.run:<id>`); never point ICP/code at an EIE base URL.

---

## 6. Forbidden surfaces (reject on sight)

Direct HTTP to EIE/CEG (`/v1/converge`, `/api/v1/enrich*`, worker `/v1/execute`); `destination_node="enrichment-engine"` from Odoo; importing EIE/CEG Python into Odoo; new SDK import sites outside `gate_client.py`; unilateral `TransportPacket` field invention.

Partner writeback allowlist (CRM hard boundary): `name, website, city, zip, street, street2, email, phone` — ignore unknown keys, drop empties, merge-not-overwrite, live by default.

```bash
rg -n "Enrichment\.Inference|/v1/converge|/api/v1/enrich|destination_node\s*=\s*[\"']enrichment" -g'*.py'
rg -n "import constellation_node_sdk|from constellation_node_sdk" -g'*.py'   # expect: gate_client.py (+ gate_config TYPE_CHECKING/availability)
rg -n "httpx\.|requests\.(get|post)" plasticos_gate plasticos_enrichment -g'*.py'  # local crawler only, never workers
```

---

## 7. Staging e2e (converge) + failure matrix

Prereqs (other repos): Constellation.Gate reachable; EIE registered for `action=converge`; same Gate_SDK SHA everywhere.

Steps: set `plasticos.gate.url`; create `res.partner` with blank `website`/`city` + an enrichment source URL; run `plasticos.enrichment.run.action_execute`. Expect `engine_used="gate"`, `state="injected"`, `fields_written>0`, `gate_packet_id`/`gate_correlation_id` set, blank fields filled (non-blank untouched), provenance rows `target_model="res.partner"`.

| Condition | Odoo behavior |
|-----------|---------------|
| URL empty / SDK missing / `enrichment_enabled=0` | skip Gate → local |
| Gate conn error / timeout / hub unroutable / EIE exception | catch → local fallback (log warning) |
| status ok, `auto_writeback=1`, fields present | `injected` + partner write + provenance |
| status ok, `auto_writeback=0` | `review` + proposal stored, no writes |
| status ok, zero allowlisted fields | do **not** fake success → local fallback |
| non-ok status | failure → local fallback |

Never block the HTTP worker indefinitely; honor `plasticos.gate.timeout_seconds`.

---

## 8. Definition of done (Odoo agent)

- SDK installs at the locked SHA; `plasticos_gate` is the sole seam; `destination_node="gate"` only; no Odoo→EIE/CEG HTTP.
- With hub+EIE live + URL set: converge yields `engine_used="gate"`, `state="injected"`, `fields_written>0` on blank website/city, provenance rows, header-sourced audit ids.
- Gate down → local fallback without `UserError` (unless local also lacks sources); `auto_writeback=0` → review-only verified; merge-not-overwrite verified; non-ok/empty → fallback verified.
- `tests/test_gate_enrichment_fallback.py` (+ match tests) pass; no docs instruct pointing Odoo at EIE direct URLs.

## 9. Out of scope for this agent
EIE `handle_converge` (EIE repo / PR #128); Constellation.Gate routing; Gate_SDK schema changes (multi-repo pin bump); Phase-3 Gate web-lead triage (stays local); CEG match algorithms.

## 10. One-line summary
Install/pin Gate_SDK, talk **only** to Constellation.Gate with `action=converge|match`, adapt Odoo builders/mappers to the live EIE/CEG payloads, keep local fallback — never call EIE/CEG directly.
