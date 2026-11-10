# Post-import PostgreSQL, worksheet originals, document AI and manager exceptions

**Scope:** additional post-import operator acceptance, not permission to run a Production importer or activate an autonomous AI writer. **Status:** planned, not run. **Source:** `Staging@d6cc3c8ba04041da1844d7d0be396f4fad907be7`.

## 1. Verify what PostgreSQL means before provisioning anything

- Odoo.sh already operates a PostgreSQL database and matching filestore. Observe the actual Production database/schema, Enterprise version, installed native Documents addon, attachment table/file storage and authorised read/write paths. A separate PostgreSQL server is **not presumed necessary**. If another service is intended, locate its verified data owner, endpoint, rights and use case before adding infrastructure.
- The ERP binary source in the existing recovery plan is **Microsoft SQL Server** (`erp_Documents` / `erp_SM` on `UCSerp`), not the Odoo PostgreSQL target. Keep source extraction and target attachment persistence distinct.
- Before any bulk import, obtain a supported Odoo.sh point-in-time **database plus filestore** backup and verify an isolated restore. Do not use new S3 recovery work as an excuse to skip the ordinary native safety point.

## 2. Source-backed worksheet originals, no invented match

Read existing owner documents first: [locked import scope](https://github.com/cryptoxdog/IB-Odoo_19/blob/d6cc3c8ba04041da1844d7d0be396f4fad907be7/docs/campaigns/_Document%20Blob%20Imports/ERP-DOCUMENT-RECOVERY-001/11_IMPORT_SCOPE.md) and [historical matching census](https://github.com/cryptoxdog/IB-Odoo_19/blob/d6cc3c8ba04041da1844d7d0be396f4fad907be7/docs/reports/evidence/blob-matching-to-transactions/BRIEF.md).

The historical Nov 4 *test-database* brief counted **97,346** eligible `W`/`#` images, **91,442** exact matches and **5,903** unmatched; one source image was corrupt and **zero** were imported. Its image-count journal was not recomputed on Nov 4. These values are **not** a current full Production census. Refresh on the authorized source manifest and exact Production population.

1. Verify immutable per-image `ImageID`, `DocID`, `RefType`, full `RefID` including any suffix, source SHA-256, decoded size, GZIP outcome and signed source epoch. Accept only `W` and `#`. Preserve `P`, `E`, `B` in the private archive; do not relabel them to make coverage 100%.
2. Match only `RefID == plasticos.transaction.name` within the permitted company. No partner/date/PO/SO/shortened-number heuristics. Missing or ambiguous targets stay quarantined, not silently dropped or bound to a guessed transaction.
3. One native Enterprise Documents original per source `ImageID`, native attachment/filestore-backed, initial `verified=False`. Preserve original hash and provenance. No move of the commercial or document decision authority into a new storage layer.
4. Implement/test one bounded importer at the Documents owner, with chunk/batch progress, dry-run, resume, idempotent source keys, failed-item journal, company/ACL/role controls and zero side effects on transaction state, GL, stock, email or verification. Use governed publisher; the existing `make import-erp` does not imply an image-import target exists.
5. Prove arithmetic **eligible = unique-match + missing + ambiguous + integrity-failed**, and **unique-match = imported + import-failed**. Inspect actual multi-image, suffix, canceled history and one corrupt example. Re-run same input to prove `created=0` and unchanged accepted originals.
6. Ensure the business file survives downloaded original checks and a DB+filestore restore. Keep bulk customer binary content and raw source archives out of Git and this ZIP.

## 3. Existing document AI, not CEG matching or enrichment

Run a guarded native Enterprise Documents AI pilot only after installed module/capability/entitlement and proper manager permissions are witnessed. Test **already existing docs** as well as newly imported worksheet originals; no need to switch to CEG/EIE or new custom LLM stack.

Samples: legible invoice/BOL/scale ticket, handwriting, unreadable scan, missing pages, two conflicting dates/amounts, wrong company, wrong worksheet, duplicate original, stale revision and an invalid/malicious embedded instruction. Candidate extraction requires source page/field provenance, confidence and explanation. Review-only candidates cannot auto-verify evidence, send email, change load/stock state, reopen trade, post invoices or approve payments.

## 4. Manager-profile exception routing: the user-facing proof

`documents.document.verification_review_required` exists in source and the document form shows a historical disagreement warning. **That does not prove** an assigned-manager queue or dashboard is already implemented.

- First inspect existing Documents review/activity/assignment UI for the actual deployed manager role. Use the smallest owner-consistent action/filter/dashboard integration needed, not a second parallel decision table or verification writer.
- Every missing, corrupt, ambiguous, low-confidence, contradictory, stale, or incorrectly associated document gets a durable attributable review state with **why**, company, assigned manager, source file, transaction/load and next action. Avoid creating false issues for merely unreviewed but otherwise normal historical originals.
- Manager sees cases on their profile/work queue, can drill into the original, select an authorized resolution and observe an audited history. Another company and ordinary user see nothing they should not. Test reassignment, status changes, empty queue, repeated AI runs and two managers acting concurrently.
- Acceptance witness: login as real manager, observe a known flagged imported document, open original and transaction, resolve/retain flag correctly; re-login/reload and prove it persists. No screenshot-only proof.

**Independent lanes:** After source and backup, blob import and accountant report validation can proceed independently. Document AI can pilot on existing originals even if some source blobs remain unresolved; final document acceptance must account for unresolved eligible cohort.
