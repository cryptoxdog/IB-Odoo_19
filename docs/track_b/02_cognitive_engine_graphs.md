# 02 — Cognitive.Engine.Graphs (CEG) — BUILD SECOND

**Repo:** `Quantum-L9/Cognitive.Engine.Graphs`
**Role:** Worker for `action="match"`. Receives a `MatchRequest` payload via the Gate, scores buyers against the supplier/intake, and returns ranked candidates keyed by **Odoo `res.partner` id**.
**Why second:** `action=match` is the **Phase-1 critical path** — Track A's matcher already calls it by default (`matching_enabled=1`). Once CEG answers through the hub, Odoo's *primary* match path goes live (local becomes fallback only). It depends on a working hub (01) but is higher value than enrichment (03).

> Read [`00_AGENT_HANDOFF.md`](00_AGENT_HANDOFF.md) §3.2 for the exact request/response. Do not invent a different shape — Track A's `map_match_response` parses it as-is.

---

## Execution steps (in order, with rationale)

### Step 1 — Register CEG as a Gate worker for `action="match"`
- **Do:** Stand up the worker endpoint and register it with the Gate hub's action router (01 Step 4) as the `match` destination. Consume packets via `Gate_SDK` (same schema pin).
- **Why first:** No request reaches CEG until the hub can route to it. Establish the routed channel before any scoring logic; smoke-test with an echo response.

### Step 2 — Parse `MatchRequest.query` defensively
- **Do:** Read `query.{polymer_type, form, color, source_type, quantity_per_load_lbs, contamination_pct, mfi, lat, lon, intake_id, supplier_partner_id, mode}` and `top_n`, `match_direction`. Treat every field as optional (Odoo may send a supplier-only query with no intake).
- **Why second:** The scoring graph traversal is built from these inputs. Defensive parsing prevents worker crashes that would force Odoo into fallback for benign missing fields. Mirror the Odoo local matcher's gate semantics (null dimension = pass) for parity.

### Step 3 — Score against the graph (Stage-2 equivalent)
- **Do:** Implement the graph-based buyer scoring (the capability Odoo's in-process Neo4j scoring approximates). Produce a `score` per buyer (0–1 preferred; 0–100 also accepted — Odoo normalizes). Optionally surface `gates_passed`/`gates_failed`, `typical_price`, `reason`, `facility_profile_id`.
- **Why third:** This is CEG's core value-add over the local matcher. It depends on parsed inputs (Step 2) and must precede id-mapping (Step 4) since you score in whatever space CEG uses internally.

### Step 4 — Map candidates back to Odoo `res.partner` ids
- **Do:** Ensure each result's `buyer_partner_id` is the **Odoo partner id** Odoo recognizes. If CEG keys nodes by its own graph id, maintain a partner-id ↔ graph-node map and translate before responding.
- **Why fourth — critical:** Track A persists matches against `res.partner` and `plasticos.facility.profile`. A non-Odoo id silently produces broken match lines. Must happen after scoring, before building the response.

### Step 5 — Build the response payload + honor `top_n`
- **Do:** Emit `{status, match_direction, top_n, results:[...]}` per §3.2, truncated to `top_n` (Odoo also caps to `max_results`). Sort by score desc (Odoo re-sorts but send ordered).
- **Why fifth:** This is the exact dict `map_match_response` reads. Shape correctness here is what makes Odoo show real candidates. Depends on Steps 3–4.

### Step 6 — Respect timeout + structured errors
- **Do:** Return within the Gate/Odoo timeout (≤30s). On internal failure, return a structured error (so the hub relays an error packet and Odoo falls back to local) rather than hanging.
- **Why sixth:** Track A wraps the Gate call in try/except and falls back. A hang defeats fallback and stalls the broker UI. Build this once the happy path works.

### Step 7 — End-to-end test from Odoo
- **Do:** With hub (01) live, set `plasticos.gate.url`, leave `matching_enabled=1`, run "Match to Buyers" on a seeded intake. Verify Odoo `plasticos.match.result.score_breakdown.match_source == "gate"`, `gate_packet_id` set, and candidates resolve to real partners.
- **Why last:** This is the milestone that proves the Phase-1 primary path. Validate parity against the local matcher on a few intakes before enabling broadly.

---

## Acceptance (CEG)
- [ ] Routed `action=match` packets reach CEG and return §3.2 response.
- [ ] `buyer_partner_id` values are valid Odoo `res.partner` ids.
- [ ] `score` interpretable (0–1 or 0–100); `top_n` honored.
- [ ] Errors/timeouts structured → Odoo falls back cleanly.
- [ ] Odoo staging shows `match_source="gate"` with correct candidates.

## Guardrails
- CEG reachable **only** via the Gate hub (no direct Odoo→CEG).
- Keep the response schema stable; coordinate any change through `Gate_SDK` + Odoo re-pin.
- Parity check vs local matcher before flipping production traffic; local stays as fallback.
