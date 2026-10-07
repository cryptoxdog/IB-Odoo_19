# PlasticOS · Odoo 19

PlasticOS is the Odoo 19 ERP spine for recycled-plastics brokerage operations. The repository contains the custom `plasticos_*` addon suite, cross-module tests, import tooling, governance, and runtime gates used to move changes from `Staging` toward `Production`.

## Repository flow

- Integration branch: `Staging`
- Production branch: `Production`
- Odoo: 19
- Python: 3.12
- Primary database: PostgreSQL 16
- Historical ERP source: SQL Server, read through deterministic projection scripts

`AGENTS.md` is the cross-tool operating guide. `CLAUDE.md` carries Claude-specific repository guidance. `ARCHITECTURE.md` and `INVARIANTS.md` describe the system boundary and repository invariants.

## Historical ERP import

ERP migration is one deterministic pipeline, not a family of spreadsheet importers:

```text
restored ERP SQL Server
        ↓
plasticos_partner_import/erp/reader.py
        ↓
SourceIndex + deterministic source identity
        ↓
partner stages
        ↓
transaction header reconstruction
        ↓
plasticos_transaction legacy ERP extension
        ↓
Odoo records
```

The direct database reader executes the canonical projection scripts under `plasticos_partner_import/erp_extracted_data/`. The frozen files under `erp_extracted_data/bulk/` are regression fixtures only. They are not runtime authority and must never be edited to make an import pass.

The canonical operator entrypoint is `make import-erp`. Partner-only execution is available with `PARTNERS_ONLY=1`. A full import includes transaction reconstruction and realization and must fail closed if that realization is unavailable or if result accounting does not reconcile.

See:

- `docs/runbooks/ERP_IMPORT.md` — operator runbook
- `docs/adr/ADR-021-erp-sql-crm-api-import.md` — source architecture decision
- `docs/erp_import_mapping.md` — source-to-Odoo mapping authority
- `plasticos_partner_import/erp/mapping_status.py` — machine-readable column disposition

## ERP date ownership

The legacy `GPLedger.TradeDt` means the date the purchase order was issued and the transaction was approved under current PlasticOS rules.

Odoo 19 already owns that concept on the purchase order. The target is `purchase.order.date_approve` (`Confirmation Date`) when the historical PO is realized. `purchase.order.date_order` remains the RFQ/order-deadline date.

Do not add a custom `plasticos.transaction.transaction_date` field to mirror the legacy source. More generally, map source concepts into native Odoo fields wherever the accounting or operational meaning already exists. Any proposed new field is an operator approval gate.

## Validation levels

Static and pure-Python tests prove source parsing, mapping, deterministic identity, and structural contracts. Real Odoo/PostgreSQL runtime gates prove ORM and transaction behavior. Direct-SQL migration readiness additionally requires a real SQL Server → Odoo run and an identical replay against a disposable nonproduction database.

A green CI run does not substitute for that live seam proof.

## Development starting points

- `AGENTS.md` — tool and repository operating rules
- `docs/LOCAL_DEV_SETUP.md` — local environment
- `reports/repo-index/` — generated codebase indexes; regenerate after behavior-changing work stabilizes
- `tests/runtime_gates/` — real-runtime proof scripts
- `skills/` — PlasticOS project skills

Do not extend retired CSV import paths. Do not create schema to mirror the legacy ERP. Keep Odoo as the operational and accounting authority.
