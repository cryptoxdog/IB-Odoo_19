# ERP extract SQL (canonical)

| # | File | Use |
|---|------|-----|
| 00 | `00_probe.sql` | Confirm DB / login / server |
| 01 | `01_census.sql` | Table size rank |
| 02 | `02_columns.sql` | P0 column inventory |
| 03 | `03_diagnostic.sql` | PK / FK / distributions |
| 04 | `04_counts.sql` | Exact row counts |
| **05** | **`05_extract_all.sql`** | **Full reload — 14 result grids** |
| 06 | `06_extract_remaining.sql` | Batches / roles / delivery / docs only |
| 10–17 | `10_counterparty.sql` … `17_prepayledger.sql` | Single-table full extracts |
| 18–19 | `18_contactroleassignment.sql`, `19_salesreps.sql` | Single-table partner projections the direct database read executes (`erp/reader.py`, `PROJECTION_SCRIPTS`) |
| | `bulk/` | Frozen row files from the 2026-08-07 grid extract — regression fixture, not runtime authority (ADR-021); never edited to make an import pass |
| | `meta/` | Column types, census, and row-count probes |
| | `diagnostics/` | Full column inventory and role distribution |

Playbook: [`docs/erp_extract_research.md`](../../docs/erp_extract_research.md)

## Direct database read (runtime form)

`make import-erp ERP_SQL_SERVER=<host> ERP_SQL_DATABASE=<db> [ERP_SQL_USER=.. ERP_SQL_PASSWORD=..]`
reads the five partner tables straight from the restored ERP database by executing
`10`, `11`, `12`, `18`, and `19` above, one result set each, with the same columns, filters,
`RTRIM`s and ordering the frozen grid was produced with. `ERP_SQL_DRIVER` is `pymssql`
(default) or `pyodbc`. The password is read from the environment only and never logged.
