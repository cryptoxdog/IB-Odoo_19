# Proposed ADR SK-A01: controlled activation of semantic supply/demand intelligence

**Status:** Proposed for source-owner adoption; operator intent locked, implementation and activation not authorized.
**Proposed owner/path:** cryptoxdog/IB-Odoo_19, docs/adr/PROPOSED-semantic-kernel-controlled-activation.md.
**Baseline:** Staging 677d734fd88615d673501d91de88734b7150ff50.
**Scope:** semantic persistence, source admission, conversion, optional integration and operator handoff.

## Context

ADR-122 introduced passive supply and demand records while preserving external matching authority. ADR-124 deliberately blocked ambiguous automatic conversion. ADR-127 separately limited field authority to specification. Those guards protected unfinished wiring, but do not implement the full industrial intelligence capability. The current CLI forces dry-run and its planner cannot prove ORM creation; the semantic module can expose a second editable record surface when installed.

The operator now requires full development while dormant: infer potential supply/demand from industrial evidence, confirm actual facts separately, synchronize current source facts, match in CEG, assess scoped gaps and hand qualified work back to one native CRM workflow.

## Decision

1. Native CRM opportunity owns one commercial attempt for a marketable load or supply contract. Derived SupplyOpportunity is not a second sales pipeline. Material profile is reusable; the approved opportunity snapshot is current offered material.
2. Preserve evidence classes: inferred, verified and current commercially actionable. Neither high confidence nor a material profile creates available supply or confirmed demand.
3. Reuse existing lead-owned facility/material identity before partner creation. Do not create a partner to satisfy semantic schema. Verified partner/PO/Won semantics remain the native commercial campaign's boundary.
4. Retain passive semantic models and stable IDs. Restrict derived supply/demand writes to checked source admission/projection; no independent commercial actions.
5. Admit a narrow optional integration bridge only after the documented sufficiency test establishes an existing owner cannot meet the integration and durable-replay needs without optional-install coupling or violation of passive-kernel boundaries. No mandatory addon may depend back on it.
6. Replace blanket supply/demand backfill prohibition only for explicitly admitted source contracts and reviewed bounded batches. Ambiguous legacy conversion remains prohibited. Dry-run remains default and ordinary install/upgrade has no data or external side effects.
7. A real persistence adapter must report committed effects, not intentions. Source revisions, mapping versions and business identity are separate. Replays and mapping upgrades cannot duplicate a load.
8. Keep backfill, projection, industrial inference, gap assessment and read-authority cutover independently scoped. Existing specification behavior is preserved. Guard every real call site; UI state or unauthenticated context is insufficient.
9. Intelligence egress remains plasticos_gate -> Gate -> EIE/CEG. The engine owners retain their concerns. No local intelligence or peer bypass is introduced.
10. Findings appear in native read-only review surfaces. Operator qualification may create/reuse a CRM lead or link a qualified opportunity. The kernel cannot send offers, create partners/POs or mark Won.
11. Production remains dormant until the final pinned release passes the proof matrix, recovery has been demonstrated and the operator separately authorizes tenant, operation and deployment scope. Tests are not authorization.

## Consequences

The useful semantic capability is retained without activating a duplicate workflow. Some existing source constraints, payload examples, ACLs and independent menus require narrow revision. The optional lane needs its own install/upgrade tests; default critical-path green does not cover it. Unqualified web-lead disposition stays deferred.

## Compatibility and migration

Preserve existing UUIDs, external identifiers and approved evidence. Retain unbound historic semantic records read-only/nonmarketable until reconciled. Current supplier/partner restrictions are changed only together with validated owner/prospect alternatives, downstream mappings and data constraints. Preserve the CRM reconciliation mechanism already present. Any future wire shape requires a versioned consumer-compatible contract.

## Required supersession

Apply only the changes listed in ADR/AMENDMENTS.md to ADR-120/121/122/124/125/126/127. ADR-003 single external authority remains binding. Commercial-first replacement of the old intake workflow is owned by the separate opportunity campaign; reference it rather than author competing lifecycle law.

## Acceptance and activation

P01-P05, P07-P13, P19-P29 and P30-P34 apply as routed. Source-owner implementation decisions, installed registry observation and an authenticated execution grant are prerequisites. The initial accepted state is ready-but-disabled; production enable is a separate operator event.
