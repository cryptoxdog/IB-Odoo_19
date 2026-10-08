# ERP extract SQL (canonical)

These SQL files define the restored ERP database projections consumed by the deterministic historical import. They are source-query authority. Frozen files under `bulk/` are regression fixtures only.

| # | File | Use |
|---|---|---|
| 00 | `00_probe.sql` | Confirm database / login / server |
| 01 | `01_census.sql` | Table size rank |
| 02 | `02_columns.sql` | Column inventory |
| 03 | `03_diagnostic.sql` | PK / FK / distribution diagnostics |
| 04 | `04_counts.sql` | Exact row counts |
| 05 | `05_extract_all.sql` | Multi-result full research extract |
| 06 | `06_extract_remaining.sql` | Supplemental research extract |
| 10 | `10_counterparty.sql` | `CounterParty` direct runtime projection |
| 11 | `11_address.sql` | `Address` direct runtime projection |
| 12 | `12_contact.sql` | `Contact` direct runtime projection |
| 13 | `13_payables.sql` | `Payables` direct runtime projection |
| 14 | `14_receipt.sql` | `Receipt` direct runtime projection |
| 15 | `15_gpledger.sql` | `GPLedger` direct runtime projection |
| 16 | `16_wksdetail.sql` | `WKSDetail` direct runtime projection |
| 17 | `17_prepayledger.sql` | Research/support projection; not part of the current runtime source set |
| 18 | `18_contactroleassignment.sql` | `ContactRoleAssignment` direct runtime projection |
| 19 | `19_salesreps.sql` | `SalesReps` direct runtime projection |
| 20 | `20_receiptbatch.sql` | `ReceiptBatch` direct runtime projection; single-result form of the query in `05_extract_all.sql` |
| 21 | `21_wksdelivery.sql` | `WksDelivery` direct runtime projection; single-result form of the query in `05_extract_all.sql` |
| — | `bulk/` | Frozen 2026-08-07 row grids; regression fixtures, never runtime authority |
| — | `meta/` | Column types, census, and row-count evidence |
| — | `diagnostics/` | Full column inventory and distribution evidence |

Playbook: `docs/erp_extract_research.md`

## Direct database read

`plasticos_partner_import/erp/reader.py::PROJECTION_SCRIPTS` is the runtime projection registry. A full direct-SQL source read covers all 11 source tables required by the partner and transaction-reconstruction pipeline:

`CounterParty`, `Address`, `Contact`, `ContactRoleAssignment`, `SalesReps`, `Payables`, `Receipt`, `ReceiptBatch`, `GPLedger`, `WKSDetail`, and `WksDelivery`.

`PARTNERS_ONLY=1` restricts the requested set to the five partner-side sources; the six deal tables are not opened in that mode.

The SQL driver is selected by `ERP_SQL_DRIVER` (`pymssql` by default, `pyodbc` when explicitly configured). Credentials are supplied through the process environment and must never be written to tracked files or emitted into import summaries.
