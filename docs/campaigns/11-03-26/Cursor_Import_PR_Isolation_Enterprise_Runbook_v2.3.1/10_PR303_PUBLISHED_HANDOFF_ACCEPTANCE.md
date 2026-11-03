# PR #303: published Cursor evidence and acceptance contract

**Test checkout:** `190c497bdea1362cad87e231c713efdcd25240d4` (verify latest actual GitHub head before testing).
**Unchanged executable baseline:** `702ebaf77d987dc844e2758bd354b2ecef4f26cd`.
**Base:** `Staging@2a3b9cda9b127c284d12f98bf35ab0344a500d10`.
**Observed GitHub delta:** one commit, ahead-by-one, **exactly five added Markdown files**, no other modifications. The docs-only update **does not invalidate executable behavior comparisons** but a new native runtime receipt must still identify the current head SHA.

## Required evidence sources (read all five at pinned revision)

The authorized, self-contained repository handoff is [the exact docs folder](https://github.com/cryptoxdog/IB-Odoo_19/tree/190c497bdea1362cad87e231c713efdcd25240d4/docs/reports/evidence/pr303-cursor-handoff). Read `README.md`, `enterprise-validation.md`, `claims-recovery-brief.md`, `offer-acceptance-brief.md`, and `security-acl-brief.md`. Treat `OBSERVED (CE runtime)` as **agent-reported Community evidence**, `OBSERVED (static)` as file inspection, `HYPOTHESIS` as unproven, and `OPERATOR DECISION` as binding policy but **no edit authorization**. If the docs, SHA, or five-file delta do not match, report `BLOCKED_SOURCE_BINDING`.

## The eight reported red runtime outcomes

The published local CE suite reports **7 failed, 1 error, out of 807 tests** at executable baseline `702ebaf`. **605 tests executed across the 39 relocated modules**, of which seven failed. These are **not** independent Enterprise results. Do not demand 807/605 from a narrowly selected Enterprise tag run; only demand that each actually selected, required method executes.

| ID | Exact test | CE observation | Accepted disposition | Cursor acceptance / limits |
|---|---|---|---|---|
| F-A1 | `TestTransactionClaimsBridgeDepends.test_freight_chargeback_recovery_flows_to_transaction` | Expected 125, observed 0 | A: `BUSINESS_SEMANTICS_UNRESOLVED` | Record as reported or reproduce safely only with separate approval; **do not calculate claims or margin** |
| F-A2 | `TestTransactionClaimsBridgeDepends.test_lightweight_penalty_recovery_flows_to_transaction` | Expected 75, observed 0 | A: `BUSINESS_SEMANTICS_UNRESOLVED` | Same; no computed field or historical backfill |
| F-B1 | `TestOfferBridge.test_offer_accept_creates_transaction` | FAIL | B: obsolete test assumption | Acceptance changes offer state only; sale-order confirmation creates transactions; test unchanged |
| F-B2 | `TestOfferActions.test_action_accept_creates_transaction` | FAIL | B: obsolete test assumption | Same; do not invent a transaction link or rewrite test |
| F-C1 | `TestClaimACL.test_claim_user_cannot_unlink` | FAIL, AccessError not raised | C: unresolved access exposure | Preserve red; no broad ACL removals without approved role matrix |
| F-C2 | `TestClaimACL.test_no_group_cannot_read` | FAIL, AccessError not raised | C: unresolved access exposure | Preserve red; report effective rules where safely observable |
| F-C3 | `TestTransactionACL.test_base_user_cannot_write_tx_line` | FAIL, AccessError not raised | C: unresolved access exposure | Preserve red; exposure to historical line edits is high-priority |
| E-01 | `TestErpWorksheetImport.setUpClass` at `plasticos_transaction/tests/test_erp_worksheet_import.py:123` | ERROR: missing `plasticos_accounting.account_40050_sales_income` | E: CE accounting-seed/install-order **hypothesis** | On existing Enterprise **clone**, verify XMLID existence, module install state and actual ORM test result; no fixture repair/reseed |

The seven assertions stay visible even if the import-only permitted runner does not execute claims/offer/commission addon tags. Distinguish `REPORTED_CE_NOT_ENTERPRISE_VERIFIED` from an independently re-run `FAIL`. **Do not expand testing into Linda/logistics or unrelated claims product work to obtain a false universal PASS.**

## The unexplained passing test and unresolved product interaction

**ACL exception origin:** `TestTransactionACL.test_base_user_cannot_unlink` **passed** in the CE run even though a broad `base.group_user` transaction ACL appears to allow delete. Cursor must identify the **actual** source of `AccessError` where the authorized existing test/readonly inspection permits; `security_hardening.xml`/record rules are hypotheses. If scope or method selection prevents safe execution, use `NOT_PROVEN / BLOCKED_SCOPE`, never guess. `ir.model.data` and `product.template` blanket grants are independently recorded HIGH-priority findings, **not permission to refactor all ACLs**.

**Compliance and posting risk:** `_compute_compliance` uses **unscoped** `is_compliant`, and its transition to compliant can call `_auto_post_pending_invoices`, which invokes `account.move.action_post()`. PR #303 now enforces **purpose-scoped** invoice compliance there and `required_for_close` at transaction closing (seeded: verified scale ticket). Source tracing alone cannot prove whether missing invoice-specific documents can unexpectedly block or permit auto-posting; an existing test must exercise the relevant transition **on a guarded clone**, or the interaction is `NOT_PROVEN / DECISION_REQUIRED`. No historical invoices are intentionally posted by Cursor merely to complete testing. **PR #301 is independent and preserves imported historical draft bills**: never treat #303-alone results as the interaction of both branches.

## PR scope and accepted decision boundary

- **A:** two margin tests reflect unresolved recovery recognition; do not compute, overwrite, backfill, or revalue historical margins.
- **B:** offer acceptance changes state only; transaction via sale-order confirmation. Existing two tests stay as written until operator approves rewrite.
- **C:** explicit role matrix required before effective ACL remediation; claim/photo uploads and CSV import must remain workable. The unexpected unlink PASS remains open.
- **D:** test discovery registration is in scope; production changes to **logistics, document compliance, match exclusion** are to be *separated later*, not changed or reverted during this test. #303 is a mixed-scope PR, **not merge-ready by evidence publication alone**. The 17 Linda tests reported in the CE relocated census are **excluded** from Cursor's targeted logistics-free acceptance.
- **E:** only existing admitted Enterprise fixture, separate #301/#303 SHAs. Both set `plasticos_transaction` to `19.0.2.3.40`; integration collision stays open until operator-approved combined revision and version advance.

## Two verdicts: do not confuse them

**`PR303_DIAGNOSTIC_COMPLETE`** may be true when Cursor has correctly tested import-facing methods, preserved all seven published failures with classifications, confirmed/blocked the accounting XMLID question honestly, reported the ACL exception and compliance cross-path as proven or explicitly unproven, and returned a bounded decision queue. Known failures need **not** magically turn green.

**`PR303_MERGE_READY = NO`** until the operator approves dispositions for A/B/C, production scope D, and integration/version E, and new affected revisions pass independently on Enterprise. Cursor cannot approve code changes, weaken tests, redesign ACLs, fix the template, merge or publish.

**Final cohesion gate stays locked** until an explicitly operator-approved integration SHA exists, the separately authorized changes pass independently, and applied ERP/CRM same-database imports and replay are authorized separately.
