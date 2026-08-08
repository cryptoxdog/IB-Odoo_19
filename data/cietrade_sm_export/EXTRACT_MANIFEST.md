# Live extract pack — `data/cietrade_sm_export`

**Playbook (SSOT):** [`docs/cietrade_sm_export_research.md`](../../docs/cietrade_sm_export_research.md)

| Path | Contents |
|------|----------|
| `sql/` | Canonical scripts `00`–`06`, singles `10`–`17` (see `sql/README.md`) |
| `bulk/` | Golden CSVs (ACCEPT) |
| `diagnostics/` | Deep diagnostic artifacts |
| `samples/` | Early top-N probes |
| `meta/` | `p0_columns.csv`, census / count probes |
| `scripts/` | Optional Windows probe helpers |

DB: **`cieTrade_SM_EXPORT`** @ `UCSCIETRADE`.

**Reload:** `pbcopy < sql/05_extract_all.sql` → SSMS Execute → Copy with Headers each grid → `bulk/`.

**Omitted from this pack (WIP-only / reject):**

- Legacy `sql/archive/` explore chunks
- Duplicate `Transactions.csv` (same shape as `WKSDetail.csv`)
- Duplicate `counterparty_full_from_file1.csv`
- Corrupt extract `cieTrade_export_20260807_183800/`
- Excel land path / `.rpt` null dumps
