# 09 — Operator handoff

**Contract:** `SM-CIETRADE-DOCUMENT-RECOVERY-001`  
**Status:** `RECOVERED_IMPORT_BLOCKED`  
**Census baseline:** 2026-10-28T16:06:07-04:00 on `UCSCIETRADE`  
**Updated:** 2026-10-28T20:09:00Z

## Source truth

Queryable transaction source: disposable SQL container `cie-sql-proof`, database `cieTrade_SM`, restored 2026-10-18 from `cieTrade_SM_2026-10-03.bak` (SHA-256 `8fee7239068ca9dc47d51909f63779574c0604489df893cba33db2d0ce2568a5`, backup taken 2026-10-03 16:35 on `UCSCIETRADE`).

That restore contains worksheet orders through 2026-10-02, including 59 `BuySell` rows ordered in September 2026. It does not contain document image bytes. `cieTrade_Documents` is not on this machine. Two older files dated 2025-09-03 are also `cieTrade_SM` media, not the documents database.

## Implementation

No branch, no diff, no importer. `Staging` was not modified. Publication, merge, and deploy were not performed. Production and Staging Odoo databases were not opened.

## Gates

| Gate | Result |
|---|---|
| A Backup discovery | FAIL — documents database absent; local `DocumentImage` empty |
| B Join proof | FAIL — no image rows to join |
| C File recovery | NOT RUN |
| D Odoo crosswalk | NOT RUN |
| E Importer | NOT RUN |
| F Tests | NOT RUN |

## Readiness

Blocked on a `cieTrade_Documents` backup. The request text is `08_PAPERSOLVE_REQUEST.md` in this directory. It has not been sent.

## Addendum 2026-10-28T19:40Z — live `cieTrade_Documents` screenshot

An SSMS window titled `UC…Administrator (92)` ran:

```sql
SELECT TOP 10 * FROM cieTrade_Documents.dbo.DocumentImage
WHERE DBName = 'cieTrade_SM'
```

That query returned rows. The documents database is online on the CieTrade server. It is still not in any local `.bak`, and this Mac cannot resolve `UCSCIETRADE`. The ten visible blobs start with `0x1F8B08` (GZIP). `DocName` and `DocType` are NULL. `DBName` is stored as both `CIETRADE_SM` and `cieTrade_SM`; the case-insensitive filter returns both.

Checked those keys against the local `cieTrade_SM` restore:

| RefType | RefID | DocID | Local result |
|---|---|---|---|
| W | 51654, 51655, 51656 | 92861, 92864, 92865, 92869, 92870 | One `BuySellNo` each. Not a `PONumber`. `WksDocument.RefFile = DocID` agrees for 92864, 92865, 92869, 92870. DocID 92861 has no registry row; worksheet 51654 still exists (ordered 2019-01-05). |
| P | 4675, 11547 | 92862, 92863, 92868 | One `PONumber` each, dated 2019-01-17. Not a `BuySellNo`. `PODocument.RefFile = DocID` names the same PO. The same integers also exist as `WKSDetail.DetailID` on other worksheets; `RefType` is what separates them. |
| W | 1232 | 92866 | No worksheet 1232 and no registry row. `DetailID` 1232 is a line on worksheet 52261. Not used. |
| P | 46 | 92867 | No PO 46. `PODocument.RefFile` 92867 belongs to PO **4676**. `DetailID` 46 is a line on worksheet 51684. Not used. |

This is a 10-row witness, not a corpus proof. No file bytes were copied.

## Addendum 2026-10-28T19:48Z — backup refused

`cieTrade_Documents` is ONLINE on `UCSCIETRADE` (SQL Server 2012 Standard, 11.0.7507.2). Data file `D:\DATA\cieTrade_DocumentImages.mdf` is 188,151 MB. Log is 156 MB. `C:` has 376,607 MB free.

`BACKUP DATABASE` was denied in `cieTrade_Documents` (Msg 262). `RESTORE VERIFYONLY` was denied because it needs `CREATE DATABASE` in `master`. No backup file was produced. Do not retry a server-side backup with this login.

## Census observed 2026-10-28T19:50Z

Operator query against live `cieTrade_Documents.dbo.DocumentImage` where `DBName = cieTrade_SM`:

| RefType | Image rows | Distinct DocID |
|---|---:|---:|
| `#` | 18 | 18 |
| `B` | 1 | 1 |
| `E` | 586 | 586 |
| `P` | 13,077 | 13,077 |
| `W` | 97,322 | 97,322 |
| Total | 111,004 | `Blob_Size` sum 39,561 MB |

Distinct DocID equals image rows for every type, so this result does not show multiple image rows sharing one DocID. `E`, `B`, and `#` are still unresolved. The PowerShell pilot was pasted into SSMS and did not run.

## Next action

Stay on live `UCSCIETRADE` (`cieTrade_Documents` and `cieTrade_SM`). Do not take a backup. The per-image manifest and the file extract have not been run. Odoo crosswalk counts were not taken from `odoo_test_night1021`.

## Locked census and later gates — 2026-10-28T16:06:07-04:00

Operator instruction: no backup. Source identity is the live census, not the October 3 restore and not a local Odoo test database.

| Item | Count |
|---|---:|
| `CIETRADE_SM` images | 111,005 |
| Distinct `ImageID` / `DocID` | 111,005 / 111,005 |
| Distinct `RefID` | 19,622 |
| W images linked by exact `BuySellNo` | 97,323 |
| P images linked by exact `PONumber` | 13,077 |
| `#` images linked by exact `BuySellNo` | 18 |
| E unassigned | 586 |
| B unassigned | 1 |
| W images with no `WksDocument` row, still source-linked | 10,570 |
| Worksheets on the live server | 9,009 |
| Worksheets with a W document | 8,813 |
| Worksheets with no W document | 196 |
| Purchase orders on the live server | 14,816 |
| Purchase orders with a P document | 10,530 |
| Purchase orders with no P document | 4,286 |
| `DocID`s with more than one image | 0 |
| `RefID`s shared by W and P | 1 |
| Other `DBName` rows excluded | 445,134 `CIETRADE` + 42,229 `CIETRADE_USSCRAP` |

One W image was created after the earlier 111,004 count. Newest `CreatedDT` is 2026-10-28 16:04:20.050. `BuySell.OrderDt` max is 2026-10-27. `PO.PODate` max is 2026-10-26.

| Later gate | Result |
|---|---|
| Snapshot backup | Not taken, by instruction |
| Per-image metadata manifest | PASS at 2026-10-28T16:23:04-04:00. See `10_MANIFEST_RECONCILIATION.md`. 111,010 rows |
| Byte extract and hash reconciliation | 20-file stream verified 2026-10-28. Journal all `ok`. Pilot raw SHA-256 values match. Full corpus not started |
| Per-image Odoo crosswalk | NOT RUN. Local `odoo_test_night1021` is a different, older database and was not used for these counts |
| Importer and replay tests | NOT RUN |

## Recount 2026-10-28T16:21:56-04:00

Same databases. No backup. `COUNT(DISTINCT ...)` on `cieTrade_Documents.dbo.DocumentImage` where `DBName` trims to `CIETRADE_SM`.

| Item | 16:06 census | 16:21 recount | Change |
|---|---:|---:|---:|
| Images / ImageID / DocID | 111,005 | 111,010 | +5 |
| `W` | 97,323 | 97,328 | +5 |
| `P` | 13,077 | 13,077 | 0 |
| `#` | 18 | 18 | 0 |
| `E` | 586 | 586 | 0 |
| `B` | 1 | 1 | 0 |
| Oldest `CreatedDT` | 2019-01-05 11:07:12 | 2019-01-05 11:07:12.000 | 0 |
| Newest `CreatedDT` | 2026-10-28 16:04:20.050 | 2026-10-28 16:13:56.000 | later |

The five new rows are all `W`. `2.rpt` in the repo is 117,910,749 bytes of `0x00` and is not a manifest.

## Five new worksheet joins — 2026-10-28T16:27:44-04:00

Same live databases. `buysell_hit` is an exact trimmed `BuySellNo` match.

| ImageID | DocID | RefID | CreatedDT | buysell_hit |
|---:|---:|---|---|---:|
| 721198 | 206292 | 60859 | 2026-10-28 16:11:34.023 | 1 |
| 721199 | 206293 | 60859 | 2026-10-28 16:11:49.087 | 1 |
| 721200 | 206294 | 60859 | 2026-10-28 16:11:49.133 | 1 |
| 721201 | 206295 | 60859 | 2026-10-28 16:11:49.180 | 1 |
| 721202 | 206296 | 60787 | 2026-10-28 16:13:56.000 | 1 |

All five stay linked `W` images. The manifest ceiling for extraction is ImageID 721202.

## Import scope revised 2026-10-28

Odoo import is worksheet evidence only. Eligible rows are 97,328 `W` plus 18 `#`. Match `RefID` exactly to one `plasticos.transaction.name`. `P` (13,077) stays in the archive and is excluded from Odoo import. `E` (586) and `B` (1) stay unattached. Generated PO and SO PDFs are skipped only when equivalence is positively proved. The repo statement is section 8 of `docs/campaigns/10-27-26/Cursor_Runbook_CieTrade_Documents_to_Odoo.md`.

Next action remains the full file extract through ImageID 721202. The crosswalk and the importer wait until that journal has 111,010 rows.
