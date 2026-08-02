# Gate Integration & Autonomy Roadmap

**Status:** Active  
**Last updated:** 2026-08-02  
**Authority (intelligence):** [ADR-003: Single External Intelligence Authority](adr/ADR-003-single-external-intelligence-authority.md)  
**Topology / phased human gates:** [ADR-002: Gate Hub, CEG Routing, and Phased Autonomy](adr/ADR-002-gate-hub-phased-autonomy.md)  
**Architecture:** [ARCHITECTURE.md](../ARCHITECTURE.md) § External Intelligence Boundary  
**Registry:** [docs/roadmap/registry.yaml](roadmap/registry.yaml) — `make roadmap` (add + sync + validate)

## Objective

Maximize pipeline autonomy over time by **removing human-in-the-middle steps only after each step has proven reliable in production** — starting with Gate-routed matching to CEG while keeping triage and offer send human-gated.

## Mothball authority (Wave 7 / M1)

As of **ADR-003-single-external-intelligence-authority** (TASK-045 / PROMOTION_APPROVED):

- CEG (via Gate) is the **matching** intelligence authority; EIE (via Gate) is the **enrichment/converge** intelligence authority.
- In-Odoo algorithmic match/enrichment paths are **non-authority transitional residue** until M2–M5 — not product design.
- Synced Phase-1 scope tables below remain registry-driven operational history; do not hand-edit marker blocks. Registry promotion of `ROAD-GATE-021` is a follow-on (out of M1 writable scope).

**Forbidden:** Odoo → CEG/EIE direct HTTP or SDK bypass of Gate.

---

## Topology (all phases)

```
                    ┌──────────────────────────┐
                    │ Cognitive.Engine.Graphs  │
                    │ (+ inference / EIE)      │
                    └────────────▲─────────────┘
                                 │
                          Gate routes action
                                 │
┌─────────┐   TransportPacket   ┌──────┐   TransportPacket   ┌─────────┐
│  Odoo   │ ───────────────────► │ Gate │ ───────────────────► │ Worker  │
│ (ERP)   │ ◄─────────────────── │      │ ◄─────────────────── │ (CEG…)  │
└─────────┘                       └──────┘                       └─────────┘
```

**Forbidden:** Odoo → CEG/EIE direct HTTP or SDK bypass of Gate.

---

## Phase 1 — Battle-testing (current target)

**Theme:** Human-in-the-loop on every high-stakes step. Gate for matching only.

### Pipeline

| Step | System | Human checkpoint |
|------|--------|------------------|
| 1. Lead ingest | Odoo (`plasticos_web_leads`) | — |
| 2. Normalize + LLM + vision + HOT/COLD | **Odoo local** (`_run_triage_pipeline`) | Review HOT leads before intake |
| 3. Intake + material profile | Odoo (`plasticos_intake`) | Broker edits specs |
| 4. Match to Buyers | **Odoo → Gate → CEG → Gate → Odoo** | Review match lines, select buyers |
| 5. Offer draft + attachments | Odoo (`plasticos_offer` / intake UX) | Edit price, qty, copy, pics |
| 6. Send Offer | Odoo (`action_send_offers`) | **Explicit click** — no auto-send |

### Implementation scope (Phase 1)

<!-- roadmap:gate-autonomy:phase1-scope:start -->
| In scope | Out of scope (defer) |
|----------|----------------------|
| - Gate client at `plasticos.buyer.matcher` seam `(ROAD-GATE-010)` | - `web_lead_gate_bridge` / Gate triage `(ROAD-GATE-020)` |
| - try Gate → fallback local matcher + Neo4j `(ROAD-GATE-011)` | - Gate-only matcher (no fallback) `(ROAD-GATE-021)` |
| - Match audit: `plasticos.match.result`, correlation IDs `(ROAD-GATE-012)` | - Auto-send offers `(ROAD-GATE-022)` |
| - Optional: Gate `converge` for enrichment (with local fallback) `(ROAD-GATE-013)` | - `plasticos.gate.webleads_*` ICP `(ROAD-GATE-023)` |
| - ICP: `plasticos.gate.url`, `plasticos.gate.matching_enabled` `(ROAD-GATE-014)` | - `plasticos.gate.auto_writeback=1` `(ROAD-GATE-024)` |
| - `external_dependencies`: `constellation-node-sdk` (match module) `(ROAD-GATE-015)` | - Phase 3 autonomy flags `(ROAD-GATE-025)` |
<!-- roadmap:gate-autonomy:phase1-scope:end -->

### Config parameters (Phase 1)

| Key | Default | Purpose |
|-----|---------|---------|
| `plasticos.gate.url` | *(unset)* | Gate endpoint; unset → local matcher only |
| `plasticos.gate.local_node` | `odoo` | Source node id in transport packets |
| `plasticos.gate.matching_enabled` | `1` | When `1` and URL set, try Gate first |
| `plasticos.gate.matching_action` | `match` | Gate action routed to CEG |
| `plasticos.matching_engine.enabled` | *(existing)* | Master kill switch (unchanged) |
| `plasticos.matching_engine.stubbed` | *(existing)* | Stub mode (unchanged) |

### Observability (required for graduation)

Track in production before advancing phases:

<!-- roadmap:gate-autonomy:phase1-observability:start -->
- Match acceptance rate (broker keeps vs removes match lines) `(ROAD-GATE-030)`
- Gate vs local fallback invocation ratio and latency `(ROAD-GATE-031)`
- Offer reply / conversion rate by match source (Gate vs fallback) `(ROAD-GATE-032)`
- Email/offer quality issues logged by brokers `(ROAD-GATE-033)`
- Gate/CEG error rate and correlation ID traceability `(ROAD-GATE-034)`
<!-- roadmap:gate-autonomy:phase1-observability:end -->

### Product gaps (Phase 1 backlog)

<!-- roadmap:gate-autonomy:phase1-backlog:start -->
- [ ] Top-N match lines selected by default (target top 10) after match run `(ROAD-GATE-001)`
- [ ] Side-by-side or logged comparison when Gate and local scores diverge (optional debug mode) `(ROAD-GATE-002)`
<!-- roadmap:gate-autonomy:phase1-backlog:end -->

---

## Phase 2 — Semi-autonomous defaults

**Entry criteria:** Phase 1 metrics stable ≥ 4–8 weeks; Gate error rate below agreed threshold; broker sign-off on match quality.

<!-- roadmap:gate-autonomy:phase2-capabilities:start -->
| Capability | Human gate remaining / Notes | ID |
|------------|----------------------------|-----|
| Auto-select top N match lines (default 10) | Can deselect before send | `ROAD-GATE-040` |
| Pre-fill offer drafts from match metadata + typical price | Edit before send | `ROAD-GATE-041` |
| Richer intake defaults from triage output | Review on intake form | `ROAD-GATE-042` |
| Enrichment auto-writeback to partner/profile (low-risk fields only) | Review queue for flagged records | `ROAD-GATE-043` |
| **Send Offer** | **Still explicit human action** | `ROAD-GATE-044` |
<!-- roadmap:gate-autonomy:phase2-capabilities:end -->

---

## Phase 3 — Higher autonomy (post-stability)

**Entry criteria:** Phase 2 proven; governance rules for confidence thresholds; rollback = ICP flip, not redeploy.

<!-- roadmap:gate-autonomy:phase3-capabilities:start -->
| Capability | Notes | ID |
|------------|-----|-----|
| Gate-routed web-lead triage (`process_web_lead`) | Replaces local LLM/vision path for high-confidence paths only | `ROAD-GATE-050` |
| Auto-intake for trusted HOT patterns | Human queue for edge cases | `ROAD-GATE-051` |
| Auto-match on intake confirm (caps, exclusions) | Audit in `plasticos.match.result` | `ROAD-GATE-052` |
| Auto-offer draft generation | Human or rule-gated send | `ROAD-GATE-053` |
| Auto-send for trusted supplier/buyer patterns | Last gate to remove; highest commercial risk | `ROAD-GATE-054` |
<!-- roadmap:gate-autonomy:phase3-capabilities:end -->

Draft pack reference (apply only after Phase 3 criteria met):

- `Current Work - IGNORE/.../Odoo - Gate Integration/odoo_repo_surgery_pack/new_files/plasticos_web_leads/models/web_lead_gate_bridge.py`
- ICP: `plasticos.gate.webleads_enabled`, `plasticos.gate.webleads_action`

---

## Graduation checklist (template)

Before moving Phase N → N+1:

- [ ] Error rate and p95 latency within SLO for 30+ days
- [ ] No open P1 bugs on the step being automated
- [ ] Broker/ops sign-off on sample audit (≥ N deals)
- [ ] Rollback procedure tested (ICP disable + local fallback verified)
- [ ] ADR/roadmap updated if scope changes

---

## Code seams (reference)

| Concern | Primary file(s) |
|---------|-----------------|
| Match button UI | `plasticos_buyer_match_engine/models/intake_extension.py` |
| Matcher orchestrator | `plasticos_buyer_match_engine/models/matcher.py` |
| Match line persistence | `plasticos_intake/models/intake_match.py` |
| Send offers | `plasticos_intake/models/intake.py` → `action_send_offers()` |
| Web lead triage (Phase 1 local) | `plasticos_web_leads/models/web_lead.py` |
| Enrichment (optional Gate) | `plasticos_enrichment/models/enrichment_run.py` |

---

## Related documents

- [ADR-003-single-external-intelligence-authority](adr/ADR-003-single-external-intelligence-authority.md) — intelligence authority (mothball M1)
- [ADR-002](adr/ADR-002-gate-hub-phased-autonomy.md) — Gate hub topology + phased human checkpoints
- [ARCHITECTURE.md](../ARCHITECTURE.md) — system structure
- [plasticos_intake/README.md](../plasticos_intake/README.md) — intake pipeline
- [Cognitive.Engine.Graphs](https://github.com/cryptoxdog/Cognitive.Engine.Graphs) — external match engine
