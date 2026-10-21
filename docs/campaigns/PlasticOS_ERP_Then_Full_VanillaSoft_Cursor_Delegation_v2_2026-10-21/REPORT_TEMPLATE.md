# Post-run evidence: ERP partners, ERP commercial documents, then full VanillaSoft CRM

Contract revision `v2.1`. Importer outcomes `created` / `updated` / `unchanged` with a persisted provider ref are imported. Approved misses caused by the active-only rule are `held`. `duplicate_rejected`, exceptions, and fetch errors are `genuine_failed`. Do not invent importer states.

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

No inactive source person, inactive alias, phone line, or note from an ineligible row. This pass writes no `sale.order`, `purchase.order`, `account.move`, or `plasticos.transaction`. Record the active-contact selection change (`parse_bool(IsActive) is True` only; blank is excluded; ineligible CT_IDs are not aliases).

## C2. Commercial document import (second ERP write)

| Document | Source worksheets in scope | Created | Updated | Unchanged | Rejected | Compiled `plasticos.transaction` | Evidence |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `sale.order` | | | | | | | |
| `purchase.order` | | | | | | | |
| `account.move` | | | | | | | |

Partner census versus section C must be unchanged except idempotent `unchanged` rows. `plasticos.transaction` rows exist only as the sale-order confirm/compile result of `native_document_import.realize`. Status: NOT_RUN / PASS / PARTIAL / BLOCKED / FAIL.

## D. VanillaSoft full source ID reconciliation (MUST SUM TO 4,876)

| Operator decision | Frozen source IDs | Valid imported/bound | Source ID fetched but held | Material failure | Why held / failure |
| --- | ---: | ---: | ---: | ---: | --- |
| YES, exact approved ERP-person link | 763 | UNKNOWN | UNKNOWN | UNKNOWN | |
| NO, rejected ERP candidate / normal CRM lead path | 18 | UNKNOWN | UNKNOWN | UNKNOWN | |
| PENDING, not approved for ERP person matching | 4,095 | UNKNOWN | UNKNOWN | UNKNOWN | |
| **TOTAL** | **4,876** | **UNKNOWN** | **UNKNOWN** | **UNKNOWN** | |

Check `imported + held + genuine_failed = 4,876`, no source ID twice. Imported means orchestrator `created`, `updated`, or `unchanged` plus one persisted provider ref. Approved `failed` from a missing excluded ERP person is `held` and has no lead. `duplicate_rejected`, exceptions, and fetch errors are `genuine_failed`. `crm.lead` need not equal 4,876.

## E. Approved identity and previous 28 exceptions

- Pinned crosswalk digest verified? UNKNOWN. Approved YES: 763 across 716 ERP CT_IDs. Actual exact links: UNKNOWN. Shared alias groups: 45 ERP people / 92 VS IDs baseline, independently verify outcome.
- Previous run: 735 bound and 28 `no_erp_person` (27 CT_IDs). New bound count: UNKNOWN. Each historical failure classified by raw company status, placeholder key, missing parent or genuine eligible missing person: UNKNOWN.
- Wrong approved person links: UNKNOWN; approved link creating duplicate `res.partner`: UNKNOWN; NO candidate bound to rejected CTID: UNKNOWN; pending source IDs falsely matched to ERP: UNKNOWN.

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

**ERP partner acceptance:** NOT_RUN / PASS / PARTIAL / BLOCKED / FAIL.  
**ERP commercial-document acceptance:** NOT_RUN / PASS / PARTIAL / BLOCKED / FAIL.  
**CRM source-cohort import acceptance:** NOT_RUN / PASS / PARTIAL / BLOCKED / FAIL.  
**Operator-approved links acceptance:** NOT_RUN / PASS / PARTIAL / BLOCKED / FAIL.  
**Full historical provider census:** NOT_PROVEN until explicitly evidenced.  
**Next one necessary action:** UNKNOWN.
