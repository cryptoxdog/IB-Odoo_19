# 03 — Enrichment.Inference.Engine (EIE) — BUILD THIRD (LAST)

**Repo:** `Quantum-L9/Enrichment.Inference.Engine`
**Role:** Worker for `action="converge"`. Receives a `ConvergeRequest` (partner snapshot + source URLs), performs CRM/material field backfill (e.g. Perplexity + inference, optionally collaborating with CEG graph context internally), and returns `final_fields` / `writeback`.
**Contract ownership:** EIE owns the `converge` handler and its payload contract (shipped in `Quantum-L9/Enrichment.Inference.Engine` PR #128, served over the SDK `/v1/execute`). Odoo is a **consumer that adapts** its builders/mappers to EIE's live contract — it does not dictate it. The shapes below are what Odoo currently emits/reads; reconcile against EIE's live handler and adapt the Odoo side if they differ. (`process_web_lead` / `process_intake` are separate EIE actions, not this path.)
**Why last:** Match (02) is higher business priority, so build EIE after the match path is live. But `action=converge` is **live by default** in Odoo (`plasticos.gate.enrichment_enabled=1`, `plasticos.gate.auto_writeback=1`): Odoo **applies** the returned allowlisted fields to the partner immediately (merge-not-overwrite, with provenance). EIE output goes straight into the CRM — return only confidently-resolved values.

> Read [`00_AGENT_HANDOFF.md`](00_AGENT_HANDOFF.md) §3.3. Odoo writes back **only** allowlisted partner fields: `name, website, city, zip, street, street2, email, phone`.

> **EIE is the executor, not the selector.** Which partners/entities to enrich and in what order is **not** an EIE (or Odoo) responsibility — CEG `engine/health/` ranks from the domain spec; Odoo only triggers converge + maps CRM writeback. See [`ADR-009`](../adr/ADR-009-enrichment-selection-ranking-not-in-odoo.md). The retired Odoo enrichment cron is not the product ranking design.

---

## Execution steps (in order, with rationale)

### Step 1 — Register EIE as a Gate worker for `action="converge"`
- **Do:** Stand up the worker endpoint and register it with the hub router (01 Step 4) as the `converge` destination. Consume packets via the pinned `Gate_SDK`.
- **Why first:** Same as CEG — no request arrives until routing exists. Smoke-test the routed channel with an echo before inference logic.

### Step 2 — Parse `ConvergeRequest` (entity snapshot + sources)
- **Do:** Read `entity_id` (`res.partner:<id>`), `domain`, `entity_snapshot.{name,website,city,zip,street,street2,comment,email,phone,source_urls}`, optional `profile_id`, `max_passes`, and `odoo` context.
- **Why second:** Inputs define the inference task and provenance. Defensive parsing avoids crashes (snapshots vary). `source_urls` seed crawling; absence means infer from snapshot only.

### Step 3 — Run convergence passes (inference + optional CEG collaboration)
- **Do:** Execute the converge loop (crawl/extract/infer; optionally consult CEG graph context *internally* for field determination). Bound iterations by `max_passes` (or your default). Track tokens/cost.
- **Why third:** Core EIE value. Any CEG collaboration stays **inside Track B** (worker-to-worker), never Odoo→CEG. Depends on parsed inputs (Step 2).

### Step 4 — Produce `final_fields` (+ optional `writeback.partner_fields`)
- **Do:** Emit converged values. Prefer returning a clean `final_fields` map; if you need a richer structure, put authoritative partner values under `writeback.partner_fields` (Odoo prefers `partner_fields` when present). Include only confidently-resolved values.
- **Why fourth:** Odoo filters to the partner allowlist and drops empties/non-allowlisted keys. Returning junk just gets ignored; returning clean allowlisted values maximizes useful proposals. Depends on Step 3 output.

### Step 5 — Response payload + audit fields
- **Do:** Emit `{run_id, status, pass_count, final_fields, writeback, total_tokens, total_cost_usd}` per §3.3. Ensure the hub preserves `correlation_id`/`packet_id` on the response.
- **Why fifth:** This is exactly what `map_converge_response` + `extract_audit_metadata` read. Odoo applies the allowlisted fields to the partner live and stores `gate_packet_id` / `gate_correlation_id` on the enrichment run for audit (plus the full `gate_proposal`).

### Step 6 — Timeout + structured errors
- **Do:** Respond within the Gate/Odoo timeout (≤30s; converge can be slow — consider async/job semantics with a fast ack if a single call can exceed it, coordinated with hub design). On failure return a structured error so Odoo falls back to its local crawl/extract/inject pipeline.
- **Why sixth:** Track A wraps converge in try/except → local fallback. Long/hanging converge would stall the enrichment action. Decide sync-vs-async with the hub before going wide.

### Step 7 — End-to-end test from Odoo (live)
- **Do:** With hub (01) live, set `plasticos.gate.url` (enrichment is on by default), run an enrichment run on a sample partner with sources. Verify Odoo run shows `engine_used="gate"`, `state="injected"`, `fields_written>0`, `gate_packet_id` set, and that the allowlisted fields are **live on the partner** with `plasticos.enrichment.provenance` rows (`target_model="res.partner"`). To validate review-only, set `plasticos.gate.auto_writeback=0` and confirm `state="review"` with no partner writes.
- **Why last:** Confirms the live writeback path (and the review-only opt-out). EIE output lands directly in the CRM, so validate field quality on sample data before enabling in production.

---

## Acceptance (EIE)
- [ ] `converge` handler added and registered (distinct from `process_web_lead`/`process_intake`).
- [ ] Routed `action=converge` packets reach EIE and return §3.3 response.
- [ ] `final_fields`/`writeback` use Odoo-meaningful keys (allowlist for partner).
- [ ] Audit ids preserved; Odoo run shows `engine_used="gate"`, `state="injected"`, provenance rows.
- [ ] Errors/timeouts structured → Odoo falls back to local enrichment.
- [ ] Returned values are backfill-quality (Odoo applies them live, merge-not-overwrite).

## Guardrails
- EIE reachable **only** via the Gate hub; CEG collaboration is worker-internal.
- Odoo applies allowlisted fields **live by default** (`plasticos.gate.auto_writeback=1`); `=0` reverts to review-only. Only allowlisted partner fields are ever written.
- Return only confidently-resolved values — junk lands in the live CRM (merge-not-overwrite protects only *existing* values, not blanks).
