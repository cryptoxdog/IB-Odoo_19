# PlasticOS Semantic Kernel: Activation, Integration and Wiring
## Version 1.0.0 | 2026-10-29 | FORMAL WORKING PLAN

**Decision:** KEEP and fully develop the capability. **Current operating posture:** DORMANT. Repair, connect and prove it before an operator separately authorizes use.

This ZIP applies the uploaded **PlasticOS Addon Strategic Development Kernel v0.2.0** to the existing optional Semantic Kernel and its Odoo/Gate/EIE/CEG consumers. It does not implement an addon, change a repository, publish a PR, install a module, execute a backfill or activate production.

The desired product is industrial supply/demand intelligence: source-backed hypotheses about likely material inputs and generated scrap; verified supply and buyer requirements; bidirectional matching; scoped supply/demand and information gaps; and explicit handoff into the one native CRM commercial workflow. These are not interchangeable operations.

## Read in this order

1. `DECISION_LOCK.md`: operator decisions and what is not authorized.
2. `DESIGN/ARCHITECTURE.md`: business purpose, evidence levels, ownership and optional integration choice.
3. `PLAN/WHOLE_CHANGE_PLAN.md`: source-owned changes, delivery order and external dependencies.
4. `DESIGN/WIRING_AND_REWIRING.md`: producer, consumer, identity, transform, denial and proof for every material seam.
5. `DELIVERY/ACTIVATION_RUNBOOK.md`: how dormant development becomes tested and only then activatable.

The detailed data, migration, inference, gap, security, ADR and test documents are routed from those files. Do not load the whole pack into every coding session.

## Plan sources of truth

- `case.json`: Odoo working case using the supplied kernel's unmodified v0.2 schema. It owns operator decisions, Odoo effects, applicability and proof obligations.
- `PLAN/CROSS_REPO_PLAN.json`: external effects, each pinned to its own repository revision. The single-repository kernel schema cannot honestly assign EIE or CEG changes the Odoo SHA, so this bounded companion is explicitly package-local, not a new global L9 contract.
- `PLAN/DELIVERY_GRAPH.json`: combined dependency order; edges mean prerequisite -> dependent, never permission.
- `PLAN/ACTIVATION_STATE.json`: all production authorization remains false.
- Human-readable tables and CSV are projections of these records. Amend the structured owner first, then regenerate/reconcile projections and hashes.

## What is locked, and what is still a gate

Business intent is locked by the user. The newly drafted implementation topology, wire changes and ADR amendments are **proposals pending source-owner admission and acceptance**, not already installed contracts. Actual runtime consumers, installed Enterprise metadata, deployment grants and historical rows were not inspected. These are explicit frontiers, not assumptions.

The included kernel intentionally refuses its plan/precode gates while those material facts are missing. Schema/graph/package checks can pass while execution remains blocked. `ASSURANCE/VALIDATION_SUMMARY.md` separates those results.

## Scope and boundaries

The web-lead, native opportunity, single match-review, offer mail and PO/Lost lifecycle work continues in the branched commercial campaign. This pack consumes its accepted interfaces and tests. It does not reopen PR #329, fix PR #322, change non-HOT Cognito handling, or add accounting/logistics/export work.

Retain the semantic concepts. Do not turn `plasticos.supply.opportunity` into a second independently managed sales pipeline. Do not infer demand from capacity or available inventory from a reusable material profile. No local Odoo intelligence engine and no direct worker egress.

## Provenance and reproducibility

`PLANNING_KERNEL/` preserves every member of the supplied v0.2.0 ZIP unchanged. Its historical source lock matches the freshly resolved Odoo Staging SHA. `EVIDENCE/PREDECESSOR_COMPARISON.json` records byte identity. No runtime results from a different campaign or an old receipt are upgraded to current proof.

Package-only checks are described in `ASSURANCE/VALIDATION_SUMMARY.md`. No target deployment or repository command is supplied as already verified. A future executor must resolve current commands at their actual owner and obtain explicit scope authorization.

**Completion of this deliverable means a formal, auditable working plan exists. It does not mean the product is implemented, source-owner accepted, runtime proven or activated.**
