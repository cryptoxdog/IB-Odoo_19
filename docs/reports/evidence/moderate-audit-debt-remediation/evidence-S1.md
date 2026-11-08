# Evidence S1 — Security findings: read-only investigation and bounded remediation proposal

- Repository: `/home/user/IB-Odoo_19`
- Branch: `claude-mobile/gracious-keller-brsxxa`
- HEAD: `237b2e0` (`237b2e00f1b83564906dbafe59e32aebebb32781`)
- Date: 2026-11-05
- **READ-ONLY; proposal only; no authorization to change security definitions.** No source, security, hook or test file was modified. This file is the only artifact written. This item decides nothing (plan task S1).
- Container: no Odoo runtime, no Odoo checkout (`import odoo` fails). Core facts were fetched from `github.com/odoo/odoo` branch `19.0` into the session scratchpad and are cited `core:<path>:<line>`. Every statement needing a running Odoo is marked **RUNTIME-REQUIRED** with the exact test.
- Prior evidence reused, not redone: `evidence-A1.md` (sudo audit; collateral findings 1–4; frozen sites #2, #3, #8, #34; unresolved #20). Git history is shallow at `6530d68` (`git rev-parse --is-shallow-repository` = true, 169 commits), so pre-2026-10-24 history was read through `gh api repos/cryptoxdog/IB-Odoo_19/commits` and is cited `remote:<sha>`.

## Core facts used by more than one section

| Key | Evidence |
|---|---|
| K1 core ACL on `ir.model.data` | `core:odoo/addons/base/security/ir.model.access.csv:19` `access_ir_model_data_user … base.group_user,0,0,0,0`; `:15` `access_ir_model_data_group_erp_manager … group_erp_manager,1,1,1,1` |
| K2 ACL check is a union and is bypassed by su | `core:odoo/addons/base/models/ir_model.py:2178-2190` `IrModelAccess.check`: `if self.env.su: return True`; otherwise `model in self._get_allowed_models(mode)`, which is one SQL over all rows whose `group_id IS NULL OR group_id IN <user groups>` (`:2157-2173`). Any one granting row is sufficient; a stricter row for a smaller group changes nothing. |
| K3 `search` enforces read ACL | `core:odoo/orm/models.py:5343-5372` `_search` → `self.browse().check_access('read')` |
| K4 xmlid lookup and xmlid upsert never touch the ACL | `env.ref` → `_xmlid_to_res_model_res_id` → `_xmlid_lookup` is raw SQL (`core:odoo/orm/environments.py:158-172`, `core:odoo/addons/base/models/ir_model.py:2297-2306`). `_update_xmlids` is a raw `INSERT … ON CONFLICT` (`core:…/ir_model.py:2392-2455`). Core import (`base_import` → `model.load` `core:addons/base_import/models/base_import.py:1488`) assigns xmlids through `_load_records`, which does `imd = self.env['ir.model.data'].sudo()` (`core:odoo/orm/models.py:5138`). Core therefore gives employees no `ir.model.data` rows and needs none for the generic Import UI. |
| K5 `odoo shell` env is superuser | `core:odoo/cli/shell.py:139-141` `uid = api.SUPERUSER_ID; … env = api.Environment(cr, uid, ctx)` |
| K6 cron runs as the job's `user_id` | `core:odoo/addons/base/models/ir_cron.py:426` and `:482` `api.Environment(cron_cr/job_cr, job['user_id'], …)` |
| K7 blanket `_all` rows origin | `remote:69eb818b4` (2026-03-11) "fix(security): grant full CRUD access to all plasticos models for internal users — Adds base.group_user with 1,1,1,1 (full access) to ALL plasticos models. This removes all ACL blockers for imports and data entry. **Security can be tightened after deployment is stable.**" — 19 `ir.model.access.csv` files in one commit, including `plasticos_base` and `plasticos_documents`. 32 `_all,` rows survive today across 13 addon CSVs (`grep -c '_all,' plasticos_*/security/ir.model.access.csv`). |

---

## S1 — `access_ir_model_data_import` (`plasticos_base/security/ir.model.access.csv:5`)

Row: `access_ir_model_data_import,ir.model.data import for internal users,base.model_ir_model_data,base.group_user,1,1,1,0` — read, write, create on `ir.model.data` for every internal user; unlink withheld. `plasticos_base` is a dependency of every PlasticOS module (A1 C1b), so the row is live wherever PlasticOS is installed.

### S1(a) Code paths that touch `ir.model.data` as a non-superuser

Inventory: `grep -rn 'ir\.model\.data' plasticos_*/ --include=*.py` (non-test) — 20 call sites in 12 files, classified below by acting user.

| Path | Entry point and acting user | Reads / writes `ir.model.data` | Needs the repo grant? |
|---|---|---|---|
| **Canonical ERP import** `make import-erp` | `Makefile:1013-1034`: `docker compose run … odoo odoo shell -d $(ODOO_DB_NAME) --no-http < plasticos_partner_import/scripts/import_erp_shell.py` (no-Docker branch `:1037-…` is also `odoo shell`). The script takes `env` from the shell globals (`import_erp_shell.py:81-86 _odoo_env`), so uid is `SUPERUSER_ID` (K5). `main()` `:383-440` → `run_erp_import.run(env, …)` `:63,:429` → `env["plasticos.erp.import"].run(...)` (`scripts/run_erp_import.py:73`). | Read: `erp_import_service.py:613, 775, 940, 960, 1013, 1029, 1129, 1164`. Write: create `:1176-1185` (`_write_identity_marker`). **Unlink**: `:1148 data.unlink()` and `:1172 data.unlink()` (stale marker replacement). | **No.** The service is `su` (K2 first line). Decisive: it *unlinks* markers, and the grant withholds unlink — if the grant were the acting ACL the import would already fail at `:1148`/`:1172`. It does not fail, so the import does not run under this grant. No service user: the identity is the shell superuser. |
| **VanillaSoft import** `make import-vanillasoft` | `Makefile:1071-1079`: `odoo shell … < plasticos_crm_sync/scripts/import_vanillasoft_shell.py` → superuser (K5) → `get_or_create_vanillasoft_connection()` `:110` → orchestrator. The same orchestrator also runs from cron `user_system_cron` (`plasticos_crm_sync/data/ir_cron_data.xml:12`) and from `action_sync_now` by any internal user (A1 #3 path c). | Read only: `plasticos_crm_sync/services/orchestrator.py:1469` `imd = self.env["ir.model.data"].sudo()  # XMLID rows are system data the sync user must read`. No write (`:2556` is a docstring saying the sync does not repair `ir.model.data`). | **No.** Already `sudo()` for exactly the non-su callers. |
| **Legacy partner import wizard** (the rationale in the commit message, see S1(b)) | `plasticos_partner_import/wizards/partner_import_wizard.py:111-116 action_import` → `_ensure_legacy_ui_retired()` `:28-36` raises `UserError` **unconditionally** ("Raised unconditionally… a direct RPC call_kw or a shell call … must not run the legacy CSV import either"). Wizard ACL is `base.group_system` only (`plasticos_partner_import/security/ir.model.access.csv:6`). Service entry points `run_full_import` `:242-254`, `run_csv_import` `:270-281` and `:84` call `_check_import_operator()` `:35-46`, which passes only `env.su`, `SUPERUSER_ID` or `is_system()`. Contract test: `tests/test_legacy_import_ui_retired.py:128 test_wizard_acl_is_system_only`, `:140`, `:163 test_service_import_entry_points_are_guarded_against_rpc_callers`. | Read `partner_import_service.py:122`; create `:130-139`, `:145-150` — unsudo'd, as the acting user. | **No.** The only reachable non-su actor is a `base.group_system` admin, and `group_system` implies `group_erp_manager`, which already holds 1,1,1,1 in core (K1 `:15`). |
| `plasticos.partner.import.validation` | `validate_reference_integrity` reads `:91-100` (public, unguarded, callers: the guarded service `partner_import_service.py:257,265,288,298` and the retired wizard `:228,267`); `repair_import_data` writes `d.module = …` `:200` behind `_check_import_operator()` `:176`. | Read; one guarded write. | **No** for every production caller (su or system admin). A direct RPC `validate_*` by a plain employee would need read — there is no such caller in the repo. |
| `_historical_transaction_ids` `plasticos_commission/models/commission_payout.py:130-141` (A1 #2) | `write` `:153-157`, `create` `:159-166`, `action_confirm`, `action_generate_for_rep` — interactive `group_accounting_ops` / `group_operations_manager` users (A1 #2). | **Read** (`search` on module/model/res_id/name) via `.sudo()` `:132`. | **No** — elevated in code. Without the grant *and* without the sudo, K1+K3 would raise `AccessError`. |
| `_historical_source_ids` `plasticos_transaction/models/account_move_inherit.py:36-51` (A1 #34) | `account.move.write/button_cancel/action_post/unlink`, `account.move.line` create/write — invoicing users (A1 #34). | **Read** via `.sudo()` `:38`. | **No** — elevated in code; same remark as #2. |
| `role_tag_binding` `plasticos_crm_bridge/models/crm_tag_adoption.py:22-27` (A1 #3) | (a) module data `<function>` and (b) migration → superuser; (c) CRM sync → `user_system_cron` or any internal user via `action_sync_now` (A1 #3). | **Read** via `.sudo()` `:24`. `:52` create is reached only from (a)/(b) (A1 #7). | **No** — elevated in code. |
| `_historical_erp_moves` `plasticos_transaction/models/transaction.py:920-940` | Sole caller `_auto_post_pending_invoices` `:892-917`; `grep -rn '_auto_post_pending_invoices('` finds **no production caller**. | **Read, unsudo'd** `:929`. | Dead path today. If it is ever called by a non-system user it would need the grant or a `sudo()` — list it as a follow-up site, not a reason to keep the grant. |
| Transaction CSV import `plasticos_transaction/models/transaction_import_service.py:282-291 _create_external_id` | Driver `plasticos_transaction/scripts/run_transaction_import.py:19 run(env, …)` (shell env, superuser). `run_csv_import` `:50` has **no** `_check_import_operator`-style guard (collateral, below). | Create, unsudo'd. | **No** for the shell driver (su). |
| Historical document realization `plasticos_transaction/models/native_document_import.py:544, 1571` | `legacy_erp_import_service.py:17-19 realize(self, …)` ← `_extend_historical_import` ← the ERP `run` (superuser). | Read + unlink, unsudo'd. | **No** (su). |
| `post_init_hook`s `plasticos_{automation,geolocalize,intake_normalizer,logistics,offer,transaction}/hooks.py:17,37` (and `:48,:68`) | Module loading env is superuser (A1 C10). | Read via `.sudo()`. | **No**. |
| `scripts/validate_partner_layer.py:148,178,500`, `plasticos_dev_tools` | Shell/operator scripts (su). | Read. | **No**. |

Conclusion (a): **no non-superuser code path requires write or create on `ir.model.data`, and every non-superuser read is already `sudo()`-elevated in code.** The two canonical imports run as the `odoo shell` superuser, not as a service user and not as `base.group_user`.

### S1(b) Why the row exists — git history

Shallow clone: `git log -S access_ir_model_data_import -- plasticos_base/security/ir.model.access.csv` returns only the graft `6530d68` (PR #303 merge). Remote history (`gh api repos/cryptoxdog/IB-Odoo_19/commits?path=…`):

- `remote:fb358c910` 2026-03-11 "fix(security): add ir.model.access.csv for plasticos.midnight.recompute (#32)" — created the file with the user/manager rows (S2).
- `remote:69eb818b4` 2026-03-11 — blanket `_all` rows on 19 CSVs (K7).
- `remote:90db3244e` 2026-03-12 "fix(security): grant ir.model.data create access to internal users" — added row 5. Message: *"Allow internal users (base.group_user) to create ir.model.data records, which is required for import wizard functionality. Without this, non-admin users get 'Access Error: You are not allowed to create Model Data (ir.model.data) records' when using Import Partners or other import wizards. Also add ir.model.data to core_models whitelist in orphan check script. Note: Unlink (delete) permission is NOT granted to prevent accidental deletion of XML IDs."* (`ci/check_orphan_model_refs.py:72` still carries that whitelist entry.)

The error quoted in the message is exactly what `partner_import_service.py:130/145` (unsudo'd `create`) produced for a non-admin clicking the wizard. That wizard is now unconditionally retired and the service refuses non-system callers (S1(a) row 3). **The rationale no longer exists.** "Other import wizards" is covered by K4: the core Import UI never needed the grant.

### S1(c) Odoo core ACL for `group_user`

K1: `core:odoo/addons/base/security/ir.model.access.csv:19` grants `base.group_user` **0,0,0,0**; only `group_erp_manager` (`:15`) — implied by `group_system` — holds 1,1,1,1. The repo row is therefore a widening of a deliberate core denial for every employee, with write on the table that binds every XML id (security groups, record rules, menus, actions, crons) to its record: an employee with write on `ir.model.data` can re-point `plasticos_documents.group_documents_manager` or any `ir.rule` xmlid to another record (the row is `module,name,model,res_id`; `_update_xmlids` is the only guarded writer and it is not involved in an ORM `write`). Core's `ir.model.data.write` has no extra guard (`core:…/ir_model.py:2350`).

### S1(d) Can the grant be narrowed without breaking `make import-erp`?

Yes — and it can be **removed**, not merely narrowed:

- `make import-erp` and `make import-vanillasoft` are superuser (K5); the ACL is never consulted (K2). The unlink evidence in S1(a) row 1 is the proof that the grant is not on the import's path.
- A dedicated import group or a service user would be a new security definition for a path that has no non-su actor. Nothing in the repo would be a member of it. Not recommended.
- Read-only for `group_user` (1,0,0,0) is the fallback shape if the operator wants employees to keep reading xmlid rows generically; nothing in the repo requires it (every non-su read is sudo'd), and core gives employees no read.
- Removing the grant also fails closed on the unguarded RPC-reachable entry points `plasticos.erp.import.run` (`erp_import_service.py:88`, no operator check) and `plasticos.transaction.import.service.run_csv_import` (`transaction_import_service.py:50`, no operator check): a non-system caller would be stopped at the first `ir.model.data` search (K3) instead of proceeding until the first `data.unlink()`.

### S1(e) Consequence for PR-A frozen sites #2, #3, #34

All three are **reads** (`search` → K3 read check):

| Grant shape | #2 `commission_payout.py:132` | #3 `crm_tag_adoption.py:24` | #34 `account_move_inherit.py:38` |
|---|---|---|---|
| Kept as is (1,1,1,0) | UNNECESSARY (A1) | UNNECESSARY (A1) | UNNECESSARY (A1) |
| Narrowed to read-only (1,0,0,0) | stays UNNECESSARY | stays UNNECESSARY | stays UNNECESSARY |
| **Removed (proposed)** | **NECESSARY** — accounting/operations users hold no `group_erp_manager`; core denies read (K1) | **NECESSARY on path (c)** (`user_system_cron` and any internal `action_sync_now` user); paths (a)/(b) stay su and the call is a no-op there | **NECESSARY** — invoicing users hold no `group_erp_manager` |

So the decision is coupled: PR-A must keep `sudo()` at #2, #3, #34 and give each the same-line comment `# sudo: ir.model.data is group_erp_manager-only in core (base ACL); <actor> lacks it; reads legacy-ERP marker rows only` if S1 is resolved by removal; it may remove them only if the operator keeps a read grant. Three scoped, read-only elevations are less privilege than one repo-wide write grant; removal is the recommended shape. `_historical_erp_moves` (`transaction.py:929`) is the only unsudo'd read that would need the same treatment if its dead caller is ever wired.

### S1 proposal and proof

Proposed change (not applied): delete `plasticos_base/security/ir.model.access.csv:5`. Fallback: `…,base.group_user,1,0,0,0`. Odoo removes the obsolete `ir.model.access` row on `-u plasticos_base` (data no longer present in the module's data is dropped by the loader's `_process_end` for non-noupdate records).

Tests that would prove canonical imports still work (none exist today; `grep -rl access_ir_model_data_import tests plasticos_*/tests` is empty):

1. **Static (runs in CI, no Odoo):** a `tests/test_*.py` assertion that no `plasticos_*/security/ir.model.access.csv` row targets a `base.model_*` core model for `base.group_user` with write or create; and an AST assertion (style of `tests/test_legacy_import_ui_retired.py:163-180`) scoped to the RPC-reachable surface: every `env["ir.model.data"]` ORM call in `plasticos_*/models/**` is either chained with `.sudo()`, inside a method that calls `_check_import_operator()`, or inside one of the catalogued superuser-only paths that must be listed as explicit exemptions with their proof — the ERP import service (`erp_import_service.py:613, 775, 940, 960, 1013, 1029, 1129, 1148, 1164, 1172, 1176`, reached only through `odoo shell` per S1(a) row 1) and the historical document realization (`native_document_import.py:544, 1571`, reached only through that same `run`). The one call outside both sets today is `transaction.py:929` (dead caller, S1(a)). Without those exemptions the assertion fails on the first run; with them it also pins the claim that no RPC-reachable path touches `ir.model.data` unelevated, which collateral 1 (the unguarded `run` entry points) currently violates, so the exemption list must shrink when those guards land.
2. **RUNTIME-REQUIRED — imports:** on the admitted clone (`scripts/test_env.sh clone`), `ERP_DRY=1 make import-erp`, then `make import-erp` (full), then `python3 scripts/validate_import_summary.py .l9/pr/import-erp-summary.json` (fail-closed equality `records_seen == created+updated+unchanged+rejected`, `duplicates == 0`); `make import-vanillasoft` likewise. Expected: identical results before and after the row change (the path is su).
3. **RUNTIME-REQUIRED — Odoo tests:** `make test-module m=plasticos_base` with a new test: `self.env["ir.model.data"].with_user(internal).search([])` raises `AccessError` and `.create({...})` raises `AccessError` (proves the grant is gone); `make test-module m=plasticos_commission` / `m=plasticos_transaction` / `m=plasticos_crm_bridge`: `plasticos.commission.payout.write` as an accounting-ops user, `account.move.action_post` as an `account.group_account_invoice` user, and `crm.connection.action_sync_now` as a plain internal user complete without `AccessError` (proves the retained `sudo()` at #2/#34/#3 is sufficient).

---

## S2 — `access_plasticos_midnight_recompute_all` (`plasticos_base/security/ir.model.access.csv:2-4`)

Rows: `:2` user `base.group_user` 1,0,0,0; `:3` manager `base.group_system` 1,1,1,1; `:4` `_all` `base.group_user` 1,1,1,1.

Model: `plasticos_base/models/midnight_recompute.py:24-33` `class PlasticosMidnightRecompute(models.AbstractModel)`, `_name = "plasticos.midnight.recompute"`. Its own docstring `:27-29`: *"AbstractModel = no database table, no ACL needed. This is a service class, not a data model. Audit tools may flag MISSING_ACL but this is a false positive for AbstractModel classes."* Fields: none. Public methods: none — `_cron_midnight_recompute` `:35-58` is `_`-prefixed (not RPC-callable) and holds an advisory lock; `_recompute_document_expiry` `:60` and `_recompute_claim_time_fields` `:63` are extension points implemented in `plasticos_documents/models/midnight_recompute.py:25-92` and `plasticos_claims`.

What creating or writing a record does: **nothing can be created or written.** An AbstractModel has no table; `create`/`write`/`unlink` on it cannot persist and the ACL is consulted only for ORM CRUD (K2), never for method calls. The `_all` row grants CRUD on an object that has no rows and no fields. It triggers no recomputation: the recompute runs only from the cron `plasticos_base/data/midnight_recompute_cron.xml:16-26` (`code = model._cron_midnight_recompute()`, `user_id = plasticos_base.user_system_cron`), as the cron user (K6), without `sudo()` — the documents extension writes `plasticos.document.is_expired` via `batch._compute_is_expired()` (`plasticos_documents/models/midnight_recompute.py:76`) and recomputes `plasticos.transaction` flags via `_compute_missing_doc_flags()` / `_compute_compliance()` (`:86-89`) in the cron user's env, so its rights come from the hook grants in S4(b), not from these rows.

Is `_all` intentional? No evidence that it is: `:2-3` were added by `remote:fb358c910` (#32 "add missing ACL for plasticos.midnight.recompute") to silence an audit, contradicting the model's own comment; `:4` arrived with the blanket `remote:69eb818b4` (K7), which added the same row to every model mechanically. The user row therefore exists because an audit demanded *an* ACL row, and the `_all` row exists because a later commit added `_all` everywhere — neither was a decision about this model. CI does not need them: `ci/check_acl_completeness.py:19-32,60` skips `AbstractModel`/`TransientModel` classes.

Proposed row set (not applied): **delete rows 2, 3 and 4.** After S1 the file would hold only its header; keeping a header-only CSV in `__manifest__.py` `data` is harmless (zero records), or the file may be dropped from the manifest with the file — operator's choice, both are a `plasticos_base` change under the plan's `write_deny`.

Risk: none at runtime (no table, no fields, no UI). Residual: a scanner that counts "models without ACL" must keep skipping abstract models (it does).

Tests: static — assert that no `ir.model.access.csv` row in `plasticos_*` names a model whose class is `AbstractModel` (reuse `_class_defines_abstract_or_transient` from `ci/check_acl_completeness.py:19`). **RUNTIME-REQUIRED:** `make test-module m=plasticos_base` after `-u plasticos_base` loads with the rows removed, and `env.ref("plasticos_base.ir_cron_midnight_recompute").method_direct_trigger()` as `user_system_cron` completes (the cron's rights are S4(b)'s concern, not these rows').

---

## S3 — `plasticos_documents/security/ir.model.access.csv` `access_*_all` rows (`:10-13`)

### Inputs

ACL (`plasticos_documents/security/ir.model.access.csv`):

| Line | id | model | group | r,w,c,u |
|---|---|---|---|---|
| 2 | `access_document_user` | document | `group_documents_user` (DU) | 1,1,1,0 |
| 3 | `access_document_manager` | document | `group_documents_manager` (DM) | 1,1,1,1 |
| 4 | `access_document_tag_admin` | tag | `base.group_system` | 1,1,1,1 |
| 5 | `access_document_tag_read` | tag | DU | 1,0,0,0 |
| 6 | `access_document_rule_admin` | rule | `base.group_system` | 1,1,1,1 |
| 7 | `access_document_rule_read` | rule | DU | 1,0,0,0 |
| 8 | `access_validation_matrix_user` | matrix | `base.group_user` (U) | 1,0,0,0 |
| 9 | `access_validation_matrix_manager` | matrix | `group_documents_extension_manager` (DEM) | 1,1,1,1 |
| **10** | `access_document_all` | document | **U** | **1,1,1,1** |
| **11** | `access_document_tag_all` | tag | **U** | **1,1,1,1** |
| **12** | `access_document_rule_all` | rule | **U** | **1,1,1,1** |
| **13** | `access_validation_matrix_all` | matrix | **U** | **1,1,1,1** |

Rows 10–13 were added by `remote:69eb818b4` (K7); rows 2–9 predate it (`remote:375815a4e`, `ad8d37e28`, `8826e4eac`).

Groups (`plasticos_documents/security/security.xml:15-33`): DU; DM `implied_ids` DU (`:23`); DEM `implied_ids` DM (`:29`, comment "Manages document validation matrix and extended document rules"). No PlasticOS group implies a core group, and `plasticos_security_base` neither defines nor implies any documents group (`grep -rn group_documents plasticos_security_base/` is empty). Every DU/DM/DEM member is an internal user, hence also in U.

Record rules: **none** on any of the four models anywhere (`grep -rn model_plasticos_document plasticos_*/security plasticos_*/data --include=*.xml` finds only the cron `plasticos_documents/data/cron.xml:6`).

UI gating: form buttons `document_views.xml:69-70` Associate (`groups=DU`), `:71-73` Verify (`groups=DU`), `:74-76` Override (`groups=DM`). Menus `menu_documents_root`/`menu_documents_list` (`:146-155`) and `menu_validation_matrix` (`validation_matrix_views.xml:54-58`) carry **no `groups=`**; tag and rule views define no action or menu at all (`document_tag_views.xml`, `document_rule_views.xml`: no `act_window`, no `menuitem`), so tags/rules are reachable only by RPC, developer mode or code.

### Effective permission per model per group (ACL union K2 + rules + inheritance)

| Model | Plain internal user (U) | DU | DM | DEM | `base.group_system` | Intended by rows 2–9 |
|---|---|---|---|---|---|---|
| `plasticos.document` | **r,w,c,u** (row 10) | r,w,c,u | r,w,c,u | r,w,c,u | r,w,c,u | U none; DU r,w,c; DM +unlink |
| `plasticos.document.tag` | **r,w,c,u** (row 11) | r,w,c,u | r,w,c,u | r,w,c,u | r,w,c,u | DU read; system CRUD |
| `plasticos.document.rule` | **r,w,c,u** (row 12) | r,w,c,u | r,w,c,u | r,w,c,u | r,w,c,u | DU read; system CRUD |
| `plasticos.document.validation.matrix` | **r,w,c,u** (row 13) | r,w,c,u | r,w,c,u | r,w,c,u | r,w,c,u | U read; DEM CRUD |

Because the union includes row 10–13 for everyone, rows 2–9 are moot for CRUD; no record rule narrows anything; the only effective separation of roles is in Python.

### What the design reserves for managers, and what compensates today

`plasticos_documents/models/document.py`:

- Commands are group-gated in code: `_require_verifier` `:526-528` (`VERIFIER_GROUP = DU`, `:49`) on `action_associate` `:654`, `action_verify` `:750`, `action_supersede` `:802`; `_require_override_manager` `:530-532` (`OVERRIDE_GROUP = DM`, `:50`) on `action_override` `:770`. These compensate for row 10 for the **decision commands** (A1 sites 11, 13, 14, 15, 16, 17 run after these checks).
- Direct writes of decision/association/eligibility fields are refused for everyone without a grant token: `_refuse_direct_decision_write` `:281-287`, `_refuse_direct_association_write` `:306-311`, `_refuse_verified_eligibility_write` `:345-360`, `_refuse_direct_eligibility_write` `:362-375`, applied in `create` `:382-389` and `write` `:391-416`. These compensate for row 10 on **verified evidence**: `test_pr322_findings.py:105-107, 126-128` already assert `AccessError` for a `base.group_user`-only actor (`:38-44 cls.internal`) and for a verifier on direct writes — today those errors come from the Python guards, not from the ACL.
- **Not compensated:** `unlink` `:418-431` has no group check (A1 #9 "any user who may unlink" is, with row 10, *every* internal user); create/write of a *pending* document by any employee (`create` `:382` only refuses decision/association fields); the transaction recompute at `document.py:426/448` and `transaction_docs.py:71/98` (A1 sites 9, 10, 18, 19) therefore elevates on behalf of an actor set that row 10 widened to all employees — the sudo is still NECESSARY, but its "actor" column in A1 should read "any internal user" until row 10 is removed.
- **Tag, rule, matrix have no in-code guard at all**: `document_tag.py`, `document_rule.py` define none (`grep has_group|AccessError|is_system` empty); `document_validation_matrix.py:58-74` `create`/`write` enforce only a uniqueness check. Rules are the compliance authority: `compliance_service.py:28` and `transaction_docs.py:151,409-420` read `plasticos.document.rule`/`tag` to decide `is_compliant` for invoice/close gates. With rows 11–13 any employee can rewrite, deactivate or create rules and matrix entries and so change the compliance verdict of every transaction, with no `has_group` and no record rule in the way. This is the material S3 finding; A1 collateral 3 covered only the document rows.
- Tie to A1 site 21 (`plasticos_logistics/models/linda_request.py:328`, `ir.config_parameter`): no relation to the documents ACL — stated so that the tie is not assumed.

### Proposed row set (not applied)

Delete rows 10–13. Keep rows 2–9 unchanged. Resulting effective matrix equals the "Intended" column above. Optional hardening in the same change, each a code or XML edit outside the CSV: `menu_validation_matrix` `groups="plasticos_documents.group_documents_extension_manager"` (today ungated; after the CSV change a plain user would see the menu and get an `AccessError` on write only); a group check in `unlink` is unnecessary once row 10 is gone because row 3 restricts unlink to DM.

Risk: any employee today able to create pending documents without DU would lose that; the native bridge (`plasticos_documents_native`) creates `plasticos.document` rows for uploads — **RUNTIME-REQUIRED** to confirm which user it runs as (A1 #20 is UNRESOLVED on the Enterprise side; `document_sync.py:80` reads tags). Tests whose actors rely on row 10 for *creating* documents would fail: `test_pr322_findings.py` creates documents through `_accept`/`_shell` helpers — their acting user must be checked at runtime; `test_expiry_final_gate.py:31-32,96,136` and `test_account_move_transaction_link.py:496,566-571` act as DU/DM and are unaffected.

Tests: static — assert no `_all` row for `base.group_user` in `plasticos_documents/security/ir.model.access.csv` (and, as a repo-wide follow-up, enumerate the remaining 28 `_all` rows). **RUNTIME-REQUIRED** (`make test-module m=plasticos_documents`): as `cls.internal` (U only) — `plasticos.document.rule.create/write/unlink` raise `AccessError`; `plasticos.document.tag.write` raises; `plasticos.document.validation.matrix.write` raises; `plasticos.document.create` raises; `plasticos.document.unlink` as DU raises (row 2 has no unlink) and succeeds as DM; the existing `test_pr322_findings.py:105-128` assertions still pass (now from the ACL layer as well as the guard); verifier/manager flows in `test_expiry_final_gate.py` unchanged; `cron_check_missing_docs`, `cron_check_scale_tickets` and the midnight recompute as `user_system_cron` still read tags/rules (DM via `plasticos_documents/hooks.py:21-31`).

---

## S4 — Inaccurate sudo comments and the cron install-order gap

### S4(a) Two inaccurate `sudo()` comments (A1 collateral 4)

1. **A1 #8 — `plasticos_crm_bridge/models/facility_profile.py:290`** (chain `:288-295`, in `_blocked_binding_labels`). Comment: `# sudo: sync ACL cannot read a scheduled message`. Inaccurate: `mail.scheduled.message` grants `base.group_user` 1,1,1,1 (A1 C4, `core:addons/mail/security/ir.model.access.csv:70`) and its only rule has `perm_read` False (`core:addons/mail/models/../mail_security.xml:346-351`), so every internal user, including `user_system_cron` (`plasticos_base/hooks.py:175`), can read it. Correct statement: no ACL gap; the elevation is UNNECESSARY and both `sudo()` and comment should go (A1 verdict). **Line drift to record for PR-A:** A1 cites this site as `:307` (lines 305-311). At HEAD `:307` is a *different* site — `self.env["mail.message"].sudo().search(  # sync ACL cannot read chatter; unlink would drop it` in `_retarget_profile_bindings` (`:300-315`) — and `:322` holds a third, `self.env["mail.followers"].sudo()  # sudo: sync ACL cannot read follower rows`. Neither `:307` nor `:322` appears in A1's 34-site table. PR-A must re-verify this file's site list before editing it; the two uncatalogued sites need their own verdict (`mail.message` read is document-based, A1 C6; `mail.followers` core ACL not fetched here).
2. **A1 #24 — `plasticos_logistics/models/linda_request.py:796`** (in `_cancel_queued`). Comment `:794-795`: `# sudo: mail.mail is readable and writable only by system users, and the caller may be any user editing or canceling the PO. Only Linda's own unsent mail is touched.` Inaccurate about the caller: all three callers pass an already-elevated recordset — `:609 stale._cancel_queued(...)` on `evidence = self.sudo()` (`:593-596`), `:837 request._cancel_queued(reason)` on `queued = self.sudo().search(...)` (`:833`), `:868` on `requests = self.env[LOGISTICS_REQUEST].sudo()` (`mail_mail_inherit.py:33`). The `.sudo()` at `:796` is a no-op. Correct statement: callers are already su; a future non-su caller is refused by `_check_evidence_writer` (`linda_request.py:304-317`); remove the elevation and the comment (A1 verdict UNNECESSARY).

Partially inaccurate (A1 rows, for completeness): #12 `document.py:572` `# checksum only; actor already passed the command check` — also reached from computes and compliance gates with no command check (`compliance_service.py:64`, `transaction_docs.py:274`); #26 `linda_response.py:206-207` names the gateway but omits that `base.automation` already runs the server action as superuser (A1 C9). Both keep their A1 verdicts; only the text is wrong.

### S4(b) Cron install-order gap in `plasticos_base/hooks.py`

Mechanism: `post_init_hook` `:47` STEP 3 `:168-205` looks up eleven groups with `env.ref(group_xmlid, raise_if_not_found=False)` `:191` and inserts `res_groups_users_rel` rows for `user_system_cron` (`:192-200`); a missing group is skipped with no log line (only the total `Added system_cron user to %d groups` `:205`). The user itself is seeded with no groups (`plasticos_base/data/service_user.xml:5-15`, `noupdate="1"`). Install order `config/odoo_module_order.yaml:97-114`: `plasticos_base` is second; `plasticos_transaction` (10th), `plasticos_documents` (11th), `plasticos_claims` (13th), `plasticos_automation` (14th), `plasticos_enrichment` (17th) come after it, so at `plasticos_base` post-init the six `plasticos_*` groups in the list (`:180-186`) do not exist and are skipped. The five core groups (`:175-179`) do exist: `plasticos_base` depends on `plasticos_odoo_standard_apps` (`__manifest__.py:9`), which depends on `account`, `purchase`, `stock`, `sale_management` (`plasticos_odoo_standard_apps/__manifest__.py:23-27`).

Compensation actually present (extends A1 collateral 2, which named only documents/claims/enrichment): `plasticos_documents/hooks.py:16-31`, `plasticos_claims/hooks.py:16-26`, `plasticos_enrichment/hooks.py:16-26` grant their own manager group to `user_system_cron` explicitly. `plasticos_transaction/hooks.py:6-50` and `plasticos_automation/hooks.py:40-…` (same template, also in `plasticos_logistics`, `plasticos_offer`, `plasticos_geolocalize`, `plasticos_intake_normalizer` hooks `:13`) grant **every group owned by the module to the `user_id` of every cron owned by the module**. `plasticos_transaction.group_plasticos_manager` (`security_hardening.xml:15`) therefore reaches `user_system_cron` only because `cron_plasticos_monthly_audit` (`plasticos_transaction/data/audit_cron.xml:11`) happens to run as that user; the automation groups likewise via the seven automation crons. On a fresh ordered install every listed group ends up granted — through an implicit coupling, not through the base list.

Which cron runs as which user: all 27 PlasticOS crons set `user_id = plasticos_base.user_system_cron` explicitly (grep above: `plasticos_admin_dashboard`, 7× `plasticos_automation`, 2× `plasticos_base`, `plasticos_claims`, `plasticos_crm_sync`, 3× `plasticos_documents`, 2× `plasticos_enrichment`, `plasticos_geolocalize`, `plasticos_intake_normalizer`, 4× `plasticos_logistics`, `plasticos_offer`, `plasticos_transaction`). A late group never changes the *user*; it changes the user's *rights*. Operational impact when a grant is missing:

- `cron_check_missing_docs` and `cron_check_scale_tickets` (`plasticos_documents`, model `plasticos.transaction`) and `cron_supplier_confirmation` / `cron_auto_create_do` (`plasticos_logistics`, model `plasticos.transaction`) need `group_plasticos_manager` to write transactions (A1 R2). Their flag writes survive through `tx.sudo()` (A1 #18/#19), but `_compute_compliance()` in the midnight recompute (`plasticos_documents/models/midnight_recompute.py:89`) and `transaction_docs._apply_missing_doc_page` paths are not elevated: without the group the cron raises `AccessError`, the `try/finally` at `midnight_recompute.py:50-58` only releases the lock, and the whole midnight job fails (every PlasticOS date-based field stays stale for the day).
- Scenarios that produce the missing grant: (1) `plasticos_transaction/data/audit_cron.xml` re-pointed to another user or removed — the only carrier of the transaction grant disappears; (2) a module upgraded (`-u`) rather than installed — `post_init_hook` does not run on upgrade, so a group added to the list later, or a group deleted and recreated from `noupdate="0"` security XML, is never re-granted; (3) an admin removing the service user's groups in Settings › Users — `service_user.xml` is `noupdate="1"`, nothing restores the relation; (4) a module installed out of order (e.g. `-i plasticos_documents` before `plasticos_transaction` on a partial database): the documents crons on `plasticos.transaction` run before the transaction hook ever grants.
- The base hook cannot detect any of this: it logs a count, not the skipped xmlids (`:205`).

Test that would catch it (none exists: `grep -rl user_system_cron plasticos_*/tests tests` is empty):

1. **RUNTIME-REQUIRED**, post-install Odoo test (`@tagged("post_install", "-at_install")`, placed in a module installed last, e.g. `plasticos_automation`, run with `make test-module m=plasticos_automation` on the from-empty template `scripts/test_env.sh template`, since `make install-smoke` clones a template whose hooks already ran): for every xmlid in `plasticos_base/hooks.py cron_groups`, `assert env.ref("plasticos_base.user_system_cron").has_group(xmlid)`; and for every `ir.cron` with `user_id = user_system_cron`, `env[cron.model_id.model].with_user(cron.user_id).check_access("write")` (or the exact operation the cron performs) passes.
2. **Static (CI, no Odoo):** parse the `cron_groups` list in `plasticos_base/hooks.py:174-187`; for each `plasticos_*` entry assert the owning module's `hooks.py` grants it to `user_system_cron` explicitly (an `env.ref("plasticos_base.user_system_cron")` + `res_groups_users_rel` insert, as in `plasticos_documents/hooks.py`) — which makes the implicit "module's own cron user" coupling an explicit contract.

Proposed change (not applied): make the base list self-describing — log each skipped xmlid at WARNING (`:191-193`), and either (i) add an explicit `user_system_cron` grant for `group_plasticos_manager` in `plasticos_transaction/hooks.py` and for the two automation groups in `plasticos_automation/hooks.py` (same shape as `plasticos_documents/hooks.py:21-31`), or (ii) move the whole downstream list out of `plasticos_base` into the owning modules. Either is a `plasticos_base` / hooks edit under the plan's `write_deny` and needs its own authorization.

---

## Collateral findings surfaced by S1–S4 (report only; nothing changed)

1. `plasticos.erp.import.run` (`erp_import_service.py:88`) and `plasticos.transaction.import.service.run_csv_import` (`transaction_import_service.py:50`) are public methods on abstract models with **no `_check_import_operator`-style guard**, unlike `plasticos.partner.import.service` (`:35-46`, contract-tested). `run_csv_import` takes a server filesystem path. Removing the S1 grant makes both fail closed at the first `ir.model.data` search for a non-system RPC caller, but the proper fix is the same operator guard. **RUNTIME-REQUIRED** to confirm RPC reachability: `env["plasticos.erp.import"].with_user(internal).run(...)`.
2. A1's `facility_profile.py` site numbering is stale: #8 is at `:290` (chain `:288-295`); `:307` (`mail.message`) and `:322` (`mail.followers`) are uncatalogued `sudo()` sites (S4(a)).
3. `plasticos_transaction/models/transaction.py:929` reads `ir.model.data` without `sudo()`; its only caller `_auto_post_pending_invoices` `:892` has no production caller.
4. 28 further `_all` rows from `remote:69eb818b4` remain outside `plasticos_base`/`plasticos_documents` (`plasticos_material_profile` 8, `plasticos_enrichment` 4, `plasticos_transaction` 3, `plasticos_claims`/`facility_profile`/`intake`/`partner_import` 2 each, `documents_native`/`intake_normalizer`/`offer`/`product` 1 each). Same provenance ("tightened after deployment is stable"), same analysis method; out of S1 scope.
5. `plasticos_partner_import/security/ir.model.access.csv:8-9` `_all` rows grant `base.group_user` CRUD on the import validation and service models — CRUD on abstract/service models is inert (S2 reasoning), but the rows contradict `:2-5`.

---

## Bounded remediation proposal

| Finding | Proposed change (file, row/line) | Risk | Test required | Dependency for PR-A |
|---|---|---|---|---|
| **S1** `ir.model.data` grant | Delete `plasticos_base/security/ir.model.access.csv:5` (fallback: `…,base.group_user,1,0,0,0`). No new group, no service user. | Low: both canonical imports are superuser; every non-su read is already `sudo()`. Fail-closed side effect on unguarded `run` entry points (collateral 1). | Static CSV/AST tests; **RUNTIME-REQUIRED** `ERP_DRY=1 make import-erp`, `make import-erp`, `make import-vanillasoft` + `scripts/validate_import_summary.py`; Odoo tests: internal `search`/`create` on `ir.model.data` raise `AccessError`; payout write, `account.move.action_post`, `action_sync_now` succeed as non-system users. | **Blocking for #2, #3, #34.** Removal → the three stay `sudo()` and become NECESSARY with the same-line comment in S1(e); read-only fallback → they may be removed as A1 says. PR-A must know which shape the operator chose. |
| **S2** midnight-recompute rows | Delete `plasticos_base/security/ir.model.access.csv:2-4` (AbstractModel; no table, no fields, no RPC method). | None at runtime; `ci/check_acl_completeness.py` already skips abstract models. | Static "no ACL row on an AbstractModel"; **RUNTIME-REQUIRED** `-u plasticos_base` loads and the midnight cron runs as `user_system_cron` (`make test-module m=plasticos_base`). | None for PR-A sites. Cron rights depend on S4(b), not on these rows. |
| **S3** documents `_all` rows | Delete `plasticos_documents/security/ir.model.access.csv:10-13`; optional `groups=…group_documents_extension_manager` on `menu_validation_matrix` (`validation_matrix_views.xml:54`). | Medium: employees lose ungated create/unlink of documents and all CRUD on tags/rules/matrix (intended); native-bridge acting user and `test_pr322_findings` helper actors must be confirmed at runtime; #20 stays UNRESOLVED. | Static "no `_all` row"; **RUNTIME-REQUIRED** `make test-module m=plasticos_documents` with the negative cases in S3 and the existing verifier/manager suites; cron reads as `user_system_cron`. | Non-blocking for verdicts: sites 9–19 stay NECESSARY. Changes the *actor* column of #9/#10 (today "any internal user") and removes the need for an `unlink` group guard. |
| **S4(a)** comments | None beyond PR-A's own scope: remove `sudo()`+comment at `facility_profile.py:288-295` (#8) and `linda_request.py:794-796` (#24) per A1; fix the text at #12 and #26. | Low. | PR-A's existing per-site tests; for #8 **RUNTIME-REQUIRED** sync as `user_system_cron` reads `mail.scheduled.message` without `AccessError`. | **PR-A must re-inventory `facility_profile.py` (sites at `:290`, `:307`, `:322`) before editing it**; #8 is still FROZEN by operator ruling until "core-ACL contradiction" is accepted. |
| **S4(b)** cron install-order gap | `plasticos_base/hooks.py:191-193` log skipped xmlids at WARNING; explicit `user_system_cron` grants for `group_plasticos_manager` in `plasticos_transaction/hooks.py` and the two automation groups in `plasticos_automation/hooks.py` (shape of `plasticos_documents/hooks.py:21-31`), or move the downstream list into the owning modules. | Low; hooks run only at install. Does not fix upgraded databases — those need the post-install test or a migration. | Static hook-grant contract test; **RUNTIME-REQUIRED** post-install test on the from-empty template: `has_group` for every `cron_groups` entry and `check_access("write")` for each cron's model as its `user_id`. | Keeps #18/#19 NECESSARY (A1); none of the S4(b) changes alters a PR-A verdict. |

All five rows are proposals. Any application needs its own authorization (plan `write_deny`: `plasticos_base/**`, ACL rows, record rules, crons) and the RUNTIME-REQUIRED proof listed, run on the admitted Docker fixture, before a `make pr`.
