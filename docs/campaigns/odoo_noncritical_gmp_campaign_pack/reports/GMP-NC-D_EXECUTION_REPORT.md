# GMP-NC-D Evidence Report — Query Boundedness Convergence

Filled from `80_FINAL_REPORT_TEMPLATE.md` (left unchanged). Contract:
`contracts/40_GMP_NC_D_QUERY_BOUNDEDNESS.md`. Date: 2026-10-10.

## Identity

- GMP ID: GMP-NC-D (convergence remediation of PR #238)
- Objective: repair four scanner false-negative patterns (D-01..D-04), prove the two runtime query changes (D-05, D-06), reconcile the Moderate `UNBOUNDED_SEARCH` census
- Repository: `cryptoxdog/IB-Odoo_19`
- Base branch / SHA: `Staging` / `92142d367abb04890b6a3a51604d227788ec92d8` (unchanged during execution)
- Working branch: `agent/cursor/gmp-nc-d` (PR #238, updated in place)
- Starting HEAD: `c40e4f55cf66785cc735a7cc5fddf3b13a48f96d` (equal to the audited HEAD; no rebinding required)
- Final HEAD: the commit that adds this report (see the PR head)
- Predecessor: PR #234 `fix/production-debt-root-cause` @ `8a07d9cfa2cdc34f3c370f16e24f82dc00a1d631` — **open, not merged**

## Phase 0 — Bound target

- Repo law inspected: `CLAUDE.md`, `AGENTS.md` (CI checklist, audit baselines, 2026-10-07 `make pr` correction), `70_EXECUTION_PLAYBOOK.md`, the NC-D contract, `plasticos-odoo-version-bump` skill
- Owners inspected: `scripts/audit/performance_audit.py` (UNBOUNDED_SEARCH helpers only), `tests/test_unbounded_search_intent.py`, `plasticos_automation/models/automation_config.py`, `plasticos_documents_native/models/document_sync.py`
- Review input: the four open Codex threads on #238 map one-to-one to D-01 (limit value), D-02 (OR branches), D-03 (conditional appends), D-04 (literal identities / dynamic `in`)
- Upstream API verified against `odoo/odoo@19.0`: `search(domain, offset=0, limit=None, order=None)` (`odoo/orm/models.py:1376`); `_search` sets no limit for `None`/`False` (`:5402`); `Query` emits `LIMIT` only when truthy (`odoo/tools/query.py:192`), so `limit=0` is unlimited; a negative limit reaches PostgreSQL, which rejects it. `cr.savepoint()` flushes, and on exception rolls back and clears the cache (`odoo/sql_db.py:87-151`)
- Entry gate: the High scanner predecessor (#234) has **not** landed on Staging, and #238 is not stacked on it. Per the remediation brief, #238 stays independently owned; integration is verified against a merged candidate (Phase 5) and reported PENDING, not PASS

## Phase 1 — Before-state census

| Scanner revision | Tree | `UNBOUNDED_SEARCH` |
|---|---|---:|
| Staging (keyword/regex) | Staging `92142d3` | 103 |
| #238 audited (`c40e4f5`) | `c40e4f5` | 14 |

## Phase 2 — Root-cause decision

- Root cause: `_retains_search` accepted spelling as proof. Any `limit` keyword, any identity term anywhere in the domain, every `append` in any nested block, and any dynamic `in` on any field each suppressed the finding.
- Owner: `check_unbounded_searches` and its helpers in `scripts/audit/performance_audit.py`. `check_n_plus_one_queries` and lines 1–61 are byte-identical to Staging (the #234 boundary).
- Realization: a three-valued verdict (`bounded` / `unbounded` / `unknown`). Only `bounded` suppresses. `unknown` is emitted with `"bound": "unknown"` and its own message, never assumed.
- Alternatives rejected: a general program analyzer; interprocedural method resolution; field-uniqueness inference from model definitions; filename, model-name or variable-name exemptions.

## Modification lock

| File | Existing/New | Why required |
|---|---|---|
| `scripts/audit/performance_audit.py` | Existing | D-01..D-04, UNBOUNDED_SEARCH helpers only |
| `tests/test_unbounded_search_intent.py` | Existing | adversarial D-01..D-04 regressions; boundary test repair (Phase 5) |
| `plasticos_documents_native/models/document_sync.py` | Existing | D-06 proven correction (below) |
| `plasticos_documents_native/__manifest__.py` | Existing | mandatory version propagation, `19.0.1.2.3 → 19.0.1.2.4` |
| `docs/campaigns/odoo_noncritical_gmp_campaign_pack/reports/GMP-NC-D_EXECUTION_REPORT.md` | New | GMP Phase 6 evidence. No prior NC-D report existed, so this is the first one |
| `.../reports/evidence/gmp-nc-d/{census.py,d05_singleton_proof.py,d06_pagination_harness.py}` | New | replayable proofs cited below |

Not modified: `check_n_plus_one_queries`, `plasticos_automation/**` (D-05 needed no change), `ci/baselines/**`, PR #234. No other files modified: YES.

## Phase 3 — Realization

### D-01 | Positive-limit assurance — REPAIRED

`_limit_verdict` reads the `limit` keyword, or positional argument 2. `_positive_int` decides the bound:

- A positive `int` literal is a bound.
- `0`, `None`, `False`, `True` and `-n` are not.
- A local name is followed through every assignment that reaches the call.
- `max(..., k>0)`, `min(all positive)`, `a if c else b` (both branches) and `x or k` are modelled. In `x or k`, falsy literals are never the result, so they are ignored.
- Parameters, attributes, calls and `**kwargs` give UNKNOWN. A parameter named `limit` with a default of `80` is UNKNOWN: naming and defaults are not proof.

### D-02 | OR-domain assurance — REPAIRED

`_elements_verdict` parses Odoo prefix notation (`&`, `|` binary; `!` unary; implicit AND for the remainder):

- AND is bounded if any operand is bounded.
- OR is bounded only if every branch is bounded.
- `!` never proves a bound.
- An empty domain is unbounded.
- Missing operands (malformed domains) and unresolved elements (`*extra`, a bare name) give UNKNOWN.

### D-03 | Conditional-domain assurance — REPAIRED

`_reaching` walks the function's statements in execution order up to the call and keeps one domain state per path:

- **Branches.** `if`/`else` fork the state. A branch that ends in `return`, `raise`, `continue` or `break` does not reach later statements.
- **Mutations followed.** `append`, `extend` and `+=` are followed. So are list literals, `*splat`, `a + b` and `list(x)`.
- **Mutations not followed.** These make the state UNKNOWN:
  - a change inside a loop, `try` or `match` block;
  - any other method call on the name (`pop`, `insert`, …);
  - subscript or tuple-unpacking assignment;
  - `global`/`nonlocal`.
- **Order.** Statements after the call are ignored.
- **Verdict.** The search is bounded only if every reaching path is bounded. One known unbounded path makes the verdict unbounded.

### D-04 | Identity versus categorical `in` — REPAIRED

Identity fields are `id`, `res_id`, `*_id` and `*_ids`. This is the existing rule and is unchanged.

- **`=` and `in` on an identity field.** A dynamic value is a bound. So is a positive `int` literal, a finite literal collection, or an empty collection.
- **Null and string values.** `False`, `None` and string literals are not bounds, and neither is a collection that contains one.
- **Literal lists on other fields.** A literal list on a non-identity field is categorical and unbounded.
- **Dynamic sets on other fields.** A dynamic set on a non-identity field is UNKNOWN, whatever its variable is called (`state in ids` → UNKNOWN; `id in statuses` → bounded).
- **Test change.** The old test `test_caller_supplied_in_set_is_input_bounded` (`name in origins` → retained) encoded the D-04 defect. It is now two tests: an identity set is retained, and a dynamic non-identity set is UNKNOWN.

### D-05 | Automation configuration singleton — PROVEN, NOT MODIFIED

No defect found, so the `search_count()` constraint is unchanged.

### D-06 | Native document sync pagination — PROVEN DEFECTS CORRECTED

Reading the code exposed two defects. The pre-correction run below confirmed both.

1. `sync_native_to_legacy` returns an empty recordset when no tag matches. The loop counted it as synced.
2. There was no isolation per document:
   - A failure after `PlasticosDoc.create` left an orphan legacy row, and the next run created a duplicate.
   - A SQL error aborted the transaction for every later document.

Correction: each document syncs inside `with self.env.cr.savepoint():`, the same pattern as `plasticos_transaction/models/native_document_import.py`. A document is counted only when the returned legacy record is non-empty. Keyset pagination, logging and business-link ownership are unchanged.

## Phase 4 — Validation

| Proof | Result | Evidence |
|---|---|---|
| Scanner suite `tests/test_unbounded_search_intent.py` | PASS 69/69 | `python3 -m pytest tests/test_unbounded_search_intent.py` |
| D-01: positive const / positional / local const / `max` / `min` retained; `0`/`None`/`False`/`-1`/positional `None`/conditional-zero flagged unbounded; param-`limit`/attribute/`or`-default/`**kw` flagged UNKNOWN | PASS | parametrized `test_*limit*` |
| D-02: identity AND status retained; identity OR status flagged; all-branches-bounded retained; mixed nesting judged correctly; `!`/empty flagged; malformed/splat/bare-name UNKNOWN | PASS | parametrized `test_*domain*` |
| D-03: conditional append flagged; both-branch append/assign retained; post-`return`-guard retained; loop-body fresh assignment retained; loop-dependent mutation UNKNOWN; zero-iteration path unbounded; `pop` UNKNOWN; append-after-search flagged | PASS | `test_*append*`, `test_*loop*`, `test_*branch*` |
| D-04: identity collections retained; categorical/null flagged; dynamic categorical UNKNOWN independent of variable name | PASS | `test_identity_collection_*`, `test_categorical_*`, `test_dynamic_category_*` |
| D-05 runtime (Odoo 19.0-20261010 + PostgreSQL 16, disposable DB) | PASS 9/9 | `evidence/gmp-nc-d/d05_singleton_proof.py` |
| D-05 scoped upgrade `plasticos_automation` `19.0.2.1.1 → 19.0.2.1.2` (`-u plasticos_automation` only) | PASS exit 0 | `ir_module_module.latest_version = 19.0.2.1.2` |
| D-06 module runtime (`plasticos_documents_native` installed) | **BLOCKED** | Enterprise `documents` / `documents_account` are not available in the disposable runtime (no `odoo-enterprise` tree). Not simulated |
| D-06 algorithm harness (the same loop on `res.partner`, 450 rows, 3 pages, 9 SQL failures, 5 empty results) | PASS 9/9 | `evidence/gmp-nc-d/d06_pagination_harness.py` |
| D-06 pre-correction counterfactual (same harness, `c40e4f5` loop shape) | Defect reproduced | `InFailedSqlTransaction` after 200/450; every document after the first failure was lost, and the run aborted |
| Audit baseline gate on HEAD (`scripts/audit/run_baseline_gate.sh`) | PASS | 0 new HIGH; 5 stale entries (pre-existing) |
| `ruff` 0.16.0 check + format on changed files | PASS | pinned `required-version` |

D-05 proofs:

- the seed has exactly one active record;
- the current record does not conflict with itself;
- an inactive record raises no false conflict;
- the DB `EXCLUDE` constraint is present and rejects a second active record (`ExclusionViolation`);
- with that constraint dropped inside a rolled-back savepoint, the `search_count` path still rejects both a second active create and a reactivation;
- the constraint is restored afterwards;
- no configuration rows were created or removed.

D-06 harness proofs:

- every eligible record is considered exactly once;
- no record is skipped at a page boundary;
- the count equals the real links (436 = 450 − 9 failed − 5 empty);
- later documents still sync after a SQL failure;
- a failure leaves no orphan legacy row;
- failed and empty documents stay eligible;
- the retry run processes only those 14, with no duplicate legacy rows (450/450);
- the third run terminates with nothing to do.

Termination argument: `last_id` strictly increases (ordered by `id ASC`, taking the last id of each non-empty page). A failed document has `id <= last_id`, so it is never re-read within the same run.

## Phase 5 — Before/after comparison

| Finding family | Before (`c40e4f5`) | After | Delta | Explanation |
|---|---:|---:|---:|---|
| `UNBOUNDED_SEARCH` (all) | 14 | 20 | +6 | false negatives exposed, nothing suppressed |
| of which `bound=unbounded` | 14 | 14 | 0 | the same 14 call sites |
| of which `bound=unknown` | — | 6 | +6 | see "Newly exposed" |

The prior Staging census of 103 reconciles completely under the corrected scanner:

| Disposition | Count |
|---|---:|
| Valid positive bound (multi-line `limit=` the regex missed) | 58 |
| Identity-bounded lookup / input-bounded batch (all parent- or record-identity scoped; both OR domains bound on every branch) | 15 |
| Business-complete set: search defines a returned domain (`.ids` in a `_search_*` result) | 5 |
| Business-complete set: same-expression projection (`.mapped`) | 4 |
| Paginated traversal (`document_sync`, `limit=200`) | 1 |
| Not an ORM query (regex `.search(text)` in `plasticos_web_leads`) | 7 |
| Survivors (in the table below) | 13 |
| **Total** | **103** |

The full per-line table is reproducible:

```bash
python3 docs/campaigns/odoo_noncritical_gmp_campaign_pack/reports/evidence/gmp-nc-d/census.py \
  scripts/audit/performance_audit.py .
```

### Survivor census (20)

| # | Site | Scanner | Disposition | Consumer and why the complete set is required |
|---|---|---|---|---|
| 1 | `plasticos_automation/models/penalty_rule.py:110` | unbounded | Business-complete (small registry) | `calculate_penalty` walks every active rule in `sequence` order; truncation skips applicable penalties |
| 2 | `plasticos_documents/models/compliance_service.py:16` | unbounded | Business-complete (registry) | `get_missing_documents`: every active rule for the model is a required document; truncation reports false compliance |
| 3 | `plasticos_documents/models/transaction_docs.py:153` | unbounded | Business-complete (registry) | thresholds are the minimum over all active rules. It also sits inside a per-transaction loop, which is High-family and owned by #234, so it is not touched here |
| 4 | `plasticos_geolocalize/models/res_partner_geo.py:55` | unknown | Valid positive bound (manual) | `limit=batch_size`, and `_geo_backfill_param` returns `max(value, 1)`. The proof is interprocedural, so the scanner reports UNKNOWN |
| 5 | `plasticos_intake_normalizer/models/intake_normalizer.py:186` | unknown | **UNKNOWN (genuine)** | cron batch `limit = config.batch_limit or 200`. `or 200` covers 0/None, but `batch_limit` has no positivity constraint. A negative value makes PostgreSQL reject the query (fails loudly; never unbounded). Proof needs `batch_limit > 0`, which is outside this lock |
| 6 | `plasticos_intake_normalizer/models/intake_normalizer.py:595` | unbounded | Business-complete (registry) | `_get_canonical_polymers`: every active polymer code; truncation rejects valid codes |
| 7 | `plasticos_partner_import/models/erp_import_service.py:753` | unknown | Input-bounded batch | `_user_ids_by_name(names)`: complete per name, so that duplicate names map to `None` |
| 8 | `plasticos_partner_import/models/erp_import_service.py:830` | unbounded | Business-complete | `_address_catalog`: every imported ERP address xmlid. Fail-closed import accounting needs every row, and the result is materialized as a list anyway |
| 9 | `plasticos_partner_import/models/erp_import_service.py:850` | unbounded | Business-complete | `_partners_by_prefix`: the complete source-key → partner map used by the import |
| 10 | `plasticos_partner_import/models/validation.py:45` | unbounded | **Genuine unbounded debt** | `validate_partner_graph` runs after every CSV partner import (`partner_import_service.py:248,280`). `company OR person` loads every partner, but errors arise only for persons. The domain could be narrowed without changing results. Application query outside this lock |
| 11 | `plasticos_partner_import/models/validation.py:102` | unbounded | Business-complete | legacy `plasticos_import` xmlids: a closed historical namespace, and every one is reported |
| 12 | `plasticos_partner_import/models/validation.py:116` | unbounded | **Genuine unbounded debt** | `audit_import_integrity` loads every location in order to filter `not facility_role` in Python. Over-fetches; outside this lock |
| 13 | `plasticos_partner_import/models/validation.py:127` | unbounded | Business-complete | the report enumerates every parentless contact; the domain is exactly the reported set |
| 14 | `plasticos_partner_import/models/validation.py:136` | unbounded | Business-complete | every new-module xmlid name, for duplicate detection |
| 15 | `plasticos_partner_import/models/validation.py:197` | unbounded | Business-complete | the migration set: every legacy xmlid must migrate |
| 16 | `plasticos_transaction/models/sale_inherit.py:167` | unbounded | Business-complete (natural-key scoped) | all POs whose `origin` is the worksheet (live-order fallback); truncation drops linked POs |
| 17 | `plasticos_transaction/models/sale_inherit.py:168` | unbounded | Business-complete (natural-key scoped) | all non-cancelled moves for the worksheet |
| 18 | `plasticos_transaction/models/account_move_inherit.py:56` | unknown | Input-bounded batch | `name in all_origins` built from `self` |
| 19 | `plasticos_transaction/models/account_move_inherit.py:61` | unknown | Input-bounded batch | `name in missing_origins` (a subset of `self`'s origins) |
| 20 | `plasticos_transaction/models/purchase_inherit.py:45` | unknown | Input-bounded batch | `name in origins` from `self` |

Totals:

- 14 retained as business-complete or input-bounded with a stated consumer;
- 1 valid bound proven by manual review;
- 2 genuine unbounded debt (`validation.py:45`, `:116`);
- 1 genuine UNKNOWN (`intake_normalizer.py:186`).

No query was truncated, no `limit=1` was added, and no exemption was keyed on a filename, comment, function name, model name or variable name.

### Newly exposed false negatives (6, relative to `c40e4f5`)

| Site | Repair that exposed it | Disposition |
|---|---|---|
| `res_partner_geo.py:55` | D-01 (a call result is not a proven limit) | Valid bound by manual review |
| `intake_normalizer.py:186` | D-01 (`x or 200` is not proven positive) | Genuine UNKNOWN |
| `erp_import_service.py:753` | D-04 (dynamic `in` on `name`) | Input-bounded batch |
| `account_move_inherit.py:56`, `:61` | D-04 | Input-bounded batch |
| `purchase_inherit.py:45` | D-04 | Input-bounded batch |

### Known limits of the scanner (stated, not hidden)

- A many-to-one equality (`*_id = value`) counts as an identity bound even where the field is categorical (for example `country_id`). This rule predates #238, and D-04 deliberately did not widen it.
- A dynamic identity value is not proven non-null at runtime.
- Passing a domain list to a helper that mutates it is not modelled.
- Aliasing (`b = domain; b.append(...)`) is not modelled.

### High predecessor integration (#234) — PENDING

The merged candidate was built as a tree with no worktree mutation: `git merge-tree --write-tree 40d49ff 8a07d9c` → `f307d3f`. The textual merge is clean.

- Both owners' suites on the merged tree (`test_unbounded_search_intent`, `test_audit_n_plus_one`, `test_audit_sensitive_logging`): **91/91 PASS**, after one test repair in this PR.
  - The repaired test is `test_n_plus_one_method_still_uses_the_line_rule`. It asserted the Staging N+1 line-rule blind spot (an aliased query in a loop is not flagged), so #234's hardened scanner failed it.
  - It is replaced by `test_query_intent_never_suppresses_a_loop_query`. The new test asserts the actual non-suppression boundary: an identity-bounded search in a loop is retained by the Moderate rule and still flagged by the High rule.
- No mutual suppression: the Moderate verdict never consults the High result, and the reverse holds too. That test proves it.
- **Combined baseline ratchet on the merged tree: FAIL, 2 new HIGH.**
  - `plasticos_automation/models/automation_config.py:63`. #234's baseline logs this line by its Staging code text `existing = self.search(` (fingerprint `9329c3606107e045`). #238's D-05 change to `search_count` changes the fingerprint. It is the same accepted constraint loop over `self`.
  - `plasticos_documents_native/models/document_sync.py:165`. Keyset pagination is by construction a query inside `while True`, and every realization of the contract's "large traversal → explicit batching/pagination" will trip a loop-query rule.
- Neither can be closed from this PR without editing #234's baseline (prohibited) or reopening High N+1 debt (prohibited). The resolution belongs to whichever of #234 or #238 merges second: re-review and log these two fingerprints in `ci/baselines/extended_audit_baseline.json` through `check_baseline.py --dump-new`.

## No-reopen proof

- Prior Critical/High remediation touched: NO. `check_n_plus_one_queries`, lines 1–61 of `performance_audit.py`, `ci/baselines/**` and #234's branch are untouched. The one test change removes a #238-owned assertion about the High scanner's internals; it does not change the High scanner.
- Previous campaign remained sealed: YES.

## Runtime propagation

- Runtime modules changed: `plasticos_documents_native` (D-06). `plasticos_automation` was changed by `c40e4f5`, and nothing further changed it here.
- Version bumps: `plasticos_documents_native` `19.0.1.2.3 → 19.0.1.2.4`, so any DB that took this branch's `1.2.3` reloads. `plasticos_automation` stays at `19.0.2.1.2` (bumped in `c40e4f5`).
- Migrations: none (no schema change).
- Upgrade proof: `plasticos_automation` scoped `-u` passed. The `plasticos_documents_native` upgrade is **BLOCKED** because Enterprise `documents` is unavailable. Operator command on an Enterprise target: `make update m=plasticos_documents_native`.

## Publication

- Publication path: Cursor-Governance SSOT `make pr` (`pr-preflight` → `run_pr_gate.sh` → `open_pr_after_gate.sh`) with `PR_BASE=origin/Staging`, updating the existing PR #238.
- Result: recorded in the PR thread and the session terminal report. This file is committed before publication, so it cannot quote its own push receipt.

## Verdict

**PARTIAL**

Completed: D-01, D-02, D-03 and D-04 repaired with adversarial tests; D-05 proven at runtime; D-06 defects corrected with an algorithm-level runtime proof; the 103-finding census plus the 6 new findings fully classified.

Pending proof obligations:

1. D-06 module-level runtime proof and the scoped upgrade of `plasticos_documents_native`, on a runtime with Enterprise `documents`.
2. Integration with #234 (unmerged). The combined ratchet needs the two High fingerprints above re-logged by the baseline owner.
3. Contract acceptance: one genuine UNKNOWN (`intake_normalizer.py:186`) and two genuine unbounded traversals (`validation.py:45`, `:116`). Each needs a runtime change outside this remediation's locked scope.

## Next action

Run `make update m=plasticos_documents_native` followed by `plasticos_documents_native.batch_sync_unlinked` on an Enterprise-enabled disposable DB holding more than 200 unlinked documents, replaying `evidence/gmp-nc-d/d06_pagination_harness.py` assertions against `documents.document`.
