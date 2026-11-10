# PlasticOS | Production PostgreSQL + Worksheet Originals: Execution Runbook

**Pack:** `PLASTICOS-WKS-DOC-IMPORT-RUNBOOK-2026-11-09/v1`  
**Date:** 2026-11-09, America/New_York  
**Status:** Source-grounded handoff. **NOT Production authorization.** The 2026-10-28 extract is finished on the server. A copy onto this Mac was still running at 18:56 ET on 2026-11-09. See `00_RESUME_HERE.md`. Gates G0–G8 are **NOT executed**.  
**Target:** `cryptoxdog/IB-Odoo_19` (governed code integration branch `Staging`; actual Odoo.sh Production identified separately at execution).  
**Parent planning artifact:** `PlasticOS_PostImport_Accounting_DR_Plan_Graph_2026-11-09.zip`, SHA-256 `0298a878b86d1c867cba2f2dff6e65b822817ac6a8f00b5f86dc6af9d4167fee`.

## Bottom line

**The next move is a read-only identity and backup preflight, not an immediate bulk import.** Prove the actual hosted Production PostgreSQL + filestore, take a native DB **plus filestore** backup and restore it into an isolated Enterprise test target. Then recover the complete private ERP-image journal/bytes, recompute the exact Production worksheet crosswalk, implement a minimal native Documents importer only if missing, and prove import + exact replay on the isolated target before authorizing Production writes.

Odoo.sh **already manages PostgreSQL**. Do not provision a second PostgreSQL server or secondary Documents store absent verified need and separate approval. ERP image source is SQL Server (`erp_Documents`), not Odoo PostgreSQL.

## Operator order of operations

| Gate | Deliverable | Work authorization / pass condition |
|---|---|---|
| G0 | Source & rights pin | Actual running Odoo.sh Production build, DB, company, installed modules, authorized user, current source journal and intended cohort verified. **READ ONLY** |
| G1 | Recoverable backup | Completed native Production database **and filestore** snapshot downloaded/secured and a separate restored Enterprise copy proven with attachments. **One native manual backup permitted after UI limit/rights check** |
| G2 | Private original corpus | Full `journal.csv` plus decoded files with source SHA-256, byte-length proofs, known source snapshot, counts and quarantine. **READ ONLY** |
| G3 | Exact Production crosswalk | Every eligible `W`/`#` image mapped by **complete** `RefID == plasticos.transaction.name`, missing/ambiguous/integrity cases explicit. **READ ONLY** |
| G4 | Bounded importer + isolated proof | Native `documents.document` / `ir.attachment` source-owned importer, dry-run, cancel/resume, one durable image identity, and negative tests. **CODE THROUGH GOVERNED `make pr`; no Production writes** |
| G5 | Dry-run acceptance | Actual frozen journal + actual Production-derived transaction census on isolated Enterprise clone; no accidental side effects. **READ ONLY / ISOLATED** |
| G6 | Production controlled batches | Only after named operator authorizes exact source/target/build/backup/manifest and first batch; no unrestricted `make import-erp` side effect. **EXPLICIT PRODUCTION WRITE GATE** |
| G7 | Full closure + replay | Reconcile all dispositions, read back originals, run identical input again with **zero newly created** documents and unchanged verified bytes. **RECEIPTS** |
| G8 | Handoff | Archived exceptions with owner, clean system, backup checkpoint, manager review/AI testing may start **separately**. **NO silent closeout** |

**Start here:** `00_RESUME_HERE.md` for the live file paths and the copy still in progress. Then `01_OPERATOR_GATES.md` for the steps, `04_AGENT_CONTRACT.md` for the coding/operations agent, `tools/reconcile_cohort.py` for a local read-only crosswalk proof, `05_ACCEPTANCE_MATRIX.csv` and `receipts/receipt.template.json` for closure.

## Scope and the locked historical baseline

- Existing 2026-10-28 frozen source: 111,010 ERP image rows; 97,328 `W` + 18 `#` = **97,346 eligible**. `P` 13,077; `E` 586; `B` 1 are **private archive only**, not Odoo imports.
- **November 4 test-database-only** join: 91,442 images exact-match and 5,903 lack a transaction; zero ambiguous; one identified corrupt image (633316); **zero actual imports**. This is historical evidence, **not** a current Production census or current installed-module proof.
- The journal was absent from the repo's indexed evidence at the November 4 check. On 2026-11-09 the finished journal and a partial `decoded/` copy were on this Mac under `/Users/ib-mac/Odoo-ERP-Files`. Paths, the missing `ImportScope` column, and the copy-in-progress rule are in `00_RESUME_HERE.md`. Hash the files after the copy is stable. Do not re-extract.
- An intact blob must attach to **one** transaction with exactly the complete `RefID` including suffix. A valid match can be Closed or Cancelled historical trade. Do not reopen trade, reconstruct missing sales, adjust ledger, or move P/E/B files into Odoo to improve counts.

## Hard stop conditions

Missing or non-restorable backup; inaccessible Production build/DB/filestore identity; absent/partial source journal; missing decoded original; unverified matching company; duplicate/ambiguous transaction name; wrong native Documents entitlement; unproven idempotency; any email/accounting/stock/AI/transaction-state mutation in the import; unapproved Production write. Report `BLOCKED` or named exception, with evidence. Never call a partial pilot `DONE`.

## Non-goals

No transaction reopening, QuickBooks/AR/AP cutover, automatic AI verification, autonomous manager overrides, Export module build, full AWS disaster-recovery campaign, unsolicited infrastructure provision, or raw document bytes in Git. Existing DR campaign is **referenced**, not copied; see `03_SOURCE_LOCK_AND_POINTERS.md`.

## Run locally (synthetic tests, no network)

```sh
python3 -m unittest discover -s tools -p 'test_*.py' -v
python3 tools/reconcile_cohort.py --help
```

The analysis script is **read-only**. It reads operator-exported CSVs and, optionally, original files to verify hashes. A passing script does **not** prove the export represents the full Production DB or that an Odoo import occurred. Those need separate hosted receipts.
