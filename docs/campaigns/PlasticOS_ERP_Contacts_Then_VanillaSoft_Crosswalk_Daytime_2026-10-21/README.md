# Cursor delegation: ERP contacts, then VanillaSoft crosswalk only

**Status:** Daytime contact slice. Not a substitute for the overnight pack.  
**Revision:** `daytime-v1` in `CURSOR_EXECUTION_CONTRACT.md`. That contract is the task. This page does not override it.  
**Overnight pack, unchanged:** `../PlasticOS_ERP_Then_Full_VanillaSoft_Cursor_Delegation_v2_2026-10-21/` (partners, then commercial documents, then all 4,876 VanillaSoft IDs).

**Why this pack exists:** On 2026-10-21 the partners-only ERP import of the full active contact set finished in one shell. The commercial worksheet pass (`sale.order`, `purchase.order`, `account.move`, `plasticos.transaction`) is the long ERP stage. Fetching all 4,876 VanillaSoft IDs, including call history, is the long CRM stage. This pack drops both. It imports every eligible active ERP contact, then only the 763 crosswalk IDs.

## How to run

1. Read `CURSOR_EXECUTION_CONTRACT.md`. Run it on one new owned clone of `config/test_env_fixture.conf` (`odoo_test_tpl_ee_c9e8a81f52f23680`). Do not reuse `odoo_test_w2495f48767` or a clone that is already running the overnight pack.
2. Do not copy private files into this directory. The crosswalk already lives in the overnight pack. Verify its SHA256 in `INPUT_MANIFEST.json`, then copy that one file into gitignored `Current Work - IGNORE/erp-contacts-vs-crosswalk/`. Copy `import_crosswalk.py` there too. The container reads `/mnt/extra-addons/Current Work - IGNORE/erp-contacts-vs-crosswalk/`.
3. Order: prove CRM and commercial documents empty, partners-only ERP import with `ERP_LIMIT` unset, then `import_crosswalk.py`. Do not start a second ERP write.
4. Fill `REPORT_TEMPLATE.md` and `RECEIPT_TEMPLATE.json` from the run. Save sanitized copies under `docs/reports/evidence/erp-contacts-then-vanillasoft-crosswalk-<date>/`.

## What this run writes

- Eligible active ERP companies, addresses, contacts, roles, and salespersons. Inactive contacts stay out. `skipped` contact rows are aliases or non-person rows, not dropped source rows. `skipped` address rows are folded onto the company.
- 763 VanillaSoft IDs from the pinned crosswalk, through `upsert_contact_external_id`. Approved binds land on `res.partner`. They do not create `crm.lead` rows.

## What this run does not write

- `sale.order`, `purchase.order`, `account.move`, `plasticos.transaction`.
- The 18 rejected links and the 4,095 pending VanillaSoft IDs. Those stay in the overnight pack.
- Owner, stage, or polymer maps. This cohort does not create leads, so those lead-field oracles are out of scope here.

**Outcome requested:** one disposable Enterprise clone, the full active ERP contact set, the 763 crosswalk binds, and an honest disposition. Held and failed rows are reported and are not counted as imported.
