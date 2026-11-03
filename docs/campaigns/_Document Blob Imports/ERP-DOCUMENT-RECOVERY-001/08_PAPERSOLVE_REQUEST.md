# PaperSolve request — not sent

**Current reading (2026-10-28):** This request was not sent. It stays here as history. The operator directed the recovery to use the live `erp_Documents` database and not to take a backup. The locked import scope is `11_IMPORT_SCOPE.md`.

**Contract:** `SM-erp-DOCUMENT-RECOVERY-001`  
**Status:** Ready for the operator to send. This file was not emailed.

**To:** PaperSolve, ticket #78996 (Mike Russo, 2026-10-08)  
**From:** Scrap Management / PlasticOS recovery

Please provide a SQL Server backup of database **`erp_Documents`** that includes `dbo.DocumentImage` rows with `DBName = 'erp_SM'`.

Please take that backup at the same recovery point as our `erp_SM` full backup:

- Backup name: `erp_SM-Full Database Backup`
- Server: `UCSerp`
- Backup window: **2026-10-03 16:35:02 through 2026-10-03 16:35:03**
- Backup set: `051D8716-6176-4418-BA23-80FE4C22EEC2`

Our copy of that `erp_SM` backup restores worksheet, PO, and ledger activity through **2026-10-02**, including September 2026. It does **not** contain the document bytes. `erp_SM.dbo.DocumentImage` exists and has **0 rows**. Its shape is not the one in ticket #78996: it has no `ImageID` and no `DBName`.

If a same-minute backup of `erp_Documents` is no longer available, send the nearest full backup of `erp_Documents` and state its backup start time so we can mark the recovery-point gap.

Also send, or confirm in writing:

1. The `CREATE TABLE` definition of `erp_Documents.dbo.DocumentImage` and of every parent metadata table that owns `DocID` or `ImageID`.
2. The meaning of `RefType` values **`W`**, **`P`**, and **`E`**, and any other `RefType` values present for `DBName = 'erp_SM'`.
3. The join from `RefID` to the source business key. We need to know whether `RefID` is `BuySellNo`, an internal worksheet primary key, `PONumber`, or another key. Please include one example row for each `RefType` showing `ImageID`, `DocID`, `RefID`, `RefType`, and the parent key it matches. Do not send the blob in that example if a key-only row is enough; we do need the blobs in the backup itself.
4. Whether several `ImageID` rows with one `DocID` are pages of one document, and which column orders those pages.
5. Whether `Blob_Image` is raw file bytes or GZIP (we were told some values start `0x1F8B08`), and how `IsCompressed` on the empty `erp_SM` table relates, if it relates at all.
6. How `erp_SM.dbo.WksDocument.RefFile` and `erp_SM.dbo.PODocument.RefFile` relate to `DocID` or `ImageID`. In our restore every `RefFile` is a distinct integer (88,259 worksheet-registry rows and 13,041 PO-registry rows) and none of them is a file path.

A read-only restored database, or a native SQL backup, is acceptable. A CSV or grid export is acceptable only if `Blob_Image` is the full VARBINARY value, not a truncated hex preview, and every reference column above is included.

We will not guess worksheet or PO links from names, dates, or amounts.
