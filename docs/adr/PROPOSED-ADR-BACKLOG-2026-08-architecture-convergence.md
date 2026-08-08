# Proposed ADR Backlog — Architecture Convergence (2026-08)

**Status:** Historical — ADR-010…019 are now **Accepted** full files; use those as SSOT (see ADR-019 §4)  
**Date:** 2026-08-07  
**Source:** Operator/agent working session on matching, enrichment, Gate, CEG, EIE ownership  
**Premise:** The architecture has **converged** on Gate-mediated external intelligence. Several in-repo docs still describe pre-mothball behavior and must be revised or superseded.

## Already accepted from this session

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-009](ADR-009-enrichment-selection-ranking-not-in-odoo.md) | Enrichment selection & ranking live outside this repo | **Accepted** |

## Ten complementary ADRs to formalize the converged architecture

> **Accepted (2026-08-07):** All ten are published as full ADR files — open the linked paths below rather than treating this backlog as normative.

| ADR | File |
|-----|------|
| ADR-010 | [ADR-010-odoo-consumer-trigger-ownership.md](ADR-010-odoo-consumer-trigger-ownership.md) |
| ADR-011 | [ADR-011-intelligence-action-topology.md](ADR-011-intelligence-action-topology.md) |
| ADR-012 | [ADR-012-crm-writeback-allowlist-provenance.md](ADR-012-crm-writeback-allowlist-provenance.md) |
| ADR-013 | [ADR-013-fail-closed-gate-transport.md](ADR-013-fail-closed-gate-transport.md) |
| ADR-014 | [ADR-014-domainspec-ssot-gates-scoring-readiness.md](ADR-014-domainspec-ssot-gates-scoring-readiness.md) |
| ADR-015 | [ADR-015-persistence-shells-matching-enrichment.md](ADR-015-persistence-shells-matching-enrichment.md) |
| ADR-016 | [ADR-016-web-lead-triage-boundary.md](ADR-016-web-lead-triage-boundary.md) |
| ADR-017 | [ADR-017-constellation-enrichment-feedback-channel.md](ADR-017-constellation-enrichment-feedback-channel.md) |
| ADR-018 | [ADR-018-human-brokerage-checkpoints.md](ADR-018-human-brokerage-checkpoints.md) |
| ADR-019 | [ADR-019-documentation-convergence-supersession.md](ADR-019-documentation-convergence-supersession.md) |


Numbers below are **proposed** next free slots after ADR-009. Rename on write if collisions appear. Each should follow ADR-001 structure (Context → Decision → Consequences → References).

---

### ADR-010 — Odoo consumer trigger ownership (when to call Gate)

**Complements:** ADR-003-single, ADR-009  
**Decision draft:** Odoo alone decides *whether/when* to emit `TransportPacket`s (`match` / `converge`). Triggers may be UI action, operator retry, future event hooks, or an explicit consumer of an external queue — never EIE/CEG deciding Odoo CRM writes. Current enrichment trigger = per-run execute/retry; enrichment cron is retired (not authority).  
**Chat evidence:** “Odoo owns when to call”; cron is disabled/no-op; EIE executes requests as they arrive.

---

### ADR-011 — Intelligence action topology (`match` vs `converge`)

**Complements:** ADR-002, track_b 02/03  
**Decision draft:** `action=match` → Gate → CEG only. `action=converge` → Gate → EIE only. No Odoo→worker direct HTTP. Worker-to-worker collaboration (EIE consulting CEG) stays inside the constellation, never as a second Odoo egress.  
**Chat evidence:** Sequence diagrams and module roles for matching vs enrichment.

---

### ADR-012 — CRM writeback allowlist, merge-not-overwrite, provenance

**Complements:** ADR-002 amendment (2026-07-19), track_b 04  
**Decision draft:** Elevate the amendment into a standalone ADR: allowlisted partner fields only; merge-not-overwrite; `plasticos.enrichment.provenance` per write; `plasticos.gate.auto_writeback` toggles live vs review-only.  
**Chat evidence:** Converge return path and writeback rules.

---

### ADR-013 — Fail-closed Gate transport (supersede stale local-fallback docs)

**Complements / supersedes language in:** ADR-002 §2 (already superseded as authority by ADR-003-single); **stale** track_b/00 (“Always falls back to a local engine”); ARCHITECTURE/README remnants that still describe local matcher/enrichment as graceful degradation.  
**Decision draft:** Gate unavailable → classified failure (retryable/permanent/degraded) on `plasticos.match.run` / enrichment run; **no** silent local scoring/enrichment authority. Align all consumer docs with M7/M8.  
**Chat evidence:** Match orchestrator and enrichment `action_execute` fail-closed behavior.

---

### ADR-014 — DomainSpec as SSOT for gates, scoring, and readiness ranking

**Complements:** ADR-009, CEG external  
**Decision draft:** PlasticOS matching semantics and enrichment *readiness/gap* prioritization derive from CEG domain YAML (gates + scoring dimensions). Odoo emits snapshots/queries; it does not redefine gate math or readiness weights.  
**Chat evidence:** CEG readiness/gap/ROI tied to domain spec during graph onboarding.

---

### ADR-015 — Persistence shells (`plasticos_matching` / `plasticos_enrichment`)

**Complements:** ADR-003-single, ADR-009  
**Decision draft:** These modules are result stores + Gate orchestration seams + operator UX/audit — not intelligence engines. Forbidden: reintroducing local Neo4j matcher, YAML inference, or selection/ranking engines into these addons.  
**Chat evidence:** Module purpose summaries; mothball M4–M8.

---

### ADR-016 — Web-lead triage boundary (Phase 1 local; Phase 3 Gate optional)

**Complements:** ADR-002 phases, GATE_AUTONOMY_ROADMAP  
**Decision draft:** Restate with sharper non-goals: web-lead HOT/COLD is **not** enrichment ranking; not CEG health; not EIE converge. Phase 1 remains Cognito → Odoo LLM/vision/classify → intake. Gate web-lead triage stays deferred.  
**Chat evidence:** Clarification that “leads” cron/ranking ≠ web-lead pipeline.

---

### ADR-017 — Constellation feedback channel (CEG health → Gate → EIE)

**Complements:** ADR-009, ADR-011  
**Decision draft:** Ranked enrichment queues and graph→enrich feedback are constellation work (CEG `engine/health/` + Gate routing + EIE execute). IB-Odoo_19 may later *consume* queue outputs as a client; it must not host the selector. Acceptance criteria live in CEG/EIE repos; Odoo only documents the consumer seam when adopted.  
**Chat evidence:** CEG nightly health scan / enrichment_trigger; EIE TODO for graph→enrich channel.

---

### ADR-018 — Human brokerage checkpoints (intake → match → offer)

**Complements:** ADR-002 phases  
**Decision draft:** Phase-1 human gates remain binding: HOT review, match-line selection, explicit Send Offer. Gate automation must not skip these without a later phase ADR.  
**Chat evidence:** ADR-002 pipeline ownership restated in session flow discussion.

---

### ADR-019 — Documentation convergence & supersession map

**Complements:** all above  
**Decision draft:** Single map of which files are authoritative vs stale after architecture convergence. Mandate a coordinated refresh of:

| Artifact | Disposition |
|----------|-------------|
| `ARCHITECTURE.md` | Revise Gate/enrichment/matching sections to ADR-003 + ADR-009; remove local-engine authority language |
| `AGENTS.md` / `CLAUDE.md` | Point agents at ADR-003-single + ADR-009 for intelligence ownership |
| `docs/track_b/00_AGENT_HANDOFF.md` | Remove “always falls back to local”; cite fail-closed + M7 |
| `docs/track_b/02` / `03` | Drop local-fallback acceptance criteria; add ADR-009 pointer for ranking |
| `ADR-002` | Mark §2 superseded (already) and add banner linking ADR-003-single + ADR-013 |
| README / module READMEs that still say “buyer matching engine” for Odoo-local scoring | Retitle to Gate orchestrator / result store |

**Chat evidence:** Operator note that architecture has converged and repo docs (including ADRs) may be stale and need replace/revise.

---

## Suggested write order

1. **ADR-013** + **ADR-019** — stop agents from following stale fallback/cron docs.  
2. **ADR-010**, **ADR-011**, **ADR-012** — lock consumer/transport/writeback contracts.  
3. **ADR-014**, **ADR-015**, **ADR-017** — constellation vs Odoo boundary (pairs with ADR-009).  
4. **ADR-016**, **ADR-018** — phase/human boundaries.

## Explicit non-goals for this backlog

- Do not renumber existing ADR-003 filename collision in this pass (contact-import vs single-authority) unless a dedicated renumber ADR is approved.
- Do not vendor CEG `engine/health/` into IB-Odoo_19.
- Do not reactivate `pipeline_v2.py` or local intelligence modules.

## Session trace (topics covered)

1. Roles of `plasticos_matching` and `plasticos_enrichment`  
2. Odoo ↔ Gate ↔ CEG/EIE data flow  
3. Enrichment cron schedule/batch (retired) vs web-lead event path  
4. Ownership clarification: Odoo triggers, Gate routes, EIE/CEG execute intelligence  
5. EIE is not the orchestrator of enrichment selection  
6. CEG health readiness/gap/ROI ranking + domain-spec onboarding  
7. Why that ranking is absent from this repo → **ADR-009**  
8. Need for complementary ADRs + doc convergence → this backlog  
