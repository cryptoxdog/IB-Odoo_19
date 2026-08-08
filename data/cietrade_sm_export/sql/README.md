# cieTrade extract SQL (canonical)

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

Playbook: [`docs/cietrade_sm_export_research.md`](../../../docs/cietrade_sm_export_research.md)
