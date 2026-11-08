# ADR-127: Field-family cutover controls (Gate-mediated authority)

## Status
Accepted (TASK-035)

## Context
Wave-9 needs an explicit, dual-gated path to cut over **one** approved field family
(`specification`) to Gate-mediated read authority, with observation metrics defined
before enable. Distinct from ADR-127-odoo-evidence-mapping-consumer.md.

## Decision
- ICP `plasticos.gate.field_family_cutover_enabled` defaults to **off** (`0`).
- ICP `plasticos.gate.field_family_cutover_operator_approved` defaults to **off** (`0`).
  Config alone is insufficient — both flags required to arm.
- ICP `plasticos.gate.field_family_cutover_family` locked to `specification`
  for this wave slice (`supply` / `demand` remain BLOCKED_AUTOMATIC).
- Observation metrics are defined in code before any enable:
  `gate_path_success_rate`, `gate_path_latency_p95_ms`, `parity_mismatch_count`,
  `local_authority_attempt_count`.
- Gate remains sole intelligence authority. Disabling cutover restores prior field
  authority and **must not** silently restore local matching/inference.
- Production cutover flip remains operator-owned; this ADR ships the control surface.

## Consequences
Operators must set both enable + operator-approved ICPs. Instant recovery: set both to `0`.
TASK-036 observation window and TASK-067 exit consume the feature-flag observation report.
