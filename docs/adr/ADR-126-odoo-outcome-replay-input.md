# ADR-126: Odoo outcome-replay input producer

## Status
Accepted (TASK-057)

## Context
Cross-service replay (TASK-033 CEG, TASK-058 integration) needs a stable Odoo-side artifact that captures business-trace fields without mutating Gate.

## Decision
- Schema id: `l9.odoo.outcome_replay_input.v1`
- Required event fields: `tenant`, `action`, `packet_id`
- Optional: `correlation_id`, `source_model`, `source_id`, `observed_at`, `payload`
- Document includes `content_hash` (sha256 over canonical JSON excluding the hash field)
- Exporter is offline-only: `gate_mutation=false`; no Gate/HTTP calls
- Events are sorted by `(packet_id, action, tenant)` before hashing

## Consequences
CEG replay (TASK-033) must accept this schema. Operators discard generated files to recover; exporter code reverts via normal git.
