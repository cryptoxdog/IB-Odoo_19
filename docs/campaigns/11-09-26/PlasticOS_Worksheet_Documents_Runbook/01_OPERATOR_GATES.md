# 01 | Operator runbook: stop/go sequence

The agent must observe exact connected surfaces before issuing commands. **Command placeholders are not executable instructions.** Only the verified current Odoo.sh UI/SSH and repo scripts may be used. Store private connection strings, snapshots, operator names, and document bytes off Git in approved custody.

## G0. Identity, company and rights (read only)

1. In the actual Odoo.sh project, open **Production → Builds** and identify the **currently running build**, associated Git revision, date, database name, Odoo version, filestore location/handling, hostname/branch and current service health. A GitHub `Production` branch SHA is **not** a hosted-build receipt; Odoo.sh can continue using an earlier successful build after a failed upgrade.
2. Using authorized read-only Odoo user/SSH/database capability, inspect one known historical transaction by worksheet name; gather total transaction count, unique names, company distribution and sample suffixes. Record an authenticated **complete** scoped export `id,name,company_id` from the running target for the local reconciliation script. Do not change users/roles or open broad ACLs.
3. Confirm native `documents` and `documents_account` are installed and `plasticos_documents_native` has loaded. Inspect `documents.document`, `ir.attachment`, existing `plasticos.document`, actual writable model owners and file access. Do not assume Git installability means hosted installation. If Enterprise missing, stop before importer build.
4. Confirm the source freeze: private SQL Server `erp_Documents` `journal.csv`, decoded files, exact `ImageID` ceiling/source epoch, content hashes and path/custodian. Verify 2026-10-28 freeze vs any later sources. No silent mixed-epoch upload.
5. Capture unchanged Production row counts and side-effect baselines: orders, transactions, `account.move` posted state, stock moves, `mail.mail`, verified document flags, and critical scheduled actions. Ensure authorized evidence export is complete across intended companies. A partial user ACL export must not be called a full census.

**G0 PASS:** Exact hosted source/rights and owned source bytes identified; read-only; no unsupported infrastructure. **Else BLOCKED.**

## G1. Safe native Odoo.sh backup and restore, before any live write

1. **Production → Backups:** inspect last completed automatic snapshots and timestamps. Verify real recent backup and whether download includes **DB + filestore**, not SQL-only. Record source time, backup ID, type, running build revision, size and status. Odoo 19 official docs describe seven daily, four weekly, three monthly automatic backups; **manual backup survives only 3 days**, max **five manual backups per day**. Provider-specific UI/limits take precedence.
2. If permission and daily allowance permit, take **one native manual Production backup** through the supported Backups UI. Do not delete Production content, import a database into Production, invent an Odoo.sh automation API or run an unverified PostgreSQL dump command against Odoo.sh.
3. Download the native complete backup where authorized to **private encrypted operator custody**; compute archive SHA-256 and record secure storage reference, not secrets or the backup in Git. A server backup with a three-day manual retention is not a long-term independent archive.
4. Restore **only to a named disposable isolated Odoo 19 Enterprise** target with matching modules and no live outbound mail/webhook/cron/EDI/payment connections. Capture destination, responsible owner, source backup checksum, code/dependencies and isolation proof. **Never restore over Production.**
5. Verify restored DB row counts, unique worksheet samples (including hyphenated IDs), `ir.attachment` metadata and representative **actual downloaded/opened document bytes** (including preexisting PDFs/images). Prove that PostgreSQL records and matching filestore resolve together, and compare sample SHA-256 to the source. A SQL-only dump is insufficient.
6. Record rollback/recovery route for **import-created** documents only, with original `ImageID` identity and a captured restore checkpoint. Rollback must not erase user activity since the checkpoint; if partial failure, prefer targeted, authorized reconciliation/recovery rather than a blind Production restore.

**G1 PASS:** Native snapshot complete, independent isolated restore performed, native document bytes opened and verifiable. **Else no Production import.**

Official vendor: https://www.odoo.com/documentation/19.0/administration/odoo_sh/getting_started/branches.html#backups and https://www.odoo.com/documentation/19.0/administration/odoo_sh/getting_started/builds.html

## G2. ERP source data, original bytes and private freeze

1. Use locked existing extract owner, **do not invent a new extractor**. Read `EXTRACT_BLOBS.ps1`, `10_MANIFEST_RECONCILIATION.md`, `11_IMPORT_SCOPE.md`, `12_GO_LIVE_SOURCE_CHAIN.md`. The existing extractor runs against **SQL Server** `erp_Documents` and emits the `journal.csv` header used in `tools/reconcile_cohort.py`.
2. Locate **private** `journal.csv`, `raw/` and `decoded/`, and verify source database/cohort/ceiling. On 2026-11-09 the finished server extract is `\\ucsservers01\home\ibeylin\Desktop\SQL 10-28-26\extract` and the Mac copy is `/Users/ib-mac/Odoo-ERP-Files` (`journal.csv` and `decoded/`; `raw/` stays on the server). Read `00_RESUME_HERE.md` before looking anywhere else. The old 2026-10-28 ceiling was `ImageID <= 721202`; do not silently assume it covers later records. Verify completeness by reconciling private journal count and source manifest, not only archive folder count. The copied journal has no `ImportScope` column; add that derived column after the copy is stable. Do not re-extract.
3. Check every eligible row `RefType W/#`: `Status=ok`, original/raw and decoded SHA-256 present, `DecodedBytes=BlobSize`, source `ImageID/DocID/RefID` intact. If files are present, verify on-disk decoded bytes/hash. Failed `not_gzip`, truncated, missing, unsupported and hash mismatch go into **integrity exception**, no Odoo write. Hash verification must not mutate originals.
4. Archive `P/E/B` under their existing approved private source custody. Never make them import eligible. Keep all source and per-image data out of PRs and the deliverable ZIP.

**G2 PASS:** Frozen source census and all eligible originals accounted for (including named integrity exceptions). **Else BLOCKED.**

## G3. Recompute exact Production crosswalk (read only)

1. Export **all** `plasticos.transaction` rows in authorized scope from the **actual running Production** (read-only) as `id,name,company_id` and record export completeness proof. For the full cohort, do not substitute the historical `odoo_test_night1021` 7,728-row test database or a Staging clone.
2. Compare `RefID` to `name` **byte-for-byte after the source extractor's already established normalization**. Preserve `51687-JCH` and other suffixes; no partner/date/PO/SO heuristic, no prefix/suffix stripping and no cross-company guesses.
3. Run `tools/reconcile_cohort.py --journal <private-file> --transactions <private-file> --decoded-dir <private-folder> --raw-dir <private-raw-folder> --output <private-receipt>`. Review partition and per-ImageID exceptions. This program does not access Production.
4. Confirm which exact company the ERP cohort belongs to, using authorized source evidence and target company ownership. Source `erp_SM` alone does not prove a free pass to bypass multi-company ACLs. A duplicate `name` across companies is **ambiguous** until source authority resolves it; do not force it into a chosen company.

**G3 PASS:** Frozen eligible cohort exhaustively partitioned and every importer candidate has one unique, company-verified target. Missing/ambiguous/corrupt remain recorded exceptions, not fabricated matches.

## G4/G5. Bounded importer implementation and Enterprise rehearsal

1. Search the **current** repo for an existing implemented document image importer and target metadata. The existing ERP `make import-erp` imports ERP business records; it is **not evidence** of a worksheet binary-import target. Reuse the installed native Documents / `ir.attachment` owner. If missing, implement only the smallest source-keyed importer and one discoverable operator entrypoint, with dry-run and resumable batches. Do not duplicate existing document or verification ownership.
2. Test on the isolated restored Enterprise DB with representative actual originals: valid `W`, `#`, multiple images for one worksheet, hyphenated ID, Closed/Cancelled transaction, duplicate source key, exact unknown key, cross-company ambiguity, hash mismatch, missing file, corrupt `633316`, interruption after partial write, concurrent duplicate attempt, and deleted/replayed file reference behavior.
3. On the isolated target, prove native `documents.document` original points to the intended `ir.attachment` and the **one** exact `plasticos.transaction`. Source provenance includes ERP database + `ImageID`, `DocID`, full `RefID`, content digest and batch/epoch. All fresh records are **unverified**. Use one commit boundary per idempotent unit/chunk; a retry cannot create a second original.
4. Compare before/after totals and exact identities for transaction state, purchase/sales orders, GL postings, bank moves, stock, emails, outbound notifications, commission, document verified/override and existing originals. All prohibited side effects **zero**. On error, log the exact image and cause; no silent `sudo` escalation or loss of journal.
5. Run identical cohort twice on clone: first creates expected originals, second `created=0`, `duplicated=0`, source links/digests unchanged. Test interrupted/chunk replay and simultaneous duplicate-worker pressure separately.

**G4/G5 PASS:** Exact Enterprise test receipt and source owner tests; runtime method proven in isolation. **Else never import into Production.**

## G6/G7. Controlled Production import and evidence closure

1. Pin *fresh* running Production build, unchanged database/source count and backup identity. Get explicit authorized operator signoff for **this exact epoch, manifest SHA, company, target, batch limit, restore identity and write window**. An approval to make this runbook or code PR is not a permit to apply it.
2. Dry-run Production read-only against the current records. Block if any baseline drift invalidates the crosswalk or backup. Confirm no generic `import-erp` rerun, no import into `Production` from a replacement archive, no job schedules or auto-verify enabled by the operation.
3. Apply bounded batches only with the tested importer. First batch: inspect several actual native files in the Production UI under the correct transaction and assert zero prohibited effects. If wrong target or a side effect is found, stop further batches immediately and preserve durable progress/error records.
4. Complete the approved frozen cohort, then run the **same** input again. Second pass creates zero originals; no prior original/verification flags/references change. Include restart mid-run, retries and recovery from a failed image, using the approved isolated evidence first.
5. Produce the complete arithmetic ledger: `eligible = unique + missing + ambiguous + integrity failure`; `unique = imported + import failed + not attempted`. For final import closure `not attempted = 0` and `import failed = 0`, **unless each remaining case has explicitly accepted remediation/blocker and the result is not mislabeled full PASS**. Preserve unmatched and corrupt source originals privately; never delete them or force a target.
6. Produce an actual post-write **DB + filestore** native snapshot checkpoint and verify representative imported originals are readable. Hand off disposition ledger and named backlog for missing/ambiguous/integrity exceptions to the operator. AI processing and manager review are the **next distinct milestone**, not implicit acceptance of the binary migration.

**G6/G7 PASS:** Operator-authorized Production imports, complete source/target closure, exact duplicate-free replay, opened original bytes, no unwanted business effects and signed evidence ledger.

## G8. Handoff / follow-on

Archive unlinked originals and exception records under approved private custody. Retain audit receipt with source epoch, target commit/build, checksum, backup identity and verified zero side effects. Reference the **existing** DR campaign for long-term independent recovery; this runbook only establishes the immediate recoverability checkpoint and import.

Do not open an Export, accounting, document-AI, or disaster-recovery implementation PR as a side effect of this bounded work.
