# 05 — Extraction reconciliation

**Contract:** `SM-CIETRADE-DOCUMENT-RECOVERY-001`  
**Gate C:** NOT RUN

No pilot and no bulk extract ran. `cieTrade_Documents.dbo.DocumentImage` is not available, and `cieTrade_SM.dbo.DocumentImage` has 0 rows and 0 blob bytes. There is no original hash, decoded hash, or output file.

| Measure | Count |
|---|---:|
| Accessible `DocumentImage` rows in the local `cieTrade_SM` restore | 0 |
| Live `cieTrade_Documents` rows with `DBName = cieTrade_SM` (queried 2026-10-28 by the operator) | 111,004 |
| Reported blob size from `Blob_Size` | 39,561 MB |
| Rows with `DBName = cieTrade_SM` in `cieTrade_Documents` | not queryable |
| Distinct DocID / ImageID | 0 / column absent |
| RefType W / P / E | not observed |
| GZIP or other compression detected | 0 |
| Decoded files | 0 |
| Failed / corrupt / unsupported | 0 |
| Hash-identical duplicates | 0 |
| Worksheet-registry rows (`WksDocument`) | 88,259 metadata only |
| PO-registry rows (`PODocument`) | 13,041 metadata only |

Inclusion rule: a row counts as found only when `Blob_Image` bytes are read from `cieTrade_Documents.dbo.DocumentImage` (or a proven equivalent). Registry rows and XML templates are excluded. Under that rule, found = 0 = decoded + failed.

`03_DOCUMENT_INVENTORY.csv` and `04_ODOO_CROSSWALK.csv` contain headers and no data rows.
