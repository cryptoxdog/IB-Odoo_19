```yaml
repository_access:
  writable:
    - https://github.com/cryptoxdog/IB-Odoo_19
  read_only: []
  unlisted_repositories: no_access
```

# CURSOR RUNBOOK | Recover CieTrade Documents and Match Them to Odoo

**Contract:** `SM-CIETRADE-DOCUMENT-RECOVERY-001`  
**Mode:** Bounded forensic recovery -> proven association -> local implementation -> disposable Odoo Enterprise test.  
**Working target:** `cryptoxdog/IB-Odoo_19`, integration branch `Staging`. A source inspection on 2026-10-28 observed `Staging@04bd0594a7c9dcad53d9c45fc65276d76817c112`; resolve and record the **actual** HEAD at run start.  
**Operator intent:** Recover the original documents from CieTrade and import worksheet evidence onto the matching `plasticos.transaction`.

**Effective import scope (2026-10-28):** section 8 below supersedes any earlier instruction to import `RefType = P` purchase-order files, to reimport purchase orders or sales orders, or to attach a document by partner, recency, sales order, or purchase order. Worksheet `RefID` matched to `plasticos.transaction.name` is the association.

## Start here: autonomous execution instruction

Act as the executing forensic/data-migration engineer in Cursor. **Do the work, not just a plan.** Inspect the existing local backup first. Continue through discovery, source joins, safe file extraction, deterministic Odoo target resolution, code implementation and tests whenever each evidence gate passes. Do not pause to ask ordinary implementation questions; record uncertain mappings and quarantine affected items. If a material source, architectural or authority gate fails, stop only the affected stage and produce the exact blocker and PaperSolve request, while preserving completed evidence. Do not wander into Export, Logistics, CRM, Inventory, accounting remediation or unrelated PRs.

The repository access header permits **local, in-scope code edits only**. It does not authorize GitHub publication or production changes. Work in a clean isolated branch/worktree based on the exact verified `Staging` state; protect unrelated user changes. **No push, PR, merge, `/gmp`, deployment or writes to production/Staging databases** without additional explicit operator authority. If publication is later authorized, use the verified canonical `make pr` publication path, never raw `git push`.

### Evidence already established

On **2026-10-08**, Mike Russo of PaperSolve wrote in ticket **#78996** that documents are **blob images in `cieTrade_Documents.dbo.DocumentImage`**, filtered by **`DBName = 'cieTrade_SM'`**. The screenshot shows:

- `ImageID`, `DocID`, `DBName`, `RefID`, `RefType`, `DocName`, `DocType`, `CreatedDT`, `Blob_Image`, `Blob_Size`.
- Example `RefType` values `W`, `P`, `E`. **These are unresolved meanings.**
- Some `Blob_Image` values start `0x1F8B08`, a GZIP signature; **verify actual encoding and recovered file format**.

PaperSolve email: https://mail.google.com/mail/u/?authuser=ib%40scrapmanagement.com#all/1a11cc79ea593108

**Crucial:** `cieTrade_Documents` is a distinct SQL Server database from `cieTrade_SM`. The `.bak` for `cieTrade_SM` may not include it. Never infer that the data is missing merely because the first backup lacks the table.

## 0. Bind local authority and source state

1. Record repo remote, current `Staging` SHA, local branch, uncommitted changes, applicable `AGENTS.md`, Cursor rules and effective Odoo invariants; do not modify invariants or architectural contracts.
2. Read these **actual existing owners**, then inspect their nearest callers, tests and schemas:
   - `docs/adr/ADR-021-erp-sql-crm-api-import.md`
   - `plasticos_partner_import/erp/reader.py`, `source_index.py`, `header_forensics.py`, `native_orders.py`
   - Current native historical import implementation under `plasticos_partner_import/models/`, and its tests; discover the actual files rather than assuming filenames.
   - `plasticos_documents/business_rules/OWNERSHIP_AND_INTEROP.md`
   - `plasticos_documents_native/models/document_native.py`, `document_sync.py`
   - Current installed Enterprise `documents.document` and `ir.attachment` API/ACL behavior where available.
3. Keep **inspection scope** broad enough for exact dependency proof, but **code modification scope** limited to the smallest necessary ERP-import / Documents integration code and its tests. No new import service, model, field or runtime dependency unless a proved representation gap is separately approved.
4. Record the actual SQL tooling, available database access, local permissions and isolated test capability. Do not infer runtime readiness from repository code alone.

## 1. Discover available SQL backups and databases [GATE A]

Search **only operator-authorized** local directories, mounted volumes and accessible SQL instances for relevant `.bak`, `.mdf`, `.ndf` and restored databases. Do not read unrelated private datasets.

For each candidate, record:

- Absolute path or server/database coordinate, source and observation time.
- File size, modification time and SHA-256 of the backup file where feasible.
- SQL Server backup-set metadata (including database name and position), not just the filename.
- Whether the accessible source includes database **`cieTrade_Documents`** and table **`dbo.DocumentImage`**.
- Backup timing relative to the `cieTrade_SM` transaction snapshot; mismatched recovery points must be explicit.

Use SQL Server's supported metadata inspection (such as `RESTORE HEADERONLY` and `RESTORE FILELISTONLY`) **only after verifying the tool/environment**. Any restore must target a **disposable isolated SQL Server instance**, explicit new DB name and separate file paths. Never use `WITH REPLACE` against existing business databases. Never mutate the original backup.

**Gate A PASS:** A complete, queryable `cieTrade_Documents.dbo.DocumentImage` source for the target company is established with provenance. Continue.

**Gate A PARTIAL:** Some document source exists. Continue extracting what is safe, but mark missing scope/recovery-point mismatch.

**Gate A FAIL:** The authorized backups and restored databases have been inventoried and do not contain or expose that database. Produce `PAPERSOLVE_REQUEST.md` for a backup of **`cieTrade_Documents`**, ideally at the same recovery point as `cieTrade_SM`, plus needed schema and reference mappings. Do not fabricate data or build a speculative importer against an unavailable corpus.

## 2. Inventory source table and discover the true relationships [GATE B]

Use parameterized, read-only SQL. Start with source table and schema metadata; avoid selecting or logging raw `Blob_Image` except for bounded extraction. Inspect all relevant parent tables, foreign keys, indexes, row counts, uniqueness constraints and document metadata tables.

A **reference inventory** may use this known table shape (verify against actual schema before running):

```sql
SELECT RefType,
       COUNT_BIG(*) AS image_rows,
       COUNT(DISTINCT DocID) AS distinct_doc_ids,
       COUNT(DISTINCT RefID) AS distinct_ref_ids
FROM cieTrade_Documents.dbo.DocumentImage
WHERE DBName = N'cieTrade_SM'
GROUP BY RefType
ORDER BY RefType;
```

Verify the semantics of **each** `RefType` from actual source joins, especially:

- `W`: possibly worksheet. **Do not assume `RefID = BuySellNo`.** It could reference an internal worksheet PK or another join.
- `P`: possibly purchase order. Identify the authoritative PO source key and its relationship to worksheet(s).
- `E`: unknown. Investigate or quarantine; never classify by guess.

`WKSDetail` has worksheet line identifiers `DetailID` and `BuySellNo`; `BuySellNo` is the source transaction/worksheet universe in the existing `SourceIndex`. This does **not** itself establish that `DocumentImage.RefID` equals `BuySellNo`.

For every observed reference type, write a **join proof**: actual SQL query or source FK; raw key value; unique parent candidate; candidate cardinality; contradiction/negative cases; relationship to original worksheet and any native order. Deliberately test collisions where two `RefType` values share the same numeric `RefID`.

**Gate B PASS:** At least one concrete, deterministic source-to-business-record join is proven for a bounded cohort. Continue with that cohort. Other types may remain quarantined.

**Gate B FAIL:** No exact join can be proven. Extract recovered files with immutable source IDs, mark all business assignments unresolved, and request specific PaperSolve data dictionary/joins. **Do not guess Odoo links.**

## 3. Recover and verify source file bytes [GATE C]

Perform a representative private pilot before bulk export: at least **10 known documents**, including available `W/P/E` rows, multiple documents per reference, a potential multi-image `DocID`, and varied blob sizes. If a class does not exist, mark not applicable rather than inventing samples.

For each `ImageID`/`DocID`:

1. Preserve original DB name, reference type/key, document ID, image ID, timestamp, filename/type metadata and source query identity.
2. Read full binary bytes with length checking. Preserve a raw copy or its verified recoverable representation, and a **SHA-256 of exact original blob bytes**.
3. Detect compression by bytes, not extension. If GZIP, decompress defensively with bounded output/memory and corruption handling. Inspect recovered file signature/MIME; do not rename all files `.pdf` or assume one blob = one complete PDF.
4. Preserve decoded bytes and their SHA-256. Distinguish original compressed bytes from decoded original document content.
5. Determine if multiple image rows form one document. Verify ordering/grouping through source fields or other authoritative evidence. **Never merge/reorder pages by speculation**; retain individual originals even when a derivative multipage PDF is justified.
6. Keep filenames unique using stable source identity (DB + `DocID` + `ImageID`); sanitize paths to block traversal and special-name collisions.
7. Record success, failure, partial, duplicate (hash-identical) and corrupt conditions without dropping records.

Only after the pilot passes, run **bulk read-only extraction** into an encrypted or access-restricted directory **outside the Git worktree**. Check free space and protect against decompression bombs. Store raw files, decoded originals, manifests and logs outside Git. Do not upload binaries, emails, personal data, source `.bak`, snapshots, or private inventories to GitHub, CI artifacts or remote AI services.

**Gate C PASS:** For the cohort, exact source IDs and decoded bytes/hashes reconcile. Expand safely to full available eligible corpus.

## 4. Prove exact Odoo destinations [GATE D]

Read ADR-021 and the current deterministic **`reader -> SourceIndex -> mapping/reconstruction -> ORM upsert`** path. Follow how existing imported ERP source keys (`BuySellNo`, `DetailID`, source PO references) map into native `sale.order`, `purchase.order`, and the `plasticos.transaction` created by the approved native sales hook. Inspect actual persisted source mappings/external IDs and existing database state; do not infer from `display_name`.

Produce a crosswalk for every recoverable document:

`source_database + company + RefType + RefID + DocID + ImageID -> proven source parent -> source BuySellNo/order key (if applicable) -> existing Odoo model + record ID + company -> association evidence`.

Rules:

- One worksheet may have many documents; one purchase order may cover more than one worksheet. Do not force one-to-one or create artificial links.
- `RefType=P` may legitimately attach first to a native `purchase.order`; link to a transaction only when the exact linkage is proven.
- `RefType=E` or any unresolved reference remains unassigned; preserve file and metadata in a quarantine manifest rather than linking by partner/date/amount/name.
- An ERP worksheet may not have imported into Odoo; record `target_missing` and retain the document for future replay.
- Never create a dummy buyer, transaction, SO, PO, picking or load to satisfy an attachment association.
- One original may support multiple **proven** typed evidence relationships with a single underlying binary. Do not duplicate original bytes for each association.
- Respect Odoo company and record access boundaries. A document from one company must never attach to another.

**Gate D PASS:** A representative set has unique exact source-to-Odoo proof. Continue only for proven matches. Unresolved rows do not pass.

## 5. Implement the minimum replay-safe importer [GATE E]

**Only after Gates A-C and a bounded Gate D PASS.** Implement in the existing ERP import/Document integration ownership surfaces; do not introduce a second direct-SQL importer or a separate document file store. Preserve ADR-021 and Documents BRS ownership.

Required behavior:

1. A staged read/extraction source driven by the verified SQL table and source identity; the existing ERP pipeline remains authoritative for commercial record identity. Do not use CSV wizard or frozen regression grids as live source.
2. **Default `DRY_RUN`**: read-only report of candidate source documents, decoded/failed count, proven target matches, duplicates, mismatches and planned creates/links. No writes or emails.
3. Native **Odoo Enterprise Documents originals** (`documents.document` using `ir.attachment`), retaining exact source provenance and a collision-resistant replay key derived from source DB/company/`DocID`/`ImageID` and the verified document grouping policy. If the existing identity system is sufficient, reuse it; otherwise prove the gap and seek approval before adding schema.
4. Reuse existing approved typed evidence associations in `plasticos_documents`, preserving one authoritative original and exact association(s). Do not use partner-recent auto-link helper, fuzzy matching, generic newest-open-transaction matching, or independent verification writes.
5. All recovered historical files start **unverified**. Do not let attachment creation change READY, weights, compliance, stock, order status, PO approval, invoice posting, payment, or accounting reconciliation.
6. Replay must be **idempotent**: same source key/content yields no duplicate originals or evidence links; changed source content requires explicit version/conflict handling, never silent overwrite.
7. Per-item failures quarantine with typed reasons. For a known match never reassign it to another target silently on replay.
8. Restrict the import to an explicit tenant/company/source database and bounded batches. Include a manifest digest, preflight counts, resumability and final reconciliation.
9. No outbound communication, mail templates, external Documents sharing/portal invitation or automation activation.

**No production/staging DB writes are authorized in this runbook.** You may create imported files and records only in a clearly verified **disposable Odoo 19 Enterprise test database** with authorized test access; otherwise run offline unit tests and mark Enterprise execution `NOT_RUN`.

If implementation needs a new authoritative business type, public schema change, provider, or undocumented Enterprise behavior, record the exact missing contract and stop only that implementation seam. Never work around it by duplicating binaries or writing directly to `plasticos.document` as an independent original store.

## 6. Validate end to end [GATE F]

At a minimum, test the following with evidence from the **exact current code revision**:

- A `W` document with a proven worksheet join attaches to the correct current Odoo transaction or authoritative native record.
- A `P` document links to its proven PO, not an unrelated worksheet.
- An unresolved `E` record is preserved but not auto-linked.
- `RefType=W` and `RefType=P` sharing numeric `RefID` do not collide.
- Two files for one worksheet are both preserved.
- Two image rows for one document retain correct page/order semantics, or remain separate if grouping is unproven.
- Duplicate source rows/content and a second replay yield **zero duplicate originals or typed links**.
- Corrupt/oversized/unsupported compression does not lose source identity or abort other items silently.
- Missing target, ambiguous target, company mismatch, stale source revision and content conflict fail closed.
- Document creation does **not** verify, send mail, post bills, alter stock or create financial side effects.
- The exact ten-document pilot matches manually inspected Odoo records and their visible attachments; verify attachments can be opened.
- Bulk inventory counts reconcile: `found = decoded + failed/unsupported` (with defined inclusion/exclusion rules); `decoded = imported + unmatched + duplicate/reused + other explicitly classified`, without double-counting multi-image groupings.

Run the repository's **verified** available focused tests and gates, then the available disposable Enterprise Odoo integration tests. Do not claim Enterprise PASS if the fixture isn't available. No weakening assertions or deleting failed cases. Summarize existing baseline failures separately from new failures.

## 7. Private deliverables and final report

Keep source documents and sensitive row-level data outside Git. Produce these **private local** files:

- `01_SOURCE_DISCOVERY.md`: all inspected backups/servers, SHA-256, backup database names, snapshot dates, missing media, limitations.
- `02_SCHEMA_AND_JOIN_PROOFS.md`: exact `DocumentImage` schema, `RefType` definitions/unknowns, SQL join proofs with negative tests.
- `03_DOCUMENT_INVENTORY.csv`: source IDs, type, size, compression, file status, original/decoded hashes, output references.
- `04_ODDO_CROSSWALK.csv`: exact source parent / worksheet / Odoo model+record ID and proof status; no guessed matches.
- `05_EXTRACTION_RECONCILIATION.md`: counts by RefType, images, documents, decoded files, failures and hash controls.
- `06_IMPORT_DRY_RUN.md`: proposed creates/links, conflicts, side-effect checks, target coverage.
- `07_TEST_EVIDENCE.md`: actual tests/commands, exit results, inspected sample attachments, replay results, Unknowns.
- `08_PAPERSOLVE_REQUEST.md`: **only if needed**, the exact missing backup/access/schema/join explanation.
- `09_OPERATOR_HANDOFF.md`: source truth, implementation diff/branch/SHA, gate results, readiness and **one next action**.

If a test fixture import runs, also produce a sanitized per-item run receipt (source keys may be in private files; no private data in PR logs). Code changes and synthetic/non-sensitive regression fixtures remain in the bounded local branch; no raw records or live documents enter Git.

### PaperSolve request when source is missing

Ask for a **SQL Server database backup of `cieTrade_Documents`** including `dbo.DocumentImage` entries with `DBName='cieTrade_SM'`, preferably from the same date as the existing `cieTrade_SM` backup. Ask for associated document metadata tables and a concise explanation of `DocID`, `ImageID`, `RefID`, `RefType` (`W`, `P`, `E`) and how to join them to original worksheet/PO identifiers. A read-only SQL export/accessible DB may be an alternative if it preserves full VARBINARY values and all reference metadata. Do **not** send the request without the operator's approval.

### Terminal statuses

- **RECOVERED_AND_TESTED**: proven source, extracted corpus, deterministic links, implemented importer, tests and disposable Enterprise replay succeeded.
- **RECOVERED_IMPORT_BLOCKED**: source files recovered; mapping/Enterprise/schema/runtime gap prevents proven import.
- **PARTIAL_RECOVERY**: safe subset recovered; exact omissions accounted for.
- **PAPERSOLVE_DEPENDENCY**: authorized local sources inventoried, document DB absent/inaccessible or reference semantics unavailable; ready-to-send request generated.
- **BLOCKED_UNKNOWN**: relevant sources or tools could not be inspected; do not call source missing or migration complete.

**Hard stop:** Never claim source missing after inspecting only one `.bak`; never claim a worksheet join until a source witness proves it; never claim importer production-ready from a static test or synthetic fixture; never create guessed links. Continue autonomously on all safe unaffected work and deliver the strongest truthful result available in this run.

## 8. Revised import scope — 2026-10-28

**Contract:** `SM-CIETRADE-DOCUMENT-RECOVERY-001`  
**Objective:** Import original historical evidence attached to CieTrade worksheets into the corresponding `plasticos.transaction` records.

Odoo already owns the commercial purchase orders and sales orders. This migration does not reimport those generated documents.

The source census is the live `UCSCIETRADE` pair `cieTrade_Documents` and `cieTrade_SM`, manifest ceiling ImageID 721202, 111,010 `CIETRADE_SM` images. No database backup is part of this scope. Extraction of that manifest completes before any Odoo load.

### Source selection

| `RefType` | Images | Odoo import |
|---|---:|---|
| `W` | 97,328 | Eligible. Worksheet evidence. |
| `#` | 18 | Eligible. Container photos on a worksheet. |
| `P` | 13,077 | Excluded from Odoo import. |
| `E` | 586 | Leave unattached. |
| `B` | 1 | Leave unattached. |

Eligible images are 97,346. The private recovery archive keeps every extracted original and its source metadata, including the excluded `P`, `E`, and `B` files.

### Exact association

`RefID` is the complete CieTrade worksheet number, including suffixes. Match it to `plasticos.transaction.name` by exact source identity. Attach the file only when exactly one transaction has that name.

One sales order may serve multiple worksheets. Each worksheet's documents stay on that worksheet's own `plasticos.transaction`.

### Document selection

Import the original worksheet evidence: scale tickets, proof of delivery, bills of lading, packing lists, loading photographs, signed documents, certificates, relevant correspondence, and other actual worksheet attachments.

A generated purchase-order or sales-order PDF is skipped only when its equivalence to the Odoo commercial document is positively established. A `.pdf` extension, or an empty `DocName` / `DocType`, does not establish that. Uncertain originals stay in the eligible set. If a later classification pass is required, report those rows separately.

### Destination and integrity

Use the existing Enterprise Documents model and `plasticos_documents_native`. One original per `ImageID`, with source provenance and SHA-256 hashes. Set `transaction_id` to the unique matched transaction. Leave `verified` false. Do not add a verification writer. Do not call the partner recency auto-link.

Creating the document does not post accounting, move stock, send mail, or write the transaction.

### Crosswalk before import

Produce the crosswalk before any create. Report these counts:

- eligible
- unique transaction match
- missing transaction
- ambiguous transaction
- proven redundant
- unresolved classification

Proven redundant starts at zero until a positive equivalence exists.

### Test

First test on the disposable Odoo 19 Enterprise database that contains the actual imported worksheet transactions. A repeated import of the same `ImageID` creates zero additional originals.

No production or Staging database writes. No pull request, merge, or deployment.
