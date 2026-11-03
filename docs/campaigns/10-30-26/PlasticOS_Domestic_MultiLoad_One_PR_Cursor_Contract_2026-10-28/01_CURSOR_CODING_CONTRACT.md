---
repository_access:
  writable:
    - https://github.com/cryptoxdog/IB-Odoo_19
  read_only:
    - https://github.com/Quantum-L9/.github
    - https://github.com/Quantum-L9/Cursor-Governance
    - https://github.com/odoo/odoo
    - https://github.com/odoo/enterprise
  unlisted_repositories: no_access
---

# Cursor coding contract | Domestic multi-load foundation | One PR

**ID:** `PLASTICOS.DOMESTIC.MULTILOAD.ONE_PR.2026-10-28`  
**Owner:** PlasticOS Logistics (`plasticos_logistics`) with strictly bounded required consumer repairs in Transactions, Claims, Documents, native Odoo Sale/Stock integration.  
**Repository:** `cryptoxdog/IB-Odoo_19` -> `Staging`.  
**Last observed comparison baseline:** `04bd0594a7c9dcad53d9c45fc65276d76817c112` on 2026-10-28. **Rebind immediately before work.**  
**Publication authorization:** ONLY `make pr` after all mandatory checks, exactly ONE standalone PR. No merge, deployment or Production mutation.

## 1. Mission and terminal acceptance

Repair the false universal one-transaction-to-one-load model without replacing PlasticOS or weakening native Odoo commercial, stock, freight, or documentary authority. A domestic PlasticOS transaction may be associated with **zero, one or multiple real physical loads**, and every associated physical load has **at most one unambiguous owning transaction** in this scope. A single sale order may legitimately have several loads, but its existence alone never proves which transaction owns a given load when the mapping is ambiguous. PO-only native receipt remains valid without a buyer, sale order, fictitious transaction or PlasticOS load. Do not introduce Export-style many-transaction bookings or many-to-many physical-load assignment.

Success requires: (1) one authoritative, stored, source-proven load-to-transaction association; (2) a native Odoo-compatible transaction-side `load_ids` collection; (3) a safe legacy singular `transaction.load_id` compatibility policy that never silently selects a first load in multi-load cases; (4) all in-scope consumers correctly follow physical load identity; (5) tested lossless and replay-safe historical migration; (6) unchanged accounting, actual source weights, dispatch authorization and company isolation; and (7) observed Enterprise validation and one PR created through `make pr`.

Implementation recommendation/authorized envelope: use `plasticos.load.transaction_id` as the **canonical persistent owning FK** and `plasticos.transaction.load_ids` as its inverse. The old stored/computed reverse design must not remain a competing source of truth. Existing `plasticos.transaction.load_id` is a compatibility API, not cardinality authority. For exactly one verified eligible load it may resolve that load; for zero or multiple it must not fabricate/select one. Preserve or deliberately reject legacy writes with explicit tests; do not make existing trusted singleton integrations fail silently. Odoo 19 ORM implementation mechanics may vary if necessary to preserve these semantics and source integrity. If an equivalent storage design would change ownership or externally visible meaning, stop for explicit architecture review, not silent improvisation.

## 2. Execution timing: strict dependency on the first Documents PR

This is **NOT** a stacked PR, a third phase of the existing branch, or permission to work concurrently. Do NOT start while the prior two-contract Documents PR is open, incomplete or unmerged. At activation:

1. Confirm predecessor implementation of `PLASTICOS.DOCS.ONE_PR.PHASE_A.2026-10-28` and Phase B (single verifier + exact evidence association) is merged to **Staging**. Record merged PR number, merge commit SHA, exact current `origin/Staging` SHA, and inspect final code/tests. If not merged, state `BLOCKED_PREDECESSOR` and do not mutate/publish.
2. Check `git status --porcelain=v1`, worktree, current branch, Git remote, merge-base, manifest versions and actual installed Odoo 19 Enterprise environment. Do not reset/discard unrelated local work. Create one fresh branch **from the post-merge Staging HEAD** (suggest `fix/domestic-multiload-foundation`). Record exact base SHA. If an unrelated PR changes relevant files, re-inventory and rebase safely; do not include it in this PR.
3. Compare the live source to the dated source evidence in `03_SOURCE_AND_CONSUMER_CENSUS.md`; invalidate stale assumptions. Source and accepted owner BRS/ADRs supersede candidate planning text where genuinely conflicting. Report any resulting semantic conflict for the correct domain owner.
4. Operate as the installed L9 Coding Agent. Resolve applicable current `.github` canonical projection binding if a valid three-artifact/three-producer-PASS receipt set is actually available. Never claim `BOUND` based on local/manual/unknown receipts. A user-authorized standalone PlasticOS coding run may proceed under this project contract without falsely claiming constitutional L9 projection conformance; record that mode explicitly. Do not invent an admitted GAR handoff.

## 3. Locked business architecture

**Identity:** `plasticos.load` = one actual physical movement. `plasticos.transaction` = commercial/transaction aggregation. Native `sale.order`, `purchase.order`, `stock.picking`, stock moves/quants = native commercial/physical facts. Planned/actual quantities and units remain distinct. No booking/container entity, Export routes or warehouse process is authorized.

**Cardinality:** transaction `0..N` physical loads; physical load `0..1` attributable transaction in this domestic scope; no duplicate physical load rows for one shipment; a physical load may remain unlinked until its true transaction is proven. Do not make all loads require a buyer. For **SO-backed outbound loads**, preserve current legitimate commercial/partner and physical readiness/dispatch guards; a PO-only purchase/receipt is not forced into that load lifecycle. If an existing business source supports a different cardinality, return an architecture decision rather than fake it.

**Attribution:** prefer an exact, existing native sale-order-to-transaction relationship and other documentary/source correlation where proven. `sale_order.transaction_id` is not infallible: the historical ERP compiler can construct more than one worksheet transaction associated with a sale-order origin. For multiple candidates, mismatched company, missing source or changed historical relationship, **abstain, retain unlinked/candidate state and surface an auditable exception**. Never choose first/last via `setdefault`, order-by-date, partner similarity, company omission, fallback `limit=1`, or guessed worksheet mapping. An SO with many physical loads is valid; an SO with ambiguous economic allocation requires proof, not default assignment.

**Owner writes:** allow one authoritative FK writer, guarded by ORM business validation and existing authorization. The old `tx.load_id` and dashboard/claim/document projections must not write a conflicting second truth. Changes to association of already-dispatched, delivered, closed or economically evidenced loads must not silently rewrite history, freight-context fingerprints, carrier acknowledgments, document applicability, audit events, accounting, or claims. Such cases either preserve the stable link or require a separately approved, explicitly audited correction; no forged bypass via context/RPC or unrestricted `sudo()`.

**History:** every old non-null `transaction.load_id` and corresponding computed/stored `load.transaction_id` association must survive exactly where source-consistent. Preserve original record IDs, company relationships, timestamps, archived/closed state, freight evidence, cash/accounting facts, documents and claims. Existing inconsistent/duplicate/ambiguous rows require a reversible discrepancy ledger and fail-closed disposition. No data deletion, no fabricated SO/PO or new buyer, no mass recalculation of historic margin/commission/weights.

**Compatibility:** retain a safe legacy `load_id` read for **only exactly one** eligible transaction load; zero/multiple MUST NOT silently map to the earliest or most recent. Legacy direct write callers must be inventoried and migrated or guarded with explicit validation; preserve genuine single-load workflows. Update `action_view_load`, UI, search, dashboard and source API callers to use truthful `load_ids` or load-owned FK, and add load count/list UX when needed. If an API or view cannot be safely adapted within scope, record named blocker instead of selecting arbitrary load.

**Documents:** the prior PR owns exact evidence relations and one business verifier. Use that **merged** representation. A BOL or claim on load 2 must stay on load 2 without changing load 1 or duplicating originals. A document verified for one load cannot clear its siblings' obligations. Do not modify native Documents custody, authoritative verification, prior PR's exact link semantics, or frozen BRS chapters.

**Claims:** an existing `plasticos.claim.load_id` related to `transaction_id.load_id` is **not** correct for multi-load. Replace or adapt that consumer to source-verified **optional per-claim load attribution**, retaining transaction-scoped claims without an invented per-load assignment. Preserve historical attributable links and make no new claims/recoveries or financial recognition automatically. Document-triggered claims use the exact authorized source evidence relationship; do not select the first transaction by load or alter notification policy.

**Financials/freight:** freight quote, rate, actual cost, calibration and immutable events remain **load-scoped**. `plasticos.transaction.freight_actual`, freight bills, purchase/customer invoices, recovery, margin, commission and payouts remain under their current business owners; do NOT auto-sum reference weights, duplicate transport costs, append the same freight invoice twice or recompute closed deal economics as a migration side effect. If an economic allocation rule is insufficient to safely express a scenario, fail closed with a named design gap. No new rate engine, dispatcher or external sender.

**Security:** existing Odoo role/company/record rules and native group assignments continue to apply. No blanket ACL removals/new broad permissions and no system-wide ACL policy work (scheduled last). Domain-specific association checks and denial tests ARE in scope. Never permit foreign-company load attachment through RPC, sudo, an unresolved company (`load.company_id` is presently SO-related), or shared partner names.

**Revision/state:** preserve native order and load lifecycle checks, `stock.assigned` not physical readiness, idempotent freight decisions, source revisions, issued messages, audit trails and their exact company/party/load identity. No booking or mail workflows activated by this PR.

## 4. Before editing: mandatory source and runtime census

Complete the **dependency-aware read inventory** in `03_SOURCE_AND_CONSUMER_CENSUS.md`. At minimum enumerate:

- **Writers/relations:** `plasticos_logistics/models/transaction_inherit.py`, `models/load.py`, `models/sale_order_inherit.py`, native `plasticos_transaction/models/sale_inherit.py`, historical import paths and current migrations. Inspect exact `create`, `write`, `unlink`, `copy_data`, `_compute_transaction_id`, `_check_load_requires_supplier_buyer`, `action_view_load` and SQL constraint semantics.
- **Consumers:** Logistics `load_dashboard.py` SQL view and drill-through; `freight_quote.py`, `freight_governance.py`, `services/freight_context.py`, `services/sal_resolver.py`, request/event issuance, dispatch/escalation; Claims `claim.py` and `document_inherit.py`; Documents `document.py`, `transaction_docs.py`, native bridge post-predecessor; transaction/commission/dashboard reports; Odoo views and XML/test imports. Search full repository for `.load_id`, `('load_id', ...`, `related="transaction_id.load_id"`, SQL joins and source/test assertions; record each occurrence disposition.
- **Migrations and DB:** current schema/SQL constraints, old/orphan/mismatched rows and inbound dependencies. Run a **read-only census on an owned disposable Enterprise database clone** with no real production/staging data mutation. Verify the existing `load.company_id` SO dependency, sale-order linkage, tenant isolation and real stock movement data.
- **Tests:** current legitimate singleton tests, source-level contract tests containing obsolete one-load assertions, API consumers, transactions/claims/documents/freight/dashboard integration and Odoo 19 Enterprise install/upgrade behavior. Record pre-existing failures before changing code.

Classify every discovered code/path as `MUST_EDIT`, `TEST_ONLY`, `READ_ONLY`, `DEFERRED`, or `BLOCKED_NEEDS_ARCHITECTURE`. An inspection finding does not automatically grant write scope. Include path/line references and decision in the PR evidence.

## 5. Explicit modification scope

**Primary allowed code:**

- `plasticos_logistics/models/transaction_inherit.py`
- `plasticos_logistics/models/load.py`
- `plasticos_logistics/models/load_dashboard.py`
- `plasticos_logistics/views/transaction_load_views.xml`
- `plasticos_logistics/views/load_views.xml` and `plasticos_logistics/views/load_dashboard_views.xml` (only cardinality-related UX)
- `plasticos_logistics/models/sale_order_inherit.py` (only exact create-load context if necessary; do not change issuance/mail)
- `plasticos_claims/models/claim.py` and `plasticos_claims/models/document_inherit.py` (only correct load attribution)
- `plasticos_documents/models/document.py`, `plasticos_documents/models/transaction_docs.py`, `plasticos_documents/models/load_docs_bridge.py` (only required load-specific attribution, compatible with merged prior PR)
- `plasticos_documents_native/models/document_native.py`, `plasticos_documents_native/models/document_sync.py` (only if updated exact evidence relationship requires a mechanically necessary and owner-approved consumer adjustment; MUST preserve prior PR semantics)

**Narrow collateral code only when a direct source/test witness requires it:** `plasticos_logistics/models/freight_quote.py`, `models/freight_governance.py`, `services/freight_context.py` and other Logistics freight consumer(s) for correct existing FK association; `plasticos_transaction/models/sale_inherit.py` only for proven exact SO/worksheet attribution with no changes to order confirmations; existing transaction views/commission projections only to eliminate verified stale singular-load reads, **never** change economic formulas. Any other production source path: request bounded expansion with source-level proof before editing.

**Version, migration, and tests:** `plasticos_logistics/migrations/<new_version>/**`, applicable `plasticos_claims/migrations/<new_version>/**` and Documents-owned migration directories ONLY when persisted fields actually change; matching `__manifest__.py` version bumps as required; `plasticos_logistics/tests/**`, `plasticos_claims/tests/**`, `plasticos_documents/tests/**`, `plasticos_documents_native/tests/**`, and only directly affected existing `plasticos_transaction/tests/test_bridge_wiring_contracts.py`, `plasticos_security_base/tests/test_bridge_contracts.py`, focused root `tests/**`, and their `tests/__init__.py` registration. Module-local README or implementation notes may be corrected only for the code actually landed.

**Forbidden writes:** `INVARIANTS.md`, accepted ADRs, original `plasticos_logistics/business_rules/BRS-*.md` and frozen Documents BRS chapters, candidate plan packs, any Export/warehouse/shop-floor addon, broad ACL/group/record rule CSV/XML, global governance rules, CI gate policy, dependency manifests beyond justified changed addons, unrelated PRs, import business data, external mail templates, financial rules, new AI/Studio services or scheduler. Do not opportunistically fix unrelated code discovered by census.

## 6. Mandatory implementation behavior and proof

1. **Single source of relation:** old tx foreign key, stored computed reverse and new inverse must not form cyclic/double writers. For the new canonical relation, enforce load identity, company, source SO, permissible lifecycle and uniqueness at ORM and DB level where applicable; reparenting must not silently mutate historical immutable evidence.
2. **Never first:** update `load.create`'s current `setdefault`/`not tx.load_id` behavior. A distinct second legitimate load can bind the same correct transaction, but two distinct matching transactions, cross-company records, or missing evidence must be unresolved. Do not globally require SO for PO-only receipt because those receipts belong to native Stock, not this load.
3. **Replace reverse readers:** dashboard SQL must join the canonical owner and remain one row per load on **fresh install and upgrade**. Modify its first-install column-existence fallback correctly; do not interpolate untrusted SQL. Update navigation/actions/searches that currently query `plasticos.transaction` by `load_id` and use `limit=1`.
4. **Preserve claim/doc truth:** claim on second load remains second; generic transaction claim remains unallocated until exact evidence. Documents prior-PR exact typed references remain authoritative and multi-file originals cannot be duplicated. All compliance and finance reads are status-only, no document-driven post/send/dispatch.
5. **Prove current freight and economics:** rate memory, RFQ, actual cost, calibration, company bounds, source revision, and load state behave per load. No automatic transaction financial rewriting from load count and no introduction of a second invoice/commission writer.
6. **Migrate safely:** use `04_MIGRATION_AND_COMPATIBILITY_PROTOCOL.md`. Fresh install, versioned upgrade, replay and conflict cases are mandatory real EE tests. Log a complete source->target mapping with preserved IDs and no lost references. Any mismatch or unresolved prior link blocks destructive update, not silently 'fixes' history.
   The historical-data reconciliation must run against an operator-authorized, protected-clone historical dataset or an approved irreversibly de-identified full-fidelity extract containing actual legacy link patterns, not only agent-invented synthetic fixtures. Synthetic cases supplement it. If this evidence is unavailable, `HISTORICAL_RECONCILIATION_UNKNOWN` blocks `make pr`; do not access live business databases without explicit authorization.
7. **Preserve security without ACL campaign:** user roles, company isolation and post-dispatch no-mutation guards must remain real ORM checks; strict negative tests, not UI-only readonly. Existing validation failures cannot be dismissed as unrelated without same-fixture baseline evidence.
8. **Work to convergence:** implement, run focused tests, diagnose in-scope failures, repair, rerun and check complete applicable CI/EE gates. Treat failed/unknown required proof as block; never weaken a test or use fake receipts. Do not self-authorize architectural scope expansion.

## 7. Publication and required delivery

When and only when `05_REQUIRED_ACCEPTANCE_MATRIX.json` required probes are genuinely executed and the same final combined tree passes real EE module upgrade tests and all mandatory local gates, commit changes on **one feature branch** and call **`make pr`** targeting Staging. The repo Makefile's `pr` target is the only publication ceremony; `git push`, `gh pr create`, direct GitHub API PR writes, `make push`, `make pr-nosmoke` and production deploy are forbidden. If checks fail, leave a clean, reviewable **local** branch/commit and report a typed blocker; do not publish a known-unverified fix. Do not merge the PR.

After publication: confirm exactly one PR, its base and head SHA, check remote required CI and review findings, and remediate any in-scope findings on the **same PR**, republishing only with `make pr`. A created PR is not a passing CI receipt or merge authorization.

Required outputs: `BEFORE_CENSUS.json`, `SOURCE_CONSUMER_DISPOSITION.md`, `MIGRATION_LEDGER.json`, `UPGRADE_REPLAY_RESULTS.json`, completed `ACCEPTANCE_RESULTS.json`, `EE_TEST_LOGS` paths, exact branch/base/commit/tree SHA, changed-file diff summary, `FINAL_EXECUTION_RECEIPT.json`, single PR URL (or `NOT_PUBLISHED`) and explicit outstanding blockers/unknowns. Evidence may be written under verified gitignored run artifacts and referenced from the PR; no secrets or raw database dumps are required in PR. Separate source/policy conflicts must be reported to their owners without auto-admission.

**Stop rules:** predecessor not merged; post-merge source/owner contract conflicts; changed authority or target without rebind; inability to account for old links; missing Enterprise fixture; unknown or failed mandatory migration test; unexpected company/finance/claim/dispatch effect; scope expansion needed to change business semantics; user worktree contamination; invalid security or publication route. Preserve progress, report exact recovery contract, and do not merge/deploy.
