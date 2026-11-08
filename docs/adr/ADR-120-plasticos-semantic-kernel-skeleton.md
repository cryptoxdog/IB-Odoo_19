# ADR-120: plasticos_semantic_kernel skeleton

## Status
Accepted (TASK-022)

## Context
W5 requires an additive Odoo semantic kernel without changing current business
behavior. Models must land in later tasks behind an isolatable addon boundary.

## Decision
- Create `plasticos_semantic_kernel` depending only on material profile,
  facility profile, and intake.
- Ship installable skeleton with ACL CSV header and empty models package.
- Forbid Gate/client/matching/inference/graph code in this module.

## Consequences
Later W5 tasks can add models/migrations without reverse-depending existing
authoritative modules. Rollback is uninstall/disable before data creation.
