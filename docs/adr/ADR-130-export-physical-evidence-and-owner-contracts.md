# ADR-130: Export physical evidence and owner contracts

**Status:** Accepted for the S2 Logistics foundation; Export (S5) parts are planned, not installed
**Decision date:** 2026-11-11
**Applies to:** `plasticos_logistics` (`plasticos.load`, `plasticos.iso.journey`, `plasticos.iso.journey.source`, freight context and evidence), `plasticos_security_base` (company and role grants), and the future `plasticos_export` addon
**Decision owner:** Operator (GATE0 module approval and code grant, 2026-11-11)
**Implementation owner:** each source module named below; Export only specializes downstream
**Sources:** `docs/campaigns/future-add-ons/PlasticOS_Export/` — `EXPORT_BRS/MODULE_DESIGN/TECHNICAL_CONTRACT_v2.7.json` (six models, twelve commands; unchanged), `EXPORT_BRS/INTEROP/SOURCE_BOUND_CHANGE_PLAN_v2.7.5.md` (C01-C09), `EXPORT_BRS/INTEROP/REPIN_OVERLAY_v2.8.json`, `STRATEGIC_EXECUTION_PLAN_v2.8.md`, and the business rules `EXPORT_BRS/RULES/BRS-EXP-01..14`. This record cites them; it does not copy or change them.

ADR-129 was taken by rate-memory reconciliation ownership, so this record uses the next free number (re-pin overlay v2.8).

## Context

Export needs a physical identity for an ocean container cycle, exact provenance from the loads, stock moves or original documents that fed it, a company for every movement, and one guard before any new instruction is issued to a carrier. The existing code tied a load's company to its sale order, so a buyerless supplier-backed movement had no company. Freight confirmation needed an intake repeat stream even for a manual rate. Several routes could release a physical instruction without one shared check, and the acknowledgment job resent the full packet.

## Decision

### Ownership

| Fact | Owner | Not owned by |
|---|---|---|
| Load source company | `plasticos.load.company_id` (Logistics): its sale order's company, or the company named for a buyerless movement | `env.company`, a default, the user running a migration |
| Load parent | `plasticos.load.transaction_id`; `plasticos.transaction.load_ids` is its inverse. One transaction may own many loads; a load has at most one parent | a `transaction.load_id` field or a UNIQUE on it (retired) |
| Container journey identity (J1) | `plasticos.iso.journey` (Logistics): company + source-cycle key | ISO number alone, trailer number, booking number, package, `plasticos.equipment.type` |
| Journey provenance (J2) | `plasticos.iso.journey.source` (Logistics): one exact typed subject (load, stock move line, or non-stock original evidence) | quantity, stock, finance, or document verification |
| Release of a new physical instruction | `plasticos.load._physical_release_errors` / `assert_can_release_physical_operation` (Logistics); Documents and Export add reasons by ordinary `_inherit` | each caller's own ad hoc check |
| Actual pickup / delivery time | `plasticos.load.actual_pickup_at` / `actual_delivery_at` with their evidence attachments, written only by `action_record_actual_event` | state transitions, imports, scheduled times |
| Business role grants on J1/J2 | `plasticos_security_base` (`group_logistics`, `group_operations_manager`) | `base.group_user` |
| Booking, slots, cargo allocation (E1-E4) | `plasticos_export` (S5) | Logistics |

### Contracts

- **Routes.** A sale-backed parent shares the load's sale order and company and names its real supplier and buyer. A buyerless load may join a purchase-backed transaction whose purchase orders are all in the load's company and which names its supplier. No buyer, sale order, transaction or picking is created to satisfy a constraint. An ambiguous sale-order match is refused, not resolved by picking one.
- **Freight context.** `freight_context_v3` stays byte-for-byte for intake-backed loads. `freight_context_manual_v1` covers a load with no intake stream: exact company and lane, equipment recorded as the explicit `unknown`, no repeat-stream key. It confirms a manual rate only. Same As Last abstains before any history lookup when there is no intake stream. The version recorded on the load selects its validator.
- **Evidence company.** Freight evidence takes the load's own company. Only a state-transition audit event of a legacy company-less load may fall back to the acting company, and it says so in its facts.
- **Release and observation.** The guard runs on schedule, dispatch, `_transition` to Scheduled or Dispatched (so the bulk wizard too), the packet and document composers, direct dispatch send and the standalone `plasticos.dispatch` transition. Recording an event that already happened is not routed through it. The acknowledgment job escalates once a day after four hours from the recorded send and does not resend the packet. `dispatch_sent` is stamped only on a confirmed send.
- **J1/J2.** Company-scoped global rules with no company-null escape. Attributed identity and accepted sources are immutable and cannot be deleted. SQL constraints prevent null-subject and duplicate-subject gaps. Evidence attachments use `ondelete="restrict"`.
- **Company isolation.** The `plasticos.load` global rule has no company-null escape. The SQL Load dashboard projects `company_id` and has its own global company rule.
- **Dependencies.** Export depends on Logistics, Documents and Security Base; nothing upstream depends on Export. Logistics does not depend on Documents, Native Documents, Security Base or Export.

### Frozen commands realized in Logistics

`plasticos.iso.journey.action_register_iso_journey`, `plasticos.iso.journey.source.action_bind_journey_source`, `plasticos.load.assert_can_release_physical_operation` and `plasticos.load.action_bind_exact_transaction_load` keep the parameters and the `{status, record_id?, reason?}` result of the technical contract. The other eight commands belong to Export, Documents and Linda and are not part of this slice.

## Migration

Logistics `19.0.1.14.20` pre-migration classifies every load from its own columns. One agreeing source company is kept or repaired and logged; no source, or conflicting sources, stops the upgrade before any row changes. J1/J2 start empty. The post-migration verifies the result and is a no-op on rerun. Security Base `19.0.1.2.25` pre-migration refuses to tighten the rules while any load lacks a company or the dashboard lacks `company_id`; it assigns nothing.

## Consequences

A database with a load that has no sale order and no other source company cannot upgrade until an operator gives that load its company. A user cannot create a load without naming its source company. Same As Last never reuses a manual rate. Booking holds and document-policy holds plug into the same release guard downstream. The +2h Linda acknowledgment notice and the request-targeted booking, acknowledgment and document-chase templates are the Linda slice (S4) and stay disabled until then.

## Proof

Runtime witnesses: `plasticos_logistics/tests/test_iso_journey.py`, `plasticos_logistics/tests/test_load_cardinality.py` (`TestLoadSourceCompanyAndPhysicalEvents`), `plasticos_security_base/tests/test_bridge_contracts.py` (`TestLoadCompanyIsolationContract`), and the pure-Python `tests/test_freight_context_service.py`. Passing tests do not activate Export, live mail or any production change.
