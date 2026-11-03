# PlasticOS domestic multi-load foundation | Cursor execution pack

> **⚠️ SUPERSEDED (2026-11-03): DO NOT EXECUTE.** The campaign's mission was implemented
> and merged into `Staging` on 2026-10-29 through the PR chain ending in PR #339
> (`2dc516aa`). All ML-ROOT and ML-CONS items are resolved in current code. See
> `10_EXECUTION_STATUS_AUDIT_2026-11-03.md` for the per-claim verification. This pack is
> retained as a historical contract record only.

**Contract status:** SUPERSEDED — IMPLEMENTED UPSTREAM (was: USER-AUTHORIZED FOR FUTURE EXECUTION, NOT EXECUTED).  
**Contract ID:** `PLASTICOS.DOMESTIC.MULTILOAD.ONE_PR.2026-10-28`  
**Target:** `cryptoxdog/IB-Odoo_19`, **Staging**, one subsequent feature PR.  
**Source evidence:** `Staging@04bd0594a7c9dcad53d9c45fc65276d76817c112` as independently inspected October 28, 2026. Not a frozen execution base.  
**Mandatory predecessor:** the *separate* Documents verification + exact association PR, implementing the two preceding contracts, must be **merged into Staging** and its updated Documents contracts/tests inspected before starting this campaign.

## Start order

1. Load the installed `l9-coding-agent` skill and current repository `AGENTS.md`, relevant `.cursor` rules, accepted ADRs, current `INVARIANTS.md`, Logistics and Documents/Claims BRS owners. Treat draft POS-INV v3.3.0 as user intent and working architecture, not as automatically admitted constitutional authority.
2. Read `01_CURSOR_CODING_CONTRACT.md` (the **single** execution contract). `02_EXECUTION_CONTRACT.yaml` is its structured mirror, not a second campaign.
3. Read `03_SOURCE_AND_CONSUMER_CENSUS.md` and `04_MIGRATION_AND_COMPATIBILITY_PROTOCOL.md`. Inventory *current* source after the predecessor merge, not just the October 28 snapshot.
4. Read `05_REQUIRED_ACCEPTANCE_MATRIX.json` (7 inherited + 25 additional required positive/negative cases, 32 total) and `06_ENTERPRISE_VALIDATION_AND_ONE_PR_GATE.md`.
5. Execute **one** branch and bounded remediation, verify on a disposable *Odoo 19 Enterprise* clone including fresh installation and upgrade migration, then run **`make pr`** once all gates pass. A protected, operator-authorized historical record set is mandatory in addition to synthetic fixtures. A protected, operator-authorized historical record set is mandatory in addition to synthetic fixtures. Never raw-push or open a second PR.
6. Emit the completed `08_EXECUTION_RECEIPT_TEMPLATE.json` with actual results and exact PR/head. An unrun probe is `NOT_RUN`, not PASS.

## Hard boundaries

**Do:** enable a real domestic transaction to own 0..N actual physical loads; preserve exactly one source-proven owning transaction per load when applicable; stop first-load selection; correct consumers and migrate historical records without inventing business facts.

**Do not:** implement Export, booking/container aggregation, warehouse/shop-floor flows, freight product expansion, AI activation, new mailing automation, financial calculation changes, inventory creation, broad ACL policy changes, constitutional rule changes, or Production deployment. No new PR before the prior Documents PR is merged. No default user/company/partner/date-based attribution.

## Source/evidence classification

- `OBSERVED_SOURCE`: the October 28 Staging source contains the one-slot transaction field, reverse compute, first-link load auto-link, multiple single-slot consumers, and SQL dashboard join.
- `USER_TARGET`: domestic multi-load cardinality with compatibility and history preservation; this contract authorizes implementation *only within its boundaries*.
- `OPEN_AT_EXECUTION`: actual final predecessor PR head, installed Enterprise schema, migrated data cardinalities, preserved accounting/claim/document semantics, local CI/EE fixture availability.
- `NOT_RUN`: all code execution, migration, runtime acceptance tests and publication in this handoff.

## Files

- `01_CURSOR_CODING_CONTRACT.md`: executable operator contract, with repository access declaration first.
- `02_EXECUTION_CONTRACT.yaml`: machine-readable normalized contract.
- `03_SOURCE_AND_CONSUMER_CENSUS.md`: pinned source observations and required refreshed dependency inventory.
- `04_MIGRATION_AND_COMPATIBILITY_PROTOCOL.md`: reversible migration and historical truth gates.
- `05_REQUIRED_ACCEPTANCE_MATRIX.json`: precise positive/negative probes, all NOT_RUN.
- `06_ENTERPRISE_VALIDATION_AND_ONE_PR_GATE.md`: exact environment, test and publication protocol.
- `07_COPY_TO_CURSOR.md`: compact paste-ready activation message.
- `08_EXECUTION_RECEIPT_TEMPLATE.json`: unfilled verification template.
- `09_OWNER_BOUNDARIES.md`: semantic ownership and prohibition summary.
- `MANIFEST.json`: SHA-256 manifest of all deliverables.

**Result of this handoff:** a contract ZIP only. No repository changes, tests, PR, merge, or deployment performed.
