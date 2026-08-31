# ADR-129 — Odoo is authoritative; Graph receives a post-commit projection

- **Status:** Accepted
- **Date:** 2026-08-31
- **Scope:** `plasticos_gate`, `plasticos_enrichment`, `plasticos_matching`
- **Supersedes nothing.** Extends ADR-002 (Gate hub), ADR-003-single (single
  external intelligence authority), ADR-011 (action topology), ADR-012
  (writeback allowlist + provenance), ADR-013 (fail-closed transport),
  ADR-015 (persistence shells).

## Context

Three seams between Odoo, the Enrichment/Inference Engine (EIE), and the
PlasticOS Graph disagreed with each other in ways that only surface at runtime:

1. **Match direction.** Odoo sent `match_direction="intake_to_buyer"`. Graph
   recognises only `supply_opportunity_to_buyer_facility` and
   `buyer_demand_to_supply_opportunity`, and rejects a direction for which no
   candidate entity exists. Odoo's response mapper also read `direction` while
   Graph publishes `match_direction`.
2. **Entity identity.** `build_converge_request` carried the Odoo id only as
   `entity["_odoo_entity_id"]`, while EIE resolves identity from `entity["id"]`
   — so Odoo-originated traffic resolved to `unknown`. The request also left
   `idempotency_key` unset, so a retry paid for the same computation again.
3. **Ownership of Graph state.** EIE wrote Graph directly after convergence,
   before Odoo had accepted the proposal. Odoo's merge policy rejects fields
   that are already populated and drops fields outside the writeback allowlist,
   so the graph could hold state Odoo never accepted:
   `EIE proposal ≠ Odoo truth ≠ Graph projection`, with no deterministic way to
   say which is right.

## Decision

**Odoo is authoritative for Odoo business state. For an Odoo-originated
enrichment, EIE computes a proposal; Odoo commits; Graph receives the
authoritative post-commit projection from Odoo.**

Concretely, in this repository:

1. **Canonical match contract.** `gate_contracts` publishes the two Graph
   directions plus `normalize_match_direction()`. `build_match_request` emits
   `supply_opportunity_to_buyer_facility` for the intake/supply flow; the legacy
   Odoo spelling is normalised, never forwarded; an unknown direction raises
   before the round trip. `map_match_response` prefers `match_direction` and
   keeps `direction` as a migration-window fallback.
2. **Canonical identity + deterministic idempotency.** `entity["id"]` carries
   `res.partner:<id>`; `_odoo_entity_id` is dual-populated for one migration
   window. `idempotency_key` is
   `odoo:<db>:<entity_ref>:converge:<pipeline_version>:<fingerprint>`, where the
   fingerprint hashes the normalised partner snapshot, deduplicated and sorted
   source URLs, object type, objective, max variations, and the pipeline
   contract version — and deliberately excludes run id, packet id, attempt
   number, and every timestamp.
3. **Transactional projection outbox.** A successful authoritative Odoo write
   enqueues `plasticos.gate.outbox` **in the same PostgreSQL transaction**. If
   Odoo commits, both the business state and the pending projection exist; if it
   rolls back, neither does. No distributed transaction. Delivery is
   at-least-once and idempotent, never described as exactly-once.
4. **Typed projection only.** Graph receives an allowlisted facility row, never
   a CRM record. Contact data, addresses, and identity fields are refused at the
   producer. Not every `res.partner` is a Facility: a partner with no facility
   profile projects nothing.
5. **Durable scheduling.** `plasticos.enrichment.run` gains scheduling and
   idempotency metadata only. The existing durable states still own the
   lifecycle — no second state machine. Human approval is never required for the
   machine to reach a terminal disposition; an unsafe or low-confidence result
   becomes `degraded` (a safe machine no-op), not a queue for a person.
6. **Independent kill switches.** Enrichment scheduling, Graph projection, and
   the outbox worker each stop on their own, so an incident in one rail does not
   force the operator to shut down the others.

## Stable facility identifier policy

Odoo has no pre-existing facility-scoped external identifier. Rather than let an
identifier be invented implicitly at a call site, this ADR adopts one:

```
facility_id = "plasticos.facility.profile:<facility_profile_id>"
```

The `plasticos.facility.profile` primary key is stable for the life of the
database, survives partner renames and re-parenting, and is not reused. Every
projected facility also carries `entity_ref = "res.partner:<partner_id>"`, so a
Graph candidate resolves back to Odoo explicitly and never by name inference.

## Retry policy

One published schedule serves both the outbox and the enrichment scheduler:
1 min, 5 min, 15 min, 1 hour, 6 hours, 6 hours, then terminal failure, with ±20%
jitter. Retries live around a durable record. `plasticos_gate.gate_client` stays
single-shot on purpose: layering transport retries under scheduler retries
multiplies load against a Gate that is already failing.

## Consequences

- Graph unavailability parks projections durably; it never rolls back a valid
  Odoo enrichment (consistent with "graph failures never block Odoo").
- A projection that cannot be built is logged and skipped, not raised.
- `plasticos_enrichment` now depends on `plasticos_facility_profile` to read the
  capability data the Facility projection needs. Both are Layer 2 and the
  install order already places `plasticos_facility_profile` first, so no cycle
  and no order change.
- Two crons are added **inactive**, and every new ICP flag is seeded **0**.
  Commissioning enables one rail at a time; nothing in this change starts moving
  on deploy.
- `PARTNER_WRITEBACK_FIELD_ALLOWLIST` (ADR-012) still governs what Odoo accepts
  from EIE. The projection allowlist here is a separate, narrower contract
  governing what Odoo publishes to Graph.

## Not decided here

Out of scope for this repository, and deliberately left to the EIE and Graph
repositories: Graph action-registration parity, Graph-side ontology validation
at ingress, EIE tenant-scoped result persistence and Redis/Postgres fallback,
suppression of EIE's direct Graph write for Odoo-originated traffic, and the
multi-provider waterfall. Until the EIE side lands, Odoo sends the canonical
identity and key it owns; a stale consumer that still reads `_odoo_entity_id`
keeps working through the dual-populated migration window.
