# Legacy ERP `SM_EXPORT` — tracked extract pack

**Runbook (SSOT):** [`docs/legacy_erp_sm_export_research.md`](../../docs/legacy_erp_sm_export_research.md)

Golden CSVs + SELECT-only SQL from `LEGACY_ERP_SM_EXPORT` @ `LEGACY_ERP_SQL_HOST` (2026-08-07 live extract). Import is wired: `plasticos_transaction/legacy_erp/` (source layer) + `plasticos_transaction/models/legacy_erp_import_service.py` (Odoo upsert), driven by `make import-legacy-erp` — see [`docs/legacy_erp_import_mapping.md`](../../docs/legacy_erp_import_mapping.md) and [`docs/runbooks/LEGACY_ERP_IMPORT.md`](../../docs/runbooks/LEGACY_ERP_IMPORT.md).

| Path | Contents |
|------|----------|
| `sql/` | Canonical scripts `00`–`06`, singles `10`–`17` |
| `bulk/` | Golden CSVs (ACCEPT) |
| `diagnostics/` | Deep diagnostic artifacts |
| `samples/` | Early top-N probes |
| `meta/` | Column inventory / census / count probes |
| `scripts/` | Optional Windows `sqlcmd` probe |

**Reload:** `pbcopy < sql/05_extract_all.sql` → SSMS Execute → Copy with Headers each grid → `bulk/`.
