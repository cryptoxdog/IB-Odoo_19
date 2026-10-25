# Reject and field-parity findings for the existing night clone

Read-only. No second import, no database write, no provider API call, and no publication.

**Checkout:** `607a64b897cb73b19adeea1b867990c5bf556189` on local `Staging`.  
**Remote `origin/Staging`:** `e78af874604890f8adb6b049694f93c48311eab4`. This SHA is 13 commits ahead of that remote tip, and no remote branch contains it. A GitHub lookup of this SHA against current `origin/Staging` does not resolve.  
**Clone:** `odoo_test_night1021`, asserted clone of `odoo_test_tpl_ee_c9e8a81f52f23680`, parity ee, fingerprint `c9e8a81f52f23680595b63d3f5ce3730f95db97195384243ef2fd10b35156c30`.  
**Source read:** `erp.reader.load_payload` executed the projection scripts on `host.docker.internal/cieTrade_SM` as `erp_reader`. SELECT only.  
**Final verdict:** PARTIAL. The 645 and 863 reconcile. Five CRM rows did not persist. Owner assignment did not follow the locked email map. Stage landing followed the installed map, including the three collapses below.

## Checkout cleanliness

Importer, order resolver, source reader, document writer, CRM orchestrator, identity module, stage map, and material normalizer blobs match this commit. The working tree is otherwise dirty in docs and governance files. The cohort runner `import_4876.py` in the campaign folder is a local edit: worktree blob `60d92f76ead4296aeef77ebae015e78aac2f7c5b`, commit blob `5a9b8606bea1ea1fde8b8af4ee6e5dfd72119bba`. The copy that ran matches that worktree file (`sha256 ef154ce1f90c218f4efcbd5603221ff1c3879ecf96bdaff47bf47476b8832d64`).

## Commercial denominator

Unique source worksheet lines: **8,373** `BuySellNo` values and **11,441** `DetailID`s. Compiled `plasticos.transaction.name` values: **7,728**. Extra compiled names outside that universe: **0**.

`8,373 - 7,728 = 645` missing worksheets. The census `worksheets_rejected` list is only the **88** savepoint rollbacks. It is not the full 645.

| Primary cause | Worksheets | What the source and clone show |
| --- | ---: | --- |
| `purchase_only_no_sale` | 465 | No sale header from `header_for_line`. A purchase header exists. The clone holds a draft purchase order. No sale order and no compiled transaction. |
| `no_both_links` | 92 | Neither side resolves a header. No sale or purchase order marker survived. |
| `savepoint_exception` | 88 | Importer anomaly is `ValueError` and the worksheet is in `worksheets_rejected`. 84 of these still had a source sale link. No sale or purchase marker survived, so the write was rolled back. |
| `sale_confirmation_blocked` | 0 | |
| `sale_compiled_elsewhere_or_identity_collision` | 0 | |
| `confirmed_but_not_compiled` | 0 | |
| `other` | 0 | |
| `unknown` | 0 | |
| **Total** | **645** | |

Source `22_po.sql` does not project a purchase-order status. Clone purchase state is `draft` for all 465 purchase-only worksheets. Dates use source `BuySell.OrderDt`. Every missing worksheet has an `OrderDt`. `unknown` year is 0. `InvoiceDt` is absent on 125 of the 645; that absence is not used as the year.

| `OrderDt` year | Worksheets | Purchase-only | Neither link | Savepoint |
| --- | ---: | ---: | ---: | ---: |
| pre-2020 | 62 | 25 | 3 | 34 |
| 2020-2023 | 263 | 176 | 41 | 46 |
| 2024 | 152 | 130 | 14 | 8 |
| 2025 | 133 | 102 | 31 | 0 |
| 2026 | 35 | 32 | 3 | 0 |
| unknown | 0 | 0 | 0 | 0 |

Status on the 645, via `worksheet_outcome`: closed 511 (`I`), cancelled 127 (`X`), active 7 (`W`, all purchase-only). Partner state uses the active-company projection (`ActiveStatus = 'A'`). A company missing from that set is inactive or absent, not guessed.

Dollar figures are source line sums, one `DetailID` each. Margin is `SAmount - PAmount` on those lines. It is not a ledger gross-profit claim.

| Cause | Sale amount | Purchase amount | Line margin | Customer receipts | Vendor payables | Credit notes (signed) | Unresolved bill rows | Unresolved bill amount |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| purchase-only | 972,320.58 | 887,915.86 | 84,404.72 | 138,162.24 | 1,300,623.88 | -6.00 | 261 | 269,144.49 |
| neither link | 98,252.81 | 86,078.47 | 12,174.34 | 43,169.73 | 65,263.66 | -30.00 | 83 | 65,263.66 |
| savepoint | 225,590.03 | 100,591.19 | 124,998.84 | 196,136.93 | 149,335.40 | -28,413.56 | 169 | 149,335.40 |
| **Total** | **1,296,163.42** | **1,074,585.52** | **221,577.90** | **377,468.90** | **1,515,222.94** | **-28,449.56** | **513** | **483,743.55** |

The census has 1,393 unresolved bill rows in total. 513 of them sit on these 645 worksheets. The other unresolved bills are outside this reject set. Savepoint payable amount `149,335.40` matches the census rollback bucket. Neither-link payable amount `65,263.66` matches the census no-order-link bucket.

Seventeen neither-link worksheets are closed, have no receipts, no payables, and no unresolved bills. They are the only mechanical quarantine screen. No acceptance decision is recorded, so none are quarantined. The 7 open purchase-only worksheets, and 34 of the 35 worksheets dated 2026, still show source payables. They are not quarantine candidates.

Secondary link failures, not a second primary cause: neither-link lines are `blank_key` on both sides (174 sale, 174 purchase). Purchase-only sale failures are `blank_key` 645 and `key_without_order_line` 18.

## Rejected lines are a different count

`10,525 created + 53 skipped + 863 rejected = 11,441` source lines.

| Line cause inside the 863 | Lines | Also neither-side | Notes |
| --- | ---: | ---: | --- |
| `neither_side_link` | 732 | 732 | Counted on worksheets that were not rolled back |
| `worksheet_rolled_back` | 131 | 4 | The 4 overlaps stay in this row, not in the 732 |
| `other` | 0 | 0 | |
| **Total** | **863** |  | |

636 further lines sit on purchase-only worksheets whose transaction was rejected. Those lines were not rejected. They are inside the 10,525 created or 53 skipped. Do not add 645 and 863, and do not add these 636 to the 863.

## CRM field parity

Checkpoint, census, and frozen snapshot are the same 4,876 ids. Every checkpoint row carries crosswalk `sha256 9aa6fcd0eee9fedf106c23090fa32b24c2faacc1576531c4f4fcc846663b72c1`.

Persisted refs: 4,123 leads and 744 person refs (737 ERP people + 7 active-company placements). Person refs have no lead on purpose.

**Owners.** The locked workbook has 12 locked rows: 11 source owner emails and 1 blank-owner fallback, covering 8 target logins. The installed writer does not use that map. It sets `crm.lead.user_id` only when exactly one user name equals the provider owner name. All **4,123** leads have an empty `user_id` (`exact 0`, `wrong 0`, `unexpected 0`, `unverified 0`, `empty 4,123`). Among the 4,108 persisted NO/PENDING leads, the snapshot has **4,053** email-shaped owners and **55** blanks. That matches the stated expectation and explains the empty result: an email does not match a user name, and the blank fallback login was not applied.

**Stages.** All 4,123 leads match the installed `STAGE_MAPPING`. The review sheet's 12 proposals are marked review, not approved, and were not installed. Against that installed map:

- `1= Currently Working With` landed on Active Supplier, and that stage has `is_won=True`: **290** leads.
- `4=Unqualified` landed on Dead Lead: **996** leads. The review proposal says New, not Dead. The installed map says Dead.
- `2c=Qualified/COLD` and `2=Qualified/Open` landed on Qualified — WARM: **853** leads.

Source ids for those three sets are in the gitignored classify directory, not in this file.

**Polymer.** 4,002 unresolved-material signals on **3,009** source ids. The earlier 3,019 figure is imported rows with any signal, including non-material warnings. Signal classes:

| Class | Signals | Source ids |
| --- | ---: | ---: |
| `unknown_common_code` | 1,806 | 1,770 |
| `comma_composite` | 1,009 | 868 |
| `unrecognized_phrase` | 611 | 543 |
| `form_only` | 444 | 308 |
| `freeform_narrative` | 129 | 125 |
| `facility_unresolved` | 3 | 3 |
| `missing_master` | 0 | 0 |
| `deferred_operator_decision` | 0 | 0 |
| `other` | 0 | 0 |

No named list of 3 polymer aliases or 11 deferred tokens is in this checkout. That comparison is **UNKNOWN**. None of the 24 exact phrases in the normalizer appear inside the unresolved signals. The clone currently has 369 material profiles and 34 polymer masters. Those counts are not attributed to this run. No new grade, owner, form, facility, or polymer master was inferred.

**Mobile.** The five failed ids have snapshot digit lengths 9, 9, 9, 9, and 8. Three have a non-US country token. None persisted a lead. The live provider API was not read. The constraint still requires 10 US digits after an optional leading 1. It was not changed.

## What was not done

No clone, import, module, crosswalk edit, pull request, merge, or deploy. Row-level billing rows and the stage id lists stay in `Current Work - IGNORE/erp-then-vs-full-crm/classify/`.
