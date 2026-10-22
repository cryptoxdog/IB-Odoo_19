# Cursor execution contract: ERP contacts, then VanillaSoft crosswalk

**Contract ID:** `PLASTICOS-ERP-CONTACTS-THEN-VS-CROSSWALK-DAYTIME-2026-10-21`  
**Revision:** `daytime-v2`  
**Target:** https://github.com/cryptoxdog/IB-Odoo_19  
**Runner:** Cursor, existing Odoo 19 Enterprise Docker fixture, restored ERP SQL database (read-only), authorized VanillaSoft API access.  
**Does not replace:** `PlasticOS_ERP_Then_Full_VanillaSoft_Cursor_Delegation_v2_2026-10-21` revision `v2.1`. That pack remains the overnight end-to-end test: partners, commercial documents, then all 4,876 VanillaSoft IDs. Run this pack on a different clone.

Rebind to the checkout SHA before any write and record it. If addon code and this contract disagree about active-contact selection or the crosswalk pin, stop and reconcile before the import.

## Scope

On **one fresh clone of the pinned Enterprise fixture**, in this order:

1. **Partners.** Every eligible explicitly active company and contact through `make import-erp` with `ERP_PARTNERS_ONLY=1` and `ERP_LIMIT` unset. That is the five partner layers: counterparties, addresses, contacts, roles, salespersons. No `ERP_LIMIT`. No second ERP write.
2. **VanillaSoft crosswalk.** The 763 IDs in the pinned crosswalk, through `upsert_contact_external_id`. Nothing else from VanillaSoft.

Commercial documents are a failed run, not an optional extra. `sale.order`, `purchase.order`, `account.move`, and `plasticos.transaction` stay at the fresh-clone baseline.

## Why this is the daytime cut

The partners-only shell is the full active ERP contact load. The commercial pass walks the BuySell, PO, receipt, and payables worksheets and is the long ERP stage. The 4,876-ID VanillaSoft pass, with call history, is the long CRM stage. This contract keeps the contact load and the crosswalk binds, which are the identity-friction cases. The 18 rejected links and the 4,095 pending IDs are ordinary `crm.lead` creates and stay on the overnight pack.

Call history for the 763 is still fetched. `upsert_contact_external_id` does that after an admitted bind. Do not replace it with a CSV load or with `make import-vanillasoft`.

## Nonnegotiable boundaries

- ERP source is the restored read-only SQL database through `make import-erp`. No second ETL, no frozen grid as runtime authority, no source writes.
- One disposable clone from `config/test_env_fixture.conf` (`TEMPLATE=odoo_test_tpl_ee_c9e8a81f52f23680`) via `scripts/test_env.sh`. Do not set `TEST_ENV_ALLOW_NEW_TEMPLATE`. No hosted Staging, Production, or Odoo.sh writes.
- Do not reuse `odoo_test_w2495f48767`. Do not reuse a clone that is already running the overnight pack, including `odoo_test_erpvs1021` while that run is live.
- Every Odoo write goes through `scripts/test_env.sh run <owned-clone> -- ...`. Bare `docker compose` against the business database `odoo` is a failure.
- A contact row is eligible only when `parse_bool(IsActive) is True`. Blank and unknown are excluded. Inactive `CT_ID`s are not people and not aliases. Company scope stays `ActiveStatus='A'`.
- No fuzzy ERP linking. The crosswalk is the only VanillaSoft-to-ERP map. Shared approved targets are not duplicated. Do not create a `res.partner` to raise the match rate.
- Approved binds write `plasticos.crm.external.ref` on `res.partner` and do not create a `crm.lead`. A missing ERP person is importer `failed` and receipt `held`. Do not activate an excluded person. Do not attach the ID to someone else.
- Do not fetch the 18 NO IDs or the 4,095 PENDING IDs. Do not create leads for them in this pack.
- No new fields, models, stages, users, or material masters. No owner-email map.
- Never place a call. No secrets or customer notes in logs, receipts, or git. A failure or a warning still keeps its operational reason. See Signal retention.
- The shell script in this directory is the runner. Private inputs stay in the overnight pack and stay out of git.

## 0. Verify the crosswalk before any database write

Required file, already stored with the overnight pack:

| Input | Path | Decision |
| --- | --- | --- |
| `03_APPROVED_CONTACT_CROSSWALK.csv` | `../PlasticOS_ERP_Then_Full_VanillaSoft_Cursor_Delegation_v2_2026-10-21/PRIVATE_INPUTS/03_APPROVED_CONTACT_CROSSWALK.csv` | SHA256 must equal `9aa6fcd0eee9fedf106c23090fa32b24c2faacc1576531c4f4fcc846663b72c1`. 759 VanillaSoft IDs, 691 ERP `CT_ID`s. A blank `erp_ct_id` is a CRM lead and is not an ERP bind. |

Copy that file, byte-exact, to `Current Work - IGNORE/erp-contacts-vs-crosswalk/03_APPROVED_CONTACT_CROSSWALK.csv`. Copy `import_crosswalk.py` to `Current Work - IGNORE/erp-contacts-vs-crosswalk/import_crosswalk.py`. Do not copy the 4,876-row CSV or the workbooks into the shell directory. A wrong digest aborts in `load_crosswalk_map` before CRM writes.

Forty-five ERP people are shared by 92 approved source IDs. Keep those aliases.

The overnight files `CRM Leads - VanillaSoft - Scrap-Management(1).csv`, the operator workbook, and the owner/stage/polymer workbooks are not inputs to this run. Their hashes live in the overnight `INPUT_MANIFEST.json` for the pack that uses them.

## 1. Gate A: pinned Enterprise clone, empty of CRM and commercial documents

- Record the commit SHA and `scripts/test_env.sh status`. The template must be `odoo_test_tpl_ee_c9e8a81f52f23680`. If that database is absent, stop. Do not create a template.
- `scripts/test_env.sh clone <new-owned-name>`.
- Before either import, record `crm.lead`, `plasticos.crm.external.ref`, `plasticos.crm.call.event`, `plasticos.crm.external.table.row`, `sale.order`, `purchase.order`, `account.move`, `plasticos.transaction`, and ERP XMLID baselines. Odoo seed partners are not a CRM import. If this clone already has CRM rows or commercial documents, drop only this owned clone and clone again.
- ERP SQL login is read-only (`erp_reader` on the restored database). Put the VanillaSoft API key on this clone's `ir.config_parameter` `plasticos_crm_sync.vanillasoft_api_key` without printing it. Project `139705` is the connection default when the field is blank.

**Gate A passes when** the clone is the pinned fixture's and the before-counts show no CRM rows and no commercial documents.

## 2. Gate B: all eligible ERP contacts (only ERP write)

Confirm inactive contacts are excluded. `mapping.explicitly_active_contact` is the predicate: explicit true only. If the checkout does not yet do that, apply that selection, add the focused test (an active row plus an inactive alias keeps the active `CT_ID` only; a blank flag is excluded), bump `plasticos_partner_import`, and let `scripts/test_env.sh run` upgrade the roster. Do not `make update-all`.

Census `IsActive` and `ActiveStatus` on the read-only source before the write. Company scope stays active counterparties only.

```bash
scripts/test_env.sh run <owned-clone> -- \
  make import-erp ODOO_DB_NAME=<owned-clone> \
  ERP_PARTNERS_ONLY=1 \
  ERP_SQL_SERVER=host.docker.internal \
  ERP_SQL_PORT=14330 \
  ERP_SQL_USER=erp_reader \
  ERP_SQL_DATABASE=<restored-reader-database> \
  ERP_REPORT_PATH=.l9/pr/erp-contacts-summary.json
```

Pass `ERP_SQL_PASSWORD` through the environment. Do not put it on the command line. Invariant 20 forbids spelling the legacy vendor name, so the restored reader database is supplied in the environment. Leave `ERP_LIMIT` unset. Leave `ERP_REQUIRE_EMPTY` at its default. Do not set `ERP_PARTNERS_ONLY` empty. Do not run `make import-erp-test`.

Reconcile the five layers. `skipped` is a no-new-partner outcome, and the report must split it:

- **Contacts.** One person per company and person key (first word and last word). Extra `CT_ID`s for that person are aliases: a `legacy_erp_contact_*` marker on the same partner, counted `skipped`. A title with no letter is a phone number written onto the company. A site-mailbox name is written onto that location. Neither creates a person.
- **Addresses.** A row folded onto the company that changes a blank remit field is `updated`. A folded row that changes nothing, because an earlier address of that company already filled street, city, zip, phone, and email, is `skipped`. A distinct street becomes a child location and is `created`. The `AddressID` marker still exists for the skipped row.

Inactive `CT_ID`s are `unresolved` (`inactive_contact`), not `skipped`, and have no XMLID. Contacts whose parent company was not imported stay unresolved. Do not activate a parent to increase matches.

**Gate B passes when** the summary equation closes, both contact validators passed, no inactive contact XMLID exists, and `sale.order`, `purchase.order`, `account.move`, and `plasticos.transaction` are still at the Gate A baseline.

## 3. Gate C: VanillaSoft crosswalk only (same clone)

There is no Gate B2.

1. The crosswalk file from section 0 is on the compose mount. `import_crosswalk.py` sets `plasticos_crm_sync.approved_contact_crosswalk` to `/mnt/extra-addons/Current Work - IGNORE/erp-contacts-vs-crosswalk/03_APPROVED_CONTACT_CROSSWALK.csv` and loads it through `SyncOrchestrator._load_approved_crosswalk` before the first contact write.
2. One checkpointed pass:

```bash
scripts/test_env.sh run <owned-clone> -- shell --no-http \
  < "Current Work - IGNORE/erp-contacts-vs-crosswalk/import_crosswalk.py"
```

The script calls `upsert_contact_external_id` once per crosswalk ID, commits that ID, then appends the checkpoint. A resume skips checkpointed IDs. An authentication failure stops the run instead of marking the rest failed. It does not read the 4,876 census.

3. Each YES ID resolves `plasticos_transaction.legacy_erp_contact_<CT_ID>`. `_bind_approved_contact` writes the provider ref on `res.partner`. ERP name and primary data stay. The Notes custom field may append to `res.partner.comment`. Missing phone lines may be added. Calls and custom-table rows come only from that method. Do not synthesize them from a spreadsheet.
4. If the person was excluded as inactive or the marker is missing, the importer outcome is `failed` and the receipt class is `held`. No lead for that ID.
5. `crm.lead` stays at the Gate A count. A lead created by this pass fails the gate.

**Gate C passes when** each of the 763 IDs has one class: imported (`created`, `updated`, or `unchanged`, plus one `res.partner` provider ref) or `held` or `genuine_failed`. Those three sum to 763. Held and failed are not imported. `crm.lead` did not grow. No provider ref points at `crm.lead`. Every held row, every genuine failure, and every warning names its reason on that ID. A class with an empty reason is not a pass.

## 4. Gate D: reconciliation

Read-only counts at before, after Gate B, and after Gate C.

- **Partners:** eligible active companies and contacts, alias markers, non-person and site-mailbox rows, excluded inactive contacts, unresolved parents. No inactive `CT_ID` XMLID. `skipped` split as in Gate B.
- **Commercial:** `sale.order`, `purchase.order`, `account.move`, and `plasticos.transaction` equal the fresh clone. Any increase fails the pack.
- **Crosswalk:** `763 = imported + held + genuine_failed`. Distinct ERP targets are 716. Shared groups stay 45 people / 92 source IDs. Compare with the previous 735 bound / 28 `no_erp_person` without importing inactive parents to improve it.
- **Leads:** `crm.lead` unchanged. The 18 NO and 4,095 PENDING IDs are `NOT_RUN` on this pack, not failed.

## 5. Deliverables

Sanitized pack at `docs/reports/evidence/erp-contacts-then-vanillasoft-crosswalk-<actual-run-date>/`:

- `README.md` from `REPORT_TEMPLATE.md`
- `receipt.json` from `RECEIPT_TEMPLATE.json` with `PASS` / `PARTIAL` / `BLOCKED` / `FAIL` / `NOT_RUN` only
- `erp_contact_census.csv` — eligibility and skip partitions, no names, emails, phones, or notes
- `crosswalk_763_disposition.csv` — ContactID, `CT_ID`, class, importer outcome, and the `signals` array from the checkpoint. No names, emails, phones, notes, or secrets. A held or failed ID with an empty `signals` array is UNKNOWN, not a closed disposition.
- `run_manifest.json` — SHA, fixture, clone, commands, exit codes, checksums

No raw API payloads, source CSV, crosswalk, or workbooks in that evidence directory. If the active-contact code changed, commit that change with the sanitized evidence only when the operator asked for a commit. No push, no merge, no deploy. If a required input or the API path is missing, finish `BLOCKED`.

## Acceptance

1. One pinned Enterprise clone, different from the October 18 clone and from a live overnight clone. CRM and commercial documents empty before any import.
2. One partners-only ERP write. Full active contact set. `ERP_LIMIT` unset. No commercial documents created.
3. Inactive contacts have no XMLID. Alias `CT_ID`s point at the one person. The skip split is in the report.
4. Exactly the 763 crosswalk IDs go through `upsert_contact_external_id`. A 4,876 pass, a 30-day list import, or a CSV load does not pass.
5. Imported + held + genuine_failed = 763, each ID once. Only imported rows have a persisted `res.partner` provider ref. `crm.lead` did not grow.
6. 763 YES stay on the operator `CT_ID` or are held. Shared approved targets are not duplicated.
7. No writes outside the clone. No customer PII in git.
8. Every held row, genuine failure, and warning keeps its reason. A warning on an imported bind stays on that ID. UNKNOWN is not counted as imported and is not counted as an explained failure.

**Agent final message:** ERP contact counts and the skip split, crosswalk 763 outcomes, whether the clone started empty of CRM and commercial documents, blockers, and the report path. Do not claim execution before it happens.

## Coordinates to read at the checkout SHA

- `scripts/test_env.sh`, `config/test_env_fixture.conf`, `Makefile` (`import-erp`, and the targets this run must not use: `import-erp-test`, `import-vanillasoft`)
- `plasticos_partner_import/erp/mapping.py` (`explicitly_active_contact`, `is_person_name`, `person_key`)
- `plasticos_partner_import/models/erp_import_service.py` (`_import_addresses`, `_import_contacts`, `_alias_xmlid`, `_apply_billing_address`)
- `plasticos_crm_sync/services/approved_identity.py`, `plasticos_crm_sync/services/orchestrator.py` (`upsert_contact_external_id`, `_bind_approved_contact`)
- `plasticos_crm_sync/adapters/vanillasoft/adapter.py` (`iter_table_rows`). From module `19.0.1.9.1` a custom-table warning includes the exception text. A warning line that names the project and omits the cause is an incomplete signal and stays UNKNOWN.
- Overnight contract `../PlasticOS_ERP_Then_Full_VanillaSoft_Cursor_Delegation_v2_2026-10-21/CURSOR_EXECUTION_CONTRACT.md` for the stages this pack deliberately omits

## Signal retention

Authority: [Quantum-L9/.github `docs/ADVISORY.md`](https://github.com/Quantum-L9/.github/blob/main/docs/ADVISORY.md) and [`semantics/error_taxonomy.yaml`](https://github.com/Quantum-L9/.github/blob/main/semantics/error_taxonomy.yaml). The weekly governance report keeps superseded and retired entries and lists them. It does not drop them.

A finding nobody sees is not advisory. It is absent. `unknown_outcome` is not collapsed into success or failure without an authoritative reconciliation. This pack uses that rule on the import itself.

`import_crosswalk.py` writes a `signals` array on every checkpoint row. Each item is `level` plus `reason`. The sources are the `plasticos_crm_sync` WARNING and ERROR log lines for that contact, the importer `error_rows` messages, and the exception text. An imported bind keeps its warnings. Those warnings do not flip the class, and they are not discarded because the bind succeeded. A held or failed row with no reason is stored as level `UNKNOWN` and reason `outcome <raw> produced no reason`.

The live log prints each signal as `signal level=... contact=... reason=...`. The finish line prints each distinct reason with its count, and `checkpoint_rows_missing_signals` for rows written by a runner that did not keep reasons. Those older rows are not treated as clean.

Credential-shaped text and email addresses are redacted. The HTTP status, the timeout, the missing ERP marker, and the adapter exception stay. Customer note bodies are not copied into the checkpoint.

The receipt `open_exceptions` lists each distinct reason with its level and count. A receipt that records `genuine_failed`, `held`, or a warning count and leaves `open_exceptions` empty does not pass. A reason the adapter never emitted cannot be reconstructed later. Record that absence as UNKNOWN. Do not fill it with a guess.

`import_crosswalk.py` exits 1 when a held or failed ID has no source reason, or when a checkpoint row has no `signals` key. A finished process with only `outcome=failed` is not a usable result. The single-contact importer keeps that reason in `error_rows` and on the warning line, including when no outcome counter is open. A missing ERP person says which marker missed, for example `ERP marker plasticos_transaction.legacy_erp_contact_<CT_ID> resolved 0 rows`.
