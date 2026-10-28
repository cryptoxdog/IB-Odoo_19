# 07 — Test evidence

**Current reading (2026-10-28):** The Gate F table below is the plan from before the locked scope. It stays here as history. A `P` file is not an Odoo import. Every `W` and `#` image is eligible, and the only target is one `plasticos.transaction` named with the complete worksheet `RefID`. The locked import scope is `11_IMPORT_SCOPE.md`.

**Contract:** `SM-CIETRADE-DOCUMENT-RECOVERY-001`  
**Gate F:** NOT RUN  
**Code revision:** no importer commit. Repo `Staging` remains `04bd0594a7c9dcad53d9c45fc65276d76817c112`.

No unit test, Odoo test, or disposable Enterprise replay was executed. The runbook forbids a speculative importer when the document database is absent, and it forbids calling a synthetic fixture an Enterprise pass.

| Check | Result |
|---|---|
| W document attaches to the proven worksheet | NOT RUN |
| P document links to the proven PO | NOT RUN |
| E record preserved and not auto-linked | NOT RUN |
| Shared numeric RefID does not collide | NOT RUN |
| Two files for one worksheet | NOT RUN |
| Multi-image page order | NOT RUN |
| Replay creates zero duplicates | NOT RUN |
| Corrupt blob quarantine | NOT RUN |
| Missing / ambiguous / company mismatch fail closed | NOT RUN |
| No verify, mail, stock, or accounting side effect | NOT RUN (no write path executed) |
| Ten-document pilot opened in Odoo | NOT RUN |
| Enterprise disposable import | NOT RUN |

SQL evidence that was run is the read-only inventory in `01_SOURCE_DISCOVERY.md` and `02_SCHEMA_AND_JOIN_PROOFS.md` against container `cie-sql-proof`, database `cieTrade_SM`, on 2026-10-28.

## Pilot bytes verified 2026-10-28T19:59Z

Ten files under `docs/campaigns/Document Blobs/SQL 10-28-26/SQL 10-28-26/` match `pilot_manifest.csv` SHA-256 values. Every file starts `1F8B0800`. Decompressed length equals `Blob_Size`. Formats: PDF, Outlook message, and one JPEG. `DocName` and `DocType` are blank. RefID 4676 (DocID 92867, RefType P) matches PO 4676. RefID 1232 is RefType E, an Outlook message, and is not a worksheet number. These files are untracked and must stay out of git.
