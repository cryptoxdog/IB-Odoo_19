# Evidence: CRM to ERP approved identity, Docker run 2026-10-18

Review brief for the Copilot agent. Machine-readable receipt: `receipt.json`.

## Verdict (current rule, commit `750f9a0`)

735 of 763 approved VanillaSoft IDs bound to their ERP person (`bound_contacts.csv`). The other 28 failed closed because the ERP import has no person for their CT_ID (`failed_contacts.csv`). No approved ID created a `res.partner` or a `crm.lead`. A CRM replay wrote nothing. A later ERP replay left the approved contacts' database state byte-identical, so it kept every CRM note, phone line and call event. The final CRM replay after that ERP replay was intentionally not executed.

The operator corrected the requirement. A CRM contact note is now appended to the ERP person's `res.partner.comment`, the ERP notes already there are kept, and ERP and CRM replays must be idempotent. This replaces the rule this brief was first written under: a note needed a lead or a provider table row, otherwise the contact was blocked. That first run is kept below, under "First run under the old rule", and its CSVs are in `raw/old_rule_first_run/`.

How the code does it:
- **CRM side** (`plasticos_crm_sync/services/approved_identity.py`, `comment_with_note`): the note is added as its own `<p>` paragraph. Presence is whole-paragraph text equality, not a substring match, so a replay writes nothing.
- **ERP side** (`plasticos_partner_import/models/erp_import_service.py`, `_comment_with_erp_notes`, called from `_upsert`): when the ERP notes are already in the comment as one paragraph, or a run of adjacent ones, nothing is written. Otherwise they go first and every existing paragraph stays. Before this change an ERP replay rewrote the whole comment, which would have dropped the CRM notes.

Results on a fresh clone of the pinned fixture (files in `raw/comment_rule/`):

| Step | Result |
|---|---|
| Odoo runtime tests, `make test-module m=plasticos_crm_sync,plasticos_partner_import` | 0 failed, 0 errors of 136, including the new `test_approved_contact_notes_append_to_the_erp_comment_and_replay` |
| Pure-python tests | 39 passed |
| ERP import 1 (`ERP_PARTNERS_ONLY=1`) | seen 12,518 = created 7,682 + updated 2,115 + unchanged 1,432 + rejected 1,289; duplicates 0. Same counts as the first run. |
| ERP replay before any CRM write (`ERP_REQUIRE_EMPTY=0`) | created 0, updated 0, unchanged 11,229, rejected 1,289, duplicates 0 |
| CRM identity run 1, all 763 approved IDs | 735 bound to their ERP person, 28 failed (`no_erp_person` only), 0 bound to another partner, 0 new partners, 0 new leads, 0 exceptions |
| Field check on the 689 people, before vs after run 1 | phone changed 0; mobile set only where empty 102, overwritten 0; comment appended 350 (360 paragraphs), unchanged 339, ERP paragraphs lost 0, duplicate paragraphs 0; all 19 existing ERP notes kept |
| CRM replay 1, all 763 approved IDs | 735 unchanged, 28 failed (the same `no_erp_person` contacts), 0 created, 0 updated; every count flat; comment/phone/mobile snapshot identical to after run 1 |
| ERP replay after the CRM notes landed, run once | created 0, updated 0, unchanged 11,229, rejected 1,289, duplicates 0; 6 validators passed |
| Database state, before vs after that ERP replay | byte-identical (same SHA-256). 689 people identical including `write_date`; 360 CRM paragraphs and 19 ERP notes each present exactly once; 840 phone lines identical; 763 contacts' 735 refs and 50,494 call events identical; 0 failures |

What this proves:
- **CRM replay is idempotent** on live VanillaSoft data: CRM replay 1 wrote nothing.
- **An ERP replay keeps every CRM-owned addition:** after the CRM notes, phone lines and call events landed, one ERP replay wrote nothing to any approved person. The state was captured directly in Odoo before and after the replay (`scripts/approved_state.py`, compared by `scripts/compare_state.py`). The state files hold names, numbers and note text, so only their hashes are recorded.

What it does not prove:
- **Final CRM replay after the ERP replay: intentionally not executed.** The operator chose not to repeat the full 763-contact VanillaSoft fetch. Because the database state after the ERP replay is byte-identical to the state CRM replay 1 left, and CRM replay 1 wrote nothing, a CRM pass is expected to write nothing too. That is an inference, not a run.
- **The ERP branch that puts missing ERP notes first** was not reached on live data, because every ERP note was already in place. It is covered only by `tests/test_erp_import_contract.py`.
- **That the ERP replay would have erased the CRM notes before this change** comes from reading the old `_differs` comparison. It was not run.

Scripts: `scripts/comment_snapshot.py` prints each crosswalk person's comment, phone and mobile, and `scripts/compare_snaps.py` compares two of those snapshots. `scripts/approved_state.py` captures the full database state of the approved contacts, and `scripts/compare_state.py` compares two captures. None of them calls VanillaSoft. The snapshots and state files hold note text and stay out of this folder.

## Failed contacts (current rule)

`failed_contacts.csv` has 28 rows, all `no_erp_person` (27 CT_IDs; one CT_ID has two VanillaSoft IDs). Each row carries the orchestrator's reason and the ERP import's own explanation: the import rejected the contact because its company is not an exported active counterparty (`Contact unresolved_counterparty: CpID=… not in exported (active) counterparties`). Nothing was written for these IDs.

`bound_contacts.csv` has the 735 bound IDs. Every one has exactly one person ref, to the partner behind `plasticos_transaction.legacy_erp_contact_<CT_ID>`, with `lead_id` empty. Its columns: the VanillaSoft and CT IDs, the partner ID, that contact's call-event count, and on the person the number of ERP-note paragraphs, CRM-note paragraphs and phone lines. Both files were built from the database state captured after the ERP replay, with no VanillaSoft call.

## First run under the old rule (superseded)

Everything from here to "Contract rules quoted" describes the first run, before the comment rule. Its contact lists are `raw/old_rule_first_run/failed_contacts.csv` and `raw/old_rule_first_run/bound_contacts.csv`.

No approved VanillaSoft ContactID created a `res.partner` or a `crm.lead`. 374 of 763 approved IDs bound to their ERP person. 389 failed closed with a recorded reason, and nothing was written for them. A replay of all 763 IDs changed nothing.

The run is not the full-history proof. VanillaSoft rejects a Contacts floor older than 30 days, so `run_full_import` from 2019 cannot run. The 763 IDs went through the existing single-contact entry point instead. See "Not proven".

## Code under review

| Item | Value |
|---|---|
| Branch | `feat/crm-erp-approved-identity`; the first run used `795c388`, the comment-rule runs used `750f9a0` |
| Base | `origin/Staging` `4ac9bfa` |
| Commits | `c36d9e1` test fixture (open as [PR #261](https://github.com/cryptoxdog/IB-Odoo_19/pull/261)), `097cba2` approved identity, `795c388` test tagging, `750f9a0` CRM notes to `res.partner.comment` |
| Modules | `plasticos_crm_sync` `19.0.1.8.9` for the first run, `19.0.1.8.10` now; `plasticos_partner_import` `19.0.2.10.25` now |
| Main files | `plasticos_crm_sync/services/approved_identity.py`, `plasticos_crm_sync/services/orchestrator.py` (`_load_approved_crosswalk`, `_erp_person_for_ct`, `_add_approved_phones`, `_bind_approved_contact`), `plasticos_partner_import/models/erp_import_service.py` (`_upsert`, `_comment_with_erp_notes`) |

## Environment

All writes went to one disposable database. Nothing ran against hosted Odoo.sh Staging or Production.

| Item | Value |
|---|---|
| Fixture | `odoo_test_tpl_ee_c9e8a81f52f23680` (Enterprise, 169 modules, us chart), pinned in `config/test_env_fixture.conf` |
| Clone | `odoo_test_w2495f48767`, a fresh clone of the fixture, all writes through `scripts/test_env.sh run` |
| ERP source | The restored ERP database (2026-10-03 backup; name supplied at run time as `ERP_SQL_DATABASE`) in SQL Server 2022 container `cie-sql-proof`, database set `READ_ONLY`, read as login `erp_reader` (`db_datareader` only) |
| CRM source | VanillaSoft API, project `139705`, read-only calls. API key bound from Infisical with `capability_bind` and written to the clone's `ir.config_parameter`; it was never printed |
| Crosswalk | `03_APPROVED_CONTACT_CROSSWALK.csv`, SHA256 `f22c707a7b6fceba40a20fa393e0c8887e3f05a8d183865ca28f0ccfc16fede2`, 763 VS IDs to 716 CT_IDs, unmodified. Set as `plasticos_crm_sync.approved_contact_crosswalk` |

The crosswalk and the operator contract live in a gitignored folder. The contract rules this review depends on are quoted at the end.

## Steps and results

1. **Odoo runtime tests** (`raw/odoo_runtime_tests.txt`)
   - The standard `make test-module m=plasticos_crm_sync` run on a fresh clone gave 0 failed, 0 errors of 50 tests.
   - The 2 tests tagged `crm_sync_semantic_kernel` need the optional `plasticos_semantic_kernel` module. On the same clone, with that module installed, they gave 0 failed, 0 errors.
2. **ERP partners-only import** (`raw/erp_import_partners_only_console.txt`, `raw/erp_import_partners_only_summary.json`)
   - The import is `make import-erp ERP_PARTNERS_ONLY=1`, a direct SQL read.
   - All five layer validators passed: counterparties, addresses, contacts, roles, salesreps.
   - Seen 12,518 = created 7,682 + updated 2,115 + unchanged 1,432 + rejected 1,289. Duplicates: 0. `final_status` is `partial` because of the rejections.
   - The summary's `errors` list is capped at 1,000 of the 1,289 rejections.
3. **Full VanillaSoft import** (`raw/vanillasoft_full_import_2019_floor.txt`, `raw/vanillasoft_contacts_lookback_probe.txt`)
   - `make import-vanillasoft` with a 2019-01-01 floor failed on the first `/Contacts` page with HTTP 400 and an empty body. It wrote nothing.
   - A direct probe found that VanillaSoft accepts a 30-day floor and rejects 31 days, 32 days, 60 days and 2019.
4. **Approved identity run** (`raw/identity_run_1.json`, `scripts/vs_identity_run.py`)
   - Each of the 763 approved IDs went through `SyncOrchestrator.upsert_contact_external_id` in its own savepoint.
   - That entry point loads the crosswalk, fetches the contact by ID, and runs `_upsert_lead`, which binds approved IDs.
5. **Replay** (`raw/identity_replay.json`): the same script on the same clone.
6. **Failure detail** (`raw/old_rule_first_run/failed_contacts.csv`, `scripts/vs_failed_detail.py`)
   - Each failed ID was re-run read-only to record its exact reason, then the transaction was rolled back.
   - Reference, phone-line and call counts were identical before and after.

| Count | Before run 1 | After run 1 | After replay |
|---|---|---|---|
| `res.partner` | 5,196 | 5,196 | 5,196 |
| `crm.lead` | 0 | 0 | 0 |
| Person refs (`plasticos.crm.external.ref`, `res_model=res.partner`) | 0 | 374 | 374 |
| Phone lines (`plasticos.partner.phone`) | 1,434 | 1,627 | 1,627 |
| Call events | 0 | 22,834 | 22,834 |
| Provider table rows | 0 | 0 | 0 |

| Outcome per ContactID | Run 1 | Replay |
|---|---|---|
| `updated` | 374 | 0 |
| `unchanged` | 0 | 374 |
| `failed` | 389 | 389 |
| `created` or `duplicate_rejected` for an approved ID | 0 | 0 |

Checks on the 374 bound contacts:

- **Bindings:** all 374 person refs point at the partner behind `plasticos_transaction.legacy_erp_contact_<CT_ID>`. None points at another partner, and every ref has `lead_id` empty.
- **Phone lines:** run 1 added 193 lines: 154 labelled `other` and 39 labelled `mobile`.
  - All 39 `mobile` lines went to people who had no mobile line. Rule 01 §3.5 Phones allows that.
  - Because `res.partner.mobile` is computed from the first `mobile` line, those 39 people now show the CRM number as Mobile. The sync never writes `mobile`.
- **ERP fields:** `phone` and `comment` were unchanged on every crosswalk person.
- **Call history:** 22,834 events were written, all with `lead_id` empty. Each one belongs to a ContactID that has a person ref (370 contacts), and no provider call ID is duplicated.

## Failed contacts in the first run

`raw/old_rule_first_run/failed_contacts.csv` has one row per failed ID: 389 rows, all with `status=failed`. `raw/old_rule_first_run/bound_contacts.csv` lists the 374 bound IDs with their partner ID. Under the comment rule the 361 `note_has_no_holder` IDs bind; the 28 `no_erp_person` IDs still fail.

| `failure_class` | IDs | Reason |
|---|---|---|
| `note_has_no_holder` | 361 | The ERP person exists. The CRM contact note has no `crm.lead` and no landed `plasticos.crm.external.table.row` to hold it, so rule 01 §3.5 Notes stops the ContactID as BLOCKED. The whole binding rolls back for that ID: no ref, no phone lines, no calls. |
| `no_erp_person` | 28 (27 CT_IDs) | `legacy_erp_contact_<CT_ID>` resolved 0 rows. The ERP import rejected that contact because its company is not an exported active counterparty (`Contact unresolved_counterparty: CpID=… not in exported (active) counterparties`). 16 of these have a CRM note and 12 don't. |

CSV columns:

| Column | Meaning |
|---|---|
| `vs_id`, `ct_id` | The crosswalk pair |
| `erp_marker_rows`, `erp_partner_id` | ERP person resolution |
| `contact_note_present`, `contact_note_chars` | The VanillaSoft `Notes` custom field. The note text is not copied here |
| `crm_phone_numbers` | Distinct CRM numbers on the contact |
| `existing_lead_for_vs_id`, `provider_table_rows` | The two places a note can be held. Both are 0 for every failed ID |
| `reason` | The orchestrator's own message |
| `explanation` | The root cause in plain words |

Why there is no lead or table row:

- **No leads:** the clone holds no VanillaSoft leads. They would come from the full import, and step 3 shows the full import cannot reach them.
- **No table rows:** VanillaSoft returned no custom table rows for any approved contact.

On a database where these contacts already have a VanillaSoft lead, rule 01 §3.5 appended the note to `crm.lead.description` instead of blocking. Commit `750f9a0` removed both that path and the BLOCKED stop: the note now goes to `res.partner.comment`.

## Not proven (current)

1. **Final CRM replay after the ERP replay:** intentionally not executed. Its expected no-op is inferred from the byte-identical state, not run.
2. **The ERP branch that puts missing ERP notes first** was not reached on live data. Only `tests/test_erp_import_contract.py` covers it.
3. **Full-history import** and **non-approved contacts:** still blocked by the VanillaSoft 30-day limit, as below.

## Not proven in the first run

1. **Full-history import:** contract item 8 asks for full history for project `139705` through `run_full_import`, with exact contact page counts and watermarks. That cannot be done now:
   - The provider returns 400 on any Contacts floor older than 30 days.
   - `CONTACT_LOOKBACK_MAX_DAYS = 31` in `orchestrator.py`, but the probe shows 31 days already returns 400.
   - The full import deliberately sends the operator's floor unclamped. It then fails outright instead of reporting a clamp.
2. **Note on a lead:** appending a note to an existing lead (contract acceptance 5) was not exercised against live data, because the clone has no leads. This item is moot under the comment rule: `750f9a0` no longer writes notes to a lead.
3. **Non-approved contacts:** contacts outside the crosswalk were not imported, because the full import failed. That path is unchanged by this branch.

## Questions for the reviewer

1. ~~Should the 361 `note_has_no_holder` contacts stay BLOCKED?~~ Answered by the operator: notes go to `res.partner.comment` (commit `750f9a0`).
2. Is `CONTACT_LOOKBACK_MAX_DAYS = 31` wrong against the observed 30-day limit? Should `run_full_import` refuse a floor older than the lookback before any request?
3. Is the single-contact entry point `upsert_contact_external_id` acceptable evidence for the identity rules until a full import is possible?

## Contract rules quoted (from the gitignored pack `01_CRM_ERP_MATCHING_RULES.md`)

- §3.3: "If missing/ambiguous, **defer only that ID** with exact reason; never guess by name/email or create a lead/person as fallback."
- §3.4: "**Create zero new `res.partner` and zero new `crm.lead` records for approved links**. The run that writes this ref, a note, or a phone line is outcome `updated`. A later run that finds the same ref and appends nothing is `unchanged`."
- §3.5 Notes (superseded by the operator's comment rule, see the top of this brief): "When no lead exists, do not create one to hold the note. Keep the note recoverable on the landed `plasticos.crm.external.table.row` for that ContactID (`lead_id` empty). If neither a lead nor a landed provider row can hold it without a new field, stop that ContactID as **BLOCKED** and do not drop the text into `res.partner.comment`."
- §3.5 Phones: "On an approved link, never assign `res.partner.phone` and never assign `res.partner.mobile`, even when those values are empty. … A new mobile uses label `mobile` only when no mobile line exists; when a mobile line already exists, the new number uses label `other`."

## Reproduce

The scripts in `scripts/` are the ones that produced these results. For repo lint, each copy gained a docstring and an `env = globals().get("env")` line, and was run through `ruff format`. Their logic is unchanged.

Run from the repo root with Docker up and `cie-sql-proof` restored:

```bash
DB=$(bash scripts/test_env.sh name)
bash scripts/test_env.sh clone "$DB"
ERP_SQL_PASSWORD="$(cat ~/.l9/erp-proof/reader.pw)" bash scripts/test_env.sh run "$DB" -- make import-erp ODOO_DB_NAME="$DB" \
  ERP_PARTNERS_ONLY=1 ERP_SQL_SERVER=host.docker.internal ERP_SQL_PORT=14330 ERP_SQL_USER=erp_reader ERP_SQL_DATABASE="$ERP_SQL_DATABASE"
# set plasticos_crm_sync.approved_contact_crosswalk and plasticos_crm_sync.vanillasoft_api_key on the clone
S=docs/reports/evidence/crm-erp-approved-identity-2026-10-18/scripts
shell() { bash scripts/test_env.sh run "$DB" -- docker compose run --rm -T odoo odoo shell -d "$DB" --no-http < "$1"; }
shell $S/comment_snapshot.py > before_crm.txt    # S0
shell $S/vs_identity_run.py                       # CRM run 1, then again for the CRM replay
shell $S/approved_state.py > state_before_erp.txt
ERP_SQL_PASSWORD="$(cat ~/.l9/erp-proof/reader.pw)" bash scripts/test_env.sh run "$DB" -- make import-erp ODOO_DB_NAME="$DB" \
  ERP_PARTNERS_ONLY=1 ERP_REQUIRE_EMPTY=0 ERP_SQL_SERVER=host.docker.internal ERP_SQL_PORT=14330 ERP_SQL_USER=erp_reader ERP_SQL_DATABASE="$ERP_SQL_DATABASE"
shell $S/approved_state.py > state_after_erp.txt
# strip the SNAPSHOT / STATE prefixes, then:
python3 $S/compare_state.py before_crm.json state_before_erp.json state_after_erp.json
```
