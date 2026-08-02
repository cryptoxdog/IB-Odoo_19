# ADR-127: Consume EIE Evidence→Odoo Mapping in plasticos_gate

**Status:** Accepted
**Task:** TASK-053
**Date:** 2026-08-02

## Decision

`plasticos_gate` consumes the EIE-produced FeatureEvidence→Odoo mapping via a
vendored consumer copy at `plasticos_gate/data/evidence_odoo_mapping.json`.

Apply policy is implemented in `plasticos_gate.services.evidence_mapping`:
- merge-not-overwrite
- human-approved precedence
- review proposals only (`propose_review`); no direct partner writes here

## Non-goals

- Activating auto-writeback ICP changes
- Cross-repo live import of EIE Python packages
- Parity checksum proof (TASK-054)

## Acceptance

- Consumer contract loads with proposal_only projections
- Allowlisted evidence yields review proposals
- Human-approved / newer Odoo field state rejects overwrite
