# Import scope — SM-CIETRADE-DOCUMENT-RECOVERY-001

**Locked:** 2026-10-28  
**Objective:** Import every CieTrade worksheet image into the one `plasticos.transaction` whose `name` equals that image's complete worksheet `RefID`.

Odoo already owns the purchase orders and sales orders. This migration does not reimport those commercial documents. Every worksheet image is imported, including a file whose content looks like a purchase order or a sales order.

Source: live `UCSCIETRADE`, databases `cieTrade_Documents` and `cieTrade_SM`. Manifest ceiling ImageID 721202, 111,010 `CIETRADE_SM` images. No database backup. The file extract finishes before any Odoo load. This scope correction does not change the extractor that is already running.

The Mac copy of the expanded files lands in `/Users/ib-mac/Odoo-ERP-Files`. That folder was renamed from `Odoo-BAK-Files` on 2026-10-28 and still holds `cieTrade_SM_2026-10-03.bak`. The running extractor keeps writing to the server share.

On go-live day the ERP database is current as of that day. A new `cieTrade_SM` backup is placed in `/Users/ib-mac/Odoo-ERP-Files/` and that file is the restore input. `make import-erp` reads the database restored from it. The October 3 restore from `sql-backup-proof` stays the historical proof. The chain is `12_GO_LIVE_SOURCE_CHAIN.md`.

## Source selection

| `RefType` | Images | Disposition |
|---|---:|---|
| `W` | 97,328 | Eligible. Every image. |
| `#` | 18 | Eligible. Every image. |
| `P` | 13,077 | Outside Odoo. Originals stay in `/Users/ib-mac/Odoo-ERP-Files`. |
| `E` | 586 | Outside Odoo. Originals stay in `/Users/ib-mac/Odoo-ERP-Files`. |
| `B` | 1 | Outside Odoo. Originals stay in `/Users/ib-mac/Odoo-ERP-Files`. |

Eligible images: 97,346.

Filename, file extension, `DocName`, `DocType`, and any judgment that a worksheet file is generated purchase-order or sales-order content do not remove a `W` or `#` image from the eligible set.

## Exact association

`RefID` is the complete CieTrade worksheet number, including suffixes. The Odoo target is `plasticos.transaction` where `name` equals that `RefID`. Attach the file only when that name matches exactly one transaction.

One sales order may serve multiple worksheets. Each worksheet's documents stay on that worksheet's own transaction.

## Destination and integrity

Existing Enterprise Documents model and `plasticos_documents_native`. One original per `ImageID`, with source provenance and SHA-256 hashes. `transaction_id` is that unique transaction. `verified` stays false. No new verification writer. No association by partner, transaction recency, sales order, purchase order, or numeric similarity.

No accounting, stock, email, or transaction mutation.

## Disposition counts

Each eligible image has one disposition. Report these counts:

| Count | Meaning |
|---|---|
| eligible | Every `W` image and every `#` image. |
| unique Odoo match | Eligible, bytes intact, exactly one `plasticos.transaction.name`. |
| missing transaction | Eligible, bytes intact, no transaction with that name. |
| ambiguous transaction | Eligible, bytes intact, more than one transaction with that name. |
| integrity failure | Eligible image whose extracted bytes do not reconcile to the source hash or declared size. |
| successfully imported | Unique match written once, unverified, on that transaction. |
| import failure | Unique match whose write did not complete. |

`eligible = unique Odoo match + missing transaction + ambiguous transaction + integrity failure`

`unique Odoo match = successfully imported + import failure`

`P`, `E`, and `B` stay outside these counts. `proven redundant` and `unresolved classification` are not import gates.

## Test

First test on the disposable Odoo 19 Enterprise database that contains the actual imported worksheet transactions. A repeated import of the same `ImageID` creates zero additional originals.

No production or Staging database writes. No pull request, merge, or deployment. The importer is not implemented and is not run by this correction.
