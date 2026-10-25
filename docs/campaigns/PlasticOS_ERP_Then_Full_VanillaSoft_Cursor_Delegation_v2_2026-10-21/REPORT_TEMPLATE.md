# Post-run evidence: ERP partners, ERP commercial documents, then full VanillaSoft CRM

Contract revision `v2.3`. Importer outcomes `created` / `updated` / `unchanged` with a persisted provider ref are imported. `placement` splits those imported rows into `erp_person`, `active_company`, and `crm_lead`. A missing ERP marker is a `crm.lead` and keeps the warning. It is not a no-lead hold. `duplicate_rejected`, exceptions, and fetch errors are `genuine_failed`. A second VanillaSoft id for an already approved active person is `duplicate_skipped`. Do not invent importer states. Copy each distinct checkpoint reason into section H. A class with no reason is UNKNOWN, not a result. Do not rerun the clone to turn a recorded warning into a different class.

> Fill only from actual execution receipts. All `NOT_RUN` values must become observed data or explicit BLOCKED/UNKNOWN. Commit only sanitized facts, no customer PII.

**Observed date/UTC:** NOT_RUN  
**Staging SHA under test:** NOT_RUN  
**Enterprise fixture / owned clone:** NOT_RUN  
**Private input SHA256 validation:** NOT_RUN  
**Final verdict:** NOT_RUN

## Bottom line

Did the CRM start empty? UNKNOWN. Were eligible active ERP people imported with inactive aliases excluded? UNKNOWN. Did the commercial pass write native sale orders, purchase orders, invoices, and only compiled transactions? UNKNOWN. Were all 4,876 frozen source IDs fetched and classified? UNKNOWN. How many real `crm.lead` records and approved-person bindings exist? UNKNOWN. Which material exceptions remain? UNKNOWN.

## A. Source and policy checks

| Source census | Observed | Evidence reference |
| --- | ---: | --- |
| Raw ERP source contacts | UNKNOWN | |
| Eligible explicitly active contacts at eligible active companies | UNKNOWN | |
| Excluded inactive contacts | UNKNOWN | |
| Active contacts excluded by parent status / placeholder / missing parent | UNKNOWN | |
| Active contacts routed to an existing nonperson/site destination | UNKNOWN | |
| Historical VanillaSoft frozen ContactIDs | 4,876 baseline; VERIFY | |
| Live API ContactIDs fetched from that list | UNKNOWN | |
| Current live additions / deleted or inaccessible IDs | UNKNOWN | |

Explain the source flag spellings and mutually exclusive eligibility/exclusion partitions, including each previously unmatched active-parent reason.

## B. Exactly one clone and ordered stage proof

| Checkpoint | Business partners | ERP person XMLIDs | `sale.order` | `purchase.order` | `account.move` | `plasticos.transaction` | `crm.lead` | Person refs | Lead refs | Calls | Evidence |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Before imports (fresh clone) | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | |
| After partners-only, before commercial | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | |
| After commercial, before VanillaSoft | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | |
| After VanillaSoft 4,876 pass | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | |

Record fixture admission, clone-ownership proof, code and Enterprise checkout digests, read-only ERP SQL proof, private provider API scope, actual commands/exit codes and no hosted writes. Odoo system/seed partner rows are not imported business counterparties.

## C. ERP active-only import results

| Layer | Input eligible | Created | Updated | Unchanged | Policy excluded | Genuine rejected | Validator evidence |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Counterparties | | | | | | | |
| Addresses | | | | | | | |
| Contacts | | | | | | | |
| Roles | | | | | | | |
| Sales reps | | | | | | | |

No inactive source person, inactive alias, phone line, or note from an ineligible row. This pass writes no `sale.order`, `purchase.order`, `account.move`, or `plasticos.transaction`. The active-contact predicate is already `parse_bool(IsActive) is True`. Confirm it. Do not record a code change that was not made.

## C2. Commercial document import (second ERP write)

| Document | Source worksheets in scope | Created | Updated | Unchanged | Rejected | Compiled `plasticos.transaction` | Evidence |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `sale.order` | | | | | | | |
| `purchase.order` | | | | | | | |
| `account.move` | | | | | | | |

Partner census versus section C must be unchanged except idempotent `unchanged` rows. `plasticos.transaction` rows exist only as the sale-order confirm/compile result of `native_document_import.realize`. Status: NOT_RUN / PASS / PARTIAL / BLOCKED / FAIL.

## D. VanillaSoft full source ID reconciliation (MUST SUM TO 4,876)

| Operator decision | Frozen source IDs | `erp_person` | `active_company` | `crm_lead` | Held | Material failure | `duplicate_skipped` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| YES, exact approved ERP-person link | 763 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | 4 expected |
| NO, rejected ERP candidate / normal CRM lead path | 18 | 0 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | 0 |
| PENDING, not approved for ERP person matching | 4,095 | 0 | 0 | UNKNOWN | UNKNOWN | UNKNOWN | 0 |
| **TOTAL** | **4,876** | **UNKNOWN** | **UNKNOWN** | **UNKNOWN** | **UNKNOWN** | **UNKNOWN** | **4 expected** |

Check `imported + held + genuine_failed + duplicate_skipped = 4,876`, no source ID twice. `imported = erp_person + active_company + crm_lead`. Imported means orchestrator `created`, `updated`, or `unchanged` plus one persisted provider ref. A blank `erp_ct_id` without an active-company placement, and a `CT_ID` whose marker missed, are `crm_lead`, not held. `duplicate_rejected`, exceptions, and fetch errors are `genuine_failed`. `crm.lead` need not equal 4,876. The four omitted YES ids are the expected `duplicate_skipped` rows.

## E. Approved identity and previous 28 exceptions

- Pinned crosswalk digest verified? UNKNOWN. Operator YES: 763. Loaded crosswalk: 759 VanillaSoft ids, 691 distinct ERP CT_IDs, 737 rows with a CT_ID, 22 blanks. Shared: 44 CT_IDs covering 90 VanillaSoft ids. Duplicate YES ids not fetched: 4. Active-company blanks: 7. Other blanks, imported as leads: 15. The figure 702 is not this file.
- Do not compare the run against the October 16 workbook's inactive CT_IDs. The daytime receipt `docs/reports/evidence/erp-contacts-vs-crosswalk-daytime-2026-10-21/receipt.json` names the file this run loads. A lead for a still-unmapped blank is the expected result.
- Wrong approved person links: UNKNOWN; approved link creating a duplicate `res.partner` outside `ACTIVE_COMPANY_CP_BY_VS`: UNKNOWN; NO candidate bound to rejected CTID: UNKNOWN; pending source IDs falsely matched to ERP: UNKNOWN.

## F. CRM field and history reconciliation

| Concern | Applied / preserved | Unknown / held | Evidenced failure | Notes |
| --- | ---: | ---: | ---: | --- |
| Existing user/owner email resolution | | | | |
| Native CRM stage + raw source Lead Status retention | | | | |
| Source/marketing data | | | | |
| Email / direct / mobile / supplemental phones | | | | |
| ERP and CRM notes preserved | | | | |
| DNC and source restrictions retained | | | | |
| Approved polymer profiles on proven facility | | | | |
| Ambiguous/unmapped material and form cases | | | | |
| Real provider call events and custom tables | | | | |

Owner, stage, and polymer workbooks are audit oracles. Record the importer's name-match `user_id`, `STAGE_MAPPING` stage, and `normalize_material` result against those oracles. Do not describe a gap as a new map that was installed. Record provider limits separately for the per-ID fetch and for call history. `make import-vanillasoft` was not the cohort path.

## G. Cohort completeness is not live history completeness

- Historical snapshot `4876` coverage: PASS / PARTIAL / BLOCKED / FAIL: UNKNOWN.
- Live provider ContactID fetch coverage for these 4876: UNKNOWN.
- New/deleted live-provider ContactIDs since the snapshot: UNKNOWN.
- Complete historical contact census beyond snapshot: PROVEN / NOT_PROVEN / BLOCKED: UNKNOWN.
- Complete call history: PROVEN / NOT_PROVEN / BLOCKED: UNKNOWN.
- Do not label a 30-day list import historical or entire CRM complete.

## H. Evidence manifest, code delta, residuals

Cite actual command paths and output files, code SHA and fixture SHA, file hashes, source-query digests, logs redacted of personal fields and secrets, the database identity under test, an exception ledger, and any PR URL.

The exception ledger is `open_exceptions.json` from the runner: one row per distinct signal, with `level`, `reason`, and `count`. Copy it here and into `receipt.json`. Include warnings that rode along on imported rows. A held, failed, or skipped count with an empty ledger means the run did not pass, even when the 4,876 equation closed. `checkpoint_rows_missing_signals` and `dispositions_without_a_source_reason` are both 0 on a pass. Do not summarize a reason as its class name or as its `placement`. If the terminal log is truncated, `crm_checkpoint.jsonl` is the authority. Do not start a second clone to recover a reason that is already in that file.

**ERP partner acceptance:** NOT_RUN / PASS / PARTIAL / BLOCKED / FAIL.  
**ERP commercial-document acceptance:** NOT_RUN / PASS / PARTIAL / BLOCKED / FAIL.  
**CRM source-cohort import acceptance:** NOT_RUN / PASS / PARTIAL / BLOCKED / FAIL.  
**Operator-approved links acceptance:** NOT_RUN / PASS / PARTIAL / BLOCKED / FAIL.  
**Full historical provider census:** NOT_PROVEN until explicitly evidenced.  
**Next one necessary action:** UNKNOWN.
