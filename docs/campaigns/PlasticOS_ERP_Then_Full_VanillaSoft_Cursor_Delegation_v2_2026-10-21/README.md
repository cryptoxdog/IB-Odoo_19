# Cursor delegation: full ERP import, then full VanillaSoft CRM import

**Status:** Delegation instructions only. The private operator inputs are kept outside git. **No Docker import has been executed.**  
**Revision:** `v2.2` in `CURSOR_EXECUTION_CONTRACT.md`, written against remote `Staging` `e78af874604890f8adb6b049694f93c48311eab4`. That contract is the task. This page does not override it.

**Why v2 exists:** The prior handoff stopped after an ERP partner import plus 763 approved CRM IDs. The Enterprise clone starts with no CRM source contacts, so that skipped the 4,876-ID import.

**What v2.1 corrects:** partners-only is the first ERP write, not the whole ERP import. The second write is the existing unlimited `make import-erp` on the same pinned fixture clone, which realizes `sale.order`, `purchase.order`, `account.move`, and compiled `plasticos.transaction` rows. The CRM cohort is a `scripts/test_env.sh run <clone> -- shell --no-http` pass over `upsert_contact_external_id`, not `make import-vanillasoft`. Owner, stage, and polymer workbooks score the current importer; they are not new maps to install.

**What v2.2 corrects:** `import_4876.py` keeps every warning and failure reason on the checkpoint row. An imported contact that also warned stays imported and keeps the warning. A held, failed, or skipped row with no reason is UNKNOWN and the script exits 1. The receipt `open_exceptions` is `{level, reason, count}` and cannot be empty while those counts are non-zero. Copy this script into `Current Work - IGNORE/erp-then-vs-full-crm/` before Gate C.

## How to run

1. Read `CURSOR_EXECUTION_CONTRACT.md`. Run it only on one owned disposable clone of `config/test_env_fixture.conf` (`odoo_test_tpl_ee_c9e8a81f52f23680`).
2. `PRIVATE_INPUTS/` is gitignored; its data files are not in the repository. Place the operator's copies there locally. Copy the crosswalk and a no-PII ID census into gitignored `Current Work - IGNORE/erp-then-vs-full-crm/` so the container can read them at `/mnt/extra-addons/Current Work - IGNORE/erp-then-vs-full-crm/`. Do not copy raw inputs to `docs/reports/`.
3. Verify the SHA256 values and row counts in `INPUT_MANIFEST.json` before any database write. The crosswalk must equal `3689fccf9c62737709ca07a05912309c1cc41ec00c828f17d0283469bce1ecd9`.
4. Order: empty-CRM proof, active-only partners, commercial documents, 4,876-ID VanillaSoft import, reconciliation. The historical CSV is an ID census, not an importer.
5. Fill `REPORT_TEMPLATE.md` and `RECEIPT_TEMPLATE.json` from the run. Save sanitized copies under `docs/reports/evidence/erp-then-vanillasoft-full-crm-<date>/`. One `make pr` only if addon code changed.

## Locked source classifications

- 4,876 distinct historical VanillaSoft ContactIDs, all `Flagged=True`.
- Operator decisions: **763 approved existing-ERP-person links**, **18 denied ERP candidate links**, **4,095 pending existing-person identity review**.
- The operator matrix still has 763 approved source IDs. The loaded crosswalk is 759 VanillaSoft ids and 702 ERP CT_IDs. Four YES ids are duplicates of a person already approved on an active contact and are not fetched.
- CRM-stage states do NOT define ERP activity. Do Not Call, Unqualified, Prison and `ClosedFlag` do not exclude the locked CRM cohort. Do Not Call remains a real contact restriction.
- Previous active-only ERP contact import returned missing-person outcomes for 28 approved source IDs; their excluded-parent reasons must be diagnosed, not silently overcome by importing inactive parents.
- The provider's historical bulk Contacts lookback is known to fail for dates older than ~30 days; a 30-day run is not full import. The existing single-contact-ID API path successfully served the approved IDs in the earlier evidence. Use the known existing adapter/orchestrator over the full cohort with the historical CSV as an ID census, never a parallel direct-CSV importer.

## Inputs

See `INPUT_MANIFEST.json` for exact filenames, sizes, SHA256s and provenance. The raw inputs are PRIVATE, may include names, contact information and notes, and are not committed. The generated receipt template and report template intentionally contain no fabricated run results.

**Outcome requested:** on one disposable Enterprise clone, eligible active ERP partners, the commercial documents the current importer writes, a populated CRM, and an honest 4,876-ID disposition. Held, failed, skipped, and blocked rows are reported with the reason that produced them and are not counted as imported. A disposition whose only content is the class name is not a result.
