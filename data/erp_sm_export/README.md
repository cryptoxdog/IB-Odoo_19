# ERP `SM_EXPORT` — tracked extract pack

**Runbook (SSOT):** [`docs/erp_extract_research.md`](../../docs/erp_extract_research.md)

The 2026-08-07 row files now live in `plasticos_partner_import/erp_extracted_data/bulk/`. The SQL query definitions live beside them. Import is wired in that module (`erp/` + `models/erp_import_service.py`), driven by `make import-erp` — see [`docs/erp_import_mapping.md`](../../docs/erp_import_mapping.md) and [`docs/runbooks/ERP_IMPORT.md`](../../docs/runbooks/ERP_IMPORT.md).

| Path | Contents |
|------|----------|
| `plasticos_partner_import/erp_extracted_data/` | Canonical scripts `00`–`06`, singles `10`–`17` |
| `plasticos_partner_import/erp_extracted_data/bulk/` | Golden CSVs (ACCEPT) |
| `plasticos_partner_import/erp_extracted_data/diagnostics/` | Column inventory and role distribution |
| `plasticos_partner_import/erp_extracted_data/meta/` | Column inventory / census / count probes |
| `samples/` | Early top-N probes, not used by the import |
| `scripts/` | Optional Windows `sqlcmd` probe |

**Reload:** `pbcopy < plasticos_partner_import/erp_extracted_data/05_extract_all.sql` → SSMS Execute → Copy with Headers each grid → `plasticos_partner_import/erp_extracted_data/bulk/`.
