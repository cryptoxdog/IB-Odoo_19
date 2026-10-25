# Cursor execution contract: ERP import, then full VanillaSoft CRM

**Contract ID:** `PLASTICOS-ERP-THEN-VS-FULL-CRM-2026-10-21-v2`  
**Revision:** `v2.3` — aligned to checkout `607a64b897cb73b19adeea1b867990c5bf556189` and to the daytime crosswalk `9aa6fcd0eee9fedf106c23090fa32b24c2faacc1576531c4f4fcc846663b72c1`. Record that SHA when the run starts. Do not stop to reconcile it again. `e78af874604890f8adb6b049694f93c48311eab4` is the older authored pin and is not this checkout.  
**Target:** https://github.com/cryptoxdog/IB-Odoo_19  
**Runner:** Cursor, existing Odoo 19 Enterprise Docker fixture, restored ERP SQL database (read-only), authorized VanillaSoft API access.  
**Supersedes:** the prior active-only delegation that stopped after a 763-ID mapping pass, and the v2 sentences that excluded commercial documents or told the agent to apply mappings this commit does not implement.

## What changed in v2.1

Checked against the commit above. These replace conflicting sentences later in older copies of this file.

1. **ERP is two ordered writes on one clone, not partners alone.** `ERP_PARTNERS_ONLY=1` is the first write: the five partner layers, with inactive contacts kept out. It must leave `sale.order`, `purchase.order`, `account.move`, and `plasticos.transaction` unchanged. The second write is the same `make import-erp` **without** `ERP_PARTNERS_ONLY` and **without** `ERP_LIMIT`. On this commit that path runs partner stages again, then `plasticos_transaction.models.legacy_erp_import_service._extend_historical_import` → `native_document_import.realize`, which writes `sale.order`, `purchase.order`, and `account.move` and confirms sale orders. Confirmation is what compiles `plasticos.transaction`. Do not hand-build those records and do not add another writer. An unset `ERP_LIMIT` is the full worksheet set (`parse_limit` of empty is `None`). `make import-erp-test` stays forbidden: its default is `LIMIT=25%`.
2. **Inactive-contact exclusion is already on this checkout.** `_row_active` calls `explicitly_active_contact`: a row is eligible only when `parse_bool(IsActive) is True`. Blank or unknown is excluded. Ineligible `CT_ID`s are not people and not aliases. Mixed groups import from eligible rows only. Company scope stays `ActiveStatus='A'` in `10_counterparty.sql`. Do not edit `mapping.py` or `erp_import_service.py` on this run, and do not bump `plasticos_partner_import`. The older defect (`_row_active` treating `None` as active, and inactive aliases still receiving XMLIDs) is closed here. Read the real `IsActive` spellings before the import so an unexpected true spelling is reported, not silently rewritten.
3. **The 4,876 CRM pass is not `make import-vanillasoft`.** That target calls `SyncOrchestrator.run_full_import` with a modified-after floor. `scripts/test_env.sh run` accepts it only when both `VANILLASOFT_CALL_FLOOR` and `VANILLASOFT_CONTACT_FLOOR` are set. A floor older than about 30 days returns HTTP 400. Do not run it, and do not call a 30-day run full. The cohort pass is `scripts/test_env.sh run <owned-clone> -- shell --no-http` with stdin. `import_4876.py` in this pack is that runner. Do not write another script from `vs_identity_run.py`.
4. **Report outcomes are a translation, not new importer states.** `upsert_contact_external_id` / `_upsert_lead` classify `created`, `updated`, `unchanged`, `duplicate_rejected`, or `failed`. In the receipt, `created`/`updated`/`unchanged` with one persisted provider ref count as imported. v2.3 replaces the older rule that a missing ERP person stays `held` with no lead: on this checkout that person is imported as a `crm.lead` and the warning stays on the row. `duplicate_rejected`, exceptions, and provider fetch errors count as `genuine_failed`, not imported. Do not patch the orchestrator during this run.
5. **Do not add owner, stage, or polymer mappers.** Owner assignment on this commit is `_lead_vals_from_dto`: `user_id` is set only when exactly one active-search `res.users` name equals `dto.owner_name` case-insensitively; otherwise it stays empty. Stage comes from `plasticos_crm_bridge` `STAGE_MAPPING`, otherwise `plasticos_crm_bridge.stage_new`. Materials go through the existing normalizer and only attach when one facility profile already exists. The owner, stage, and polymer workbooks are audit oracles. Score what the importer wrote. Mismatches are field gaps. Do not create users, stages, polymer masters, or an email crosswalk in this run.
6. **The crosswalk file must be on the compose mount.** `load_crosswalk_map` reads a host path inside the container. The repo is mounted at `/mnt/extra-addons`. A path outside the repo is invisible there. Copy the byte-exact crosswalk and a no-PII ID census into gitignored `Current Work - IGNORE/erp-then-vs-full-crm/`. Set `plasticos_crm_sync.approved_contact_crosswalk` to the in-container path `/mnt/extra-addons/Current Work - IGNORE/erp-then-vs-full-crm/03_APPROVED_CONTACT_CROSSWALK.csv`.

## What changed in v2.2

A class name without the reason that produced it is not a result. The October 21 cohort run died with `outcome=failed` lines that named no marker, no HTTP status, and no exception, and the receipt could still have been filled with `held` and an empty `open_exceptions` list. That receipt cannot be remediated. v2.2 makes that shape fail.

1. **`import_4876.py` in this pack is the cohort runner.** Copy it to `Current Work - IGNORE/erp-then-vs-full-crm/import_4876.py` before Gate C. It is the script the Gate C command already names. It loads `crm_id_census.csv` (`vanillasoft_contact_id,decision` only, 4,876 rows, `YES`/`NO`/`PENDING`). It calls `upsert_contact_external_id` once per id that is allowed to be fetched.
2. **Every checkpoint row has a `signals` array.** Each item is `level` plus `reason`. The sources are the `plasticos_crm_sync` WARNING and ERROR lines for that contact, the importer `error_rows` messages, and the exception text. An imported row keeps its warnings. Those warnings do not flip the class, and they are not discarded because the bind succeeded. A held, skipped, or failed row with no reason is stored as level `UNKNOWN` and reason `outcome <raw> produced no reason`.
3. **The runner exits 1** when any non-imported row has no source reason, or when any checkpoint row has no `signals` key, or when the checkpoint does not cover 4,876 ids. Exit 2 is only a rejected credential, and that line prints the redacted reason before it stops. A finished process whose log only says `outcome=failed` is not a usable result.
4. **The receipt `open_exceptions` is the distinct reasons.** Each item is `{level, reason, count}`. A receipt that records `held`, `genuine_failed`, `duplicate_skipped`, or a warning count and leaves `open_exceptions` empty does not pass. A reason the adapter never emitted cannot be reconstructed later. Record that absence as UNKNOWN. Do not fill it with a guess.
5. **Four YES ids are duplicates of a person already approved on an active contact.** `OMITTED_DUPLICATE_VS_IDS` (`1045036935`, `1179868294`, `584402429`, `585278462`) are not fetched and are not turned into leads. Their class is `duplicate_skipped` and the checkpoint reason says so. A YES id that is neither in the loaded crosswalk nor in that omit set is `genuine_failed` with the reason `YES id is missing from the loaded crosswalk`, and it is not fetched. A NO or PENDING id that is in the crosswalk is `genuine_failed` with that reason and is not fetched.
6. **A blank `erp_ct_id` is not an ERP bind.** `ACTIVE_COMPANY_CP_BY_VS` places that person on the named company when the id is in that map. Every other blank is a `crm.lead`. On this checkout a non-blank `erp_ct_id` whose marker resolves 0 rows is also a `crm.lead`, and the warning keeps the marker text (`ERP marker plasticos_transaction.legacy_erp_contact_<CT_ID> resolved 0 rows`). Do not replace that text with the word `held`, and do not recode the path into a no-lead hold.
7. **Redaction keeps the cause.** Credential-shaped text and email addresses are removed. HTTP status, timeout, missing ERP marker, and exception text stay. Customer note bodies are not copied into the checkpoint.

The operator matrix is still 763 YES + 18 NO + 4,095 PENDING = 4,876. The executable crosswalk file pinned by this pack is 759 VanillaSoft ids and 691 ERP CT_IDs (`9aa6fcd0eee9fedf106c23090fa32b24c2faacc1576531c4f4fcc846663b72c1`). The four omitted YES ids account for 763 − 759.

## What changed in v2.3

The daytime run on clone `odoo_test_day1021` loaded an older 763-id file, then the executable CSV was replaced. `docs/reports/evidence/erp-contacts-vs-crosswalk-daytime-2026-10-21/receipt.json` records the file the next run loads: SHA256 `9aa6fcd0eee9fedf106c23090fa32b24c2faacc1576531c4f4fcc846663b72c1`, 759 VanillaSoft ids, 691 ERP contacts, 22 blank `erp_ct_id` rows. That file is the map. The October 16 workbook is only the YES/NO/PENDING census. Do not restore an inactive `CT_ID`. Do not edit `plasticos_crm_sync` or `plasticos_partner_import` on this run.

1. **This checkout is `607a64b897cb73b19adeea1b867990c5bf556189`.** Active-only selection is already here: `_row_active` calls `explicitly_active_contact`, and blank `IsActive` is excluded. Read it. Do not rewrite it.
2. **The stale figure 702 is void.** The file is 759 VanillaSoft ids, 691 distinct `CT_ID`s, 737 rows that name a `CT_ID`, and 22 blanks. 44 of those `CT_ID`s are shared by 90 VanillaSoft ids. `validate_crosswalk` rejects any other census.
3. **YES split the runner records and does not repair:**
   - `duplicate_skipped`, not fetched: `1045036935`, `1179868294`, `584402429`, `585278462`.
   - Retargets already in the file: `619579299` → `148650001`, `625031140` → `9500001`.
   - Blank ids in `ACTIVE_COMPANY_CP_BY_VS`: `572647290` → company `399`, `573474286` → `1405`, `579156006` → `1484`, `700174793` → `1257`, `683417624` → `1380`, `609608749` → `2461`, `715993397` → `2076`. The importer reuses one same-named child or creates the contact on that company. Do not remove that create. If the company marker is missing or the name is ambiguous, it writes a `crm.lead` and a warning. Record that warning. Do not rerun to force the placement.
   - The other 15 blanks are leads, not binds and not holds. Seven are the still-unmapped ids in `docs/reports/evidence/erp-contacts-vs-crosswalk-daytime-2026-10-21/unmapped_for_judgment.csv`: `580439040`, `580439043`, `580439230`, `581463517`, `658176498`, `933860677`, `940320088`. Eight more are `572647389`, `572647457`, `572648070`, `572648259`, `573474338`, `576092568`, `579155547`, `1085161977`. Do not invent a `CT_ID` for them.
4. **A missing ERP person becomes a lead on this checkout.** `_upsert_lead` logs the warning and imports a `crm.lead`. `import_4876.py` keeps that warning on an imported row and sets `placement` to `crm_lead`. Do not patch the orchestrator back to a no-lead hold. A non-zero warning count is not a reason to drop the clone.
5. **One pass.** The runner commits each id. Do not change that batching. Resume the same checkpoint after exit 2 (`credential_stop.json`). Exit 1 means a row has no reason, a row has no `placement` or the pinned `crosswalk_sha256`, or coverage is not 4,876. Read `crm_checkpoint.jsonl` and `open_exceptions.json` before resuming. A `crosswalk_stamp.json` for a different digest refuses the resume. Do not delete this clone and start the ERP import over because a warning fired.
6. **Trace files in `Current Work - IGNORE/erp-then-vs-full-crm/`.** `crm_checkpoint.jsonl` (one row per id, with `signals`, `placement`, `crosswalk_sha256`), `crosswalk_stamp.json`, `open_exceptions.json` (written before a failing exit), and `credential_stop.json` on exit 2. `placement` is `erp_person`, `active_company`, `crm_lead`, `duplicate_skipped`, `not_fetched`, `held`, or `genuine_failed`. Copy `open_exceptions.json` into the receipt. The checkpoint is the authority if the terminal log is truncated.

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
- No fuzzy ERP person linking. Do not promote the 4,095 pending IDs. The 18 rejected links never attach. Preserve provider ContactID. Do not invent a `CT_ID` for a blank row. The active-company placement may create the contact on the company named in `ACTIVE_COMPANY_CP_BY_VS`. That create is the current importer. Do not remove it, and do not use it for any other id.
- No new Odoo fields, models, stages, or material masters. No new owner-email map.
- One full two-stage ERP load and one 4,876 CRM pass. No second full provider replay. A targeted read proves uniqueness.
- Do not change addon code on this run. Copy `import_4876.py` into `Current Work - IGNORE/erp-then-vs-full-crm/` and leave it out of Git. No `make pr`, no merge, and no deploy unless the operator asks after the evidence exists.

## 0. Verify private inputs before any database write

| Input | Purpose | Decision status |
| --- | --- | --- |
| `CRM Leads - VanillaSoft - Scrap-Management(1).csv` | Immutable 4,876-row historical snapshot and ContactID census | ID list only. Not a CSV importer |
| `PlasticOS_ERP_VanillaSoft_Operator_Confirmed_Crosswalk_2026-10-16.xlsx` | Operator identity matrix | Authoritative for 763 YES, 18 NO, 4,095 PENDING |
| `03_APPROVED_CONTACT_CROSSWALK.csv` | Allowlist for `plasticos_crm_sync.approved_contact_crosswalk` | SHA256 must equal `9aa6fcd0eee9fedf106c23090fa32b24c2faacc1576531c4f4fcc846663b72c1`. 759 VanillaSoft IDs, 691 ERP `CT_ID`s. A blank `erp_ct_id` is a CRM lead and is not an ERP bind. |
| `VanillaSoft_4876_Field_Mapping_Resolved_Owners_Stage_Review.xlsx` | Field, owner, and stage audit oracle | Score the importer. Do not install STAGE REVIEW or a new owner map |
| `VanillaSoft_to_Odoo_Polymer_Mapping_Decisions_2026-10-14.xlsx` | Material audit oracle | Score `normalize_material` output. Do not create masters |

Check `INPUT_MANIFEST.json` hashes, 4,876 distinct ContactIDs, all `Flagged=True`, and partition `763 + 18 + 4,095 = 4,876`. The loaded crosswalk is 759 VanillaSoft ids, 691 distinct ERP `CT_ID`s, 737 rows with a `CT_ID`, and 22 blanks, at the pinned digest. The other four operator YES ids are the duplicate skip set. Keep the 44 shared `CT_ID`s that cover 90 VanillaSoft ids. Do not duplicate the person. The figure 702 is not this file.

Historical snapshot SHA256: `40df04991e9497b3b723e1478f5ea8b1a5dda74e8a052054beb856d81eb942d9`.

Build `Current Work - IGNORE/erp-then-vs-full-crm/crm_id_census.csv` with columns `vanillasoft_contact_id,decision` only (`YES`/`NO`/`PENDING`). No names, emails, phones, or notes. The shell reads that file. Host-side scoring may read the workbooks.

## 1. Gate A: pinned Enterprise clone, CRM empty

- Record commit SHA, installed modules, and fixture fingerprint from `scripts/test_env.sh status`. The template name must be `odoo_test_tpl_ee_c9e8a81f52f23680`. If that database is absent, stop. Do not set `TEST_ENV_ALLOW_NEW_TEMPLATE`.
- `scripts/test_env.sh clone <new-owned-name>`. Do not reuse the October 18 clone `odoo_test_w2495f48767`.
- Before either import, record `crm.lead`, `plasticos.crm.external.ref`, VanillaSoft sync runs, `plasticos.crm.call.event`, `plasticos.crm.external.table.row`, and business-partner / ERP XMLID baselines. Odoo seed partners are not a CRM import. If this clone already has CRM source rows, drop only this owned clone and clone again.
- ERP SQL login is read-only. VanillaSoft credentials go to the clone's `ir.config_parameter` through the existing secret path. No secrets or customer notes in logs, PRs, or receipts.

**Gate A passes when** the clone is the pinned fixture's and the before-counts show no CRM source contacts.

## 2. Gate B: active-only partners (first ERP write)

- Census `IsActive` and `ActiveStatus` spellings, placeholder IDs, and missing parents on the read-only source. Confirm `_row_active` already calls `explicitly_active_contact` (`parse_bool(IsActive) is True`; blank is excluded). Do not edit that predicate on this run.
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

The script calls `SyncOrchestrator.upsert_contact_external_id` once per ID that v2.3 allows it to fetch, commits that id, and records it so a resume skips ids already durable. It does not call the provider twice per ID. It does not import the historical CSV into `crm.lead` by hand. Every checkpoint row carries `signals`, `placement`, and `crosswalk_sha256`. The script prints `placement=...` and `signal level=... contact=... reason=...` as each row is written, then writes `open_exceptions.json` and prints each distinct reason with its count. It exits 1 when a non-imported row has no source reason, when a checkpoint row has no `signals` or `placement`, or when coverage is not 4,876. Copy `import_4876.py` from this pack into that Current Work path before the command. Start Gate C with no `crm_checkpoint.jsonl` from an older runner. A copy that only stores `held` or `failed` is not this runner.

4. **763 YES.** A row with a `CT_ID` resolves `plasticos_transaction.legacy_erp_contact_<CT_ID>`. `_bind_approved_contact` writes `plasticos.crm.external.ref` on `res.partner` and does not create a lead for that bind. ERP name and primary data stay. CRM may append the `Notes` custom field to `res.partner.comment` and add missing phone lines. If that marker resolves 0 rows, this checkout logs the marker text and imports a `crm.lead`. `placement` is `crm_lead`. Do not activate an excluded person and do not attach the id to a different `CT_ID`. A blank `erp_ct_id` is a company placement when the id is in `ACTIVE_COMPANY_CP_BY_VS`, and a `crm.lead` otherwise. The four duplicate YES ids are `duplicate_skipped` and are not fetched. The v2.3 YES split is the expected shape. A lead for a blank or a missing marker is the result, not a defect to rerun.
5. **18 NO.** Not in the crosswalk, so `_upsert_lead` creates or updates a normal `crm.lead` keyed by `vanillasoft_id`. The lead's provider ref must be `crm.lead`, not `res.partner`. The rejected `CT_ID` must not be the partner.
6. **4,095 PENDING.** Same normal lead path. No `res.partner` provider ref and no match by name, email, phone, or company.
7. All 4,876 statuses stay in the cohort. Keep Do Not Call and the raw lead status. Do not reclassify "Currently Working With" as Won. Do not add stages.
8. Score owner, stage, phones, notes, DNC, and materials against the workbooks after the write. Gaps stay gaps.
9. Calls and custom tables come only from `upsert_contact_external_id` (it calls `iter_calls_for_contact` and `_sync_tables_for_lead` after an admitted outcome). Do not synthesize calls from the CSV "Last Call Date/Result" columns. Live additions or deletions versus the frozen 4,876 are a separate delta.

**Gate C passes when** each of the 4,876 IDs has one class: imported (`created`/`updated`/`unchanged` plus one valid provider ref), `held`, `genuine_failed`, or `duplicate_skipped`. Those four sum to 4,876. Held, failed, and skipped are not imported. Imported covers `placement` `erp_person`, `active_company`, and `crm_lead`. Every checkpoint row has `signals` and `placement`. Every non-imported row has a source reason that is not `produced no reason`. The receipt `open_exceptions` is the copy of `open_exceptions.json`: each distinct reason as `{level, reason, count}`, including warnings on imported rows. The CRM baseline was empty and this pass created the CRM rows.

## 5. Gate D: reconciliation

Read-only counts at before, after Gate B, after Gate B2, and after Gate C.

- **Partners:** eligible active companies and contacts, nonperson/site routing, aliases, excluded inactive and invalid parents. No inactive `CT_ID` XMLID.
- **Commercial:** `sale.order`, `purchase.order`, `account.move`, and compiled `plasticos.transaction` versus the importer summary. Partner counts flat versus Gate B except idempotent unchanged.
- **CRM:** `4876 = 763 + 18 + 4095` and `4876 = imported + held + genuine_failed + duplicate_skipped`. `crm.lead` need not equal 4,876. `placement` `erp_person` and `active_company` do not create the approved lead. `placement` `crm_lead` does, including the 15 blank ids and any `CT_ID` whose marker missed. `duplicate_skipped` does not.
- **Approved identity:** 763 operator YES decisions. The loaded crosswalk is 759 VanillaSoft ids and 691 `CT_ID`s. Four YES ids are `duplicate_skipped`. Split the 759 by `placement` using the v2.3 lists. Do not import inactive parents to raise the bind count. Copy every distinct signal reason into the report. Do not replace a reason with its class or with its `placement`.
- **Fields:** owner name-match versus the locked email oracle, stage actually written versus raw status, phones and notes, DNC, material normalizer results. Unknown is not mapped.
- **History:** separate frozen-ID coverage, IDs fetched from the current API, live census, call completeness, and Odoo writes. API limits stay `PARTIAL` or `BLOCKED`.

## 6. Deliverables

Sanitized pack at `docs/reports/evidence/erp-then-vanillasoft-full-crm-<actual-run-date>/`:

- `README.md` from `REPORT_TEMPLATE.md`
- `receipt.json` from `RECEIPT_TEMPLATE.json` with `PASS`/`PARTIAL`/`BLOCKED`/`FAIL`/`NOT_RUN` only
- `erp_active_census.csv` — eligibility partitions, no PII
- `erp_commercial_census.csv` — document and transaction counts, no party names
- `crm_4876_disposition.csv` — ContactID, YES/NO/PENDING, class, `placement`, importer outcome, `crosswalk_sha256`, and each signal `level` and `reason`. No names, emails, or notes. A row whose reason column is empty does not pass. Copy `open_exceptions.json` into the receipt.
- `approved_763_link_results.csv` — ContactID, CT_ID, link result, no names/emails/notes
- `crm_field_coverage.csv` — mapped/unmapped/held by field, stage, and material
- `run_manifest.json` — SHA, fixture, clone, commands, exit codes, checksums

No raw API payloads, source CSV, or workbooks in Git. Addon code is not part of this run. Do not open a PR from it. If a required input or API path is missing, finish `BLOCKED`. Do not claim the run before it happens. Do not drop the clone and start over because `open_exceptions` is non-empty.

## Acceptance

1. One pinned Enterprise clone. CRM empty before any import. Both ERP writes and the CRM pass use `scripts/test_env.sh run` on that clone.
2. Partners-only pass: every explicitly active eligible row, zero inactive people or aliases, zero commercial documents written by that pass.
3. Commercial pass: the existing extension, unlimited worksheets, partner census preserved, documents reconciled or explicitly `BLOCKED`.
4. All 4,876 Flagged IDs go through `upsert_contact_external_id`. A 763-ID pass, a 30-day list import, or a CSV load does not pass.
5. Imported + held + genuine_failed + duplicate_skipped = 4,876, each ID once. Only imported rows have a persisted provider ref. Every non-imported row has a source reason in `signals` and in `open_exceptions`. A checkpoint row without `signals`, `placement`, or the pinned `crosswalk_sha256` fails the run. Warnings on imported rows are in `open_exceptions` too.
6. The 759 loaded YES ids follow the v2.3 split. The four omitted YES ids are `duplicate_skipped`. 18 NO never attach to the rejected `CT_ID`. 4,095 PENDING get no guessed ERP partner. Shared approved targets are not duplicated. A blank or a missing marker that became a lead is not put back onto an inactive `CT_ID`.
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
