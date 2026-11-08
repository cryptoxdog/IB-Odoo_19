# 02 — Schema and join proofs

**Contract:** `SM-erp-DOCUMENT-RECOVERY-001`  
**Observation time:** 2026-10-28T19:33:11Z  
**Gate B:** FAIL

## PaperSolve shape (ticket #78996, 2026-10-08)

Mike Russo described blob images in `erp_Documents.dbo.DocumentImage`, filtered by `DBName = 'erp_SM'`, with columns `ImageID`, `DocID`, `DBName`, `RefID`, `RefType`, `DocName`, `DocType`, `CreatedDT`, `Blob_Image`, `Blob_Size`. Example `RefType` values were `W`, `P`, and `E`. Some blobs were said to start `0x1F8B08`. That database is not on this machine, so those types were not verified here.

## Actual `erp_SM.dbo.DocumentImage`

Observed on the 2026-10-03 restore. No foreign keys. Primary key `PK_DocumentImage (DocID)`. Nonunique index `IE1_DocumentImage (RefID)`.

| Column | Type | Nullable |
|---|---|---|
| DocID | int | no |
| RefID | varchar(255) | yes |
| RefType | char(1) | no |
| DocName | varchar(50) | yes |
| DocType | varchar(50) | yes |
| Blob_Image | image | yes |
| Blob_Size | float | yes |
| CreatedDT | datetime | no |
| CreatedBy | varchar(150) | yes |
| ModifiedDT | datetime | yes |
| ModifiedBy | char(10) | yes |
| Desc1 | varchar(255) | yes |
| FileExt | char(4) | yes |
| IncludeOnReport | bit | yes |
| IsCompressed | bit | yes |
| IsConfirmed | bit | yes |
| ciePhoto | bit | yes |
| sessionID | varchar(100) | yes |
| ciePhotoTareWt | varchar(25) | yes |
| WebPublish | bit | yes |

This table has no `ImageID` and no `DBName`. A column search of `dbo` found `ImageID` only on `EKMAN_AddInImage` and `DBName` only on `MobileAppUsers`. Row count is 0, so `RefType` cannot be counted and no join to `BuySell`, `PO`, or `WksDocument` can be proven or falsified from data.

## Registry tables that are not file bytes

`WksDocument` columns used for identity: `DocumentID`, `DocType`, `BuySellNo`, `CreationDt`, `RefFile`.  
88,259 rows, 8,606 distinct `BuySellNo`, 88,259 distinct `RefFile`, every `RefFile` numeric, no empty `BuySellNo`. `DocType` is `G` on 88,241 rows and `#` on 18 rows. `RefFile` does not contain a path, slash, or extension.

`PODocument` columns used for identity: `PODocID`, `DocType`, `PONumber`, `CreationDt`, `RefFile`.  
13,041 rows, 10,472 distinct `PONumber`, 13,041 distinct numeric `RefFile` values.

`xDocHeader.SourceID` / `xDocValue.FieldValue` are generated form data. They were not treated as scanned originals and were not joined to Odoo.

## Join proof

No `RefType` cohort exists in the accessible `DocumentImage`. There is no source witness that `RefID` equals `BuySellNo`, an internal worksheet key, or a PO number. `WksDocument.BuySellNo` proves only that the worksheet registry points at worksheets. It does not prove that a missing blob’s `RefID` is that number. Numeric `RefFile` values are unique inside each registry table; whether they equal `DocID` or `ImageID` in `erp_Documents` is unproven and is asked in the PaperSolve request.

**Gate B result:** FAIL. No deterministic source-to-business-record join for a document image. No Odoo link was assigned.
