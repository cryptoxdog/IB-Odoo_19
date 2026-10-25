# Post-run evidence: ERP partners, ERP commercial documents, then full VanillaSoft CRM

Contract revision `v2.3`. Observed on clone `odoo_test_night1021`. The runner exited 0. The class equation closed. Five contacts did not persist, and unresolved material names stayed as signals on imported rows. This report records that result. It does not ask for a second clone.

**Observed date/UTC:** 2026-10-22T05:49:33Z through 2026-10-22T08:04:13Z  
**Staging SHA under test:** `607a64b897cb73b19adeea1b867990c5bf556189`  
**Enterprise fixture / owned clone:** `odoo_test_tpl_ee_c9e8a81f52f23680` / `odoo_test_night1021` (owner `w2495f48767`, parity ee)  
**Private input SHA256 validation:** crosswalk `9aa6fcd0eee9fedf106c23090fa32b24c2faacc1576531c4f4fcc846663b72c1` verified before the clone. Census file 4,876 rows (763 YES, 18 NO, 4,095 PENDING).  
**Final verdict:** PARTIAL

## Bottom line

The fresh clone started with empty CRM source rows and empty ERP markers. Partners-only wrote no commercial documents. The second ERP pass compiled 7,728 `plasticos.transaction` rows and left native sale orders, purchase orders, and invoices on the same clone. All 4,876 frozen VanillaSoft ids received one placement. `crm.lead` is 4,123, matching the lead placement. Provider refs are 4,867, matching imported rows. Five pending contacts failed phone validation and have no lead. Material-name mismatches were recorded and did not change placement.

## A. Source and policy checks

| Source census | Observed | Evidence reference |
| --- | ---: | --- |
| Historical VanillaSoft frozen ContactIDs | 4,876 | `crm_id_census.csv` in the gitignored work directory |
| Live API ContactIDs fetched from that list | 4,872 attempted; 4 failed were not fetched (duplicate YES) | checkpoint `duplicate_skipped` |
| Operator YES / NO / PENDING | 763 / 18 / 4,095 | workbook `CRM STATUS - ALL`, joined to every checkpoint row |

Raw ERP contact eligibility counts were not printed as a separate census. The partner-pass service totals are in section C. Inactive exclusion was the code already on this SHA. No importer file was edited for this run.

## B. Exactly one clone and ordered stage proof

| Checkpoint | `sale.order` | `purchase.order` | `account.move` | `plasticos.transaction` | `crm.lead` | Provider refs | Calls | Table rows | Legacy ERP xmlids |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Before imports | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| After VanillaSoft | 6,951 | 7,054 | 20,310 | 7,728 | 4,123 | 4,867 | 152,967 | 0 | 61,876 |

Gate A printed the before-import zeros, including `plasticos_crm_external_ref`, `plasticos_crm_call_event`, and `plasticos_crm_external_table_row`. The after row is `psql` on `odoo_test_night1021` after the runner finished. Company `res.partner` rows are 2,567 and include seed companies, so that count is not the imported counterparty count. Commands were `scripts/test_env.sh clone`, then `test_env.sh run` for partners-only `make import-erp`, commercial `make import-erp` with `ERP_REQUIRE_EMPTY=0`, then `shell --no-http` of `import_4876.py`. No hosted write. `make import-vanillasoft` was not used.

## C. ERP active-only import results

Service line at 2026-10-22T05:50:26Z, partners only. Rejected 0 on every partner layer. Transactions and lines stayed 0.

| Layer | Created | Updated | Skipped | Rejected |
| --- | ---: | ---: | ---: | ---: |
| Counterparties | 1,300 | 0 | 0 | 0 |
| Locations | 1,266 | 1,297 | 39 | 0 |
| Contacts | 2,615 | 0 | 1,116 | 0 |
| Contact roles | 2,498 | 0 | 180 | 0 |
| Salespersons | 0 | 818 | 97 | 0 |

## C2. Commercial document import (second ERP write)

Service line at 2026-10-22T06:23:14Z. Partner layers were skipped (1,300 / 2,602 / 3,731 / 2,678 / 915), which matches the first pass already being present. The importer summary does not split created sale orders, purchase orders, and invoices. Post-run table counts are in section B.

| Document | Created | Updated | Skipped | Rejected |
| --- | ---: | ---: | ---: | ---: |
| Transactions (`plasticos.transaction` compiled) | 7,728 | 0 | 0 | 645 |
| Transaction lines | 10,525 | 0 | 53 | 863 |

`plasticos.transaction` count after the run is 7,728, the same as created. Status: PARTIAL, because 645 transactions and 863 lines were rejected and those reject reasons are in the Odoo log, not in a separate ledger.

## D. VanillaSoft full source ID reconciliation

Checkpoint join to the census. Each of the 4,876 ids appears once.

| Operator decision | Frozen source IDs | `erp_person` | `active_company` | `crm_lead` | Held | `genuine_failed` | `duplicate_skipped` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| YES | 763 | 737 | 7 | 15 | 0 | 0 | 4 |
| NO | 18 | 0 | 0 | 18 | 0 | 0 | 0 |
| PENDING | 4,095 | 0 | 0 | 4,090 | 0 | 5 | 0 |
| **TOTAL** | **4,876** | **737** | **7** | **4,123** | **0** | **5** | **4** |

`imported + held + genuine_failed + duplicate_skipped = 4,867 + 0 + 5 + 4 = 4,876`. `imported = 737 + 7 + 4,123 = 4,867`. Held is 0. `checkpoint_rows_missing_signals = 0`. `dispositions_without_a_source_reason = 0`.

The five failures are pending ids `1049157719`, `1079111169`, `1166741035`, `654802349`, and `906084410`. Each signal is `Mobile must be a 10-digit US number`. No lead was created for them.

## E. Approved identity

The pinned digest matched before any write. YES placements are the expected split: 737 people, 7 active-company placements, 15 blank-CT leads, 4 duplicate ids not fetched. The 15 blank-lead warnings and the 7 active-company warnings are in the checkpoint. No second clone was started.

## F. CRM field and history reconciliation

| Concern | Applied / preserved | Unknown / held | Evidenced failure | Notes |
| --- | ---: | ---: | ---: | --- |
| Email / direct / mobile / supplemental phones |  |  | 5 | Invalid mobile stopped the contact write |
| Ambiguous/unmapped material and form cases | 3,019 imported contacts still carry a signal |  | 4,002 unresolved-material signals | Placement stayed imported |
| Real provider call events and custom tables | 152,967 call events |  |  | `plasticos_crm_external_table_row` stayed 0 |

Owner, stage, and polymer workbook oracles were not compared in this pass.

## G. Cohort completeness is not live history completeness

- Historical snapshot `4876` coverage: PARTIAL. Every id is classified. Five did not persist.
- Live provider ContactID fetch coverage for these 4876: 4,872 fetched; 4 duplicate YES ids were not fetched by design.
- New or deleted live-provider ContactIDs since the snapshot: NOT_PROVEN.
- Complete historical contact census beyond the snapshot: NOT_PROVEN.
- Complete call history: NOT_PROVEN. Call events exist for fetched contacts. That is not a full-history proof.

## H. Evidence manifest and residuals

- Log: `Current Work - IGNORE/erp-then-vs-full-crm/overnight.log` (gitignored). The Cursor terminal capture stopped near progress 3,025; the tee log and `crm_checkpoint.jsonl` contain all 4,876 rows and the finish line.
- Runner finish: `finished processed_this_run=4876 classes={"duplicate_skipped": 4, "genuine_failed": 5, "imported": 4867}`.
- Placements: `{"active_company": 7, "crm_lead": 4123, "duplicate_skipped": 4, "erp_person": 737, "genuine_failed": 5}`.
- Signal families, counted from the checkpoint without copying note text: 4,002 unresolved material, 15 blank-CT lead warnings, 7 active-company warnings, 5 invalid-mobile errors, 5 dependent-write warnings on those same five failures, 4 second-id warnings.
- The raw `open_exceptions.json` stays in that gitignored directory. Many unresolved-material strings are free-text call notes with names, phone numbers, and addresses, so they are not copied into this report.
- No addon code change. No pull request.

**ERP partner acceptance:** PASS.  
**ERP commercial-document acceptance:** PARTIAL.  
**CRM source-cohort import acceptance:** PARTIAL.  
**Operator-approved links acceptance:** PASS for the YES split above.  
**Full historical provider census:** NOT_PROVEN.  
**Next one necessary action:** Read the five mobile failures and the transaction/line reject lines in the overnight log. Leave this clone in place.
