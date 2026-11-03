# Source-proven consumer map and refresh obligation

**Observation only:** `cryptoxdog/IB-Odoo_19`, `Staging@04bd0594a7c9dcad53d9c45fc65276d76817c112` (2026-10-28). These direct source findings justify the *scope* of the contract. They are NOT a complete current-code census and NOT Enterprise runtime proof. Cursor must redo the inventory from **post-Documents-merge Staging** and record all relevant consumers, tests and migrations before code mutation.

## Root relationship defects (confirmed source)

| Stable ID | Source seam | What current source proves | Required disposition |
|---|---|---|---|
| `ML-ROOT-01` | `plasticos_logistics/models/transaction_inherit.py` lines 10-22 | Stored `plasticos.transaction.load_id` is Many2one; `UNIQUE(load_id)` prevents one load being referenced by two tx rows but does NOT grant tx multiple loads. | Replace authoritative single-slot architecture with 0..N reverse collection and one load-owned FK. Do not indiscriminately drop SQL integrity. |
| `ML-ROOT-02` | same file lines 24-50 | create/write explicitly call reverse `load._compute_transaction_id()` on old/new legacy load. | Retire/redirect stale recompute; one writer; live inverse stays correct. |
| `ML-ROOT-03` | same file lines 54-74 | `_check_load_requires_supplier_buyer` and `action_view_load` operate on the single field. | Keep real outbound party guards; truthfully navigate zero/one/multiple, no fabricated buyer for PO-only native Stock. |
| `ML-ROOT-04` | `plasticos_logistics/models/load.py` lines 130-138, 417-428 | `load.transaction_id` is a *stored computed reverse*, searching tx by `load_id`. | Make an independently guarded authoritative FK or demonstrate equivalent one-writer implementation; no stale reverse compute. |
| `ML-ROOT-05` | `plasticos_logistics/models/load.py` lines 258-299 | `load.create` builds `tx_by_sale` by `setdefault`, then links only if `not tx.load_id`. | Permit every genuine same-tx load, reject ambiguous/unproven SO->tx associations. Avoid `first` selection. |

## Affected current readers/writers: minimum targeted census

| Stable ID | Code or contract | Evidence / hazard | Test or correction obligation |
|---|---|---|---|
| `ML-CONS-01` | `plasticos_logistics/models/load.py` `write` / `_compute_delivery_term_overridden` | Current state lock prevents many writes once dispatched; `transaction_id.delivery_term` compute depends on reverse link. | No reparenting past protected state; delivery-term override and freight context use correct owning tx. |
| `ML-CONS-02` | `plasticos_logistics/models/load.py::_cron_check_dispatch_acknowledgments`, `action_view_transaction` | Searches transaction by `('load_id','=',load.id), limit=1`, including owner for activity. | Use canonical FK; no arbitrary deal in CRM link, task or notification. Preserve send behavior; no new emails. |
| `ML-CONS-03` | `plasticos_logistics/models/load_dashboard.py::init` | Static SQL `LEFT JOIN plasticos_transaction t ON t.load_id = l.id`; first-install fallback probes column `t.load_id`; drill-through repeats `limit=1`. | Rebind SQL view to new canonical load FK with safe first-install/upgrade behavior and one row per physical load. |
| `ML-CONS-04` | `plasticos_claims/models/claim.py:load_id` | Stored `related='transaction_id.load_id'` assigns generic claim one synthetic single load; cannot express second load. | Preserve historical exact claim loads; explicit optional source-verified attribution; generic tx claims not silently assigned. |
| `ML-CONS-05` | `plasticos_claims/models/document_inherit.py::_check_claim_trigger` | `res_model=='plasticos.load'` searches transaction by legacy load FK `limit=1`; then creates claim/send. | Resolve via actual load owner; honor source document exact-link constraints; no wrong-load claim or surprise mail. |
| `ML-CONS-06` | `plasticos_documents/models/document.py::_get_related_transactions` | Legacy load `res_model/res_id` resolves via `tx.search([('load_id', '=', record.res_id)], limit=1)`. | Must use post-prior-PR exact evidence links and actual load owner; avoid guessing and false compliance recompute. |
| `ML-CONS-07` | `plasticos_documents/models/transaction_docs.py` | Scale-ticket cron reads `tx.load_id` and checks doc status for that one load. | No transaction-wide clearing from one load; preserve individual proof clocks when applicable, without activating new chasers. |
| `ML-CONS-08` | `plasticos_documents_native/models/document_native.py` | Pre-Docs-PR native bridge has legacy `transaction_id`/`load_id` and `_auto_link_partner` latest-partner matching. | Do NOT resurrect previous PR's eliminated recency association. Integrate with post-merge exact links, one original, one verifier. |
| `ML-CONS-09` | `plasticos_logistics/models/freight_quote.py`, `models/freight_governance.py`, `services/freight_context.py` | RFQ/immutable freight events rely on `load.transaction_id` and load/company coherence. | Preserve RFQ ownership, immutable events, context fingerprint, company and load ID for each separate load. |
| `ML-CONS-10` | `plasticos_transaction/models/transaction.py::_compute_financials` | Freight cost uses billed freight or transaction `freight_actual`; bills/recoveries enter gross margin. | Prevent duplicate aggregation, accounting edits or stored recompute for historic loads; economic policy unchanged. |
| `ML-CONS-11` | `plasticos_transaction/models/sale_inherit.py` | `sale.order.transaction_id` exists; historical `import_mode` compiles worksheet transactions, sometimes multiple per source order/origin. | Do not assume exactly one tx from SO name or order. Existing exact source link only if unambiguous and company-consistent. |
| `ML-CONS-12` | `plasticos_logistics/views/transaction_load_views.xml` | Form, smart button, tree and search all expose single `load_id`. | Show all legitimate loads, accurate count, one-link UX for true singleton, safe search/filter. |
| `ML-CONS-13` | `plasticos_logistics/migrations/19.0.1.10.3/pre-migrate.py` | Existing migration refuses duplicate tx rows referencing one physical load before SQL uniqueness. | Leave historical migration intact; new versioned migration must honor same uniqueness/provenance and be replay-safe. |
| `ML-CONS-14` | `plasticos_logistics/tests/test_load_cardinality.py` | Tests singleton creation, close chatter, delivery term and duplicate claimant; *does not* prove 2+ same-transaction loads. | Keep valid assertions and extend to two+ loads; do not delete failing tests just to pass. |
| `ML-CONS-15` | `plasticos_transaction/tests/test_bridge_wiring_contracts.py`, `plasticos_security_base/tests/test_bridge_contracts.py` | Assertions/docstrings explicitly claim one load per transaction; one comment incorrectly derives the singularity from UNIQUE. | Correct tests to authoritative cardinality while maintaining meaningful legacy compatibility checks. |
| `ML-CONS-16` | `plasticos_logistics/models/load.py::company_id` | Company derives from `sale_order_id.company_id` (no SO -> no standard load company). | Do not construct SO-less PlasticOS load as a replacement for PO-only receipt or force buyer creation. |
| `ML-CONS-17` | `plasticos_logistics/models/load.py::_transition`, freight methods | State/dispatch guards, confirmed freight evidence and per-load event integrity already exist. | Preserve and regression-test existing production behavior; no new workflow phase or bypass. |

Exact source URL pattern: `https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/<relative_path>`. For fresh execution replace the inspected SHA in every evidence coordinate with the actual post-prior-merge Staging SHA and compare code, do not blindly rely on old line numbers.

## Mandatory full-read inventory at Cursor execution

Run a bounded `rg` in the **current checkout**, covering Python, XML, SQL, migrations, tests, manifests, contract assertions, reports, import flows and external API mapping. Search these patterns and follow dynamic consumers:

```bash
rg -n 'transaction_id\.load_id|tx\.load_id|rec\.load_id|transaction\.load_id|load\.transaction_id|load_ids|_compute_transaction_id' plasticos_* tests
rg -n '(\[.load_id.|\(.load_id.|JOIN plasticos_transaction|t\.load_id|related=.*load_id|setdefault\()' plasticos_* tests
rg -n 'load_id' plasticos_logistics plasticos_claims plasticos_documents plasticos_documents_native plasticos_transaction plasticos_commission plasticos_security_base tests
```

These are suggested search examples, not an exhaustive regex claim. Filter generic `load_id` fields from unrelated models. For each actual dependent site record: source file and symbol, read/write type, legacy behavior, intended 0/1/N behavior, exact owner, change/test disposition, cross-company restriction, and observed validation. Do not confuse source code presence with installed Enterprise runtime proof. Compile a complete *affected-closure* inventory; unrelated modules outside the closure remain untouched.

## Current governing owner files to read before mutation

- Root `INVARIANTS.md` current admitted version, not blindly draft v3.3.0; all accepted relevant ADRs.
- `plasticos_logistics/business_rules/REGISTRY.json`, `EFFECTIVE_RULES.md`, `SUPERSESSION.md`, `NATIVE_DOCUMENTS_INTEROP.md`, `LINDA_BUILD_PLAN.md`, and original BRS-01..07 (verbatim, no edit).
- `plasticos_documents/business_rules/REGISTRY.json`, `EFFECTIVE_RULES.md`, `OWNERSHIP_AND_INTEROP.md`, `BRS-POS-02/-03/-09`, `OPEN_DECISIONS_AND_PROOFS.md` as updated by the predecessor PR.
- `plasticos_logistics/AGENTS.md`, `plasticos_documents/AGENTS.md`, `plasticos_documents_native/AGENTS.md`, `plasticos_claims` owner policy, root `AGENTS.md`, and any applicable current Cursor governance.
- Candidate `POS-INV-10/11/21/22` in prior graph-pack v3.3.0 and this user's explicit domestic scope for design intent **only**; do not overwrite repository constitutional law.

## Known Unknowns, not permissions to assume

- Exact final Documents PR implementation, merged SHA, and schema at execution time.
- Actual duplicate/missing/reversed legacy links in an owned runtime clone; per-record provenance and archival impact.
- Whether existing installed Odoo 19 Enterprise native Stock route exposes all movement identities the acceptance cases need.
- Safe upgrade mechanics for changing Odoo stored computed FK to authoritative stored FK and handling `tx.load_id` compatibility.
- Existing test fixture availability and head-specific failures. All remain `UNKNOWN/NOT_RUN` in this handoff.
