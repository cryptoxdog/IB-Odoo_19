# PlasticOS | Production-first working plan graph v5.0

**Bottom Line:** The November 9 objective is a usable, imported, test-ready **Production** for humans to test, not a bug-free final release. After data/installation/Admin proof, test native web-lead qualification, domestic logistics automation and document automation; exhaustively inspect active UI and remove only verified bloat; **then** authorize Export. External matching and enrichment stay dormant.

**Status:** WORKING PLAN, NON-ADMITTED, NO DEPLOYMENT/IMPORT/MAIL/POSTING AUTHORIZED BY THIS ZIP.
**Source checkpoint:** GitHub `Staging@bdc222246fbfb647e8e008046b759eecd60a2028` and `Production@729d3ab0b7cd7a0cb1058528e7c0e28cdcc08b56` observed 2026-11-09. Original v4.0 working predecessor SHA-256 `f3f5dfb1d4e145ddb6d97f5d19ba25ce816d64bcfe7bf6e1b28d6c0faebf7818`. PR #408 merged `Staging@b5b6056f01639212e722ccdec5b964b36deee9f5` into `Production` 2026-11-08, but Odoo.sh runtime installation and imported database rows have NOT been independently inspected.

## What exists in source and what does not yet have hosted proof

- **Admin menu and dashboards exist** on the Production branch (`plasticos_admin_dashboard/views/admin_dashboard_views.xml`): Admin -> Command Center -> Logistics Dashboard / Sales Dashboard / Rep Performance. Admin menu group is `plasticos_security_base.group_system_admin`. The addon is `installable=True`, **`auto_install=False`**, so actual addon installation, group membership, home tile visibility and navigation must be tested on the real Production account.
- **Load dashboard is not a full historical-load census by default:** the underlying SQL VIEW (`plasticos_logistics/models/load_dashboard.py`) excludes closed loads last changed before the current month. The Logistics menu also defaults to the active filter. The operator expects *all loads*. A bounded owner-side choice/fix and a real UI/data test are required before calling this a complete snapshot; do not add a parallel dashboard to hide the issue.
- **Documents** native verify/override delegate to one PlasticOS business decision; partner-recency no longer authoritatively attaches an original (`#322`). **Transactions support 1:N loads** in source; both need Production behavior tests.
- **Constitutional `INVARIANTS.md` v3.0.0 was admitted November 8**, not the old v3.2/v3.3 draft proposed here. External intelligence fail-closed requirement remains active; matching/enrichment activation is out of current QA.
- **Limited Nov 8 rehearsal recorded seven gates PASS** for its source head; it does not show full ERP/CRM import or current hosted Production status. `workflow_state.md` still records unresolved full cohort/source coverage and the no-auto-post accounting boundary.
- **Staging is newer than Production:** PR #414 Same As Last/VanillaSoft fidelity and #415/416 Gate work are merged on Staging after #408. PR #418 was open at this checkpoint. Test what is truly installed on Production and promote only separately authorized changes.

## Required stage order

1. **Test-ready Production baseline.** Verify pinned Odoo.sh Production build, required addons installed/healthy, source-authenticated full ERP/CRM transactions/contacts import census with explicit exceptions, no duplicates or archival accounting posting. Confirm source DB vs target. Verify Admin tile, allowed group, Command Center and drill-throughs. **No inference that imports are done from a merge or 10% rehearsal.**
2. **Basic functionality smoke.** Three parallel lanes on current hosted code with safe tagged test records: `PL-PROD-WEBLEAD-QA` (qualification and HOT/other state); `PL-PROD-LOGISTICS-QA` (many-load, Same As Last, rate, timers/reminders in safe mode); `PL-PROD-DOC-QA` (original, exact association, verification, request, expiry/compliance). Confirm no forbidden mails, stock movement or postings. Do not use CEG matching or EIE enrichment.
3. **Kick-the-tires UI sweep.** Enumerate installed root menus, child menus, actions, form buttons, wizards and notifications; click all permitted paths on tagged reversible test data. Capture per-button PASS/FAIL/SKIP with exact build, actor, permissions, expected/actual, screenshot/log and defect owner. Fix blocking failures; remove a UI path only when the proper owner confirms it is duplicative or unused. Do not create more dashboards or blanket refactors.
4. **Export next.** Once basic QA and UI sweep are accepted, implement `PL-FUT-01` in a *separately authorized* phase, reusing domestic Logistics, native Sales/Purchase/Stock, Documents and Linda. Export should integrate, not fork, domain writers. Optional AI, matching, enrichment and warehouse/shopfloor are not upstream blockers.

## Key active failures vs completion

| Criterion | This ZIP's evidence class | Current disposition |
|---|---|---|
| Production GitHub branch promoted | GitHub PR #408 + current Production branch | SOURCE CONFIRMED; hosted app not confirmed |
| All eligible ERP + VanillaSoft + transaction history imported | Read-only Production source/target census needed | UNKNOWN; test-ready target, not completion |
| Admin tile accessible in live Production | Code XML + addon manifest only | SOURCE PRESENT; LIVE ACCESS UNKNOWN |
| Admin shows literally all loads | Current SQL VIEW filters older closed loads | SOURCE CONTRADICTION, bounded acceptance item |
| Web-lead qualification, logistics, documents | Source available; live interactive tests not performed here | NOT RUN |
| Every button and all installed app screens | No hosted UI access | NOT RUN |
| Matching/enrichment and Export | Operator explicitly defers | NOT AUTHORIZED CURRENT PHASE |

**Read:** `03_DOMAIN_PHASE_AND_DEPENDENCY_VIEW.json` (owned work DAG); `11_CAPABILITY_OWNERSHIP_AND_IMPLEMENTATION_GRAPH.json` (implementation capability state); `24_RELEASE_GATE_GRAPH_2026-10-30.json` (release gate view, now refreshed to Nov 9); `29_RELEASE_SOURCE_BINDING_AND_NEXT_PROOFS.json` (current GitHub evidence); `30_PRODUCTION_QUALITY_SWEEP_2026-11-09.md` (exact user QA workflow); `20_SUCCESSOR_VALIDATION_AND_CHANGE_REPORT.json` (change integrity and limits). `02` and `22` are historical non-admitted strategic overlays, not newly admitted source.

**Package basis:** October 30 v4.0 working ZIP was used as predecessor because it contains the full current graph plus prior release overlays; tracked repo October 28 graph contains only the earlier 25-file slice. All 32 predecessor files are retained or updated and their changed bytes recorded in the successor report. No missing invariant draft file has been invented or claimed present.

## Nov 9 v5.1 post-import enrichment (supersedes narrower v5.0 exit order)

Operator added four obligations after Production base data import: verified PostgreSQL+filestore, full worksheet-original import, native document AI with manager review exceptions, and source-grounded accounting opening balances with a repeatable controlled reopen Make target. The already-locked DR v1.3 campaign is linked, not replicated. The next Export build now waits for post-import acceptance `PL-PROD-EXTENDED-ACCEPT`, not only a clean UI sweep. The live financial-ledger writer switchover is a **separate explicit authority gate**.

Start with `03_DOMAIN_PHASE_AND_DEPENDENCY_VIEW.json` (dependency graph), `31_POST_IMPORT_BLOBS_AND_DOCUMENT_AI.md`, `32_ACCOUNTING_REPORTS_AND_REOPEN_MAKE.md`, `33_EXISTING_DISASTER_RECOVERY_POINTER.md`, `34_POST_IMPORT_ACCEPTANCE_CASES.json`. Existing v5.0 files and non-admitted historical strategic candidates remain preserved. All new cases are `NOT_RUN`.
