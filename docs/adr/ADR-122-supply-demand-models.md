# ADR-122: Supply opportunity and buyer demand models

## Status
Accepted (TASK-024)

## Decision
Add `plasticos.supply.opportunity` and `plasticos.buyer.demand` in `plasticos_semantic_kernel` with chatter, immutable `canonical_uuid` via `models.Constraint`, and no automatic ambiguous conversion helpers.

## Consequences
Matching remains Gate/CEG authority; Odoo only stores opportunity/demand records.
