# plasticos_partner_import

PlasticOS historical ERP source ingestion and deterministic partner realization for Odoo 19.

## Current purpose

The current ERP architecture is defined by ADR-021:

- ERP data enters through SQL.
- VanillaSoft CRM data enters through `plasticos_crm_sync` API integration.
- Frozen CSV/grid files are regression fixtures, not runtime authority.
- Legacy CSV wizards remain compatibility/technical surfaces only and must not be extended as the production path.

The canonical ERP operator entrypoint is `make import-erp`.

## Deterministic pipeline

```text
restored ERP SQL Server
        ↓
erp.reader
        ↓
erp.source_index
        ↓
partner realization in plasticos.erp.import
```

`models/erp_import_service.py` owns counterparties, addresses/locations, contacts, roles, and salespersons. `_extend_historical_import()` does not write `plasticos.transaction` or `plasticos.transaction.line`. A full run is refused before any write.

Stable ERP source keys are written through `ir.model.data` identity markers. Names, email addresses, phone numbers, address text, and Odoo database IDs are never identity.

## Source forms

Production-intent source:

- Direct read of the restored SQL Server database using the projection registry in `erp/reader.py`.

Compatibility/test forms:

- SQL statement payloads understood by the same reader.
- Frozen `erp_extracted_data/bulk/` grids for regression and replay tests.

The compatibility forms do not authorize new CSV mappings or CSV-first operating procedures.

## Partner stages

Partner stages always execute in this order:

1. counterparties
2. addresses / locations
3. contacts
4. roles
5. salespersons

`PARTNERS_ONLY=1` limits a run to those sources and stages. Layer mode can execute one partner stage after the preceding stage has been validated.

## Full historical import

A full run uses the same source/index path, then delegates deal realization to the `plasticos_transaction` extension. A full run must fail closed when that extension is unavailable. Partner-only completion is not a successful full historical import.

Result accounting must reconcile every source row into created, updated, unchanged, or rejected outcomes. A reconciliation mismatch is a material failure, not a warning.

## Mapping law

`erp/mapping_status.py` is the machine-readable disposition registry for source columns. `docs/erp_import_mapping.md` is the narrative mapping and identity contract.

Do not create fields to mirror the legacy ERP. Map into native Odoo fields wherever the business meaning already exists. Any proposed new field requires a proven semantic gap and explicit operator approval.

`GPLedger.TradeDt` is the historical PO issue/approval date. When a historical purchase order is realized, the native Odoo target is `purchase.order.date_approve`. Do not add `plasticos.transaction.transaction_date` for this concept.

## Legacy UI

The partner CSV wizard is not the production ERP import path. It may remain for controlled technical compatibility until separately retired, but documentation, new features, and normal operator procedures must use the deterministic SQL-backed pipeline.

VanillaSoft CRM CSV surfaces are likewise deprecated in favor of `plasticos_crm_sync`.

## Module reference

Retained from the previous README; unrelated to the ERP source correction above.

### Migrations

| Version | Change |
|---|---|
| `19.0.1.1.0` | Renames `x_vanillasoft_id` → `vanillasoft_id` in DB |
| `19.0.1.2.0` | Renames `x_facility_role` → `facility_role` in DB |

**Note:** Migration scripts reference the old `x_` names intentionally — that is correct behavior for migration files. Do not treat those as bugs.

### Deployment

```bash
docker compose -p odoo19 run --rm odoo \
  -d odoo --db-host db --db-port 5432 --db-user odoo --db-password odoo \
  -u plasticos_partner_import --stop-after-init
```

### Integration Points

| Module | Notes |
|---|---|
| `plasticos_facility_profile` | Imported partners can be assigned facility profiles post-import |
| `plasticos_crm_bridge` | Optional. When installed, ERP partners take its UTM source; not a manifest dependency, so partner import does not pull the transaction spine |
