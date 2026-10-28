# Manifest reconciliation

**File:** `docs/campaigns/Document Blobs/SQL 10-28-26/3.rpt`  
**Query completion:** 2026-10-28T16:23:04.5116003-04:00  
**Server:** live `UCSCIETRADE`, `cieTrade_Documents.dbo.DocumentImage`, `DBName` trimmed to `CIETRADE_SM`  
**Backup:** none

The file is UTF-8 with BOM, fixed-width SSMS output, 111,015 lines. It is gitignored. Do not commit it.

## Counts

| Check | Result |
|---|---:|
| Data rows | 111,010 |
| Distinct `ImageID` | 111,010 |
| Distinct `DocID` | 111,010 |
| `ImageID` order | strictly increasing, 451699 through 721202 |
| `W` | 97,328 |
| `P` | 13,077 |
| `#` | 18 |
| `E` | 586 |
| `B` | 1 |
| `disposition` mismatches against `RefType` | 0 |
| `IsCompressed = 1` | 111,010 |
| `IsCompressed = 0` | 0 |
| Blank `RefID` | 0 |
| Rows with `DocName` | 18, all `RefType` `#`, name `Container`, type `Container-Photo` |
| Non-numeric `W` `RefID` | 1,811 |
| Non-numeric `P` `RefID` | 11 |
| `Blob_Size` sum | 41,485,898,661 bytes (39,564.036 MB) |
| Oldest `CreatedDT` | 2019-01-05 11:07:12.000 |
| Newest `CreatedDT` | 2026-10-28 16:13:56.000 |

`disposition` is the `RefType` label from the export. It is not a new worksheet or PO join. `linked_worksheet` is 97,346 because it includes 97,328 `W` plus 18 `#`. `unassigned` is 587 because it includes 586 `E` plus 1 `B`.

The ten pilot rows match `ImageID`, `DocID`, `RefID`, `RefType`, and `Blob_Size`.

## Rows created after the 16:06 census

`CreatedDT` after 2026-10-28 16:04:20.050. All five are `W`. Rechecked at 2026-10-28T16:27:44-04:00: each `buysell_hit` is 1 on an exact trimmed `BuySellNo`. Four images are worksheet 60859. One image is worksheet 60787.

| ImageID | DocID | RefID | FileExt | Blob_Size | CreatedDT | CreatedBy |
|---:|---:|---|---|---:|---|---|
| 721198 | 206292 | 60859 | pdf | 1,029,024 | 2026-10-28 16:11:34.023 | jm |
| 721199 | 206293 | 60859 | jpg | 563,383 | 2026-10-28 16:11:49.087 | jm |
| 721200 | 206294 | 60859 | jpg | 638,342 | 2026-10-28 16:11:49.133 | jm |
| 721201 | 206295 | 60859 | jpg | 599,156 | 2026-10-28 16:11:49.180 | jm |
| 721202 | 206296 | 60787 | pdf | 7,763 | 2026-10-28 16:13:56.000 | RT |

## FileExt stored as-is

Extensions are not normalized. Leading-dot and letter-case variants are different stored values. Every row is compressed. One stored extension is not a file type: ImageID 520621, DocID 112632, RefID 53049, `W`, FileExt `1353`, Blob_Size 16478, CreatedDT 2020-07-22 10:31:41.

| FileExt | Rows |
|---|---:|
| pdf | 63,894 |
| .msg | 18,462 |
| jpg | 13,076 |
| JPG | 5,826 |
| PDF | 3,015 |
| jpeg | 2,808 |
| xlsx | 660 |
| png | 619 |
| doc | 519 |
| xls | 439 |
| docx | 409 |
| JPEG | 380 |
| eml | 293 |
| heic | 183 |
| msg | 139 |
| PNG | 136 |
| htm | 33 |
| html | 19 |
| HEIC | 17 |
| tif | 14 |
| mov | 14 |
| rtf | 12 |
| MOV | 8 |
| txt | 8 |
| mp4 | 6 |
| TIF | 4 |
| JPE | 4 |
| bmp | 3 |
| gif | 3 |
| m4a | 3 |
| xlsm | 1 |
| pptx | 1 |
| 1353 | 1 |
| tiff | 1 |
