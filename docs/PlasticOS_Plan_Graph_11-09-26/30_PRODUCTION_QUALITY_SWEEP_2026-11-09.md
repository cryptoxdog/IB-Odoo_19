# Production quality sweep and Export exit gate | 2026-11-09

**Intended starting point:** Odoo.sh Production testable under a named admin account, complete eligible ERP/CRM historical datasets imported and reconciled, and all required active addons installed. It is a **target requiring receipt**. A clean Git merge and partial rehearsal do not prove it.

## P0. First five minutes: verify environment, not feature depth

1. Record active **Production build/commit**, database name, company, user groups, active addon list, and install/upgrade logs. GitHub `Production@729d3ab0b7cd7a0cb1058528e7c0e28cdcc08b56` is only repository evidence. Do not assume newer Staging patches exist in Production.
2. Obtain *read-only* Production import census for source ERP partner/transaction/invoice/bill cohorts and VanillaSoft full approved contact cohort, including exclusions and unresolved counts, collision/replay evidence and source SHA. Archive invoices/bills remain drafts; no opening GL, payments, or automatic posting from this plan. A prior 10% rehearsal does not count as a full import.
3. Open Odoo home as authorized Admin. Confirm **Admin** root tile/menu exists. Open **Command Center**, Refresh, Sales Dashboard, Logistics Dashboard, Rep Performance. Test no-data, zero-count/empty state and real imported history separately. A lack of live transactions is an acceptable zero KPI, not proof of a broken import or an invisible load list.
4. Verify **Admin group** membership and module `plasticos_admin_dashboard` installed (`auto_install=False`). If tile is missing, inspect actual installed module/group/menu instead of adding a duplicate menu or assuming source has no Admin.
5. Test dashboard **all-load** truth: with a closed load older than start of current month, confirm whether it appears. The source VIEW filters it out (`WHERE l.state != 'closed' OR l.write_date >= date_trunc('month', NOW())`). The Logistics menu's default active filter is additional restriction. For a literal all-load snapshot, resolve at `plasticos_logistics/models/load_dashboard.py` and existing action/search definitions with company scoping and performance proof, not another model/UI layer.

## P1. Core automation probes, safe side effects

| Feature | Positive path | Negative/guard path | Result required |
|---|---|---|---|
| Web lead | Valid authenticated lead; HOT qualification creates or links correct Partner/Material Profile + Opportunity | Invalid auth, duplicate/replay, non-HOT/manual review, unknown polymer | Correct state and provenance, no synthetic facility or external matcher |
| Transactions | Imported historical records visible, operational draft/SO/PO navigation; multi-load membership | Archived invoice cannot auto-post, stale/unauthorized edit, duplicate same-source replay | No silent loss, no commercial duplicate, no financial side effect |
| Logistics | Create/edit load from transaction, two loads per transaction, milestones and dashboards | No buyer for valid PO-only, ambiguous freight, unsafe dispatch, cross-company, stale link | Each load correctly attached, no fabricated order or message |
| Linda automation | Due reminder/task shows correct recipient/milestone/revision in controlled mode | Shadow/disabled does not send; uncertain provider outcome does not resend | No real external messages without separate permission |
| Same As Last | Copy latest completed deal as one draft: orders, carrier, freight, one load per source load | Two concurrent attempts, unfinished copy, no fingerprint | Exactly one safe draft result, never auto confirm/post |
| Documents | Upload original; exact typed association; verify/override; request/reminder; expiry | Wrong revision, unauthorized role, partner-recency guess, read-only compliance | One decision writer, no invoice posting/mail/stock from read |
| Admin | Refresh, drill-down to Sales, Logistics, all load states and Rep Performance | Missing admin group, stale SQL view, empty-state screen, old closed load | Visible authorized tile, accurate data/projection, no access leak |

**Control:** Every dangerous action (external mail, production payment, financial posting, stock movement, public webhook, actual dispatch) requires an authorized test account/mode or separately authorized disposable records. Do not produce real economic or customer effects by clicking blindly.

## P2. Every-button sweep

Build a census from the **installed** `ir.ui.menu`, `ir.actions.*`, active forms/buttons, list/kanban actions, wizards, server actions and scheduled automations. For each available role (Admin, Sales, Logistics, Documents, Accounting) and each active installed app, record:

`build SHA | company | role | module/menu/view/button | test record | expected action | actual | PASS/FAIL/SKIP with reason | log/screenshot | issue/owner | retest SHA`

**Coverage:** Admin and dashboards; Partners/Materials; ERP/CRM imports and search; leads/qualification; Opportunity/Offer presentation (without Gate match execution); Transactions/SO/PO and accounting historical archive; Logistics/Loads/Linda/dispatch/rate; Documents/uploads/requests/verification/compliance; security/navigation/reports/Settings only if installed and within the role's access. Check zero-live-data empty states and histories separately. Enumerate actual installed menus rather than assuming every source addon is enabled.

Test navigation, create/edit/search, filters, changed dates, state transitions, validation errors, disabled fields, binary attachments, company/role isolation, back buttons, refreshes, concurrent clicks, and UI-triggered cron/scheduler routes with an explicit safe test harness. Capture exceptions even when Odoo toast dismisses them.

**Defect disposition:** P0 stop: data corruption, duplicate financial/source identity, unintended outbound sends, wrong company access, or broken core screen. P1 fix before accepting core: live crash, nonfunctional core button, missing Admin access, wrong load coverage, essential automation failure. P2 file and triage before Export: cosmetic or optional edge flows. A known issue is not silently waived; every one needs fix, proven invalid, or explicit nonblocking exception.

**Zero bloat:** Only installed and user-facing paths are candidates. Remove duplicate buttons, redundant menus, dead automations, and gratuitous parallel models after source-owner and permission review. Do **not** sweep unrelated packages or refactor code that already satisfies the current obligation. Do not add a duplicate logistics dashboard to fix an SQL filter.

## P3. Exit to Export

Go when `PL-PROD-TEST-BASE`, `PL-PROD-CORE-SMOKE`, `PL-PROD-UI-SWEEP` and `PL-RELEASE-BUSINESS-ACCEPT` are independently accepted with exact build and no undisposed P0/P1 failures. Accepted documented P2 bugs are permitted; bug-free is not required. This is *permission to propose an Export build*, not automatic deployment or a new global product architecture.

Reuse domestic native Sale/Purchase/Stock and existing `plasticos_logistics` physical loads, `plasticos_documents` originals/evidence and Linda correspondence. Bound the Export-specific BRS, logistics shipment grouping, container, customs and reporting owners without stealing the domestic writer. External matching, enrichment, AI extraction and warehouse/shopfloor remain independent later phases.

## Live verification to request, not claim

No live signed-in Production Odoo UI or database was accessible in this planning run. The Admin menu and view code were inspected on GitHub `Production@729d3ab0b7cd7a0cb1058528e7c0e28cdcc08b56`; true tile visibility, group membership, installed module, dashboard contents and data import completeness must be observed at the hosted instance. If the current Production build lacks PR #414/#415/#416, do not assume their features are already deployed.

## P4. Post-import work added Nov 9: source-owned follow-on gates

Core QA remains first. Follow `31_POST_IMPORT_BLOBS_AND_DOCUMENT_AI.md`, `32_ACCOUNTING_REPORTS_AND_REOPEN_MAKE.md`, and `33_EXISTING_DISASTER_RECOVERY_POINTER.md` with machine-checkable unrun cases in `34_POST_IMPORT_ACCEPTANCE_CASES.json`.

- Verify native PostgreSQL **and** filestore plus prechange backup before importing worksheet binary originals. Current extraction/match counts are historical test evidence, never Production proof.
- Import all eligible `W/#` exact worksheet originals once, quarantine unmatched/corrupt, reconcile complete source counts, no automatic verification or financial side effects.
- Test real native document AI with existing docs and imported evidence, and signed-in manager account review queue. `verification_review_required` in source alone is insufficient.
- Financial report cutoff: ERP transaction/AP/AR/inventory, QuickBooks TB+remaining GL, bank statement opening; original full-gross historic invoices remain Draft. Reopening trade is a **different** operation from residual opening AP/AR.
- Build and test `make reopen-erp-transactions` from approved *operational* exception reports, dry-run and replay proof; native Accounting still owns residual-only AR/AP opening and zero AR/AP clearing.
- Run existing DR v1.3 contracts, not a substitute new DR plan. Prove full independent restore on real post-import DB+filestore and refresh after any separately authorized finance posting.
- Exit to Export after `PL-PROD-EXTENDED-ACCEPT`; full 2h DR RPO optimization and Production financial writer cutover remain distinct, separately authorized gates.
