# Live extract pack — `data/legacy_erp_sm_export`

**Playbook (SSOT):** [`docs/legacy_erp_sm_export_research.md`](../../docs/legacy_erp_sm_export_research.md)

| Path | Contents |
|------|----------|
| `sql/` | Canonical scripts `00`–`06`, singles `10`–`17` (see `sql/README.md`) |
| `bulk/` | Golden CSVs (ACCEPT) |
| `diagnostics/` | Deep diagnostic artifacts |
| `samples/` | Early top-N probes |
| `meta/` | `p0_columns.csv`, census / count probes |
| `scripts/` | Optional Windows probe helpers |

DB: **`LEGACY_ERP_SM_EXPORT`** @ `LEGACY_ERP_SQL_HOST`.

**Reload:** `pbcopy < sql/05_extract_all.sql` → SSMS Execute → Copy with Headers each grid → `bulk/`.

**Omitted from this pack (WIP-only / reject):**

- Legacy `sql/archive/` explore chunks
- Duplicate `Transactions.csv` (same shape as `WKSDetail.csv`)
- Duplicate `counterparty_full_from_file1.csv`
- Corrupt extract `legacy_erp_export_20260807_183800/`
- Excel land path / `.rpt` null dumps
