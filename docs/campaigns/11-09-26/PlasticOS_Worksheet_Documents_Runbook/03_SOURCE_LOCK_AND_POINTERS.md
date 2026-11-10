# 03 | Exact source coordinates and supersession boundaries

**Repository:** https://github.com/cryptoxdog/IB-Odoo_19  
**Observed at authoring:** `Staging@d6cc3c8ba04041da1844d7d0be396f4fad907be7`, Git `Production@02b90f199f2ae8733e3759b3d60cda85800ee486`. These are **Git refs only**, not proof of the currently running Odoo.sh hosted Production build. **Refresh before execution.**

## Locked governing source and current evidence

1. [Locked worksheet-original import scope](https://github.com/cryptoxdog/IB-Odoo_19/blob/d6cc3c8ba04041da1844d7d0be396f4fad907be7/docs/campaigns/_Document%20Blob%20Imports/ERP-DOCUMENT-RECOVERY-001/11_IMPORT_SCOPE.md): all `W/#` images, exact source `RefID == plasticos.transaction.name`, one native original per `ImageID`, no commercial side effects, `P/E/B` archive only. **Do not modify to relax import exceptions.**
2. [Live-source extract code](https://github.com/cryptoxdog/IB-Odoo_19/blob/d6cc3c8ba04041da1844d7d0be396f4fad907be7/docs/campaigns/_Document%20Blob%20Imports/ERP-DOCUMENT-RECOVERY-001/EXTRACT_BLOBS.ps1): real Windows PowerShell 5.1 / SQL Server `erp_Documents` exporter; journal schema, size/hash/scope, frozen `ImageID` ceiling. **Do not run outside verified real environment or rewrite a successful source extract.**
3. [Manifest count baseline](https://github.com/cryptoxdog/IB-Odoo_19/blob/d6cc3c8ba04041da1844d7d0be396f4fad907be7/docs/campaigns/_Document%20Blob%20Imports/ERP-DOCUMENT-RECOVERY-001/10_MANIFEST_RECONCILIATION.md): Oct 28, 111,010 rows/41,485,898,661 declared decoded bytes, 97,346 `W/#`; manifest and bytes are outside repository.
4. [Go-live source chain](https://github.com/cryptoxdog/IB-Odoo_19/blob/d6cc3c8ba04041da1844d7d0be396f4fad907be7/docs/campaigns/_Document%20Blob%20Imports/ERP-DOCUMENT-RECOVERY-001/12_GO_LIVE_SOURCE_CHAIN.md): distinguishes current ERP SQL backup (business import) from the **separate** binary documents archive. Does not authorize reloading ERP data for image import.
5. [Read-only exact-match evidence](https://github.com/cryptoxdog/IB-Odoo_19/blob/d6cc3c8ba04041da1844d7d0be396f4fad907be7/docs/reports/evidence/blob-matching-to-transactions/BRIEF.md) and [receipt](https://github.com/cryptoxdog/IB-Odoo_19/blob/d6cc3c8ba04041da1844d7d0be396f4fad907be7/docs/reports/evidence/blob-matching-to-transactions/receipt.json): November 4, 97,346 eligible, 91,442 matched, 5,903 missing, 1 integrity failure, none imported; **historical test DB, not Production**; private source image journal not recomputed.
6. [Native Enterprise Documents owner](https://github.com/cryptoxdog/IB-Odoo_19/blob/d6cc3c8ba04041da1844d7d0be396f4fad907be7/plasticos_documents_native/__manifest__.py) and [native synchronization service](https://github.com/cryptoxdog/IB-Odoo_19/blob/d6cc3c8ba04041da1844d7d0be396f4fad907be7/plasticos_documents_native/models/document_sync.py); Enterprise `documents`, `documents_account` are dependencies. An addon manifest is not evidence of hosted installation.
7. [Documents business policy](https://github.com/cryptoxdog/IB-Odoo_19/tree/d6cc3c8ba04041da1844d7d0be396f4fad907be7/plasticos_documents/business_rules); native Documents owns files, business Documents owns acceptance/verification.
8. [ADR-022](https://github.com/cryptoxdog/IB-Odoo_19/blob/d6cc3c8ba04041da1844d7d0be396f4fad907be7/docs/adr/ADR-022-erp-historical-closure-and-accounting-opening-balances.md): historical commercial and accounting records remain separate; image imports must not reopen trades or post originals.
9. [Makefile](https://github.com/cryptoxdog/IB-Odoo_19/blob/d6cc3c8ba04041da1844d7d0be396f4fad907be7/Makefile): observed `make import-erp` and `make import-vanillasoft`. **No confirmed `make import-erp-documents` exists** at the authoring revision; treat any such target as a proposal requiring scoped implementation.

## Vendor operational authority

- [Odoo 19 Odoo.sh backup UI and guarantees](https://www.odoo.com/documentation/19.0/administration/odoo_sh/getting_started/branches.html#backups): native DB + filestore automatic backups, vendor manual control and limits, download and restore options.
- [Odoo 19 hosted build behavior](https://www.odoo.com/documentation/19.0/administration/odoo_sh/getting_started/builds.html): live Production can run previous successful build if a new one fails; staging clones are neutralized.
- Never invent a generic Odoo.sh platform API, `pg_dump` permission, or new PostgreSQL service.

## Existing disaster-recovery plan: cite, DO NOT replicate

[SM-ODOO-DR-CAMPAIGN-001 v1.3](https://github.com/cryptoxdog/IB-Odoo_19/blob/d6cc3c8ba04041da1844d7d0be396f4fad907be7/docs/campaigns/future-add-ons/SM_Odoo_AWS_DR_v1.3_FINAL/README.md), especially [Contract 01: native backup and isolated restore](https://github.com/cryptoxdog/IB-Odoo_19/blob/d6cc3c8ba04041da1844d7d0be396f4fad907be7/docs/campaigns/future-add-ons/SM_Odoo_AWS_DR_v1.3_FINAL/contracts/01_ODOO_NATIVE_BACKUP.md). This runbook's G1 uses the supported immediate native backup and isolated-restore proof; it does **not** claim the independent AWS + S3 + 1Password disaster-recovery campaign is deployed, licensed, validated or complete. No policy fork and no duplicate recovery infrastructure.

## Evidence classification at pack publication

- **OBSERVED SOURCE:** Git file contents and branch pointers above, existing source metadata and documented prior test census.
- **NOT OBSERVED:** Live Odoo.sh Production running build, database/filestore accessibility, backup completion, Production target census, implemented source-image importer, actual import/replay results, management authorization. The private journal and a partial decoded copy were observed on this Mac on 2026-11-09; the copy was still running. Paths are in `00_RESUME_HERE.md`. `raw/` was still only on the server.
- **Decision:** Working runbook, not execution receipt or new release gate admission. Subsequent agent must pin refreshed exact source before code or hosted operation.
