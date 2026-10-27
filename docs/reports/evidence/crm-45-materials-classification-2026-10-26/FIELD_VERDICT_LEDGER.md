# CRM-4 / CRM-5 field verdict ledger

Synthetic Enterprise readback on the runtime commit. This is not a 96-field historical acceptance.

## Receipt

| Item | Value |
| --- | --- |
| Runtime commit | `28af585274cdfdf62170f3c532dd8499092cdb67` |
| Stack ancestor (PR #312 head) | `2fe9627c14da680d3ca1eae258aebf9ab69b5c91` |
| Branch | `feat/crm-45-materials-and-crm-classification` |
| Modules | `plasticos_crm_sync` `19.0.1.9.7`, `plasticos_crm_bridge` `19.0.3.4.11` |
| Database | `odoo_test_w6cb014f012` |
| Template | `odoo_test_tpl_ee_c9e8a81f52f23680` |
| Fingerprint | `c9e8a81f52f23680595b63d3f5ce3730f95db97195384243ef2fd10b35156c30` |
| Odoo | `19.0-20261015` |
| PostgreSQL | `15.19` (Debian 15.19-1.pgdg13+2). Not PostgreSQL 16. |
| Tree | `dirty: false` at the runtime commit |
| Enterprise ORM | 75 tests, 0 failed, 0 errors. Scope `plasticos_crm_bridge,plasticos_crm_sync`. |
| Receipt | `.l9/runtime/test-env/odoo_test_w6cb014f012.test-receipt.json` |
| Pure classification | `tests/test_crm_sync_classification.py`: 25 passed |

The worktree has no `odoo-enterprise` symlink. The run set `ODOO_ENTERPRISE_PATH` to the admitted checkout `/Users/ib-mac/Dropbox/Repo_Dropbox_IB/IB-Odoo_19/odoo-enterprise`. The fixture was not rebuilt.

A docs-only commit may follow this file. It does not change the modules under test. The receipt head stays the runtime commit above.

## What the synthetic run read back

- Exact `Buyer` and `Supplier` tokens link native `crm.tag` records on an existing `crm.lead`. Replay does not add a second link. `res.partner.category`, `company_role`, `supplier_rank`, `customer_rank`, and Odoo `company_type` stay unchanged.
- `End User` is `BLOCKED_ROLE_TOKEN`. A person with no lead stays lead-free and records `BLOCKED_NO_CRM_LEAD`.
- `Manufacturer` links the existing manufacturer category on one verified company. `Broker` is `BLOCKED_COMPANY_TYPE_SEMANTIC_OVERLAP` when `company_role` is already broker. `Grinder_Processor` links `Grinder/Processor` after that role is clear.
- `2a=Qualified/HOT` uses the existing hot stage. `2c=Qualified/COLD` and `7=Do Not Call` stay off Warm and Dead. An existing hot lead is not moved by `5=Dead Lead`. An already-won stage is not moved by `1= Currently Working With`. Unapproved statuses record `BLOCKED_STAGE_APPROVAL` and a ContactID-labelled Lead Status line.
- `Materials (MRF's)` `HDPE Drums` becomes HDPE + drums on the lead facility. Two materials plus `Type` `PE` stay HDPE and LDPE. Bare `PE` and `1-7` create no profile and record `BLOCKED_UNRESOLVED`.
- One HDPE section accepts `40000 lbs`, loads `4`, and color `Blue`. A later `2000 lbs`, `5+`, and `Blue, Green` leave the stored weight, loads, and color in place.
- `PP Supersacs` still creates generic PP with an empty form. `Notes (PPS)` does not land on that profile or on the lead description, and records `BLOCKED_PPS_PROFILE_IDENTITY`. Previous Content, Size, and Notes attach only when a profile already contained `supersac` in `freeform_notes`.
- An approved person with one existing facility profile receives HDPE drums and no new lead.

## Field classes

These classes cover source fields 1–96 from the CRM-4/CRM-5 disposition sheet. None of them is a historical population PASS.

| Class | Fields | Verdict |
| --- | --- | --- |
| Inherited CRM-3 identity and contact fields | ContactID, Flagged, Contact Owner, Last Result Code, Last Call Date, Company, First Name, Last Name, Address 1, City, State, Zip Code, Direct, Mobile 1, Country, Email, Lead Source, Location Type, Notes, Location | `INHERITED_NOT_REPROVEN`. Zip Code provider alias and the private crosswalk stay `BLOCKED`. |
| CRM role | Buyer/Supplier | Synthetic tag readback on the fixtures above. Historical rows are not accepted. |
| Company type | Company Type | Synthetic manufacturer, overlap, and grinder alias only. The other registry categories and the historic distinct values are `BLOCKED_COMPANY_TYPE_VALUE` until a private census. |
| Lead status | Lead Status | Four approved mappings remain. Eight unapproved statuses stay `BLOCKED_STAGE_APPROVAL`. The ORM witness covers COLD, DNC, Dead on an existing lead, and Currently Working With on a won stage. |
| Material phrases | Materials, Materials (MRF's), Material (MRP), Material (PPS), Material (LDPE), Material (HDPE), Material (PP) | Synthetic section identity for MRF HDPE drums, two materials, bare PE, 1-7, and generic PP Supersacs. Other phrase shapes are the same section parser and are not a historical PASS. |
| Section type and form | Material Type, Material Form, Type (MRP/PPS/LDPE/HDPE/PP), Form (LDPE/HDPE/PP) | A type hint is used only when the contact has one accepted phrase and the hint is not bare PE or 1-7. Two materials record `BLOCKED_UNRESOLVED` and do not take the hint. |
| Weight, loads, color | Weight and Loads/Month or Loads Per Month for MRP, PPS, LDPE, HDPE, and PP; Color for PPS, LDPE, HDPE, and PP | Synthetic HDPE fill-blank and non-overwrite. Other sections use the same section bucket. Contradictions and inexact values are `APPROVED_SKIP`. |
| PPS context | Previous Content (PPS), Size (PPS), Notes (PPS) | `BLOCKED_PPS_PROFILE_IDENTITY` unless one profile already said supersac. Not copied onto the lead or person comment. |
| Other section notes | Notes (MRP), Notes (LDPE), Notes (HDPE), Notes (PP) | Attached to the one profile of that section when the section has one identity. Contact-description placement is not claimed. |
| Exclusions | Load Ready, ClosedFlag, Team, Call Back Date, Call Back Time, Scheduled Call User, SIC Code, SIC Code Description, NAICS Code, NAICS Code Description, Sales Volume Range, Sales Volume, Employees, Square Footage, Fleet Size, Product (MFR), Truck Size (E), Equipment, Price Quoted and FOB/FAS for MRP, PPS, LDPE, HDPE, and PP, Melt and Density for LDPE, HDPE, and PP, Load Ready (HDPE) | Existing exclusion tests in the 75-test run passed. That is a regression witness for the current filter, not a historical negative readback of every source key. |

## Still blocked

- Private 763:716 mapping, historical API, custom-table, and call census.
- Full 96-field business acceptance and the 43-obligation integration stage.
- Unapproved stage destinations. No new stage was created for them.
- Company-type values outside the ten existing categories, and any category that repeats `company_role`, `facility_role`, or `partner_type_id`.
- PPS context without a pre-existing supersac profile.
- Production import, merge, and deploy. None of those were run.
