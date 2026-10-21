# Cursor execution contract: ERP import, then full VanillaSoft CRM

**Contract ID:** `PLASTICOS-ERP-THEN-VS-FULL-CRM-2026-10-21-v2`  
**Revision:** `v2.1` — corrections against remote `Staging` `e78af874604890f8adb6b049694f93c48311eab4`. Rebind before execution and record the actual SHA. If it is not that commit, stop and reconcile this contract to the new SHA before any write.  
**Target:** https://github.com/cryptoxdog/IB-Odoo_19  
**Runner:** Cursor, existing Odoo 19 Enterprise Docker fixture, restored ERP SQL database (read-only), authorized VanillaSoft API access.  
**Supersedes:** the prior active-only delegation that stopped after a 763-ID mapping pass, and the v2 sentences that excluded commercial documents or told the agent to apply mappings this commit does not implement.

## What changed in v2.1

Checked against the commit above. These replace conflicting sentences later in older copies of this file.

1. **ERP is two ordered writes on one clone, not partners alone.** `ERP_PARTNERS_ONLY=1` is the first write: the five partner layers, with inactive contacts kept out. It must leave `sale.order`, `purchase.order`, `account.move`, and `plasticos.transaction` unchanged. The second write is the same `make import-erp` **without** `ERP_PARTNERS_ONLY` and **without** `ERP_LIMIT`. On this commit that path runs partner stages again, then `plasticos_transaction.models.legacy_erp_import_service._extend_historical_import` → `native_document_import.realize`, which writes `sale.order`, `purchase.order`, and `account.move` and confirms sale orders. Confirmation is what compiles `plasticos.transaction`. Do not hand-build those records and do not add another writer. An unset `ERP_LIMIT` is the full worksheet set (`parse_limit` of empty is `None`). `make import-erp-test` stays forbidden: its default is `LIMIT=25%`.
2. **Inactive contacts are still imported today.** `12_contact.sql` selects every contact. `mapping.parse_bool` returns true for `Y`/`1`/`TRUE`, false for `N`/`0`/`FALSE`, and `None` for blank or any other spelling. `_row_active` treats `None` as active. `_import_person` sets the person active if **any** alias is active and writes `plasticos_transaction.legacy_erp_contact_<CT_ID>` for **every** alias, including inactive ones. An all-inactive person is still upserted with `active=False`. Before the first import, change that selection so a row is eligible only when `parse_bool(IsActive) is True`. Blank or unknown is an exclusion, not an active row. Ineligible `CT_ID`s are not people and not aliases. Mixed groups import from eligible rows only. Company scope stays `ActiveStatus='A'` in `10_counterparty.sql`, including its placeholder exclusions. Read the real `IsActive` spellings from the read-only source before coding, so an unexpected true spelling is not dropped as unknown. Bump `plasticos_partner_import` with the change. `scripts/test_env.sh run` upgrades the PlasticOS roster on the clone before the command; that upgrade is what loads the bump. Do not `make update-all`.
3. **The 4,876 CRM pass is not `make import-vanillasoft`.** That target calls `SyncOrchestrator.run_full_import` with a modified-after floor. `scripts/test_env.sh run` accepts it only when both `VANILLASOFT_CALL_FLOOR` and `VANILLASOFT_CONTACT_FLOOR` are set. A floor older than about 30 days returns HTTP 400. Do not run it, and do not call a 30-day run full. The cohort pass is `scripts/test_env.sh run <owned-clone> -- shell --no-http` with stdin, one `upsert_contact_external_id` per frozen ContactID. The October 18 script `docs/reports/evidence/crm-erp-approved-identity-2026-10-18/scripts/vs_identity_run.py` is the pattern; extend it from the 763 approved IDs to all 4,876. `run` upgrades the roster with stdin discarded, then the shell inherits the pipe.
4. **Report outcomes are a translation, not new importer states.** `upsert_contact_external_id` / `_upsert_lead` classify `created`, `updated`, `unchanged`, `duplicate_rejected`, or `failed`. An approved ID whose ERP person is missing is `failed`, not a native `held`. In the receipt, `created`/`updated`/`unchanged` with one persisted provider ref count as imported. Approved `failed` because the active-only import excluded that person counts as `held`, not imported. `duplicate_rejected`, exceptions, and provider fetch errors count as `genuine_failed`, not imported.
5. **Do not add owner, stage, or polymer mappers.** Owner assignment on this commit is `_lead_vals_from_dto`: `user_id` is set only when exactly one active-search `res.users` name equals `dto.owner_name` case-insensitively; otherwise it stays empty. Stage comes from `plasticos_crm_bridge` `STAGE_MAPPING`, otherwise `plasticos_crm_bridge.stage_new`. Materials go through the existing normalizer and only attach when one facility profile already exists. The owner, stage, and polymer workbooks are audit oracles. Score what the importer wrote. Mismatches are field gaps. Do not create users, stages, polymer masters, or an email crosswalk in this run.
6. **The crosswalk file must be on the compose mount.** `load_crosswalk_map` reads a host path inside the container. The repo is mounted at `/mnt/extra-addons`. A path outside the repo is invisible there. Copy the byte-exact crosswalk and a no-PII ID census into gitignored `Current Work - IGNORE/erp-then-vs-full-crm/`. Set `plasticos_crm_sync.approved_contact_crosswalk` to the in-container path `/mnt/extra-addons/Current Work - IGNORE/erp-then-vs-full-crm/03_APPROVED_CONTACT_CROSSWALK.csv`. This campaign directory is untracked and is not gitignored. Do not `git add` it or `PRIVATE_INPUTS/`.

## Outcome

On **one fresh clone of the pinned Enterprise fixture**, in this order:

1. **Partners.** Eligible explicitly active companies and contacts through `make import-erp` with `ERP_PARTNERS_ONLY=1`. No inactive people, inactive companies, or inactive aliases. No commercial documents yet.
2. **Commercial documents.** The existing full ERP import on that same clone. Native `sale.order`, `purchase.order`, `account.move`, and `plasticos.transaction` rows only as the sale-order confirm/compile result of that extension.
3. **VanillaSoft.** All 4,876 frozen `Flagged=True` ContactIDs through `upsert_contact_external_id`, with the operator identity matrix. This writes CRM. It is not a spreadsheet reconciliation and not a 763-ID pass.
4. **Reconcile.** Every source ID once, plus partner, document, and CRM counts.

**Meaning of "full" for CRM:** all 4,876 IDs in the verified October 13 snapshot, plus a reported check of whether the live provider has additions or deletions after that snapshot. The snapshot is not proof of current provider history.

## Nonnegotiable boundaries

- ERP source is the restored read-only SQL database through `make import-erp` / the projection reader. No second ETL, no frozen grid as runtime authority, no source writes, no retired vendor UI.
- One disposable clone from `config/test_env_fixture.conf` (`TEMPLATE=odoo_test_tpl_ee_c9e8a81f52f23680`) via `scripts/test_env.sh`. Do not build or rename another template. No hosted Staging, Production, or Odoo.sh writes.
- Every Odoo write goes through `scripts/test_env.sh run <owned-clone> -- ...` after `assert-clone`. Bare `docker compose` against the business database `odoo` is a failure.
- CRM cohort is all 4,876 `Flagged=True` IDs, including Unqualified, Do Not Call, Prison, and `ClosedFlag`. Do Not Call is a contact restriction, not an ERP `IsActive` filter and not a reason to drop the ID. Never place a call.
- No fuzzy ERP person linking. Do not promote the 4,095 pending IDs. The 18 rejected links never attach. Preserve provider ContactID. Never create or relink a `res.partner` to raise a match rate.
- No new Odoo fields, models, stages, or material masters. No new owner-email map.
- One full two-stage ERP load and one 4,876 CRM pass. No second full provider replay. A targeted read proves uniqueness.
- Code changes only where this revision says they are required (the active-contact selection, and a checkpoint shell script under `Current Work - IGNORE/`). One `make pr` to `Staging` only if addon code changes. No merge and no deploy. The shell script and private inputs stay out of Git.

## 0. Verify private inputs before any database write

| Input | Purpose | Decision status |
| --- | --- | --- |
| `CRM Leads - VanillaSoft - Scrap-Management(1).csv` | Immutable 4,876-row historical snapshot and ContactID census | ID list only. Not a CSV importer |
| `PlasticOS_ERP_VanillaSoft_Operator_Confirmed_Crosswalk_2026-10-16.xlsx` | Operator identity matrix | Authoritative for 763 YES, 18 NO, 4,095 PENDING |
| `03_APPROVED_CONTACT_CROSSWALK.csv` | Allowlist for `plasticos_crm_sync.approved_contact_crosswalk` | SHA256 must equal `f22c707a7b6fceba40a20fa393e0c8887e3f05a8d183865ca28f0ccfc16fede2` |
| `VanillaSoft_4876_Field_Mapping_Resolved_Owners_Stage_Review.xlsx` | Field, owner, and stage audit oracle | Score the importer. Do not install STAGE REVIEW or a new owner map |
| `VanillaSoft_to_Odoo_Polymer_Mapping_Decisions_2026-10-14.xlsx` | Material audit oracle | Score `normalize_material` output. Do not create masters |

Check `INPUT_MANIFEST.json` hashes, 4,876 distinct ContactIDs, all `Flagged=True`, partition `763 + 18 + 4,095 = 4,876`, and crosswalk `763` VanillaSoft IDs / `716` ERP `CT_ID`s. Forty-five ERP people are shared by 92 approved source IDs. Keep those aliases. Do not duplicate the person.

Historical snapshot SHA256: `40df04991e9497b3b723e1478f5ea8b1a5dda74e8a052054beb856d81eb942d9`.

Build `Current Work - IGNORE/erp-then-vs-full-crm/crm_id_census.csv` with columns `vanillasoft_contact_id,decision` only (`YES`/`NO`/`PENDING`). No names, emails, phones, or notes. The shell reads that file. Host-side scoring may read the workbooks.

## 1. Gate A: pinned Enterprise clone, CRM empty

- Record commit SHA, installed modules, and fixture fingerprint from `scripts/test_env.sh status`. The template name must be `odoo_test_tpl_ee_c9e8a81f52f23680`. If that database is absent, stop. Do not set `TEST_ENV_ALLOW_NEW_TEMPLATE`.
- `scripts/test_env.sh clone <new-owned-name>`. Do not reuse the October 18 clone `odoo_test_w2495f48767`.
- Before either import, record `crm.lead`, `plasticos.crm.external.ref`, VanillaSoft sync runs, `plasticos.crm.call.event`, `plasticos.crm.external.table.row`, and business-partner / ERP XMLID baselines. Odoo seed partners are not a CRM import. If this clone already has CRM source rows, drop only this owned clone and clone again.
- ERP SQL login is read-only. VanillaSoft credentials go to the clone's `ir.config_parameter` through the existing secret path. No secrets or customer notes in logs, PRs, or receipts.

**Gate A passes when** the clone is the pinned fixture's and the before-counts show no CRM source contacts.

## 2. Gate B: active-only partners (first ERP write)

- Census `IsActive` and `ActiveStatus` spellings, placeholder IDs, and missing parents on the read-only source. Apply the selection change in "What changed" item 2. Add a focused test: one person with an active row and an inactive alias imports the active row only; the inactive `CT_ID` has no XMLID; a blank flag is excluded.
- Run, with `ERP_LIMIT` unset and `ERP_REQUIRE_EMPTY` left at its default fail-closed value:

```bash
scripts/test_env.sh run <owned-clone> -- \
  make import-erp ODOO_DB_NAME=<owned-clone> \
  ERP_PARTNERS_ONLY=1 \
  ERP_REPORT_PATH=.l9/pr/erp-partners-summary.json
```

- Reconcile the five layers. Policy exclusions are separate from invalid references. Classify each of the previous 28 `no_erp_person` IDs (27 `CT_ID`s) from real parent status. Do not activate a parent to increase matches.

**Gate B passes when** eligible active partners are on this clone, no ineligible contact or alias was written, and `sale.order`, `purchase.order`, `account.move`, and `plasticos.transaction` counts are unchanged from the fresh clone.

## 3. Gate B2: commercial documents (second ERP write, same clone)

Partner rows now exist, so the empty-database guard must be opened explicitly. Still no `ERP_LIMIT` and no `ERP_PARTNERS_ONLY`:

```bash
scripts/test_env.sh run <owned-clone> -- \
  make import-erp ODOO_DB_NAME=<owned-clone> \
  ERP_REQUIRE_EMPTY=0 \
  ERP_REPORT_PATH=.l9/pr/erp-commercial-summary.json
```

Partner replay must not create inactive people or aliases the first pass excluded. New commercial rows must be `sale.order`, `purchase.order`, `account.move`, and `plasticos.transaction` only when sale-order confirmation compiled them. Reconcile worksheet identity, created/updated/unchanged/rejected, and the payables check this importer already fail-closes on. A validator failure rolls back that stage; do not continue by writing documents another way.

**Gate B2 passes when** the commercial summary accounts for the source worksheets and the partner census from Gate B is unchanged except for idempotent `unchanged` rows. If the extension fails closed, mark commercial `BLOCKED` and do not start CRM until the partner census is shown still equal to the Gate B result.

## 4. Gate C: full VanillaSoft cohort (same clone)

1. Copy the verified crosswalk into `Current Work - IGNORE/erp-then-vs-full-crm/` and set `plasticos_crm_sync.approved_contact_crosswalk` to the container path in "What changed" item 6 **before the first CRM write**. A wrong digest aborts via `CrosswalkError`. Load the 18 NO and 4,095 PENDING IDs from `crm_id_census.csv` in the same preflight.
2. Probe that one ContactID older than 30 days still resolves, including calls and custom fields. If it does not, stop and report the blocked cohort. Do not fill rows from the CSV.
3. One checkpointed pass over all 4,876 IDs:

```bash
scripts/test_env.sh run <owned-clone> -- shell --no-http \
  < "Current Work - IGNORE/erp-then-vs-full-crm/import_4876.py"
```

The script calls `SyncOrchestrator.upsert_contact_external_id` once per ID, commits in bounded batches, and records processed IDs so a resume skips IDs already durable. It does not call the provider twice per ID. It does not import the CSV into `crm.lead` by hand.

4. **763 YES.** The crosswalk resolves `plasticos_transaction.legacy_erp_contact_<CT_ID>`. `_bind_approved_contact` writes `plasticos.crm.external.ref` on `res.partner` and does not create a lead for that bind. ERP name and primary data stay. CRM may append the `Notes` custom field to `res.partner.comment` and add missing phone lines. If the person was excluded as inactive, the outcome is `failed` in the importer and `held` in the receipt. Do not activate the person or attach the ID to someone else. Do not create a lead for that held ID.
5. **18 NO.** Not in the crosswalk, so `_upsert_lead` creates or updates a normal `crm.lead` keyed by `vanillasoft_id`. The lead's provider ref must be `crm.lead`, not `res.partner`. The rejected `CT_ID` must not be the partner.
6. **4,095 PENDING.** Same normal lead path. No `res.partner` provider ref and no match by name, email, phone, or company.
7. All 4,876 statuses stay in the cohort. Keep Do Not Call and the raw lead status. Do not reclassify "Currently Working With" as Won. Do not add stages.
8. Score owner, stage, phones, notes, DNC, and materials against the workbooks after the write. Gaps stay gaps.
9. Calls and custom tables come only from `upsert_contact_external_id` (it calls `iter_calls_for_contact` and `_sync_tables_for_lead` after an admitted outcome). Do not synthesize calls from the CSV "Last Call Date/Result" columns. Live additions or deletions versus the frozen 4,876 are a separate delta.

**Gate C passes when** each of the 4,876 IDs has one class: imported (`created`/`updated`/`unchanged` plus one valid provider ref) or `held` or `genuine_failed`. Those three sum to 4,876. Held and failed are not imported. The CRM baseline was empty and this pass created the CRM rows.

## 5. Gate D: reconciliation

Read-only counts at before, after Gate B, after Gate B2, and after Gate C.

- **Partners:** eligible active companies and contacts, nonperson/site routing, aliases, excluded inactive and invalid parents. No inactive `CT_ID` XMLID.
- **Commercial:** `sale.order`, `purchase.order`, `account.move`, and compiled `plasticos.transaction` versus the importer summary. Partner counts flat versus Gate B except idempotent unchanged.
- **CRM:** `4876 = 763 + 18 + 4095` and `4876 = imported + held + genuine_failed`. `crm.lead` count need not equal 4,876: approved binds do not create leads. Held approved IDs also do not get leads.
- **Approved identity:** 763 decisions, 716 `CT_ID`s, 45 shared people / 92 source IDs. Compare with the previous 735 bound / 28 `no_erp_person` without importing inactive parents to improve it.
- **Fields:** owner name-match versus the locked email oracle, stage actually written versus raw status, phones and notes, DNC, material normalizer results. Unknown is not mapped.
- **History:** separate frozen-ID coverage, IDs fetched from the current API, live census, call completeness, and Odoo writes. API limits stay `PARTIAL` or `BLOCKED`.

## 6. Deliverables

Sanitized pack at `docs/reports/evidence/erp-then-vanillasoft-full-crm-<actual-run-date>/`:

- `README.md` from `REPORT_TEMPLATE.md`
- `receipt.json` from `RECEIPT_TEMPLATE.json` with `PASS`/`PARTIAL`/`BLOCKED`/`FAIL`/`NOT_RUN` only
- `erp_active_census.csv` — eligibility partitions, no PII
- `erp_commercial_census.csv` — document and transaction counts, no party names
- `crm_4876_disposition.csv` — ContactID, YES/NO/PENDING, destination type/ID or hold/error class, fetch result, no names/emails/notes
- `approved_763_link_results.csv` — ContactID, CT_ID, link result, no names/emails/notes
- `crm_field_coverage.csv` — mapped/unmapped/held by field, stage, and material
- `run_manifest.json` — SHA, fixture, clone, commands, exit codes, checksums

No raw API payloads, source CSV, or workbooks in Git. If the active-contact code changed, one `make pr` to `Staging` with that change and the sanitized evidence. If a required input or API path is missing, finish `BLOCKED`. Do not claim the run before it happens.

## Acceptance

1. One pinned Enterprise clone. CRM empty before any import. Both ERP writes and the CRM pass use `scripts/test_env.sh run` on that clone.
2. Partners-only pass: every explicitly active eligible row, zero inactive people or aliases, zero commercial documents written by that pass.
3. Commercial pass: the existing extension, unlimited worksheets, partner census preserved, documents reconciled or explicitly `BLOCKED`.
4. All 4,876 Flagged IDs go through `upsert_contact_external_id`. A 763-ID pass, a 30-day list import, or a CSV load does not pass.
5. Imported + held + genuine_failed = 4,876, each ID once. Only imported rows have a persisted provider ref.
6. 763 YES stay on the operator `CT_ID` or are held. 18 NO never attach to the rejected `CT_ID`. 4,095 PENDING get no guessed ERP partner. Shared approved targets are not duplicated.
7. Owner, stage, and polymer gaps are reported from the current importer. No new masters or maps.
8. No writes outside the clone. No customer PII in Git.

**Agent final message:** ERP partner counts, commercial document counts, CRM 4,876 outcomes, approved/NO/pending, whether CRM started empty, blockers, PR URL if any, and the report path. Do not claim execution before it happens.

## Coordinates to read at the checkout SHA

- `scripts/test_env.sh`, `config/test_env_fixture.conf`, `Makefile` (`import-erp`, `import-erp-test`, `import-vanillasoft`)
- `plasticos_partner_import/erp_extracted_data/10_counterparty.sql`, `12_contact.sql`
- `plasticos_partner_import/erp/mapping.py` (`parse_bool`), `plasticos_partner_import/models/erp_import_service.py` (`_row_active`, `_import_person`, `_extend_historical_import`)
- `plasticos_transaction/models/legacy_erp_import_service.py`, `plasticos_transaction/models/native_document_import.py`
- `plasticos_crm_sync/services/approved_identity.py`, `plasticos_crm_sync/services/orchestrator.py` (`upsert_contact_external_id`, `_bind_approved_contact`, `_upsert_lead`, `_lead_vals_from_dto`)
- `plasticos_crm_sync/scripts/import_vanillasoft_shell.py` — the path this run must not use for the cohort
- `docs/reports/evidence/crm-erp-approved-identity-2026-10-18/README.md` and `scripts/vs_identity_run.py`
