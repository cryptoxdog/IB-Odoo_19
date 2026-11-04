repository_access:
  target: https://github.com/cryptoxdog/IB-Odoo_19
  mode: inspect_then_bounded_local_implementation
  observed_origin_staging: e78af874604890f8adb6b049694f93c48311eab4
  overnight_local_checkout_claim: 607a64b897cb73b19adeea1b867990c5bf556189
  revision_policy: verify_actual_checkout_and_worktree_first; never_reset_or_overwrite_local_changes
  inspect_scope:
    - existing source projections/index and inventory/warehouse references
    - native order, transaction, receiving and warehouse/location code
    - relevant focused tests and local Enterprise test harness
  mutate_scope:
    - directly necessary inventory-inbound source projection and source-index mapping
    - directly necessary inventory-inbound branch of historical importer
    - targeted regression tests and local sanitized evidence
  remote_mutation: forbidden
  source_database: read_only
  permitted_target: owned_disposable_enterprise_test_clone_only
  forbidden: [production, odoo_sh, merge, deploy, push, pr_creation, broad_reimport, accounting_changes, crm_changes]

# Execution contract: ERP-INVENTORY-INBOUND-001

## Locked business semantics

When `BuySell.CustID` is exactly `(INV)`, the Sold To entry describes an internal inventory movement. The field immediately below `(Inventory)` in the source UI identifies the warehouse where the material is held. It is not a missing external customer. The purchase side may have a fully valid PO without any linked customer SO or load yet. Inventory outflow is a different direction; preserve it unchanged. Source status `X` cancelled worksheets are excluded.

Do not create `res.partner` for `(INV)`, a fake sale order, a customer invoice, or a sale-linked `plasticos.transaction` solely to placate an existing compiler. Do not introduce a new independent importer or new product/partner models. Do not alter the vendor-bill or customer-invoice implementation, historical posting behavior, terms, CRM, or salespeople in this change.

## Task sequence (one concern, one bounded execution)

### 0. Resolve actual revision and existing behavior (READ ONLY)

Record `git rev-parse HEAD`, `git status --short`, `git log --oneline -n 5`, the current upstream Staging SHA, and the actual source-code revision used by the overnight import. The earlier local checkout is 13 commits ahead of the observed upstream; do not reset it, overwrite local changes, or assume origin/Staging has the implementation. Inspect the narrow source graph: `reader.PROJECTION_SCRIPTS`, `source_index`, `native_document_import._realize_one`, `header_for_line`, `purchase`/`sale` native models, existing stock receiving/warehouse models and their tests. Establish an external-sale and inventory-outbound control case. Preserve observed stable behavior.

### 1. Identify the true warehouse join (READ ONLY; REQUIRED GATE)

Run `READ_ONLY_SOURCE_PROBE.sql` through the EXISTING source reader against the RESTORED SQL DATA ONLY, with no application interaction. Confirm `BuySell.CustID=(INV)` on 60403; verify actual PO `33498`, DetailID(s), and the field that drives the second Sold To dropdown. The frozen Address grid has `(INV)` warehouse site AddressID 404812, `GREENVIEW WASHINGTON WAREHOUSE`; do not mistake the separate real-party address 404811 for it.

Inspect the complete `dbo.BuySell` column list because the checked-in `24_buysell.sql` does NOT project the warehouse. If necessary inspect verifiable related tables and 60403 source values. Identify precise join semantics, source key, uniqueness, multiplicity, blank handling and whether the source selector references `AddressID`, `(CpID, Type)` or something else. Do NOT infer site from the unrelated `WKSDetail.WarehouseLocation` / Reserve bin without proof. Check whether existing native Odoo site/location models already map this warehouse.

If exact destination identity or a lawful Odoo owner/location representation remains unknown, produce a bounded blocker with raw evidence kept privately and a sanitized summary. STOP before writing warehouse or stock artifacts. No source guess, fake buyer, default location or unapproved new schema.

### 2. Implement only the confirmed inbound root-cause correction

At the existing canonical source/importer seams, add an explicit source-ID recognition of inventory INBOUND (`CustID == '(INV)'`). Preserve the pseudo-party's destination site as a typed inventory location relationship, without importing it as a commercial customer; use the proved source key and stable Odoo native mapping. Recover the destination from the source row that selected it, including AddressID where source-verifiable. Preserve PO, vendor, grade, quantity, delivery evidence, date, and worksheet identity. When the source has a valid PO and no customer SO because it is an inventory receipt, do not call that an external commercial rejection.

Use the repository's existing stock/receiving path and source-marker pattern if source completion and target ownership can be proved. Avoid creating actual current stock or valuation balances from historical receipts whose later outflow/current inventory are not reconciled. If implementing physically completed historical stock movements requires new policy about present-day inventory, stop that portion explicitly and keep the proven source recognition; do not substitute a fake Odoo receipt. Do not add accounting changes as a workaround.

Preserve the existing outward inventory path. Normal external customers still use current sale-order semantics. Missing actual purchase/order identity and missing warehouse are explicitly held exceptions, not fabricated completions. Cancelled inventory-bound worksheets never create new inventory stock events.

Use the existing separate `*-census.json` for inventory-inbound outcome accounting if appropriate. Do not break or arbitrarily reinterpret `records_seen = recorded_outcomes` or the shared `import-run-summary` schema. Do not silently reduce rejections without an equivalent positive/held class.

### 3. Focused tests (no full import)

Implement deterministic pure tests for `(INV)` inbound, absence of SPO_ID, warehouse selection, ambiguous/missing warehouse, real customer control, exact vendor/PO identity, and idempotent source markers. Run the targeted Odoo Enterprise native tests on a VERIFIED disposable clone, including 60403, 58868 and 58975 when source fixtures permit. Include one source-proven outbound inventory control and one ordinary sale control. Keep the existing overnight clone unmodified for evidence. Use one focused run; do not run whole history or multiple full replays. If actual stock moves are produced, prove quantity/valuation is not double-counted and replay adds zero records.

### 4. Report and stop

Write sanitized proof under `docs/reports/evidence/erp-inventory-inbound-2026-10-22/` locally, or the existing preferred local evidence convention. Include source-column/key determination, files changed, source/target SHA, baseline, tests actually executed, exact per-case before/after, current-stock safety, remaining exceptions and `RECEIPT_TEMPLATE.json` filled with observed facts. Retain raw customer/warehouse data in a local gitignored directory. Do not publish code or evidence unless the operator separately authorizes the repo's `make pr` ceremony. Do not merge or deploy.

## Success criteria

See `ACCEPTANCE_MATRIX.md`. A successful inventory-bound purchase is recognized and tied to the exact intended warehouse without a fictitious buyer; the source evidence and idempotent native document identities remain intact; inventory outbound and normal customer sales do not regress. Unknown source destination links or stock-posting policy are explicitly reported, not guessed.
