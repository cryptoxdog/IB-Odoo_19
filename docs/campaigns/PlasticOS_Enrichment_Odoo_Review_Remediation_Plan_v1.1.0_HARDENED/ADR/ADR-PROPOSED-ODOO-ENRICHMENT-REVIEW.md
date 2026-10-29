# Proposed ADR: Odoo-native granular Gate-result review and verified CRM admission

**Status:** PROPOSED, not adopted by repository source owners. No repository file is changed by this ZIP.
**Owner:** `cryptoxdog/IB-Odoo_19`; current baseline `2dc516aa29718b4545faf67e79ca225589ac6d7f`.
**Proposed final repository path:** `docs/adr/PROPOSED-enrichment-granular-approval.md` until source owner assigns a unique approved ADR number.

## Context

`plasticos.enrichment.run.action_execute()` sends Gate `converge` to EIE and currently stores a `gate_proposal` with `proposed_partner_fields` plus run-level metadata. It defaults to `review` under two OFF ICPs. `action_inject()` applies all eligible fields at once, not field by field. `plasticos.enrichment.provenance` records applied writes; it is not a reliable approval-state model. An independent accepted ADR-012 claims live one-switch default, contradictory to the current two-switch OFF code. Broad current ACLs, old cron manager grant and legacy local injector create risk if review is extended without hardening.

## Decision proposed

1. Preserve the existing addon, `res.partner` (current run requires existing partner), `mail.thread`, native models/menus, `plasticos_gate` sole SDK route, current eight-field allowlist and existing failure/retry envelopes.
2. Introduce one minimal **proposal-line** ORM model within `plasticos_enrichment`, not an alternate enrichment/supply/CRM addon. Raw mapped Gate response stays source evidence on `enrichment.run`; proposal lines are immutable projections plus user decisions. `enrichment.provenance` remains committed-write history.
3. Successful completed Gate converge produces review lines; no partner write occurs until each eligible line is explicitly approved and separately applied by an authorized human. The runtime's legacy auto_writeback switches are not approval for this workflow and stay OFF.
4. Show current and proposed values, honest evidence scope (per-field if source-bound, else aggregate run only), typed validity, field availability, reviewer and decision in native Odoo forms. Operator attestation is separate from EIE evidence and must be captured explicitly.
5. Apply Approved is server-authorized, company-scoped, row-lock/CAS protected, exact-source-and-field-revalidated, idempotent, and writes no nonallowlisted, conflicting, unavailable or prefilled field. Successful fields and provenance commit atomically; rejects remain unmodified.
6. Do not mark a completed no-writable-field Gate response as transport failure or injected. Do not mark 0 applied as injected. Preserve trusted source/digest/packet/correlation/KB/inference-version metadata and unknown confidence honestly.
7. Disable legacy local material-profile injection from old `validated` records. Retain old local runs, extraction/source records, original migration and stable Odoo IDs as audit; no cleanup wipes history.
8. Amend broad ACLs, company record rules, terminal state guards and retired cron privilege grants only after installed-state census. Preserve retired local crons and their no-op entrypoints.
9. No external EIE/CEG/Gate service/code changes, no Odoo autonomous enrichment ranking, no semantic kernel or offer integration. Only approved existing contacts, not new suppliers before PO.
10. Build/rehearse on Odoo 19 Enterprise with a verified DB+filestore pair and captured negative cases, then obtain independent review and a separate publication/deployment grant. A source-bound plan is not operational readiness.

## Alternatives rejected

- Bulk Inject unchanged: cannot express field-by-field approval or stale/source guards.
- Reuse `plasticos.enrichment.provenance` as pending approval: converts an actual write receipt into ambiguous proposal evidence and corrupts historic semantics.
- New addon/service/queue: duplicates existing ownership and risks dependency coupling.
- Immediate auto_writeback after successful EIE run: contradicts the locked manual approval requirement.
- Reinstate old crawler or crons: contradicts accepted external Gate/EIE/CEG authority.

## Contract/migration/assurance

No new external packet fields assumed. All changes are to the Odoo owner, its native schema/UI, accepted ADR-012 and controlled tests. Additive version migration preserves historical rows and explicitly verifies installed ACL and cron states. `case.json` effects E01-E33, proofs P01-P32 and `DELIVERY/DEPENDENCY_GRAPH.json` are the bounded implementation contract proposal, subject to U00 closure and source-owner acceptance. Any material discovering an external contract gap stops that feature and requires separate authorization.
