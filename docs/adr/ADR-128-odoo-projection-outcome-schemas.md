# ADR-128: Compile Odoo Projection and Outcome Schemas

**Status:** Accepted
**Task:** TASK-042
**Date:** 2026-08-02

## Decision

Odoo is the schema producer for:

- `canonical-projection` — rebuildable approved facts (never CEG SoR)
- `sync-projection` — upsert/tombstone stream with revision idempotency
- `outcome-feedback` — idempotent observed business outcomes

Artifacts live under `contracts/schemas/` and are checksum-aligned with the
CEG consumer copies from TASK-061. Runtime validators and store proofs live in
`scripts/projection_outcome_schemas.py` (outside `plasticos_*`).

## Acceptance

- Fixtures validate; transport fields / unknown ops / unknown outcomes reject
- Sync apply is idempotent; rebuild from authority stream works
- Outcome apply is idempotent by `idempotency_key`
- Schema text affirms Odoo remains authority

## Non-goals

- Cross-repo parity harness (TASK-062)
- Activating live writeback or CEG ingest wiring
