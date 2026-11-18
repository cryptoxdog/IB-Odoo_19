---
auto_generated: false
authority: derived-index
component_id: plasticos_partner_import
component_name: Plasticos Partner Import
module_version: 19.0.2.10.41
layer: 3
installable: true
auto_install: true
application: false
depends:
  - base
  - base_setup
  - contacts
  - account
  - crm
  - utm
  - plasticos_base
  - plasticos_facility_profile
  - plasticos_intake
models_owned:
  - plasticos.erp.import
  - plasticos.partner.import.service
  - plasticos.partner.import.validation
  - plasticos.partner.import.wizard
  - plasticos.partner.bulk.update.wizard
models_extended: []
crons: []
---

# Plasticos Partner Import

The front matter above is a derived index. `__manifest__.py` and the `_name` lines in `models/` and `wizards/` win on any conflict.

## What it does

Imports the historical ERP's partners into native Odoo records: companies, facility addresses, contacts, contact roles, and salespersons. With `plasticos_transaction` installed, the same run goes on to write historical sale orders, purchase orders, and draft invoices and bills. The contract is [ADR-021](../docs/adr/ADR-021-erp-sql-crm-api-import.md) and its 2026-10-24 amendments.

## How it works

`plasticos.erp.import.run()` (`models/erp_import_service.py`) is the entry point.

1. **Read.** `erp/reader.py` `load_payload()` loads the source tables. With a database source (`ERP_SQL_SERVER` and `ERP_SQL_DATABASE`), each table is read from the restored ERP SQL Server through its script in `PROJECTION_SCRIPTS`. Without one, it reads statement files under `erp_extracted_data/`. The checked-in scripts are `SELECT` projections, so that read is empty and the reader falls back to the frozen grid pack in `erp_extracted_data/bulk/`. The reader's docstring calls that grid a regression and comparison fixture, not runtime authority. A real import uses the database source.
2. **Index.** `erp/source_index.py` builds the source index keyed by ERP ids (CpID, AddressID, CT_ID, CRA_ID, BuySellNo, DetailID).
3. **Partner stages,** in order: counterparties, addresses, contacts, roles, salesreps (`PARTNER_LAYERS`). The salesreps stage sets each company's Salesperson from its assigned rep, matched to `res.users` by login, and creates no user. An `after_stage` hook runs after each stage and before anything commits; the shell driver uses it to run `scripts/validate_partner_layer.py`, and a failed layer is rolled back.
4. **Identity.** A record's identity is always a stable ERP key in `ir.model.data` under module `plasticos_transaction`, for example `legacy_erp_cp_<id>`, `legacy_erp_address_<id>`, and `legacy_erp_contact_<id>`. Names, emails, phones, address text, and Odoo database ids are never identity. A re-import updates the same records.
5. **Historical documents.** Unless `partners_only` or `layer` is set, the run calls `_extend_historical_import()`. In this module that method returns false. When `plasticos_transaction` is installed, its override (`plasticos_transaction/models/legacy_erp_import_service.py`) writes `sale.order`, `purchase.order`, and `account.move`, leaves the moves in draft, creates no payment, and owns its own commits. It does not create `plasticos.transaction`. Confirming the imported sale order is what compiles a transaction.

Other models:

- `plasticos.partner.import.service` is the older deterministic CSV import (`run_csv_import`), reachable from `scripts/run_import.py`. It restricts its mutating entry points to the shell or Settings users. The two CSV files at the module root are its default inputs; the ERP pipeline does not read them.
- `plasticos.partner.import.validation` checks that foundation models exist before an import.
- `plasticos.partner.import.wizard` is retired: its import, audit, and repair actions always raise, and it has no view or menu.
- `plasticos.partner.bulk.update.wizard` edits many partners at once and has a view.

## Operator command

`make import-erp` pipes `scripts/import_erp_shell.py` into `odoo shell` on `ODOO_DB_NAME`.

- `DRY=1` resolves and maps without persisting.
- `LIMIT` counts worksheets, newest first (`LIMIT=25%` is the newest quarter); anything else is refused before any write.
- `PARTNERS_ONLY=1` runs only the five partner stages and does not open the deal files.
- `LAYER=<stage>` runs one partner stage; it opens only after the previous layer's validator passes.
- `ERP_SQL_SERVER` / `ERP_SQL_DATABASE` (with credentials from the environment) select the direct database read and win over `PAYLOAD_ROOT`.
- The machine summary is written to `.l9/pr/import-erp-summary.json` by default and is validated by `scripts/validate_import_summary.py`.

This is the command. It is not evidence that a live import has run on any database.

## Models

| Model                                  | Kind             | File                                    |
| -------------------------------------- | ---------------- | --------------------------------------- |
| `plasticos.erp.import`                 | owned, abstract  | `models/erp_import_service.py`          |
| `plasticos.partner.import.service`     | owned, abstract  | `models/partner_import_service.py`      |
| `plasticos.partner.import.validation`  | owned, abstract  | `models/validation.py`                  |
| `plasticos.partner.import.wizard`      | owned, transient | `wizards/partner_import_wizard.py`      |
| `plasticos.partner.bulk.update.wizard` | owned, transient | `wizards/partner_bulk_update_wizard.py` |

## Runtime

- No cron, no `data/` directory, no install hook.
- Manifest `data` holds only the access CSV and the bulk-update wizard view.
- `auto_install` is true.

## Boundaries

- The ERP is a source, not a schema template. The importer writes native fields and existing PlasticOS relations, not source-mirroring fields.
- It creates no `plasticos.transaction` and no `plasticos.transaction.line` itself, posts nothing, and creates no payment.
- Source-accurate posting, settlement, and full direct-SQL replay are not proven (ADR-021 amendments).
- SQL credentials come from the environment and are never written to this repository.

## Read next

- [`models/erp_import_service.py`](models/erp_import_service.py)
- [`erp/reader.py`](erp/reader.py)
- [`scripts/validate_partner_layer.py`](scripts/validate_partner_layer.py)
- [`../plasticos_transaction/models/legacy_erp_import_service.py`](../plasticos_transaction/models/legacy_erp_import_service.py)
- [ADR-021](../docs/adr/ADR-021-erp-sql-crm-api-import.md)
