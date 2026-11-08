# ADR-010: Odoo owns CRM writeback policy

## Status

Accepted — LOCKED

## Date

2026-08-31

## Context

EIE returns enrichment information. Whether that information may modify a
customer record — and which fields, and whether a human approves first — is a
business and data-governance question about Odoo's own CRM, not an inference
question.

## Options Considered

### Option A: Odoo owns writeback policy (chosen)
- Pros: the system that owns the data owns the mutation rules; the allowlist
  and review state live next to the records they protect; EIE stays a pure
  producer.
- Cons: every consumer of EIE must implement its own writeback policy.

### Option B: EIE or Gate returns a `writeback` directive Odoo applies
- Pros: one policy shared by all consumers.
- Cons: an external service would decide which CRM fields to overwrite, with no
  view of Odoo's field semantics, permissions, or audit obligations.
  **Rejected.**

## Decision

EIE returns enrichment information. Odoo determines whether and how that
information modifies CRM state. Odoo exclusively owns: the field allowlist;
merge-not-overwrite; review state; business identity mapping; automatic
writeback enablement; the writeback audit trail.

Canonical policy:

| Field state | Behavior |
|---|---|
| blank, allowlisted | may populate |
| populated, allowlisted | preserve existing value |
| not allowlisted | never write automatically |

Odoo writeback policy must not move into EIE, Gate, or Gate_SDK.

## Consequences

- Automatic writeback stays off by default; the proposal is stored for human
  review with provenance until an operator enables it.
- Repo ADR-012 (CRM writeback allowlist, merge-not-overwrite, provenance)
  remains the detailed field-level specification; this ADR fixes the ownership.
