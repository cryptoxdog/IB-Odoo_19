# 09 — Operator handoff

**Contract:** `SM-CIETRADE-DOCUMENT-RECOVERY-001`  
**Status:** Live-server extract in progress. Import scope locked. Importer not started.  
**Census baseline:** 2026-10-28T16:06:07-04:00 on `UCSCIETRADE`  
**Updated:** 2026-10-28T21:05:00Z

## Current status

This section is the current reading. It supersedes the opening gate table, the readiness line that the work is blocked on a `cieTrade_Documents` backup, and any later sentence that says the manifest or the file extract has not been run. Those passages stay in this file with their original timestamps.

The source is the live `UCSCIETRADE` databases `cieTrade_Documents` and `cieTrade_SM`. No backup was taken. The manifest reconciled to 111,010 `CIETRADE_SM` images at 2026-10-28T16:23:04-04:00. A 20-file stream verified. The full extract through ImageID 721202 is running and is not changed by this correction. The Odoo importer has not been implemented and has not been run.

The locked import rule is `11_IMPORT_SCOPE.md`. Every `W` and `#` image is eligible. `P`, `E`, and `B` stay outside Odoo, with their originals kept in the private archive.

## Mac landing folder

The expanded files land on this Mac in `/Users/ib-mac/Odoo-ERP-Files`. That folder was `Odoo-BAK-Files` until 2026-10-28. The same folder holds `cieTrade_SM_2026-10-03.bak` (97,973,248 bytes). The running extractor still writes on the server share `\\ucsservers01\home\ibeylin\Desktop\SQL 10-28-26\extract`. This folder is the copy destination after that extract, not a change to the extractor.

Inside the IB-PC Remote Desktop session the copy path is `\\tsclient\Odoo-ERP-Files`. Windows App still has the IB-PC folder redirect saved as `Odoo-BAK-Files` → `/Users/ib-mac/Odoo-BAK-Files`, and that path no longer exists. Re-add `/Users/ib-mac/Odoo-ERP-Files` on the IB-PC connection before copying. The Admin-PC connection does not redirect this folder.

## Go-live ERP source

`12_GO_LIVE_SOURCE_CHAIN.md` is the chain for go-live day. A new full backup of live `cieTrade_SM`, current as of that day, is placed in `/Users/ib-mac/Odoo-ERP-Files/`. That file is the restore input. `make import-erp` then reads the database restored from it.

`docs/campaigns/PlasticOS_Plan_Graph` is tracked and published with this pack. It is planning only.

The October 3 restore below is the historical proof. Its restore input was `/Users/ib-mac/sql-backup-proof/cieTrade_SM_2026-10-03.bak`. Worksheet activity in that database stops at 2026-10-02.

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

## Locked import scope — 2026-10-28

Every `RefType` `W` image (97,328) and every `RefType` `#` image (18) is eligible. Content, filename, and document type do not remove one. A file is imported only onto the single `plasticos.transaction` whose `name` equals its complete worksheet `RefID`.

`P` (13,077), `E` (586), and `B` (1) stay outside Odoo. Their originals stay in `/Users/ib-mac/Odoo-ERP-Files`, the same folder as `cieTrade_SM_2026-10-03.bak`.

Disposition counts for the eligible images are: eligible, unique Odoo match, missing transaction, ambiguous transaction, integrity failure, successfully imported, and import failure. `eligible = unique Odoo match + missing transaction + ambiguous transaction + integrity failure`. `unique Odoo match = successfully imported + import failure`.

The repo statement is section 8 of `docs/campaigns/10-27-26/Cursor_Runbook_CieTrade_Documents_to_Odoo.md`. The full extract through ImageID 721202 is the running step. The crosswalk and the importer wait until `journal.csv` has 111,010 rows.
