# 09. Frozen scope, known deferred concerns, honest proof limits

## Import campaign inclusion

- **ERP partner source:** direct SQL projection, CounterParty, Address, Contact, ContactRoleAssignment, SalesReps, stable identity and import summary.
- **VanillaSoft CRM:** owner-email crosswalk, approved existing ERP persons, separate phone classifications, disabled numbers, preserved notes, history ownership, material profile, historical contact/call floors, watermarks and replay.
- **ERP commercial:** worksheet association, inventory inbound without a sale, buyer/seller, multi-worksheet grouping, source weights and amounts, purchase orders, customer invoices, vendor bills, PayablesBatch header/index and report fidelity.
- **Open PR-specific surfaces:** #301 vendor bill date/ref/payment terms and PO date/no phantom stock; #303 discovery of import-facing ORM tests and import-adjacent document/transaction behavior, each independently from its own head.

## Excluded by operator

Open PR #302 and #304 and merged #300 are Linda/logistics and excluded. No Linda operations, logistics feature work or logistics test selection (`plasticos_logistics`, Linda freight events/PO issuance). Do not choose all-module tests or `make test-odoo`. Loading unavoidable installed dependencies from the already admitted module roster is not itself approval to analyze logistics, and **#303 includes changed logistics production code**: do not call it logistics-free. Also do not expand into claims/offer/security ACL or matching feature redesign from the broad #303 PR. Report dependency failures factually without debugging that business domain.

No Odoo.sh deployment, live ERP or CRM mutation, credentials/config edits, code or test edits, PR review comments/issue creation, automatic staging, direct-SQL applied import or real VanillaSoft sync in independent phases. Only owned disposable Enterprise test clone side effects are approved. Full live-source and whole-system data replay require specific operator authorization in `06_FINAL_COHESION_GATE.md`.

## Source and policy constraints carried forward

1. ERP partner is single source of truth for approved people; VanillaSoft enriches without overwriting ERP name, email, phone or existing comment. The approved crosswalk itself is not to be rebuilt or guessed by Cursor.
2. Tiffany's accepted Odoo login is `sa@scrapmanagement.com`; do not restore `ss@` or `tw@` aliases without an operator decision. Preserve any mapping source with exact evidence.
3. Canonical material-profile identity is `(partner_id, polymer_id, form_id)` with nullable form supported. No guessed polymer/form taxonomy.
4. One vendor bill per `PayableID` (approved #301 decision), not per `APBatchNo`. No historical payment/posting inferred from batch flags. QuickBooks ownership of settlement stays out of importer scope.
5. Worksheet weights, not SO/PO placeholders, control historical weight; incomplete weights, zero-weight unit-priced lines, unresolved reversal links, pending vendor credits and document replay ownership remain subject to their existing explicit policies and are **not** silently converted to new requirements.
6. Historical invoice dates, term fallback and PO approval trade date from #301 are candidate behavior on that PR only until tested. A draft historical invoice may be **implementation-correct yet business-fidelity-incomplete**: report separately, do not post it to make the ledger look accurate.
7. GitHub issue #299 tracks possible further `address2`, separate country code/extension, `Website`/`title` mappings. These are **deferred**; the independent campaign may report evidence but cannot reopen this work as a remediation without approval.
8. Frozen August 2026 extraction is a fixture, not proof of the current restored SQL Server. No fixture-count mismatch authorizes changing data, inventing source rows or testing a production connection.

## Known environment and test coverage limitations

- The repository fixture is Enterprise-only and pinned at `config/test_env_fixture.conf`; it demands production-like module roster and US accounting. Do not replace it with the Community runner. Do not change the Postgres major or the Docker image to manufacture parity.
- `scripts/test_env.sh status` is not side-effect-free: it invokes Docker service and image management; only call after the strict non-provisioning checks in document 07. If unexpected rebuild or DB changes are needed, fail closed.
- `make test-module` sets `-u` to the declared complete PlasticOS roster and limits `--test-tags` to the requested module(s). Thus the fixture may load logistics even when it does not run logistics tests. It is impossible to guarantee zero incidental loading from #303 while using its exact head. Such a guarantee requires a separately approved code/test-environment plan, **not improvisation by Cursor**.
- #303 reports a Community Odoo test census after relocating 39 tests; it is evidence about possible coverage gaps, **not** admission that Enterprise import methods were executed. Tests moved into addons must prove discovery and runtime execution on their own PR SHA.
- A green source-reader/pure test is not an Odoo/SQL Server full import. An Odoo `TransactionCase` may roll back writes, so an ORM green is not a persisted multi-provider integration pass. F1-F3 uses synthetic contacts and independent real PostgreSQL, not a live VanillaSoft sync.
- Existing importer may refuse applied replay on a populated database. Do not bypass `ERP_REQUIRE_EMPTY` or change importer guards without explicit approval. True same-database end-to-end pass needs existing supported path and separate authorization.

## Exit and escalation

A run can end VALID_PASS for the exact independently covered behaviors while other rows remain NOT_PROVEN/DECISION_REQUIRED. The PR must never be called globally PASS/merge-ready with known uncovered required behaviors or unrelated changed product behaviors. Each failure must identify whether remediation belongs to the source, reader, mapper, Odoo, tests, environment or to the *operator's business policy*. Cursor proposes and stops; operator chooses.

## #303 published evidence update

Only five Markdown files were added between implementation `702ebaf...` and PR head `190c497...`; no source, manifest, permission or test code changed. The published briefs are binding policy context but not a code-change authorization. The CE-observed seven failing test IDs remain recorded even though this import-focused campaign explicitly excludes broad claims/offer/security/logistics runtime sweeps. One CE setup error in `TestErpWorksheetImport` might be an accounting seed/install-order issue, but **only the existing Enterprise test clone can settle that** without repair. The `test_base_user_cannot_unlink` pass remains unexplained. Unscoped compliance state may trigger automatic invoice posting, which then invokes the new purpose-scoped invoice gate; source analysis is not runtime proof.
