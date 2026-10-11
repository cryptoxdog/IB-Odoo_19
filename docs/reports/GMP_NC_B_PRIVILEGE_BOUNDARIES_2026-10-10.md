# GMP-NC-B — Privilege Boundary Remediation Evidence

Template: `docs/campaigns/odoo_noncritical_gmp_campaign_pack/80_FINAL_REPORT_TEMPLATE.md`.
Contract: `docs/campaigns/odoo_noncritical_gmp_campaign_pack/contracts/20_GMP_NC_B_PRIVILEGE_BOUNDARIES.md`.
Raw runtime excerpts: `docs/reports/evidence/gmp-nc-b-2026-10-10/`.

## Identity

- GMP ID: GMP-NC-B (GAR/Codex remediation of PR #236)
- Objective: close B-01, B-02 and B-03 and reconcile the privilege census truthfully
- Repository: `cryptoxdog/IB-Odoo_19`
- Base branch: `Staging`
- Base SHA: `92142d367abb04890b6a3a51604d227788ec92d8`
- Working branch: `agent/cursor/gmp-nc-b`
- Audited HEAD (start): `474c8b26057861b915e76d9d94fcff17b9676463`
- Final HEAD: the commit that carries this report (see the PR head)
- Predecessor: none required (GMP-NC-A not consumed)

## Phase 0 — Bound target

- Remote PR head was equal to the audited SHA before mutation; the work ran in a dedicated worktree.
- Repo law on placement is verified in `.cursor/rules/71-plasticos-security-model.mdc` ("inline comment on the same line")
  and `.cursor/rules/00-plasticos-master-context.mdc`. `AGENTS.md` and `INVARIANTS.md` require an "explicit
  justification" but do not specify the line. They are not cited as the source of the same-line rule.
- Odoo 19 behaviour is read from Odoo 19 CE source:
  - `odoo/service/model.py::get_public_method` makes any public, non-`@api.private` method RPC-callable. Model access is not checked first.
  - `ir.config_parameter` is `base.group_system` only.
  - `res.partner` write is `base.group_partner_manager` (plus the PlasticOS sales/logistics rows). `base.group_user` is read only.
- Entry gate: PASS

## Phase 1 — Before-state census

| Measure | Staging / audited head | Final | Evidence |
|---|---:|---:|---|
| Runtime `.sudo()` lines (`plasticos_*`, excluding tests/migrations) | 71 | 61 | `grep -rn '\.sudo()'` on both trees |
| Of those, in scanner scope (`models/`) | 28 | 18 | same |
| `UNJUSTIFIED_SUDO` findings, scanner at Staging | 22 | — | scanner run on the Staging tree |
| `UNJUSTIFIED_SUDO` findings, scanner at audited head | 4 | — | intake 621/635, normalizer 73/618 |
| `UNJUSTIFIED_SUDO` findings, final scanner on final tree | — | 0 | documentation check only, see B-02 |

### 22 → 4 reconciliation (the PR's original claim)

The PR cleared 20 of the 22 Staging findings by adding comments only. It also exposed 2 new ones: normalizer 73/618, which the old ±3-line window had hidden behind preceding comments.

| Staging finding | Classification of the PR's reduction | Final disposition |
|---|---|---|
| `commission_config.py:31` (getter) | documentation-only | Verified legitimate (cat 1): fixed two-key read, returns an int |
| `commission_config.py:51` (setter) | documentation-only **suppression of a real defect** | **Corrected authorization boundary** (B-01): `is_system()` check, sudo removed |
| `intake.py:621`, `:635` | unresolved | **Removed** (B-03) |
| `sales_dashboard.py:349` | documentation-only over a false claim | **Removed**: unnecessary; it bypassed the rep payout rule |
| `web_lead.py:724` | documentation-only over a false claim | **Removed**: it let any internal user trigger provider calls with admin keys |
| `web_lead.py:1216`, `:1304`, `:1313` | documentation-only over a false claim | **Removed**: unnecessary (only a system user can complete these actions) |
| `partner_import_service.py:51` | documentation-only | **Corrected authorization boundary**: service read-ACL check before elevation |
| `admin_dashboard.py:450` | documentation-only, inaccurate text | Verified legitimate (cat 5); comment corrected |
| `sales_dashboard.py:230` | documentation-only | Verified legitimate (cat 5); comment accuracy for Enterprise `documents.document` not verifiable here (D-07) |
| `freight_governance.py:245` | documentation-only | Verified legitimate (cat 3): `_require_freight_evidence_authority` guards company, load access and logistics group first |
| `match_result_writer.py:37`, `:59` | documentation-only | Verified legitimate (cat 3): receipt, state and buyer-access checks come first |
| `web_lead_review_snapshot.py:134` | documentation-only | Verified legitimate (cat 3): share/public refusal, `check_access("write")`, private approval token |
| `load.py:199`, `:217`, `commission_service.py:91`, `crm_connection.py:56`, `res_config_settings.py:35`, `enrichment_service.py:201` | documentation-only | Verified legitimate (cat 1): fixed, non-secret parameter reads (secrets are never returned) |
| *(new)* `intake_normalizer.py:73` | newly surfaced | **Removed** (B-03) |
| *(new)* `intake_normalizer.py:618` | newly surfaced | **Removed** (B-03) |

The count of four was not used as a target, and no elevation was reclassified as authorized without evidence.

### Full census, by category (final tree, 61 lines)

| Category | Count | Notes |
|---|---:|---|
| 1 system parameter / config | 26 | ICP and config reads; every write path reviewed. The only ICP write outside the commission setter is `field_family_cutover.recovery_disable`, which has no runtime caller and writes toward OFF |
| 2 cron / install maintenance | 28 | 25 `hooks.py` sites (superuser env, no-op sudo), `ir_attachment` ×2 (cron, advisory lock), `intake_normalizer.py:183` (cron config read, `plasticos_base.user_system_cron`) |
| 3 server-owned evidence | 4 | freight evidence, match result ×2, review snapshot |
| 4 workflow privileged mutation | 1 | `web_lead_api.py:171`, after `_authenticate` |
| 5 read-only reporting | 2 | `admin_dashboard.py:450`, `sales_dashboard.py:230` |
| 6 unnecessary elevation | 0 | the 10 found were removed |
| 7 UNKNOWN | 0 | |

Census method: I classified the 7 owned sites directly. A separate read-only reviewer classified the other 64, quoting the guard code for each. I re-verified each CONCERN against source before acting on it.

## Phase 2 — Root-cause decision

- Root cause: comments were accepted as if they were authorization proof, and the scanner's text search let any `#` count as a comment. A comment cannot carry authority; only the code before the elevation can.
- Owner per finding: the module that owns each elevated operation. No global sudo abstraction, new group, ACL redesign, field or schema change was introduced.
- Alternative rejected for B-03 intake: keeping `sudo()` behind a new guard. The caller's own partner rights are the existing boundary. Plain removal is smaller and cannot widen access.
- Alternative rejected for the normalizer log: adding fields or selection values to `plasticos.automation.log`. That is a shared schema change, prohibited here (deferred, D-01).

## Modification lock

| File | Existing/New | Why required |
|---|---|---|
| `scripts/audit/business_logic_audit.py` | Existing | B-02 scanner |
| `tests/test_unjustified_sudo_scanner.py` | Existing | B-02 regression matrix |
| `plasticos_commission/models/commission_config.py`, `__manifest__.py` | Existing | B-01 |
| `plasticos_commission/models/sales_dashboard.py` | Existing | census: unnecessary elevation |
| `plasticos_commission/tests/*` | New (module had only `.gitkeep`) | runtime proof |
| `plasticos_intake/models/intake.py`, `__manifest__.py`, `tests/*` | Existing / New tests | B-03 |
| `plasticos_intake_normalizer/models/intake_normalizer.py`, `__manifest__.py`, `tests/*` | Existing / New tests | B-03 |
| `plasticos_web_leads/models/web_lead.py`, `__manifest__.py`, `tests/__init__.py`, `tests/test_web_lead_config_privilege.py` | Existing / New test | census: authority crossing |
| `plasticos_partner_import/models/partner_import_service.py`, `__manifest__.py`, `tests/*` | Existing / New test | census: RPC-public elevated read |
| `plasticos_admin_dashboard/models/admin_dashboard.py` | Existing | inaccurate justification text |
| this report and `docs/reports/evidence/gmp-nc-b-2026-10-10/*` | New | evidence |

Other files modified: none beyond the comment-only edits already in the PR at `474c8b2`.

## Phase 3 — Realization, per finding

### B-01 — public commission configuration setter · **FIXED**

- Source: `set_max_budget_tokens()` is `@api.model` and public, so any authenticated user can reach it through `/web/dataset/call_kw`. At `474c8b2` it checked only `value > 0`, then wrote both global keys under `sudo()`.
- Obligation: an elevated global write must be preceded by the caller's administrative authority.
- Counterexample (runtime, audited code): `base.group_user` and commission-manager users both changed the budget. Evidence: `odoo_run_old.txt` (`test_internal_user_is_denied_and_nothing_changes`, `test_commission_manager_without_settings_is_denied` FAIL).
- Change:
  - `if not self.env.is_system(): raise AccessError` runs before value validation.
  - The write now runs without `sudo()`, so `ir.config_parameter`'s `group_system` ACL also applies to both keys.
  - Keys, legacy compatibility and the getter are unchanged.
- Proof: 8 tests in `plasticos_commission/tests/test_commission_config_access.py`, all passing:
  - RPC reachability
  - admin success with both keys set
  - internal user denied, both keys unchanged
  - commission manager denied
  - unauthorized invalid value denied before validation
  - admin invalid values rejected
  - getter fallbacks for ordinary users
  - no broader ICP access granted
- Remaining uncertainty: none known.

### B-02 — scanner false negatives · **FIXED**

- Source: `_same_line_sudo_boundary()` used `str.find("#")`. Any `#` inside a string literal, and any comment at all (`# noqa`, an empty `# sudo:`), cleared the finding.
- Counterexample: the new matrix run against the audited scanner fails 7 of 14 (`#internal` string, `# noqa`, empty marker, placeholder, `.sudo()` text in strings or comments, untokenizable source, schema wording).
- Change:
  - The scanner now tokenizes source with `tokenize`. Only executable `.` `sudo` `(` `)` tokens count as elevation.
  - The justification must be a real `COMMENT` token on the same physical line, matching `# sudo: <reason>` or `# cron-sudo-justification: <reason>` (the two spellings already in `models/`).
  - The reason needs at least two words and cannot be only placeholder words.
  - Untokenizable files fail closed.
  - Schema keys, `UNJUSTIFIED_SUDO` and `MODERATE` are unchanged. No filename exemptions, no parallel scanner.
- Proof: `tests/test_unjustified_sudo_scanner.py`, 14 passing (the full matrix from the task, plus chained-call placement and schema preservation).
- The scanner docstring and `fix` text state that a passing check documents a justification and is never proof of authorization.

### B-03 — intake / normalizer elevations

| Operation | Entry point and actor | Finding | Disposition |
|---|---|---|---|
| Preferred-contact sync (`intake.py:621`) | `plasticos.intake.write` (UI/RPC); any `base.group_user` (intake ACL grants CRUD) | `res.partner` write needs `group_partner_manager` or a PlasticOS sales/logistics role. Odoo 19 default internal users have neither. With sudo, an intake edit wrote partner fields the user could not write directly. | **FIXED**: write runs as the caller |
| Lead-source sync (`intake.py:635`) | same | same; first-set-only semantics preserved | **FIXED**: write runs as the caller |
| Normalizer config read (`intake_normalizer.py:73`) | `action_normalize` button/RPC | `plasticos.normalizer.config` is readable by `base.group_user` (and seeded), so elevation was unnecessary | **FIXED**: sudo removed |
| Automation-log create (`intake_normalizer.py:618`) | after normalization | The payload (`record_id`, `detail`, `normalize_*` action types, no `name`/`res_id`) cannot be created on `plasticos.automation.log`, so the create always failed and was swallowed at debug level. The sudo granted nothing, but would have become a log-forgery path for every internal user if the payload were ever aligned. | **FIXED** (elevation removed, behaviour unchanged); functional defect **BLOCKED → deferred D-01** |

- Counterexample (runtime, audited code): a `base.group_user` user wrote `preferred_contact_id` and `lead_source_id` onto a partner through an intake (`odoo_run_old.txt`, two FAILs).
- Proof: `plasticos_intake/tests/test_intake_partner_sync_access.py` (8) and `plasticos_intake_normalizer/tests/test_normalizer_privilege.py` (3) all pass. They cover:
  - an authorized editor succeeds
  - an unauthorized user is denied, with both intake and partner unchanged after rollback
  - an existing lead source is not overwritten
  - non-sync edits are unaffected
  - another company's partner stays isolated
  - server-side (superuser) execution still syncs
  - a normalization by an internal user forges no log
- `intake_normalizer.py:183` (the cron's config read) is kept. It runs as `plasticos_base.user_system_cron`, whose groups are provisioned out of band, and reads only the non-secret singleton.
- **Intentional behaviour change:** a user who can edit intakes but cannot write partners (e.g. plain `base.group_user`, or Accounting only) now gets `AccessError` when changing an intake's contact or first lead source. The remedy is to grant Contact Creation or a PlasticOS sales/logistics role, not to restore `sudo()`.

### Census corrections beyond the four warnings

| Site | Counterexample (runtime, audited code) | Change |
|---|---|---|
| `sales_dashboard.py:349` | Rep A received rep B's payout id for A's deal (`odoo_run_old2.txt` FAIL) | sudo removed; every dashboard reader group already has payout read |
| `web_lead.py:724` (+1216/1304/1313) | A `base.group_user` user's `action_retry_triage` reached the provider call under admin keys before the write failed (`odoo_run_old2.txt` FAIL) | sudo removed. The config model is `group_user`-readable; only key fields are system-only, so the key read now denies non-admins first. Admission stays on the authenticated su env. |
| `partner_import_service.py:51` | A portal user resolved the configured server path (`odoo_run_old2.txt` FAIL) | `self.check_access("read")` (service ACL: internal users) before the elevated read |

## Phase 4 — Validation

| Proof | Result | Evidence |
|---|---|---|
| Fresh install (Odoo 19 CE, disposable DB `ncb_runtime_test`) of commission, intake, normalizer, automation; module tests | PASS 19/19 | `odoo_run1.txt` |
| New tests against audited code (B-01/B-03) | 4 FAIL + 1 ERROR, as expected | `odoo_run_old.txt` |
| Upgrade audited → final versions, then tests | PASS 19/19 | `odoo_run_upgrade.txt` |
| Fresh install incl. web_leads, partner_import, admin_dashboard; all tests of the five touched test modules (includes existing web-lead hardening + inbound HTTP suites) | PASS 60/60 | `odoo_run2.txt` |
| Census tests against audited code | 3 FAIL, as expected | `odoo_run_old2.txt` |
| Upgrade audited → final versions, then tests | PASS 49/49 | `odoo_run_upgrade2.txt` |
| `pytest tests/` (CI pure-Python tier) | PASS 1250, 48 skipped | local run |
| Scanner regression matrix | PASS 14/14 | `tests/test_unjustified_sudo_scanner.py` |
| `pre-commit run --files <changed>` | PASS | local run |
| `make audit-baseline` | PASS, 0 new; 5 stale entries identical on Staging (D-09) | local run |
| `check_module_wiring.py`, `check_circular_deps.py`, `cron_invariant_check.py` | PASS | local run |

Runtime environment: Odoo 19 CE (`odoo/odoo@19.0`) with local PostgreSQL 16, using throwaway databases created for this run. No production or template database was touched. Enterprise addons were not available, so Enterprise-only paths (D-07) are not runtime-verified.

## Phase 5 — Before/after comparison

| Finding family | Before | After | Delta | Explanation |
|---|---:|---:|---:|---|
| `UNJUSTIFIED_SUDO` (Staging scanner → final scanner) | 22 | 0 | −22 | 10 elevations removed, 2 boundaries corrected, the rest verified with substantive same-line text (above) |
| Runtime `.sudo()` lines | 71 | 61 | −10 | intake ×2, normalizer ×2, commission setter, payout lookup, web-lead config ×4 |

New unrelated findings: see Deferred (REPORT ONLY).

## No-reopen proof

- Prior completed Critical/High remediation touched: NO. Contract files for GMP-NC-A/C/D/E/F were not modified.

## Runtime propagation

| Module | Version | Migration |
|---|---|---|
| `plasticos_commission` | 19.0.1.4.0 → 19.0.1.4.1 | none (no schema change) |
| `plasticos_intake` | 19.0.5.3.1 → 19.0.5.3.2 | none |
| `plasticos_intake_normalizer` | 19.0.1.0.0 → 19.0.1.0.1 | none |
| `plasticos_web_leads` | 19.0.2.8.4 → 19.0.2.8.5 | none |
| `plasticos_partner_import` | 19.0.2.10.21 → 19.0.2.10.22 | none |

Comment-only modules (`admin_dashboard` and the PR's earlier comment edits) are not bumped, per `skills/plasticos-odoo-version-bump`.

Scoped upgrade for deploy: `make update m=plasticos_commission,plasticos_intake,plasticos_intake_normalizer,plasticos_web_leads,plasticos_partner_import`. Upgrade proof: `odoo_run_upgrade*.txt`.

## Deferred obligations (REPORT ONLY — not fixed here)

| ID | Item | Why deferred |
|---|---|---|
| D-01 | Normalizer automation-log payload is incompatible with `plasticos.automation.log` (fields and selection values), so the normalization log is never written and the failure is logged at debug level | Requires a shared automation schema decision |
| D-02 | `partner_import_service.run_csv_import` / `run_default_csv_import` are public and accept caller-chosen server paths for any internal user | Not a `sudo()` site; partner-import authority is a policy decision |
| D-03 | `res_partner_geo.cron_geo_backfill` is RPC-public (no `_` prefix) | Not a `sudo()` site |
| D-04 | Any internal user can trigger a CRM sync using the admin-configured VanillaSoft key (matches the module ACL as written) | Policy; the key is never returned to the caller |
| D-05 | CRM webhook accepts its token in the query string (access-log exposure) | Not a `sudo()` site |
| D-06 | `web_lead_api.py` class docstring claims config creation happens only after token validation (it runs pre-auth by design); line 171's comment lacks the `sudo:` marker (controller, outside scanner scope) | Documentation in an out-of-scope controller |
| D-07 | `sales_dashboard.py:230` justification depends on Enterprise `documents.document` access, which cannot be verified without Enterprise | Environment |
| D-08 | `match_result_writer.persist_match_lines` is public by name (guarded and not usable via JSON args); defence in depth would mark it private | Hardening, not a defect |
| D-09 | 5 stale entries in `ci/baselines/extended_audit_baseline.json`, identical on Staging | Pre-existing baseline maintenance |
| D-10 | 25 `hooks.py` `sudo()` calls are no-ops (superuser env) | Out of scanner scope; legitimate |

## Publication

- Publication path: `make pr` from the Cursor-Governance SSOT, run against this workspace (`WS`), with `PR_BASE=origin/Staging`, updating the existing PR #236. Result: see the PR.
- Attempt 1 failed before validation for environmental reasons, not because of the change:
  - The gate's locked-writer ruff falls back to the governance venv (`ruff 0.16.1`) when the workspace has no `.venv`.
  - This repo pins `required-version = "==0.16.0"`, so ruff refused to run (`writers stage exited 123`).
  - Fix: built the repo's canonical `.venv` with `make venv` (`ruff==0.16.0` from `requirements-dev.txt`), then re-authorized and republished. No gate was weakened or skipped.

## Verdict

Set in the PR thread after publication and inspection of the published head's checks.
