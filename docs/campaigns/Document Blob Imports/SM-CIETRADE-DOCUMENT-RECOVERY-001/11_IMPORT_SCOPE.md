# Import scope — SM-CIETRADE-DOCUMENT-RECOVERY-001

**Revised:** 2026-10-28  
**Objective:** Import original historical evidence attached to CieTrade worksheets into the corresponding `plasticos.transaction` records.

Odoo already owns the commercial purchase orders and sales orders. This migration does not reimport those generated documents.

Source: live `UCSCIETRADE`, `cieTrade_Documents` and `cieTrade_SM`, manifest ceiling ImageID 721202, 111,010 `CIETRADE_SM` images. No database backup. Extraction completes before any Odoo load.

## Source selection

| `RefType` | Images | Odoo import |
|---|---:|---|
| `W` | 97,328 | Eligible. Worksheet evidence. |
| `#` | 18 | Eligible. Container photos on a worksheet. |
| `P` | 13,077 | Excluded from Odoo import. |
| `E` | 586 | Leave unattached. |
| `B` | 1 | Leave unattached. |

Eligible images: 97,346. The private archive keeps every extracted original and its source metadata, including excluded files.

## Exact association

`RefID` is the complete CieTrade worksheet number, including suffixes. Match it to `plasticos.transaction.name` by exact source identity. Attach only when exactly one transaction has that name.

One sales order may serve multiple worksheets. Each worksheet's documents stay on that worksheet's own `plasticos.transaction`.

## Document selection

Import original worksheet evidence: scale tickets, proof of delivery, bills of lading, packing lists, loading photographs, signed documents, certificates, relevant correspondence, and other actual worksheet attachments.

A generated purchase-order or sales-order PDF is skipped only when its equivalence to the Odoo commercial document is positively established. A `.pdf` extension, or empty `DocName` / `DocType`, does not establish that. Uncertain originals stay eligible. A later classification pass reports those rows separately.

## Destination and integrity

Existing Enterprise Documents model and `plasticos_documents_native`. One original per `ImageID`, with source provenance and SHA-256 hashes. `transaction_id` is the unique matched transaction. `verified` stays false. No new verification writer. No partner recency auto-link.

No accounting, stock, email, or transaction mutation.

## Crosswalk counts required before import

eligible, unique transaction match, missing transaction, ambiguous transaction, proven redundant, unresolved classification.

Proven redundant is zero until a positive equivalence exists.

## Test

Disposable Odoo 19 Enterprise database that contains the actual imported worksheet transactions. A repeated import of the same `ImageID` creates zero additional originals.

No production or Staging database writes. No pull request, merge, or deployment.
