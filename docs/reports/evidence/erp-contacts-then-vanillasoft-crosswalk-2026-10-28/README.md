# Post-run evidence: ERP contacts, then VanillaSoft crosswalk

Contract revision `daytime-v2`. This pack does not include commercial documents or the VanillaSoft IDs outside the pinned crosswalk. Those belong to the overnight pack. `make import-vanillasoft` was not run.

**Observed date/UTC:** 2026-10-28T21:34:01Z through 2026-10-28T21:50:36Z  
**Branch and SHA under test:** `feat/crm-lead-material-identity` at `9ce3a302cc472c8865d4b40235efbd24e1f9a4f1`  
**Worktree:** dirty. The clone upgraded the PlasticOS roster from the working tree, including the uncommitted `plasticos_crm_sync` crosswalk file.  
**Enterprise fixture / owned clone:** `odoo_test_tpl_ee_c9e8a81f52f23680` cloned to `odoo_test_day1028`  
**Crosswalk SHA256:** `9aa6fcd0eee9fedf106c23090fa32b24c2faacc1576531c4f4fcc846663b72c1`  
**Final verdict:** FAIL

## Bottom line

The fresh clone started with no CRM rows and no commercial documents. The partners-only ERP import closed its summary equation, passed every layer validator, wrote no inactive-contact XMLID, and left `sale.order`, `purchase.order`, `account.move`, and `plasticos.transaction` at zero. The live pass fetched all 759 pinned crosswalk IDs. 737 of them bound to the ERP person named by their CT_ID, with zero marker mismatches. Seven more, whose CT_ID is blank, were placed on an active company and created seven `res.partner` rows. Fifteen more, also with a blank CT_ID, were created as `crm.lead` rows. That lead growth fails the daytime gate. The overnight 4,876-ID import was not run.

## A. Source and policy checks

| Source census | Observed | Evidence reference |
| --- | ---: | --- |
| Raw ERP `Contact` rows read by `erp_reader` | 4084 | `erp_contact_census.csv` |
| Counterparties in the live table | 1504 | same |
| Counterparties in the partners-only payload | 1300 | importer log |
| Eligible explicitly active contacts, split out from aliases | not split by the importer log | |
| Excluded inactive contacts | 2 appear in the 1000-row error sample; the other 291 rejections are outside that sample | summary `records_rejected` 1291 |
| Active contacts excluded by parent status / placeholder / missing parent | sample only: `missing_parent_key` 19, `unresolved_counterparty` on contacts 332 | |
| Alias CT_IDs pointing at an already created person | contacts skipped 1116, not split further | layer log |
| Active contacts routed to a company phone or a site mailbox | not split | |
| Pinned crosswalk VanillaSoft IDs | 759 | file SHA above |
| Distinct ERP CT_IDs in the crosswalk | 691, plus 22 blank CT_IDs | file census |
| Crosswalk IDs fetched from the live API | 759 | live checkpoint, `processed_this_run=759` |

The receipt template still says 763 IDs and 716 distinct targets. The loader refuses any file whose digest is not the pin above, and that file contains 759 VanillaSoft IDs and 691 distinct ERP CT_IDs. This run used that file. The 18 rejected links and the 4,095 pending IDs were not fetched.

Inactive contact XMLIDs after the ERP import: 0.

## B. One clone, three checkpoints

| Checkpoint | Business partners | Contact XMLIDs | `sale.order` | `purchase.order` | `account.move` | `plasticos.transaction` | `crm.lead` | Partner refs | Calls | Evidence |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Before imports | 10 (1 company, 9 people; the fixture) | not measured | 0 | 0 | 0 | 0 | 0 | 0 | 0 | baseline shell |
| After partners-only | 5191 | 3734 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | after-ERP shell |
| After crosswalk pass | 5198 | 3734 | 0 | 0 | 0 | 0 | 15 | 744 | 52156 | after-CRM shell and Postgres |

Commercial documents stayed at the fresh-clone zero. Fixture fingerprint `840872d079d2c0ef99771994de01ceb64e7c05388edc04fb52a722ee83e41c02`. Clone owner `w2495f48767`, parity `ee`. ERP SQL `erp_SM` on `cie-sql-proof` was `READ_ONLY`. The password and the VanillaSoft key were not printed. The key was copied onto this clone's `ir.config_parameter` (length 82). Project `139705` is the connection default.

An earlier checkpoint file already in `Current Work - IGNORE/erp-contacts-vs-crosswalk/` made the first shell exit 0 with `processed_this_run=0`. That file was from another run. It was moved aside. The numbers in this pack are the second shell, which started from an empty checkpoint and fetched all 759 IDs.

## C. ERP contact import

| Layer | Created | Updated | Unchanged (`skipped`) | Rejected in the layer counter |
| --- | ---: | ---: | ---: | ---: |
| Counterparties | 1300 | 0 | 0 | 0 |
| Addresses | 1266 | 1297 | 39 | 0 |
| Contacts | 2615 | 0 | 1116 | 0 |
| Roles | 2498 | 0 | 180 | 0 |
| Salespersons | 0 | 914 | 2 | 0 |

The five layer counters sum to created 7679, updated 2211, unchanged 1337. The summary adds rejected 1291. `12518 = 7679 + 2211 + 1337 + 1291`. Duplicates 0. `final_status` is `partial` because those 1291 rows were rejected. The published error list holds 1000 of them. In that sample: Address unresolved counterparty 366, Contact unresolved counterparty 332, Contact missing parent key 19, Contact inactive 2, role unresolved contact 135, role unresolved 4, salesperson unresolved counterparty 142. The other 291 rejections are counted and their reasons are not in the sample.

Validators passed: database, counterparties, addresses, contacts, roles, salesreps. Exit code 0. `ERP_PARTNERS_ONLY=1`. `ERP_LIMIT` was unset. Transactions created 0.

The importer log did not split address skips into folded-unchanged versus child locations beyond created 1266 / updated 1297 / skipped 39, and it did not split the 1116 contact skips into alias markers versus non-person rows.

## D. Crosswalk reconciliation

The pinned cohort is 759, not the 763 written in the older contract sentences.

| Result | IDs | Notes |
| --- | ---: | --- |
| Imported, partner ref matches `legacy_erp_contact_<CT_ID>` | 737 | outcome `updated`; marker mismatches 0 |
| Imported, blank CT_ID, placed on an active company | 7 | outcome `updated`; partner count rose by 7 |
| Held, target excluded or missing, no lead | 0 | |
| Genuine failure: a `crm.lead` was created | 15 | outcome `created`; signal `created_crm_lead` |
| **TOTAL** | **759** | |

`crm.lead` delta: 15. Provider refs on `crm.lead`: 15. Provider refs on `res.partner`: 744. IDs fetched outside the crosswalk: 0. Call events: 52156. Custom-table rows: 0.

The 15 lead creates fail the gate. The daytime rule is that a missing ERP person is held and creates no lead. This orchestrator imported those 15 as leads.

## E. Approved identity against the previous run

- Pinned digest verified on the file the loader read.
- Shared groups in this file: 44 ERP people covering 90 source IDs. The template's 45 / 92 belongs to the older 763-row file.
- Previous run on the older file: 735 bound and 28 missing. This run bound 737 of 737 non-blank CT_IDs. Held: 0.
- Marker mismatches: 0. The seven new partners are the active-company placements. No second partner was created for a non-blank CT_ID.

## F. What this pack does not score

Owner, stage, and polymer scores belong to the overnight lead pack. This pack created 15 leads, so those scores are still not claimed here.

| Bind detail | Observed |
| --- | --- |
| Call events stored | 52156 |
| Custom-table rows stored | 0 |
| Notes appended on the ERP person | not measured |
| Phone lines added | not measured |

## G. Evidence manifest

| Item | Value |
| --- | --- |
| Clone | `odoo_test_day1028` |
| Module-test clone | `odoo_test_sync1028` |
| ERP summary | `.l9/pr/erp-contacts-day1028-summary.json` (gitignored; totals copied here) |
| Live checkpoint | `Current Work - IGNORE/erp-contacts-vs-crosswalk/crm_checkpoint.jsonl` (gitignored; not published) |
| ERP exit | 0 |
| Live crosswalk exit | 0 |
| Module tests | 0 failed, 0 errors of 73 tests |

**ERP contact acceptance:** PASS. Equation closed, validators passed, inactive-contact XMLIDs 0, commercial documents unchanged.  
**Commercial documents stayed absent:** PASS.  
**Crosswalk cohort acceptance:** FAIL. 759 IDs were fetched and classified, and 15 of them created leads.  
**`crm.lead` stayed empty:** FAIL.  
**Signals retained:** PASS. Every non-imported row has `created_crm_lead`. No row is UNKNOWN.  
**Next one necessary action:** stop `upsert_contact_external_id` from creating a `crm.lead` when the pinned crosswalk has a blank CT_ID, then rerun Gate C on a fresh clone.

## H. Signals kept

The disposition file stores a reason code. It does not store the unresolved-material text, because that text includes a personal name and note text.

| Level | Reason | Rows | What it changes |
| --- | --- | ---: | --- |
| WARNING | `created_crm_lead` | 15 | These rows are `genuine_failed`. A lead was created. |
| WARNING | `active_company` | 7 | Stays imported. The person was placed on the active company. |
| ERROR | `unresolved_material` | 7 | Stays on those same seven company placements. The source phrase is withheld. |
| UNKNOWN | outcome produced no reason | 0 | |

Checkpoint rows missing a `signals` key: 0.

## Tests that ran

Pure Python, no VanillaSoft and no ERP writes: 471 passed. That set includes the in-memory full-import tests. It does not call the live API and it does not load the 4,876-ID census.

Odoo runtime, on `odoo_test_sync1028`, a different clone from the import: `plasticos_partner_import` and `plasticos_crm_sync`, 0 failed, 0 errors of 73 tests. The module stat lines in that log say 68 and 17. The pass/fail line and the test-env receipt say 73, and those are the numbers this pack uses.

`tests/contracts/test_crm_lead_contracts.py` imports `odoo.addons` and does not live in either module's test package, so neither runner collected it.

`make import-vanillasoft` was not run.
