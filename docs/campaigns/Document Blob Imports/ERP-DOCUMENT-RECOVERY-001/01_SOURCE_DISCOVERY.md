# 01 — Source discovery

**Current reading (2026-10-28):** The Gate A FAIL below is the 19:33Z local-backup inspection. It stays here as history. The live `cieTrade_Documents` database on `UCSCIETRADE` is the source. No backup was taken. The locked import scope is `11_IMPORT_SCOPE.md`.

On 2026-10-28 the home folder `Odoo-BAK-Files` was renamed to `/Users/ib-mac/Odoo-ERP-Files`. The backup row below was the path at inspection time. That same `cieTrade_SM_2026-10-03.bak` now lives in the renamed folder. Expanded extract copies land in that folder. The other three backup copies were not moved.

Go-live does not reuse this October 3 file. `12_GO_LIVE_SOURCE_CHAIN.md` names the chain: a new `cieTrade_SM` backup, current as of that day, is placed in `/Users/ib-mac/Odoo-ERP-Files/` and is the restore input for that day's `make import-erp`.

**Contract:** `SM-CIETRADE-DOCUMENT-RECOVERY-001`  
**Observation time:** 2026-10-28T19:33:11Z  
**Gate A:** FAIL

## Repository state at run start

| Item | Value |
|---|---|
| Remote | `https://github.com/cryptoxdog/IB-Odoo_19.git` |
| Local branch | `feat/crm-lead-material-identity` |
| Local HEAD | `524f8db25cb098414257fbc964d83b0b3ab3d6cb` |
| `Staging` and `origin/Staging` | `04bd0594a7c9dcad53d9c45fc65276d76817c112` |
| Uncommitted work | Present on the feature branch. Left untouched. No isolated code branch was created because no importer was authorized. |

No production database and no Staging database were opened. The only SQL instance queried is the local disposable container below.

## SQL instance

| Item | Value |
|---|---|
| Container | `cie-sql-proof` |
| Image | `mcr.microsoft.com/mssql/server:2022-latest` |
| Started | 2026-10-18T02:54:18Z |
| Port | `127.0.0.1:14330` → 1433 |
| Tool | `/opt/mssql-tools18/bin/sqlcmd` inside the container |
| Host `sqlcmd` / `pyodbc` | Not installed |
| Other SQL ports | `127.0.0.1:1433` closed. Host name `UCSCIETRADE` does not resolve. |
| Mount | `/Users/ib-mac/sql-backup-proof` → `/var/opt/mssql/backup` (read-only) |

`sys.databases` on this instance: `master`, `tempdb`, `model`, `msdb`, `cieTrade_SM`.  
`cieTrade_Documents` is not attached and has no data file under `/var/opt/mssql/data`.

`msdb.dbo.restorehistory` records one user restore: `cieTrade_SM`, full, `2026-10-18 02:55:15`, backup set `051D8716-6176-4418-BA23-80FE4C22EEC2`. That UUID is the backup set inside `cieTrade_SM_2026-10-03.bak`.

## Backup files

Spotlight and a depth-limited search of home, Downloads, Desktop, Documents, the IB-Odoo worktrees, and `Dropbox/Odoo - Master Folder` found six `cieTrade*.bak` files and no `cieTrade*.mdf` / `.ndf` outside the container. No file name contained `cieTrade_Documents`.

### `cieTrade_SM_2026-10-03.bak` — one backup, four copies

| Path | Bytes | SHA-256 |
|---|---:|---|
| `/Users/ib-mac/Odoo-BAK-Files/cieTrade_SM_2026-10-03.bak` | 97,973,248 | `8fee7239068ca9dc47d51909f63779574c0604489df893cba33db2d0ce2568a5` |
| `/Users/ib-mac/sql-backup-lab/cieTrade_SM_2026-10-03.bak` | 97,973,248 | same |
| `/Users/ib-mac/sql-backup-proof/cieTrade_SM_2026-10-03.bak` | 97,973,248 | same |
| `plasticos_partner_import/erp_extracted_data/bulk/cieTrade_SM_2026-10-03.bak` | 97,973,248 | same |

`RESTORE HEADERONLY` on the copy mounted in the container:

| Field | Value |
|---|---|
| Backup name | `cieTrade_SM-Full Database Backup` |
| Backup type | Full, position 1, one backup set |
| Database name | `cieTrade_SM` |
| Server / user | `UCSCIETRADE` / `UCSINC\ibeylin` |
| Database created | 2019-01-04 11:20:03 |
| Backup window | 2026-10-03 16:35:02 through 2026-10-03 16:35:03 |
| Backup set UUID | `051D8716-6176-4418-BA23-80FE4C22EEC2` |
| Compressed backup size | 97,984,718 bytes |

`RESTORE FILELISTONLY` logical files are `cieTrade_SM.mdf`, `cieTrade_SM_1.ndf` (full text), `cieTrade_SM_2.ldf`, and the full-text catalog. There is no second database in this media.

### September 3, 2025 media — `cieTrade_SM`, not the documents database

| Path | Bytes | SHA-256 |
|---|---:|---|
| `/Users/ib-mac/Dropbox/Odoo - Master Folder/Odoo/20250903cieTrade_SM.bak` | 88,404,480 | `b9b8b9cc62f9c57444ae1f9da8940d5ffe7c155f6a289cde2d00a8d6d4fe016d` |
| `/Users/ib-mac/Dropbox/Odoo - Master Folder/Odoo/Odoo Development Sprint/20250903cieTrade_SM.bak` | 88,404,480 | `65c50d4a3df208150370b5796405d77563fda0263b0457d27499766fbac40deb` |

The two files are not byte-identical. `RESTORE LABELONLY` on both returns the same media identity: MediaSetId `84B703A1-47FE-43DE-9A34-4E666594FA60`, MediaDate `2025-09-03 13:16:25`, Microsoft SQL Server, compressed. `RESTORE FILELISTONLY` on both lists the same logical files, with data file physical name `D:\DATA\cieTrade_SM.mdf`. `RESTORE HEADERONLY` on both terminates with message 3013 and does not return a header row. These files were not restored: the container filesystem had about 768 MB free and the data file alone is 476,250,112 bytes. File-list metadata is enough to show the database inside the media is `cieTrade_SM`.

## What the October 3 restore actually contains

Operator note received during this run: `cieTrade_SM_2026-10-03.bak` contains older transactions and nothing from September.

Measured on the restored `cieTrade_SM` (read-only aggregates):

| Column | Min | Max | Rows |
|---|---|---|---:|
| `BuySell.OrderDt` | 2019-01-05 | 2026-10-02 | 8,961 |
| `BuySell.InvoiceDt` | 2019-01-05 | 2026-10-02 | 8,961 |
| `BuySell.ShippingDt` | 2019-01-05 | 2026-10-19 | 8,961 |
| `GPLedger.TradeDt` | 2019-01-05 | 2026-10-02 | 8,353 |
| `PO.PODate` | 2019-01-05 | 2026-10-02 | 14,724 |
| `WksDocument.CreationDt` | 2019-01-17 | 2026-10-02 16:48:30 | 88,259 |
| `PODocument.CreationDt` | 2019-01-17 | 2026-10-02 16:42:58 | 13,041 |

Month counts inside that restore:

| Month | `BuySell.OrderDt` | `GPLedger.TradeDt` | `WksDocument.CreationDt` |
|---|---:|---:|---:|
| 2026-08 | 75 | 68 | 577 |
| 2026-09 | 59 | 60 | 417 |
| 2026-10 | 9 | 11 | 63 |

September 2026 worksheet, ledger, and document-registry rows are in this backup. The latest order, invoice, and trade dates are 2026-10-02, which matches a full backup taken 2026-10-03. `ShippingDt` values after the backup timestamp are dates stored on the worksheet, not a later backup. Activity after 2026-10-02 is outside this snapshot.

## Document bytes

| Object | Rows | Non-empty `Blob_Image` |
|---|---:|---:|
| `cieTrade_SM.dbo.DocumentImage` | 0 | 0 |
| `dbo.Docs` | 0 | — |
| `dbo.DocumentHeader` | 0 | — |
| `dbo.CRMAttachment` | 0 | 0 |
| `dbo.DocFingerPrint` | 0 | 0 |
| `dbo.DocSigns` | 0 | 0 |

`dbo.WksDocument` (88,259) and `dbo.PODocument` (13,041) have no binary column. `RefFile` is a numeric token on every row, not a filesystem path. `dbo.xDocHeader` (23,916), `dbo.xDocValue` (675,562), and `dbo.xDocMaster` (91) are form-field and template tables. `dbo.DocumentType` has 36 template rows. None of these is `cieTrade_Documents.dbo.DocumentImage`.

## Gate A result

FAIL. The authorized backups and the only restored SQL instance were inventoried. They expose `cieTrade_SM` only. `cieTrade_Documents.dbo.DocumentImage` is not queryable, and the same-named table inside `cieTrade_SM` has no rows and no blob bytes. No extraction, matching, or importer was run against a guessed corpus.
