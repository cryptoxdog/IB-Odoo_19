# 02 | Identity, native Documents ownership, reconciliation and replay contract

## Owner/source map

| Meaning | Authoritative owner | Not an owner |
|---|---|---|
| ERP original bytes | Existing SQL Server `erp_Documents` extract; source `ImageID` + SHA-256 | Odoo PostgreSQL; AI OCR output |
| Worksheet commercial identity | `plasticos.transaction.name` from actual Odoo target | `res.partner`, `sale.order`, `purchase.order`, shortened number |
| Original document storage | Odoo 19 Enterprise `documents.document` + `ir.attachment` + filestore, extended by `plasticos_documents_native` | New PostgreSQL DB, new S3 document backend, legacy parallel original table |
| Business verification/manager override | `plasticos_documents` (native bridge projects its decisions) | Image migration / source extractor |
| Provider backup/restore | Native Odoo.sh DB + filestore backup | A SQL-only dump or files-only folder |
| Long-term independent DR | Existing `SM-ODOO-DR-CAMPAIGN-001` | This runbook; raw Git ZIP |

## Locked input and output

Source journal columns (existing `EXTRACT_BLOBS.ps1`): `ImageID,DocID,RefID,RefType,FileExt,BlobSize,CreatedDT,RawBytes,RawSha256,DecodedBytes,DecodedSha256,Status,ImportScope`. The manifest does not contain the raw original bytes. The bytes are in private `decoded/<ImageID>.<safe-source-extension>`.

**Input eligibility:** `RefType == W OR #` for all extracted images, including corrupt ones as named **integrity exceptions**. `P/E/B` are excluded and privately archived. Do not drop images on file extension/name/content classification.

**Source integrity before target matching:** `Status == ok`, both source hash strings present, `DecodedBytes == BlobSize`, and when actual files are accessible, `sha256(decoded bytes) == DecodedSha256` and file bytes equal that length. Corrupt bytes have no target write even if a transaction happens to match. An undecodable image still contributes to **eligible** and **integrity failure** counts, not silently absent.

**Exact target:** each intact eligible `RefID` matches **one** `plasticos.transaction.name` across the intended authorized company census. Suffixes and case remain unchanged. A worksheet can have many `ImageID`s; each image must have one original attached to that worksheet. Two same-name targets are **ambiguous**. No orphan native document gets auto-assigned by partner recency.

**Durable idempotency key:** `(source_database='erp_SM', ImageID)` within the source corpus. Validate that an existing native original with that source key has the same bytes and exact target/company; a changed digest or target is a hard conflict. Do not identify originals solely by filename, SHA-256 (two distinct ImageIDs may share bytes), `DocID`, or model record ID. The implementation must persist a concurrency-safe uniqueness constraint at the existing appropriate owner and provide an inspectable Odoo lineage link, not an in-memory seen-set.

**One accepted original:** native `documents.document` with a real `ir.attachment`; source `ImageID`, `DocID`, full `RefID`, source/decoded digests and company; link to exact transaction; `verified` starts false and no manager override. Creation/sync may use the existing native-to-business Documents bridge, but must not call verification/AI or trigger workflow automation. No historical SO/PO/invoice/stock/mail mutation.

## Required cohort accounting

Set counts by exact frozen source epoch, NOT from the historical test snapshot. Partition and reconcile:

```text
eligible = unique_match + missing_transaction + ambiguous_transaction + integrity_failure
unique_match = successfully_imported + import_failure + not_attempted
```

For a **fully completed approved import**, `not_attempted == 0`. `import_failure` must be remediated or explicitly blocked; do not report full PASS while positive matches are unwritten. Missing transaction and corrupt originals may legitimately remain in archive with named dispositions and business owner. They must never become hidden “skipped” or fabricated transactions.

The last historical source read (Nov 4) was **not Production**, yielded 97,346 eligible, 91,442 exact, 5,903 missing, 0 ambiguous, 1 corrupt; 0 imported. These are **comparison reference only**. The old journal bytes were not present in the published repo evidence at that date.

## Local read-only crosswalk tool

```sh
python3 tools/reconcile_cohort.py \
  --journal '<PRIVATE_SOURCE>/journal.csv' \
  --transactions '<PRIVATE_EVIDENCE>/transactions.csv' \
  --decoded-dir '<PRIVATE_SOURCE>/decoded' \
  --raw-dir '<PRIVATE_SOURCE>/raw' \
  --output '<PRIVATE_EVIDENCE>/preflight.json'
```

Optional post-apply `--imports '<PRIVATE_EVIDENCE>/import_results.csv'`. **No script-invented credentials and no Production connection.** Transaction export header `id,name,company_id` must contain every authorized target row, including conflicting same-name records. Import result header is `ImageID,odoo_document_id,odoo_transaction_id,status,decoded_sha256,reason`, with `status` `imported` or `failed`. Other fields can exist and the agent should bind a hosted ORM receipt to the private file. An approved interpreter may adapt private operational exports into this schema, but must never fabricate rows or copy large source bytes into Git.

The script reports structural counts, rows with problems, first ten exception identities, input SHA-256 and whether source binary verification was done. **It cannot authenticate that the supplied CSV is the complete Production census, or that the exported import ledger is truthful.** Confirm those in separate live readback receipts.

## Acceptance/negative evidence

- Two original files to one worksheet: two native originals attached to the same exact transaction, no duplicate transaction or SO/PO.
- Source `RefID` with `-INV` or `-JCH` stays exact, not truncated or numerically parsed.
- Same ImageID twice in journal: fail closed; second importer run: no new original; concurrent same-key attempt: one winner/one reuse or conflict, never two originals.
- Same byte SHA from different ImageIDs: do not collapse independent source image identity, though physical binary dedup by the native filestore is allowed.
- Missing, ambiguous, wrong-company target: no attachment, no `sudo` ACL bypass; private quarantine reason.
- Non-gzip ImageID **633316**, missing/raw mismatch/empty bytes: no write and specific integrity ledger entry.
- `P/E/B`: never automatically attached to worksheet even if a numeric ID happens to match.
- Native `documents.document` download works; native sync is idempotent; imported documents remain unverified; no AI/manager override writes.
- No `mail.mail`, account posting, purchase/sales order, commission, stock, transaction state, or outbound webhook mutation under any test.

## Crash/resume contract

Persist one write receipt per `(source, ImageID)` after the native original + association are durably established. At chunk retry, look up existing key and verify original SHA/target. Do not reuse a half-created unrelated attachment, omit a failed row or report an image as imported before its native document and filestore bytes are readable. Batches must have explicit preview and bounded size; resume must not require a full re-import of ERP commercial records. An error has a row-level disposition; cancellation leaves an inspectable checkpoint.

For the **frozen October 28 cohort only**, additional CLI assertions may be supplied: `--expect-source-count 111010 --expect-eligible-count 97346`; do not use these historic assertions when the authorized source epoch is newer. After actual application, add `--require-complete-import --imports <private-receipt.csv>` alongside `--decoded-dir --raw-dir` and the independently accepted current manifest counts. The script still attests only **operator-exported data**, not a hosted Odoo transaction.
