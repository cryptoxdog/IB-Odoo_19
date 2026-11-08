# ADR-121: Material specification and observation models

## Status
Accepted (TASK-023)

## Context
PlasticOS needs versioned normative requirements (`plasticos.material.specification`) and attributed measurements (`plasticos.material.observation`) as additive semantic-kernel models, without scoring or inference execution inside Odoo.

## Decision
- Place both models in `plasticos_semantic_kernel`.
- Specification inherits `mail.thread` (operator decisions); observation does not.
- Issue immutable `canonical_uuid` at create; unique SQL constraint.
- Many2one fields define explicit `ondelete` per `ODOO_MODEL_FIELD_SPEC.yaml`.
- No Gate client, ranking, or match logic in this module.

## Consequences
Install/upgrade of `plasticos_semantic_kernel` creates schema only. Backfill and Gate persistence land in later tasks.
