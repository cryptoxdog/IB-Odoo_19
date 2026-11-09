# Graph placement and closure | current overlay 2026-11-09

**Primary objective:** A fully imported and navigable Production codebase solid enough for functional testing. Imported history and live business activity are different populations, and a blank live KPI is not evidence for or against the ERP/CRM import.

- **Existing owner repaired in source:** Documents single verification authority and exact association (`#322`); transaction-to-many-load (`#339/#346`). Keep their capability identities. No second writer or load model.
- **Admitted doctrine:** `INVARIANTS.md` v3.0.0 November 8, supersedes historical v2.2 drafts in this pack. Old v3.3 proposed admission step is CLOSED by actual v3.0 admission, not to be rerun.
- **Import proof:** `PL-RELEASE-DATA` -> `PL-RELEASE-RECONCILE` -> `PL-PROD-IMPORT-CENSUS`. This is read-only acceptance on actual Production and authorized source manifests, not replaying imports automatically.
- **Admin proof:** `PL-RELEASE-MIGRATION` -> `PL-PROD-ADMIN-ACCESS`. Admin's `application=False, auto_install=False` source can still define a root menu but installation and group membership must be witnessed. `PL-PROD-LOAD-SNAPSHOT` is a separate scoped truth defect because the existing SQL VIEW excludes old closed loads.
- **Core and UI:** `PL-PROD-TEST-BASE` -> three independent core smoke lanes -> `PL-PROD-CORE-SMOKE` -> `PL-PROD-UI-SWEEP` -> `PL-RELEASE-BUSINESS-ACCEPT` -> future Export `PL-FUT-01`.
- **False prerequisites removed:** Export no longer waits for proposed AI candidate extraction or Linda mail owner paperwork unrelated to its actual native boundaries. Matching/enrichment do not block domestic production tests. Legacy XMLID #307 is a ticket whose code fix merged in PR #413, requiring issue disposition and runtime regression proof, not another broad rewrite.
- **Still separate:** financial ledger writer cutover, external real mail activation, AWS DR expansion, optional historical binary import, Export implementation and shopfloor hardware. They do not automatically prevent testing imported records with safe internal UI paths.

**Adversarial check:** A GitHub merge followed by an empty dashboard could represent a correctly empty live business population, a missing admin installation, an active-only load filter or a partially imported dataset. The cheapest discriminating probes are exact Odoo.sh build, installed-module state, Admin group test, a read-only census and a known old closed load. Do not infer a success state from the same empty UI.

**Authority:** non-admitted operator working plan. No global plan primitives/relations are added; `02` and `22` remain unchanged historical strategic candidates. Structural validation is not a hosted feature test. No code or Production writes performed.

## Nov 9 v5.1 affected dependency closure

Post-import starts after `PL-PROD-IMPORT-CENSUS`; PostgreSQL/filestore and prechange native backup are shared foundations for new binary import and any financial posting. Documents owns byte-originals, extraction candidates and manager review; Odoo accounting owns opening entry, QB/ERP cutoff and clearing; `plasticos_transaction` owns operational `reopen-erp-transactions` command only. Reopening financial debt automatically from a Closed transaction violates ADR-022.

Documents and finance rehearsal are parallel after shared foundation, converging with the existing DR restore path at `PL-PROD-EXTENDED-ACCEPT`. The original `PL-RELEASE-DR` remains an independent full-campaign pointer and is not falsely closed by the minimum restored checkpoint. `PL-FUT-01` now requires extended acceptance and preserved Export BRS owner references. Historical v5.0 operator release list and PR state are predecessor evidence; source head rechecked separately. No new strategic plan primitives.
