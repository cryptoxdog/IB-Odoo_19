# Legacy ERP `SM_EXPORT` — tracked extract pack

**Runbook (SSOT):** [`docs/legacy_erp_sm_export_research.md`](../../docs/legacy_erp_sm_export_research.md)

Golden CSVs + SELECT-only SQL from `LEGACY_ERP_SM_EXPORT` @ `LEGACY_ERP_SQL_HOST` (2026-08-07 live extract). PlasticOS import for this dump is not wired yet.

| Path | Contents |
|------|----------|
| `sql/` | Canonical scripts `00`–`06`, singles `10`–`17` |
| `bulk/` | Golden CSVs (ACCEPT) |
| `diagnostics/` | Deep diagnostic artifacts |
| `samples/` | Early top-N probes |
| `meta/` | Column inventory / census / count probes |
| `scripts/` | Optional Windows `sqlcmd` probe |

**Reload:** `pbcopy < sql/05_extract_all.sql` → SSMS Execute → Copy with Headers each grid → `bulk/`.
