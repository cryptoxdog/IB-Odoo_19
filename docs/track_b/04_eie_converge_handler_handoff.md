# EIE Handoff — Add the `converge` Handler

**Target repo:** `https://github.com/Quantum-L9/Enrichment.Inference.Engine`
**Goal:** Add a Gate worker handler for **`action="converge"`** that enriches a partner from a snapshot (+ source URLs) and returns allowlisted CRM fields. Odoo applies the result **live** (auto-writeback ON by default), so output lands directly in the production CRM.
**Owner of contract:** PlasticOS Odoo (`plasticos_gate` in `cryptoxdog/IB-Odoo_19`, branch `feat/gate-client-matcher-fallback`). **Do not redesign the wire format** — conform to it.

> This is the one thing blocking true end-to-end live enrichment. Match (`action="match"`, CEG) is a separate path and already contracted.

---

## 0. Context (why this exists)

- Odoo's enrichment run (`plasticos.enrichment.run.action_execute`) tries Gate **`converge` first**, then falls back to its local crawl/extract/inject pipeline on any error/timeout.
- Odoo already sends `converge` packets. EIE currently ships only `process_web_lead` / `process_intake` — **neither answers `converge`**, so every converge attempt errors and Odoo silently falls back to local.
- Decision (ADR-002 amendment, 2026-07-19): the contract stays **`converge`**; EIE must implement it. See `docs/track_b/03_enrichment_inference_engine.md` and `docs/track_b/00_AGENT_HANDOFF.md §3.3`.

---

## 1. Where to add it (mirror existing handlers)

Add the handler next to `process_web_lead` / `process_intake` and register it with the same dispatch mechanism those use (same worker bootstrap, same `Gate_SDK` packet consumption, same action→handler registry).

- **Register** `converge` → `handle_converge` in whatever action map the existing handlers use.
- **Consume/emit** packets via the pinned SDK: `Quantum-L9/Gate_SDK` (`constellation-node-sdk`). Odoo pins the exact SHA in its `requirements.txt`; build against the **same** SDK version/packet schema.
- **Reachability:** EIE is reachable **only** through the Gate hub (`Quantum-L9/Constellation.Gate`). Never expose a direct Odoo→EIE path (ADR-002).

---

## 2. Request contract (what Odoo sends)

`header.action == "converge"`. The packet **payload** is `ConvergeRequest.to_dict()`:

```jsonc
{
  "entity_id": "res.partner:55",          // "res.partner:<odoo_partner_id>" — echo the id back untouched
  "domain": "plasticos",
  "entity_snapshot": {                     // present keys only; any may be absent
    "name": "Acme Recycling",
    "website": "https://acme.example",
    "city": "Charlotte",
    "zip": "28202",
    "street": "1 Polymer Way",
    "street2": "Suite 200",
    "comment": "freeform notes",
    "email": "info@acme.example",
    "phone": "+1 704 555 0100",
    "source_urls": ["https://acme.example/about"]   // seed crawl targets; may be absent
  },
  "odoo": {                                // audit/context; do not require any specific key
    "model": "plasticos.enrichment.run",
    "record_id": 7,
    "company_id": 1,
    "user_id": 2,
    "db_name": "...",
    "correlation_id": "plasticos.enrichment.run:7"
  },
  "profile_id": null,                      // optional (omitted when null)
  "max_passes": null                       // optional bound on convergence passes (omitted when null)
}
```

**Parsing rules**
- Treat every `entity_snapshot.*` key as optional; parse defensively.
- If `source_urls` is present, crawl them; if absent, infer from the snapshot only.
- Honor `max_passes` when provided; otherwise use your own sane default and bound iterations.

---

## 3. Response contract (what Odoo reads)

Return a packet whose **payload** matches `map_converge_response` exactly:

```jsonc
{
  "run_id": "eie-2026-...",          // your run id (string) — stored for audit
  "status": "ok",                     // "ok" on success; anything else + a clear error is treated as failure
  "pass_count": 2,
  "final_fields": {                   // preferred output map
    "website": "https://acme-new.example",
    "city": "Raleigh"
  },
  "writeback": {                      // OPTIONAL. If present, partner_fields WINS over final_fields
    "partner_fields": { "website": "https://acme-new.example", "city": "Raleigh" }
  },
  "total_tokens": 1234,
  "total_cost_usd": 0.05
}
```

**Field precedence Odoo uses:** if `writeback.partner_fields` is a non-empty dict, Odoo uses it; otherwise it uses `final_fields`.

### 3.1 Partner field ALLOWLIST (hard limit — everything else is dropped)

Odoo writes back **only** these `res.partner` keys:

```
name, website, city, zip, street, street2, email, phone
```

- Any other key you return is **ignored** on the Odoo side.
- Values that are `null` / `false` / `""` are dropped.
- Use these **exact** field names (they are Odoo `res.partner` column names).

### 3.2 How Odoo applies it (so you calibrate output quality)

- **Live by default** (`plasticos.gate.auto_writeback=1`): allowlisted fields are written to the partner immediately.
- **Merge-not-overwrite:** Odoo only fills fields that are currently **blank** on the partner; it never clobbers an existing value. So a wrong value can only land in a *previously empty* field — still the live CRM. **Return only confidently-resolved values.**
- Every write creates a `plasticos.enrichment.provenance` row (`target_model="res.partner"`). The `run_id` / packet id are stored for audit and rollback.
- Operators may set `plasticos.gate.auto_writeback=0` to switch Odoo to review-only, but do not rely on that — assume live.

---

## 4. Audit / correlation (via the hub, not the payload)

- The Gate hub sets `response_packet.header.packet_id` and preserves `response_packet.header.correlation_id`.
- Odoo reads those from the **header**, not the payload → stored as `gate_packet_id` / `gate_correlation_id`.
- **Keep `correlation_id` stable request→response.** Do not put audit ids in the payload; the hub owns the envelope.

---

## 5. Timeout & failure semantics

- Respond within Odoo's `plasticos.gate.timeout_seconds` (default **30s**). Converge can be slow — if a single synchronous call may exceed it, coordinate an async/job pattern (fast ack + follow-up) with the hub owner **before** going wide.
- On any failure, return a **structured error** (non-`ok` status / hub error packet) — never hang. Odoo catches it and falls back to its local pipeline, so a clean error degrades gracefully; a hang stalls the enrichment action.

---

## 6. Definition of done

- [ ] `converge` handler added and registered alongside `process_web_lead` / `process_intake`.
- [ ] Routed `action=converge` packets reach EIE and return the §3 payload.
- [ ] Output uses the §3.1 allowlist keys (extras are fine but ignored).
- [ ] `correlation_id` preserved; response `packet_id` set by the hub.
- [ ] Timeouts/errors are structured (no hangs) → Odoo falls back to local.
- [ ] Validated end-to-end from Odoo on **sample data**: an enrichment run on a partner with blank `website`/`city` shows `engine_used="gate"`, `state="injected"`, `fields_written>0`, the fields live on the partner, and matching `plasticos.enrichment.provenance` rows.

---

## 7. Odoo-side validation snippet (for the reviewer)

```bash
# In Odoo staging, with the hub live:
#   ir.config_parameter:
#     plasticos.gate.url = https://<gate-host>
#     (enrichment_enabled=1, auto_writeback=1 are the seeded defaults)
#   Create res.partner with blank website/city + an enrichment source URL.
#   Run the enrichment -> expect:
#     run.engine_used == "gate"
#     run.state == "injected"
#     run.fields_written > 0
#     partner.website / partner.city populated
#     plasticos.enrichment.provenance rows with target_model="res.partner"
```

---

## 8. Guardrails (do / don't)

- **Do** mirror the existing handler registration/bootstrap; reuse the pinned `Gate_SDK`.
- **Do** keep CEG collaboration (if any) **worker-internal** (EIE↔CEG through the hub/worker mesh) — never Odoo→CEG.
- **Don't** change the packet schema unilaterally — bump `Gate_SDK` and coordinate an Odoo re-pin.
- **Don't** invent new partner fields — the §3.1 allowlist is the hard boundary.
- **Don't** repurpose `process_intake` as `converge` — they are distinct actions with distinct payloads.
