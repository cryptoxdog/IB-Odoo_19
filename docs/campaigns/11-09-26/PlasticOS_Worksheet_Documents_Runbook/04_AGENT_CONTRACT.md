# 04 | Copy-and-run agent execution contract

**Role:** Single bounded Odoo 19 Enterprise document migration implementation/operations agent. **Target:** `https://github.com/cryptoxdog/IB-Odoo_19`, authorized integration base `Staging`; production is **actual hosted Odoo.sh**, not a Git branch alias. **Mission:** After observed safe DB+filestore backup and isolated restore, import every proven, unique-match `W/#` worksheet-image original into the correct native Enterprise Documents transaction association, preserve exceptions, reconcile the entire eligible cohort and prove zero-duplicate replay.

## Mandatory intake

Read this pack in order: `00_RESUME_HERE.md`, `README.md`, `01_OPERATOR_GATES.md`, `02_EXACT_MATCH_AND_IMPORT_CONTRACT.md`, `03_SOURCE_LOCK_AND_POINTERS.md`, `05_ACCEPTANCE_MATRIX.csv`. Resolve current repo/branch/build and policy before selecting real executable commands. Read existing source `11_IMPORT_SCOPE.md`, existing source extractor `EXTRACT_BLOBS.ps1`, historical evidence, native Documents BRS/AGENTS, and native Odoo.sh DR Contract 01. **Do not use the repo's frozen journal absence as license to invent data.**

## Authorized lane A: observe and prepare

1. Read-only identify actual running Production Odoo.sh build/DB/filestore and Enterprise Documents installation. Confirm complete authorized company-scoped target export. Determine whether a second PostgreSQL service has any proven need; default **no**.
2. Through authorized Odoo.sh native UI only, obtain fresh completed **DB+filestore** backup and prove isolated restore; save backup SHA, source time and file-read receipts privately. Do not restore into Production or modify production DB configuration.
3. Locate private existing SQL Server extract `journal.csv` and `decoded/` files and verify their frozen completeness and hashes. Reconcile current desired cohort vs Oct28 ceiling; don't silently change import scope or mix source epochs.
4. Execute read-only offline `tools/reconcile_cohort.py` on source and **complete actual Production** transaction list. List missing/ambiguous/corrupt, account for `P/E/B`, bind exact company and `RefID`.

## Authorized lane B: bounded code, only if actually absent

Implement the **smallest** native Documents import path. Reuse current `plasticos_documents_native`, `documents.document`, `ir.attachment`, existing verification owner/bridge, existing shell and repo tool conventions. Add a durable database-enforced source key `(source_db, ImageID)` or reuse an authoritative existing equivalent **only after inspecting real current schema and tests**; plan/prove migration safety for existing attachments. Source `DocID`/`RefID`/hash are provenance; they are not alone concurrency locks. Require exact target/ACL; no guessed match, no broad `sudo` bypass. Start unverified, preserve every original, no new service/parallel verification or AI engine.

Provide one verified scoped dry-run + resume/batch entrypoint. If no equivalent exists and repo Make conventions support it, propose/implement **`make import-erp-documents`** with dry-run default or mandatory explicit apply permit, but **do not claim the target exists today**. Avoid refactoring `make import-erp` and `make import-vanillasoft`. No changed accounting, CRM, logistics, transaction life cycle, DR policy, Export or AI behavior.

Test in disposable **Odoo 19 Enterprise** after a native restore; all positive and negative checks of `05_ACCEPTANCE_MATRIX.csv`. Test first successful batch, full eligible cohort if feasible, two identical passes, restart/interruption, concurrent same-source attempts, file download/readback and zero side effects. Keep historical source business records unchanged. Publish code through the repository's verified `make pr` publisher only; **no raw push**, no merge, no deployment or Production database write from PR authority.

## Authorized lane C: Production operator gate (not implied by document authoring)

Stop for the named operator's explicit, revision-bound approval identifying the live target, source freeze/journal SHA-256, verified backup/restorable checkpoint, company, execution window, proposed batch count, impact/rollback and executable exact command. Do not treat approval to produce this runbook or code PR as approval for a bulk Production data import. If approved: dry run again on Production, run small guarded batch, inspect real native files/associations/side-effect baselines, proceed to bounded larger chunks, reconcile every ImageID, exact replay produces zero new originals; record hosted receipts. If not approved, complete everything else and return the exact missing authorization.

## Nonnegotiable acceptance

- Source completeness from private immutable journal and files; no raw source binaries or SQL exports in Git/this ZIP.
- Native Odoo Production backup+filestore recoverability demonstrated on isolated Enterprise restore, not just a download/screenshot.
- `W/#` only, one original per source image, target **exact** full worksheet name, company proven; missing/ambiguous/corrupt items quarantine; `P/E/B` remain private outside Odoo.
- `eligible=unique+missing+ambiguous+integrity` and `unique=imported+failed+not_attempted`; full closure requires no unattempted unique items and no unexplained import failures.
- Native file original opens and content digest matches, initial `verified=False`; no source document accepted by AI/manager automatically.
- No transaction state, order, posting, stock, commission, email/outbound or verification changes; no duplicate original after replay/concurrent retry.
- Tests/negative controls executed on genuine isolated Enterprise target and Production first-batch readback witnessed; local script PASS proves **counts only**.
- Every in-scope finding dispositioned as FIXED, PROVEN SATISFIED, INVALID, or EXPLICIT_BLOCKED; nothing silently dropped.

## Output / publication

Return one compact status summary plus a structured `receipts/receipt.template.json`-conformant evidence ledger (private if identifying source/people), source commit/build/backup and exact test outcomes, changes/PR URI, crosswalk cohort/identity counts, mapped/unmapped/image failures, selected sample native original links/hashes, second-pass delta, no-side-effect delta and blocking actions. **Do not assert Production DONE without G0-G8 receipts.** Existing DR Contract 01 may consume G1's valid receipts, but this task cannot independently mark the entire DR campaign PASS.
