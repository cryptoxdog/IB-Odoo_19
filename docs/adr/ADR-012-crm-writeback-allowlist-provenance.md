# ADR-012: CRM Writeback Allowlist, Merge-Not-Overwrite, and Provenance

**Status:** Accepted  
**Date:** 2026-08-07  
**Deciders:** Igor Beylin  
**Scope:** How Gate `converge` results are applied to `res.partner`  
**Related:**
[ADR-002-gate-hub-phased-autonomy.md](ADR-002-gate-hub-phased-autonomy.md) (amendment 2026-07-19 elevated here),
[ADR-010-odoo-consumer-trigger-ownership.md](ADR-010-odoo-consumer-trigger-ownership.md),
[ADR-011-intelligence-action-topology.md](ADR-011-intelligence-action-topology.md),
[`docs/track_b/04_odoo_gate_consumer_wiring.md`](../track_b/04_odoo_gate_consumer_wiring.md)

## Context

ADR-002’s 2026-07-19 amendment made enrichment converge live with allowlisted writeback. That rule is easy to miss when reading ADR-002 for hub topology alone. Agents need a dedicated binding ADR for CRM mutation semantics.

## Decision

### 1. Allowlisted partner fields only

Odoo may write from converge responses **only** these `res.partner` fields (unless a later ADR expands the list and bumps allowlist code + tests):

`name`, `website`, `city`, `zip`, `street`, `street2`, `email`, `phone`

Non-allowlisted keys in `final_fields` / `writeback.partner_fields` are ignored.

### 2. Merge-not-overwrite

Writeback fills **blank/falsy** partner fields only. Existing non-empty values are never clobbered by Gate converge auto-writeback.

### 3. Provenance required on live writes

Each applied field creates a `plasticos.enrichment.provenance` row (audit trail). Packet/correlation ids are stored on the enrichment run.

### 4. Auto-writeback toggle

| ICP | Behavior |
|-----|----------|
| `plasticos.gate.auto_writeback=1` (default) | Live apply allowlisted blanks; run → `injected` when successful |
| `plasticos.gate.auto_writeback=0` | Review-only: store `gate_proposal`, state `review`, **no** partner writes |

### 5. Confidence discipline

EIE should return only confidently resolved values. Merge-not-overwrite protects existing data, not empty fields — junk blanks still become live CRM data.

## Consequences

### Positive

- Safe live enrichment without silent overwrites.
- Auditable field lineage for operators and compliance.

### Negative / constraints

- Expanding the allowlist is a deliberate ADR/code change, not a mapper drive-by.
- Review-only mode requires operator follow-through to inject.

### Implementation rules (agents)

1. Change allowlist only with tests + this ADR update.
2. Do not bypass provenance on live writeback paths.
3. Prefer `writeback.partner_fields` when present; else `final_fields` (existing mapper contract).

## References

- ADR-002 amendment 2026-07-19 (historical; this ADR is the binding writeback SSOT)
- `plasticos_gate/services/gate_mappers.py` (`partner_writeback_from_converge`)
- `plasticos_enrichment` enrichment run Gate path
