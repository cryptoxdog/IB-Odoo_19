# ADR-021: ERP Data Imports from SQL, CRM Data Imports from the API

**Successor boundary:** [ADR-022](ADR-022-erp-historical-closure-and-accounting-opening-balances.md)
records the operator's proposed historical closure and separately authorized
QuickBooks/ERP residual accounting cutover. It does not supersede the single
ERP SQL ingestion pipeline or authorize go-live posting.

**Status:** Accepted  
**Date:** 2026-10-01  
**Deciders:** Igor Beylin  
**Scope:** ERP partner and historical transaction import; VanillaSoft CRM import  
**Supersedes:** The CSV transport in ADR-003. ADR-003's partner hierarchy and role/rank semantics remain applicable.

## Context

Two inbound streams had drifted toward CSV-oriented operating instructions: ERP data and VanillaSoft CRM data. That transport is retired. The ERP already has canonical SQL projection definitions under `plasticos_partner_import/erp_extracted_data/`, and CRM has an API integration.

The architecture must preserve deterministic source identity while preventing the frozen regression grids from becoming a second runtime authority.

## Decision

1. **ERP data enters through SQL.** Partners, facilities, contacts, contact roles, salespersons, and historical transaction reconstruction inputs are read from the restored ERP database through canonical SQL projection scripts.
2. **CRM data enters through the API.** VanillaSoft leads and calls load through `plasticos_crm_sync`.
3. **CSV is legacy or test evidence only.** The old CSV wizards and `erp_extracted_data/bulk/*.csv` are not the runtime architecture. Frozen grids may remain as immutable regression fixtures.
4. **Source identity stays source-native.** ERP upserts use ERP keys (`CpID`, `AddressID`, `CT_ID`, `BuySellNo`, `DetailID`, and the applicable set-valued relationships), never names, email addresses, phone numbers, or Odoo database IDs.
5. **One import pipeline.** Direct SQL must feed the existing deterministic `reader → SourceIndex → mapping/reconstruction → ORM upsert` path. No parallel direct-SQL importer is permitted.
6. **Native Odoo semantics first.** A legacy field does not justify a new Odoo field. Map into native Odoo or an existing PlasticOS field when the business meaning already exists. A new field requires a proven representation gap and explicit operator approval.
7. **Trade date is a PO approval date.** `GPLedger.TradeDt` means the date the purchase order was issued and the transaction approved under current PlasticOS rules. When the historical PO is realized, its native target is `purchase.order.date_approve` (`Confirmation Date`). `purchase.order.date_order` remains the RFQ/order-deadline date. No custom `plasticos.transaction.transaction_date` field is authorized.
8. **Full import fails closed.** A full ERP import must not report success by writing `plasticos.transaction` or `plasticos.transaction.line`. Commercial documents are `sale.order`, `purchase.order`, and `account.move`, and this import does not realize them yet. A full run is refused before any write. Partner imports still fail closed when source-row accounting does not reconcile.
   *Amended 2026-10-24 (see Amendments): the last two sentences before "Partner imports" no longer describe the code.*

## Amendments

### 2026-10-24 — Decision 8 describes a full run that no longer exists

Decision 8 as written on 2026-10-01 says a full run is refused before any write and does not realize commercial documents. The code has since changed:

- A full run (no `PARTNERS_ONLY`) runs the partner stages, then `plasticos_transaction` (`legacy_erp_import_service._extend_historical_import` → `native_document_import.realize`) writes `sale.order`, `purchase.order`, and draft `account.move` records from the source index.
- The importer writes no `plasticos.transaction` or `plasticos.transaction.line` itself. It confirms the sale orders it realizes (`native_document_import._confirm_sales`), and the sales hook compiles the transaction from the confirmed order.
- The importer creates no payment and posts nothing itself.

The first sentence of Decision 8 still holds: the importer must not report success by writing transaction records directly. Partner imports still fail closed when source-row accounting does not reconcile.

Not proven: source-accurate posting state, settlement, vendor bill identity (`PayablesBatch` header vs one bill per `PayableID`), and a complete direct-SQL import with identical replay. This amendment records current behaviour. It authorizes no new import policy and makes no claim that the accounting is complete.

### 2026-10-24 — Vendor bill identity and header facts (operator decision)

- A vendor bill stays one `account.move` per `Payables.PayableID`. It is not regrouped per `PayablesBatch`: 599 multi-row batches span more than one worksheet in the 2026-08-07 extract, and documents are realized per worksheet.
- The bill takes its `PayablesBatch` header's `InvoiceDt`, `InvoiceNo` and terms. `APTerms` naming an existing `account.payment.term` sets the term; no term is created. Otherwise the header `DueDate` is the due date, with no term set.
- No invoice or bill takes the worksheet order date as its invoice date.
- `purchase.order.date_approve` is the earliest `GPLedger.TradeDt` of the worksheets the order serves (Decision 7). The order stays a draft.
- A `Delivered` price basis carries no Incoterm. Confirming a historical sale order launches no procurement, so no picking or stock move is created.
- Whether a re-import updates documents that already exist is not decided. They are left as they are.

### 2026-11-12 — Price basis to Incoterm (BRS-EXP-02-R006, operator decision)

The 2026-10-24 crosswalk mapped the recycler's `fob`, `fob supplier dock` and `pickup` price bases onto the Incoterms 2020 `FOB`. That is wrong. These are domestic shipping-point bases: the buyer collects at the supplier's dock. Incoterms FOB is delivery on board a vessel at the port of shipment. BRS-EXP-02-R006 keeps the commercial trade label apart from the legal Incoterm.

- `fob`, `fob supplier dock` and `pickup` map to no Incoterm. They are declined and reported like `delivered` (`plasticos_partner_import/erp/native_orders.py`: `DOMESTIC_SHIPPING_POINT_BASES`, `DECLINED_PRICE_BASES`).
- `fas` maps to `FAS` only, because it is the literal Incoterm.
- `delivered` is unchanged. It sets no Incoterm and clears one an earlier run wrote.
- Already-imported orders are not rewritten. A domestic shipping-point basis never writes the Incoterm field of an order that already exists. The stored value is reported ("stored Incoterm … left unchanged"), not cleared. No migration changes them.
- No field is added: the commercial label lives on the Export cargo link (BRS-EXP-02-R006), not on the order.
- Import summaries reconcile as before. A declined basis is an anomaly row, not a rejected record, so `records_seen == records_created + records_updated + records_unchanged + records_rejected` is unaffected.
- The production-rehearsal fidelity verifier (`tests/production-rehearsal/fidelity.py`) applies the same crosswalk. An order that still carries the pre-amendment `FOB` for a domestic basis is reported there as a difference from the source, not rewritten.

## Direct database projections

The direct database reader covers the five partner-side sources and the six transaction-reconstruction sources used by the deterministic pipeline:

- `CounterParty`
- `Address`
- `Contact`
- `ContactRoleAssignment`
- `SalesReps`
- `Payables`
- `Receipt`
- `ReceiptBatch`
- `GPLedger`
- `WKSDetail`
- `WksDelivery`

The projection mapping is owned by `plasticos_partner_import/erp/reader.py::PROJECTION_SCRIPTS`. `20_receiptbatch.sql` and `21_wksdelivery.sql` provide the single-result forms of the corresponding queries from the multi-result extract script.

## Consequences

- `make import-erp` with `ERP_SQL_*` selects the direct restored-database source.
- `PARTNERS_ONLY=1` restricts execution to Concern 1 partner tables and stages.
- A full run may read and reconstruct transaction data only through the same source/index seam used by tests and fixture replay.
- Runtime proof from a frozen fixture is useful but does not by itself prove the SQL Server → Odoo seam. Direct-SQL production readiness requires a live disposable-database import and identical replay.
- Documentation that calls the frozen `bulk/` directory authoritative, says direct SQL is partner-only, or presents the CSV transaction wizard as the current import path is stale.

## Compliance

- Do not reintroduce a CSV wizard as the normal ERP or CRM operator path.
- Do not add legacy-source-mirroring fields to Odoo merely because the source exposes them.
- Do not create `plasticos.transaction.transaction_date` for `TradeDt`; use the native PO approval date when PO realization is implemented.
- Keep unresolved or unsupported source semantics explicit. Do not coerce them into a green import result.
