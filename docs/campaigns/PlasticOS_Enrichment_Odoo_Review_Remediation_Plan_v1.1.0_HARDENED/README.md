# PlasticOS Enrichment | Odoo-Only Completion Plan v1.1.0 HARDENED

**Status:** PLAN_REVIEW, NOT AUTHORIZED TO IMPLEMENT, NO REPOSITORY MUTATION.
**Root:** `cryptoxdog/IB-Odoo_19` Staging `2dc516aa29718b4545faf67e79ca225589ac6d7f` (2026-10-29).
**Method:** Uploaded PlasticOS Addon Strategic Development Kernel v0.2.0 (original 24 file members preserved byte-for-byte in `PLANNING_KERNEL/`). The original v1.0.0 ZIP and package digest are recorded as a distinct predecessor.

## Bottom line

The current addon already sends **Odoo -> Gate -> EIE converge**, stores the returned proposed partner fields in `plasticos.enrichment.run.gate_proposal`, enters `review` under the OFF default, and exposes **Inject**. That button applies every eligible missing field together, not independently. This plan completes an Odoo-native field-by-field review, adds strong server-side security/idempotency/provenance and keeps automatic writeback OFF.

**Start clean means remove unsafe/dead execution branches, not delete historical data.** The current source contains broad all-internal-user ACL grants, a retired cron user granted manager privileges, a stale accepted ADR-012 that claims auto-writeback defaults ON, a local material injector reachable on old runs, and an injected-run state guard with a state+payload bypass. These are now explicit P0/P1 owners and tests.

## Hard constraints

Only `IB-Odoo_19` source may be changed by a later authorized implementation. The EIE/CEG/Constellation.Gate service repositories and Gate_SDK are read-only. The auto-writeback ICPs remain OFF. No CEG nightly scheduler/queue, Semantic Kernel, Offer Drafting/Response, CRM partnerless creation, material matching, local intelligence, payment or accounting work. The two retired Odoo crons stay OFF.

## What the user will see

Native **Contacts > Enrichment** / **Enrichment Runs > Needs Review** with an explicit line per proposed partner field showing current and proposed values, Gate packet ID, source/evidence classification and genuinely available confidence. User chooses **Approve**, **Reject**, or **Skip** individually. A guarded **Apply Approved** action performs fresh source comparison, Odoo access/company/allowlist checks, and atomic writeback/provenance. No changes before approval.

## Read in this order

1. `HARDENING/RECURSIVE_ALIGNMENT_REPORT.md`: source defects, decisions, remaining boundaries.
2. `INVARIANTS.md`: all 21 plan-level locked requirements, not an alteration of the repository's constitution.
3. `REVIEW_UX_AND_DATA.md` and `SECURITY_AND_APPROVAL.md`: exact native Odoo model, field state, approval and evidence semantics.
4. `case.json` and `IMPLEMENTATION_LEDGER.md`: canonical Odoo kernel case and per-file effects; `PLAN/FILE_CHANGE_LEDGER.csv` is a derived view.
5. `ADR/`, `MIGRATION_AND_RECOVERY.md`, `DELIVERY/GRAPH.md`, `TESTS.md` for adoption, testing, rollout and recovery.
6. `ASSURANCE/VALIDATION_SUMMARY.md`: honest distinctions between package-only PASS, intentional kernel readiness refusal and product tests NOT_RUN.

## Proof posture

The case is schema-valid and source-bound to a fresh 30-manifest/current-source-lock census. The kernel **still refuses** plan/precode readiness for three real unknowns: installed Odoo.sh Enterprise/dynamic consumers, remaining source-owner/operator choices, and external deployed packet/config. Those are U00 requirements, not reasons to manufacture PASS. No code, deployment or production writeback was changed by this pack.
