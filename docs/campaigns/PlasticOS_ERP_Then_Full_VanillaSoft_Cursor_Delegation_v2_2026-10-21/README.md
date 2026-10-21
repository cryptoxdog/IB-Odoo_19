# Corrected Cursor delegation: ERP partner import THEN full VanillaSoft CRM import

**Status:** Delegation instructions and private operator input data only. **No Docker import has been executed by this ZIP.**

**Why v2 exists:** The prior handoff stopped after ERP active-only import plus binding the 763 approved CRM source IDs, even though the Enterprise test clone starts with no CRM source contacts. That skipped the required real full CRM import. This v2 replaces the prior handoff; do not execute both.

## How to run

1. Unpack on the workstation running Cursor. Read `CURSOR_EXECUTION_CONTRACT.md` as the agent's task. The user has already authorized this test within the owned disposable Enterprise Docker clone only.
2. Place `PRIVATE_INPUTS/` OUTSIDE the Git working tree or under an already-verified ignored private runtime directory. Do not copy it to `docs/reports/`; do not commit or attach the raw input files to the PR. Its CSV contains customer contact data and the workbooks contain identity/field mappings.
3. Verify the SHA256 and input row counts recorded in `INPUT_MANIFEST.json` before touching databases. `03_APPROVED_CONTACT_CROSSWALK.csv` was reconstructed from the operator-approved workbook and **byte-verified** against the repository's pinned SHA256 `f22c707a7b6fceba40a20fa393e0c8887e3f05a8d183865ca28f0ccfc16fede2`.
4. Execute the steps strictly in order: verified clone and CRM=empty proof, ERP active-only partners import, then **4,876-ID actual VanillaSoft provider-backed CRM import**, then reconciliation. Do not mistake the input snapshot for already-imported CRM records.
5. Complete `REPORT_TEMPLATE.md` and `RECEIPT_TEMPLATE.json` from run evidence; save sanitized versions under repo `docs/reports/evidence/erp-then-vanillasoft-full-crm-<date>/`. One PR only for necessary bounded code changes, through the repository's existing `make pr` path.

## Locked source classifications

- 4,876 distinct historical VanillaSoft ContactIDs, all `Flagged=True`.
- Operator decisions: **763 approved existing-ERP-person links**, **18 denied ERP candidate links**, **4,095 pending existing-person identity review**.
- 763 approved source IDs point to 716 distinct ERP CT_ID identities. 45 ERP targets accept 92 source-ID aliases, without minting additional people.
- CRM-stage states do NOT define ERP activity. Do Not Call, Unqualified, Prison and `ClosedFlag` do not exclude the locked CRM cohort. Do Not Call remains a real contact restriction.
- Previous active-only ERP contact import returned missing-person outcomes for 28 approved source IDs; their excluded-parent reasons must be diagnosed, not silently overcome by importing inactive parents.
- The provider's historical bulk Contacts lookback is known to fail for dates older than ~30 days; a 30-day run is not full import. The existing single-contact-ID API path successfully served the approved IDs in the earlier evidence. Use the known existing adapter/orchestrator over the full cohort with the historical CSV as an ID census, never a parallel direct-CSV importer.

## Inputs included

See `INPUT_MANIFEST.json` for exact filenames, sizes, SHA256s and provenance. The raw inputs are PRIVATE and may include names, contact information and notes. The generated receipt template and report template intentionally contain no fabricated run results.

**Outcome requested:** a real populated CRM on one disposable Enterprise Odoo database, a complete and honest 4,876-ID disposition, and independent report/receipt. A blocked API/eligibility item is reported as blocked, never counted as imported.
