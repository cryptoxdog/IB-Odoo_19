# Live extract pack — `data/erp_sm_export`

**Playbook (SSOT):** [`docs/erp_extract_research.md`](../../docs/erp_extract_research.md)

| Path | Contents |
|------|----------|
| `plasticos_partner_import/erp_extracted_data/` | Canonical scripts `00`–`06`, singles `10`–`17` (see that folder's `README.md`) |
| `plasticos_partner_import/erp_extracted_data/bulk/` | Golden CSVs (ACCEPT) |
| `plasticos_partner_import/erp_extracted_data/diagnostics/` | Column inventory and role distribution |
| `plasticos_partner_import/erp_extracted_data/meta/` | `p0_columns.csv`, census / count probes |
| `samples/` | Early top-N probes, not used by the import |
| `scripts/` | Optional Windows probe helpers |

DB: **`LEGACY_ERP_SM_EXPORT`** @ `LEGACY_ERP_SQL_HOST`.

**Reload:** `pbcopy < plasticos_partner_import/erp_extracted_data/05_extract_all.sql` → SSMS Execute → Copy with Headers each grid → `plasticos_partner_import/erp_extracted_data/bulk/`.

**Omitted from this pack (WIP-only / reject):**

- Legacy `sql/archive/` explore chunks
- Duplicate `Transactions.csv` (same shape as `WKSDetail.csv`)
- Duplicate `counterparty_full_from_file1.csv`
- Corrupt extract `legacy_erp_export_20260807_183800/`
- Excel land path / `.rpt` null dumps
