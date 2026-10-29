# Historical-data integrity and cardinality migration protocol

**Owner:** `plasticos_logistics` for the association; Transactions, Claims, Documents and Accounting owners for their affected consumers. **Class:** required migration design and proof for the single domestic multi-load PR, not an executed migration or approval to touch production data.

## A. Pre-change inventory and invariants

1. Rebind to **post-Documents-merge Staging** and note exact addon manifest versions, Odoo 19 Enterprise build, database-template ID and PostgreSQL version. Establish safe owned clone from `config/test_env_fixture.conf`, never live Production/Staging.
2. Read old tables/model fields and ORM metadata for `plasticos_transaction.load_id` and `plasticos_load.transaction_id`; current former is a stored FK with unique constraint, latter a stored computed reverse. Capture physical FK constraints, indexes, record rules, migration history, and fresh-install behavior. Identify how Odoo recomputation/DDL affects changing `compute`, `store`, `inverse`, `readonly`, `ondelete`, and SQL materialized source.
3. Create a **read-only before-census** (IDs, not raw secrets) with buckets:
   - `LEGACY_ONE_TO_ONE_CONSISTENT`: tx.load_id ↔ load.transaction_id exact, each company/SO consistent.
   - `LEGACY_TX_ONLY`: tx points to load but stored reverse missing/stale.
   - `LEGACY_LOAD_ONLY`: load reverse exists but old tx field absent; establish whether source-proven or derived stale.
   - `DUPLICATE_TX_FOR_LOAD`: several tx rows claim one physical load (do not resolve by max/min ID).
   - `MULTI_LOAD_SAME_TX`: several real loads with provenance to one transaction, only one old tx.load_id can represent them.
   - `AMBIGUOUS_SO_OR_WORKSHEET`: several candidate tx for a SO/origin or inconsistent historic imports.
   - `COMPANY_OR_SOURCE_MISMATCH`: company/party/SO/transaction disagree or company unproven.
   - `CLOSED_OR_EVENT_LOCKED`: links with historical dispatch, immutable freight evidence, claims, documents, invoice/commission evidence.
   - `UNLINKED_OR_PO_ONLY`: legitimate unlinked loads or native PO/picking only; neither should get a guessed buyer/transaction.
   Unknown cells must remain `UNKNOWN`, not counted as safe.
4. Record baseline counts and the exact input `(tx_id, legacy_load_id, reverse_load_tx_id, so_id, company_id, linked_claim_ids, linked_doc_ids, freight_event_ids)` as permitted by data governance. Preserve existing audit integrity; do not export attachment contents, secrets or personal data into a PR.

## B. Safe migration strategy

- Design one **versioned** addon migration using a **new** module version number greater than the *execution-time* manifest version. If Claims or Documents stored fields change, add their own appropriate versioned migrations and manifest bumps. Preserve old migration history verbatim.
- Run an **idempotent dry-run** from legacy FK to the new authoritative load-side relationship. Each source-proven consistent old link maps to exactly the same physical load ID and exact transaction ID. Re-run migration twice on the disposable clone; zero additional changes on second run.
- Do not backfill guessed SO/tx/partner/owner from arbitrary `limit=1`, alphabetical/time ordering, shared company, or `sale.order.transaction_id` unless that source relationship is unique and proven. Historical imported worksheets may map several source orders/transactions; ambiguity blocks mutation for that row.
- Refuse conflicting attempts that would bind one physical load to two commercial transactions; preserve the original old data and record `REVIEW_REQUIRED`, or block upgrade if unresolved rows would violate integrity. Never disable integrity constraints temporarily to force a green migration.
- A canonical stored relationship is the sole authoritative writer. Keep the old `tx.load_id` only as a **compatibility read/projection** or a strictly validated delegating single-load command, with no independent/competing column writes. For >1 legitimate loads, it must yield a deliberate ambiguous/empty result, not a default first physical load. Document any source API consumers that need adaptation. Safe deprecation/removal of old stored column/constraint requires a rehearsed, lossless migration and owning approval; never delete historical FK bytes before preserving a reversible mapping.
- Historical `claim.load_id` values derived from `transaction.load_id` cannot be assumed valid for every multi-load claim. Preserve exact historic attribution when it was provable; where only a generic transaction claim exists, leave per-load attribution unset and retain source claim/document links. No automatic claim re-resolution or recovery/margin recalc.
- Documents' merged exact-link architecture remains the semantic owner. Do not clone an original or write a document's `verified` fact during migration. Preserve original attachment IDs and current/historical verified application scope.
- Preserve `plasticos.load.company_id` legal-company boundary. Only associate an SO-backed load to a matching exact transaction/source company. For PO-only native receipt with no SO, leave Stock's own PO/picking truth intact and do not mint PlasticOS loads.
- Freight rate/resolution and actual cost evidence are indexed per load and must retain their original `load_id`, currency, amount, fingerprint, selection, correction chain, idempotency IDs and immutable events. Do not merge per-load rate histories across sibling loads.
- Account moves, purchase/vendor bills, buyer invoices, credit/debit notes, historical financial fields, stored commissions and closed transaction state are **read-only during migration**. Do not invoke `action_post`, `button_confirm`, `action_validate`, `action_dispatch`, message sends or source-dependent business transitions while migrating.
- Do not cascade-delete load, claim, document or event history when removing an old FK; evaluate `ondelete` policy and test actual deletion/archival refusals. Corrections after delivered/closed/evidenced state require explicit source-owner authority and audit, not write bypass.

## C. Runtime upgrade acceptance

On a disposable **Odoo 19 Enterprise** clone with realistic synthetic fixtures:

1. Test **fresh install** of every changed addon and dependent view: no SQL column-not-found at `load_dashboard.init`, no circular compute or registry errors, no field missing from downstream models; verify Odoo tests actually collected.
2. Test **old-to-new versioned upgrade** from a clone with at least: one linked tx/load, two distinct SO loads for one tx, a distinct unlinked load, an ambiguous same-SO candidate set, a second-company same external reference, a closed/evidenced load, a claim on a second load, a document on a second load, a PO-only native receipt and real freight evidence. If any fixture cannot be represented pre-upgrade, stage it in a safe source-proven equivalent and explain the actual limitation.
3. Capture before/after `row_count`, sorted `(load_id, tx_id)` mapping, stable physical IDs, `claim_id, load_id`, document evidence link IDs, source attachment hashes or IDs, freight event IDs, stock picking IDs, financial values, commissions, timestamps and states. Check no deletions, duplicates, unapproved additions, cross-company links or changed posted/accounting facts.
4. **Re-run upgrade** with the same version/record set and assert zero further link changes, duplicate views, duplicate freight evidence or inconsistent computed projections. Assert mixed old/new transaction UI and search behave truthfully.
5. Exercise *failed migration* on intentionally contradictory mapping: fail with a precise reproducible reason and no partial irreversible mutations. Demonstrate rollback through owned-clone database transaction/savepoint/backup restore and compare preserved source fingerprints. Do not drop the guarded test template.
6. Check pre-existing singleton workflows (create, link, freight quote, close, claim, document, dispatch) against the new model; ensure each two-load path stays bound to its actual load. Check permission and company isolation with realistic groups, not sudo-only success.
7. Run focused tests, all touched module tests, full `make test-odoo`, `make install-smoke`, applicable pre-commit and `make pr-check`. Record baseline-vs-change failures; no disabled/renamed assertion or skip of a required Enterprise case.

## D. Mandatory machine-readable evidence

`BEFORE_CENSUS.json` (source revision, observed DB identity and counts, classification); `MIGRATION_LEDGER.json` (every source->target mapping ID and disposition); `UPGRADE_REPLAY_RESULTS.json` (fresh install, first upgrade, repeated upgrade, intentional conflict, restore); `FINANCIAL_AND_EVIDENCE_DIFF.json` (hashes/counts for immutable financial, claim, documents and freight facts); `CONSUMER_DISPOSITION.md` (one row per affected caller); `ACCEPTANCE_RESULTS.json` with actual per-probe status and run evidence. **Do not embed real secrets/PII or full database dumps in the PR.**

The dry-run/upgrade results are `NOT_RUN` in this ZIP. They become PASS only after the Cursor agent runs and records real EE receipts tied to the exact final commit and protected template.
