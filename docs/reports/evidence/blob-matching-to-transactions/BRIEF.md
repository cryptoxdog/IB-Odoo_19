# Brief: worksheet blobs matched to transactions

Read-only. No blob was imported. No transaction was created or renamed. Nothing was written to Staging or Production.

A blob attaches only when its full worksheet RefID equals `plasticos.transaction.name`. Suffixes stay. Partner, date, sale order, purchase order, and a shortened number are not matches.

## Eligible blobs

Eligible means RefType `W` or `#`, extract status `ok`, decoded size equal to the stored blob size, and both SHA-256 values present. Filename, extension, document name, and document type do not drop a `W` or `#` blob.

| Population | Images | Disposition |
|---|---:|---|
| `W` | 97,328 | Eligible |
| `#` | 18 | Eligible |
| Eligible total | 97,346 | Match by worksheet name |
| `P` | 13,077 | Outside Odoo |
| `E` | 586 | Outside Odoo |
| `B` | 1 | Outside Odoo |

One eligible blob failed extraction and is not in the match set: ImageID `633316`, DocID `166136`, RefID `56993`, RefType `W`, extension `pdf`, blob size 76,432, decoded size 0, status `not_gzip`. Worksheet `56993` has four other intact blobs. Those four sit in the purchase-only unmatched group.

## Database

The baseline is `odoo_test_night1021`. Rechecked 2026-11-04: 7,728 transactions, 7,728 distinct names.

| State | Transactions |
|---|---:|
| closed | 6,869 |
| cancelled | 771 |
| active | 88 |

Seven names contain a hyphen. Each is a full worksheet id: `51687-JCH`, `57328-INV`, `57430-INV`, `58075-INV`, `58239-INV`, `58425-INV`, `58427-INV`.

`odoo_test_erpvs1021` is not the baseline. It has 3,396 transactions. On that database 44,895 images matched and 52,450 did not (5,467 worksheets). The miss was the missing transactions. A cancelled worksheet still matches when a row with that name exists.

## Match on night1021

The image counts are the join from the extract journal. That journal is no longer in `docs/campaigns/_Document Blob Imports/SQL 10-28-26/extract/`, so the image counts were not recomputed on 2026-11-04. The transaction count was.

| | Images | Worksheets |
|---|---:|---:|
| Eligible | 97,346 | 8,836 intact RefIDs |
| Exact name match | 91,442 | 7,641 |
| No transaction | 5,903 | 1,195 |
| Ambiguous name | 0 | 0 |
| Integrity failure | 1 | RefID `56993` |

`W`: 91,425 matched, 5,902 unmatched, 1 integrity failure. `#`: 17 matched, 1 unmatched.

Eligibility closes: 97,346 = 91,442 + 5,903 + 0 + 1. Successfully imported and import failure are both 0, because nothing was written.

Of the 5,467 worksheets missing on the smaller database, 4,272 now match (46,547 images) and 1,195 still do not (5,903 images).

Matched worksheets by transaction state in that join: closed 6,864 (88,541 images), cancelled 694 (2,386 images), active 83 (515 images).

## The 1,195 worksheets with no transaction

The four groups are disjoint. They sum to 1,195 worksheets and 5,903 images.

| Cause | Worksheets | Images |
|---|---:|---:|
| Purchase documents realized, no sale, no transaction | 450 | 2,980 |
| ValueError rollback | 86 | 1,108 |
| No sale link and no purchase link | 62 | 270 |
| RefID is outside the 8,373 indexed worksheets | 597 | 1,545 |

The import census (`.l9/pr/erp-commercial-summary-census.json`, finished 2026-10-22T06:23:14Z, `final_status` `partial`) still supports the worksheet sets those groups were cut from:

- 469 purchase-only anomaly keys, 4 of which also rolled back, so 465 net. 450 of those have an eligible blob. The 2,980 images are 2,979 `W` and 1 `#`.
- `worksheets_rejected` is 88, all ValueError keys. 86 have an eligible blob.
- 561 worksheets have no sale link. Minus the 469 purchase-only keys, 92 have neither a sale nor a purchase link. 62 have an eligible blob.
- 597 RefIDs were never in the indexed worksheet walk. 506 of them were named in a payable anomaly as a BuySellNo with no worksheet lines.

The nightly import realized 7,728 of 8,373 indexed worksheets, rejected 645, and skipped 0. 88 + 465 + 92 = 645. The database still holds exactly those 7,728 names. `records_seen` was 32,332 and duplicates were 0.

## Left undone

The 91,442 matches are not in Odoo. The 5,903 unmatched blobs stay in the archive. ImageID `633316` was not recovered. No blob was attached to a purchase order.
