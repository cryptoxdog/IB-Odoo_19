# ADR-021: ERP Data Imports from SQL, CRM Data Imports from the API

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
