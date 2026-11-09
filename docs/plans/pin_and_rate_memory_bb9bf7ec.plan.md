---
name: Pin and rate memory
overview: "Plan PR 1 only. #217 and #182 stay separate future workstreams. Neither is implemented, locked, or closed in this wave."
todos:
  - id: verify-baseline
    content: Re-read origin/Staging, open PRs, and worktree dirt immediately before the plan branch. Do not reuse a remembered SHA.
    status: completed
  - id: publisher-fixes
    content: On the plan branch only, edit scripts/build_pr_body.py, scripts/pr_stack_parent.sh, tests/test_build_pr_body.py, and tests/test_make_pr_publication.py.
    status: in_progress
  - id: plan-pr-1
    content: Commit the revised plan plus those four files. PR_CHECK_SCOPE=full PR_CHECK_SMOKE_CACHE=0 make pr into Staging. Record URL, head SHA, and base.
    status: pending
  - id: ws-217
    content: "#217 status blocked on evidence. Candidates cryptography 50.0.2 and pyOpenSSL 26.4.0. make lock-deps required. Not authorized in this wave."
    status: pending
  - id: ws-182
    content: "#182 status blocked on decision/evidence. ADR and cross-company visibility need human approval. Not authorized in this wave."
    status: pending
isProject: false
---

# Plan PR 1 — #217 and #182

Status of this document: **published for review** only after Plan PR 1 is open. Until that URL exists, this file is the revision. Issue remediation is **not** authorized.

Status words used below: `ready for bounded implementation`, `blocked on decision/evidence`, `published for review`, `merged but awaiting environment proof`, `closed`.

## Verified baseline (2026-11-08, this revision)

Read in this checkout. Re-read again before creating the branch. A SHA here is a review pin, not permission to skip that read.

| Fact | Value |
|---|---|
| `origin/Staging` | `b5b6056f01639212e722ccdec5b964b36deee9f5` |
| Local `HEAD` | branch `Staging` at that same SHA. Not detached. Not `9b3ec0a5`. |
| Open pull requests | [#409](https://github.com/cryptoxdog/IB-Odoo_19/pull/409) `docs/agent-rule-realignment` → `Staging` only. #408 is not open. |
| Dirty worktree | `INVARIANTS.md`, `constraints.txt`, `requirements.txt`, `tests/production-rehearsal/evidence/latest` |
| [#217](https://github.com/cryptoxdog/IB-Odoo_19/issues/217) | OPEN |
| [#182](https://github.com/cryptoxdog/IB-Odoo_19/issues/182) | OPEN |
| ADR directory | `docs/adr/` is the only binding ADR directory (`docs/adr/README.md`). Do not create another. |

Do not stash, pop, reset, or checkout across those dirty files. Do not assume a pathspec commit isolates them. Plan PR 1 is built in a new worktree from a freshly fetched `origin/Staging`.

`03_CURSOR_PLAN_SAL_AND_VANILLASOFT.yaml` is not in this checkout. PR 2 (#307, #354, #353) and PR 3 (#183, #299) are not started here. Do not start PR 2 until Plan PR 1 is open at the recorded head SHA. Do not start PR 3 until PR 2 is open at its recorded head SHA. Do not start remediation of any of the seven issues until all three plan PRs are open, and then stop for a separate implementation authorization.

## Campaign shape

Three plan PRs, one after another, same agent, no issue code:

1. **Plan PR 1** (this document) into `Staging`. Also the four publisher fixes below.
2. **Plan PR 2** onto PR 1's head, for #307, #354, #353. Not this wave.
3. **Plan PR 3** onto PR 2's head, for #183 and #299, which stay deferred. Not this wave.

#183 and #299 stay deferred. They are not edited.

## Plan PR 1 publication allowlist

Commit only these paths:

| Path | Role |
|---|---|
| `docs/plans/pin_and_rate_memory_bb9bf7ec.plan.md` | In-repo copy of this revised plan. The Cursor copy stays at `~/.cursor/plans/pin_and_rate_memory_bb9bf7ec.plan.md`, which is outside the git repo, so the PR carries the basename under `docs/plans/`. |
| `scripts/build_pr_body.py` | Stop writing `git diff --stat` into Changes. |
| `scripts/pr_stack_parent.sh` | Allow a proven chain of three PRs ending at Staging. |
| `tests/test_build_pr_body.py` | Changes has no stat manifest. Test plan section stays the template. |
| `tests/test_make_pr_publication.py` | Three-deep success. Deeper, Production, loops, and broken chains still refuse. |

No other file. In particular not `requirements.txt`, `constraints.txt`, any `plasticos_logistics` file, `Makefile`, `scripts/git_open_pr.sh`, `scripts/git_push_with_pr.sh`, `scripts/make_push_pipeline.sh`, `scripts/pr_check_run.sh`, `.github/pull_request_template.md`, or `.github/workflows/**`.

### Publisher fix A — PR body

`scripts/build_pr_body.py` `fill_template` puts `git diff --stat` inside a fence under `## Changes` (lines 46–48 and 78–80). The fallback body does the same (lines 55–58).

- Keep `## Summary`, `## Changes`, and `## Test plan` from `.github/pull_request_template.md`. Do not edit the template file.
- Summary stays the commit subject list.
- Changes becomes that same subject list as prose bullets, not a `--stat` table and not a filename inventory. If the stat string is still computed, do not write it into the body.
- Test plan stays the template text, including the CI Gate, Odoo.sh, and module-upgrade checkboxes.
- Stacked-base note (`Stacked on ...`) stays.

`tests/test_build_pr_body.py` today asserts `"AGENTS.md"` appears under Changes because the fixture stat is `AGENTS.md | 2 +-`. Replace that assertion. Changes must contain the commit subject. Changes must not contain `|`. Test plan must still equal the template section.

Before `make pr`, run `python3 scripts/build_pr_body.py Staging` in the plan worktree and confirm the preview has the three headings and no `|` stat line.

### Publisher fix B — three-deep stack

`scripts/pr_stack_parent.sh` `prove` lists open PRs with `base=Staging` and `head=<parent>`. A parent whose own PR targets another feature branch returns "no open PR into Staging". `tests/test_make_pr_publication.py` `test_stacked_base_on_a_stacked_parent_refuses` locks that refusal. The fixture is child → `feat/parent` → `feat/grand` → `Staging` (grand's base defaults to Staging). That is the three-deep chain this campaign needs. It must succeed.

Walk from the immediate parent:

- Exactly one open PR in `cryptoxdog/IB-Odoo_19` whose head is that branch. Wrong repo still refuses.
- Follow `base.ref` at most two hops (parent, then grandparent). The new PR is the third.
- The walk must end at `Staging`.
- `Production`, `main`, and a case-folded `staging` that is not the branch `Staging` still refuse in `name`.
- A hop with zero PRs or more than one PR refuses.
- A cycle refuses.
- A chain that reaches `Production` refuses.
- A chain longer than grandparent refuses (the existing "too-deep" case).
- A missing middle PR refuses.
- `GH_REPO` still required. `git fetch` and `git merge-base --is-ancestor` of the immediate parent still required.
- Do not change L4, authentication, smoke, or push gates. Do not edit the scripts that call this one.

Update `test_stacked_base_on_a_stacked_parent_refuses` so the grandparent-into-Staging case opens the child PR and does not push before prove succeeds. Keep `test_stacked_chain_that_does_not_reach_staging_refuses` red for Production, a loop, a broken chain, and the six-deep chain. The direct-parent lookup may no longer send `base=Staging` only. Assert the new query still cannot accept a foreign `full_name`.

### Publisher tests before make pr

```bash
python3 -m pytest tests/test_build_pr_body.py tests/test_make_pr_publication.py -q
python3 scripts/build_pr_body.py Staging
```

Both must exit 0. The preview is part of the PR evidence. A failure stops the wave. No `make pr-nosmoke`.

### Branch and publish

1. `git fetch origin Staging` and record `git rev-parse origin/Staging`. If it is not `b5b6056f01639212e722ccdec5b964b36deee9f5`, stop and amend this plan's baseline table before branching.
2. `git worktree add -b docs/plan-217-182 <new-worktree> origin/Staging`. Do not use the dirty Staging checkout.
3. Copy this revised plan to `docs/plans/pin_and_rate_memory_bb9bf7ec.plan.md` in that worktree. Apply only the four publisher edits there.
4. Stage those five paths by name. Do not `git add -A`. Do not `make commit` without pathspecs.
5. One commit on that branch. Subject: `docs(plan): revise the #217 and #182 plan and the PR publisher`.
6. From that worktree, attached:

```bash
PR_CHECK_SCOPE=full PR_CHECK_SMOKE_CACHE=0 make pr
```

7. Stop if install-smoke or the Odoo runtime gate is skipped, cached, or absent from the log. A green pre-push hook is not a substitute. `scripts/pr_check_run.sh` does not run the pure-Python suite as this local gate. Run the pytest command above separately and keep its exit status. Do not claim `make pr` ran pytest.
8. Record the open PR URL, `head` SHA, and `base` ref. Base must be `Staging`. Do not merge. Do not close #217 or #182.

`make pr` for this wave publishes the plan. It does not authorize the issue fixes.

## Workstream #217 — blocked on evidence

[#217](https://github.com/cryptoxdog/IB-Odoo_19/issues/217). Status: **blocked on evidence**. Not `ready for bounded implementation` until the lock diff is classified and the proofs below exist. It does not wait on #182. It is not published in Plan PR 1.

Candidates, not a verified pair: `cryptography==50.0.2` and `pyOpenSSL==26.4.0`. PyPI `requires_dist` for 26.4.0 is `cryptography>=49,<51` and `requires_python >=3.9`. The Gate SDK pin in `requirements.txt` (`7ec6cdf5e26c837057ca35b7324a88de4d499ea3`) requires `cryptography>=43.0.0`. Locked `xmlsec` is `1.3.16` and does not declare cryptography. Re-check all four against the tree at implementation time. If the solver, the SDK pin, `xmlsec`, or the Odoo.sh base image disagrees, stop. Update the shim comment to the pair that actually installed.

Lock: run `make lock-deps`. Diff `constraints.txt`. If any package other than `cryptography` and `pyOpenSSL` changes, **stop and report the lock-scope conflict**. Do not hand-edit the lock. Do not accept a broad upgrade in silence. An exception needs the issue owner to amend #217 in writing.

Closure proof, each with a receipt. Missing any one keeps the issue open. Status may become `merged but awaiting environment proof` after the code merges. It becomes `closed` only when all of these are true:

- Resolved versions in the venv match the pins.
- `pip-audit -r requirements.txt` reports no cryptography or pyOpenSSL advisory.
- `make install-smoke` on the pinned fixture `odoo_test_tpl_ee_c9e8a81f52f23680` loads the registry. Log has no `GEN_EMAIL` or `X509_` import failure.
- A targeted Odoo 19 process imports `base` with the new pair.
- An Odoo.sh Staging build for that SHA shows the same clean import. Read the endpoint from `.cursor/rules/98-odoo-sh-staging.mdc` and `.env.local` at that time. Do not invent a host. Local Docker is not this proof.
- `constellation-node-sdk` still imports. `xmlsec` still imports.

Future allowlist, not granted now:

- `requirements.txt` — pins and a comment that matches the installed pair
- `constraints.txt` — output of `make lock-deps` only

## Workstream #182 — blocked on decision/evidence

[#182](https://github.com/cryptoxdog/IB-Odoo_19/issues/182). Status: **blocked on decision/evidence**. The issue is a human architecture and security decision. Optional `company_id` is a proposal, not an approval. Do not write the ADR until the owner accepts both the data rule and the visibility rule. If the ADR path cannot be confirmed at that time, record `BLOCKED: human decision + ADR` and stop. Do not invent a second ADR directory. The existing directory is `docs/adr/`. Pick the next unused number from `docs/adr/README.md` at approval time and add one file there. Cite its commit SHA in the implementation PR.

Proposed data rule, for the decision record:

- Exact single match: `company_id` is the load company (`company_id`, else `sale_order_id.company_id`).
- `invalid_lane_key`, `no_candidate_match`, `multiple_candidate_matches`, `candidate_scan_truncated`: `company_id` is `False` in the vals. The field default is `env.company`. Omitting the key would fabricate an owner.
- Legacy cache `create`, `write`, and `unlink` stay frozen. Do not change those methods.
- `_check_canonical_load_company` stays. An empty `canonical_load_id` is already allowed. A load whose company differs from `company_id` still raises.

Security question, also required before code: the domain `['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]` shows every unowned reconciliation row to every company that can read the model. That is cross-company disclosure. Do not treat it as harmless. The ADR must either accept that disclosure or name a tighter reader set that still uses the existing record-rule model. Exact-match rows stay in their load's company. ACLs stay as they are. Logistics already has create and not write or unlink in `plasticos_security_base`. Do not edit that module.

Functional proof after approval, on a real Odoo 19 upgrade of `plasticos_logistics` (manifest bump checked against Staging, currently `19.0.1.14.16`):

- One immutable row per legacy row for each of the four non-exact dispositions, plus the existing exact-match case.
- Second reconcile adds nothing.
- Company mismatch on a canonical load is rejected.
- Logistics can read an approved empty-company row and cannot write or unlink it.
- A user outside Logistics cannot create evidence.
- A second company cannot read an exact-match row owned by the first company.
- The negative test for the approved empty-company policy fails if visibility is wider or narrower than the ADR.
- `-u plasticos_logistics` on a database that already has the NOT NULL column leaves the column in place and allows NULL. A manifest bump alone is not that proof.

Future allowlist, not granted now:

- `plasticos_logistics/models/rate_memory.py` — only `action_reconcile_to_canonical_history` and the vals it builds
- `plasticos_logistics/models/freight_governance.py` — `company_id` required flag only, unless the ADR says otherwise
- `plasticos_logistics/security/record_rules.xml` — `rule_rate_memory_reconciliation_company` only
- `plasticos_logistics/tests/test_linda_freight_models.py`
- `plasticos_logistics/__manifest__.py` — patch bump only
- one new file under `docs/adr/` plus its row in `docs/adr/README.md`, after the number is chosen

Anything else stops for scope review.

## Prohibited implementation edits

- `plasticos_security_base/security/ir.model.access.csv` and all other `plasticos_security_base/**`. Do not widen ACLs to make tests green.
- `plasticos_logistics/models/rate_memory.py` outside `action_reconcile_to_canonical_history` and the vals it builds. Do not relax the legacy cache `create`, `write`, or `unlink` freeze. Do not invent company attribution. Do not mutate historical rows.
- `plasticos_logistics/security/record_rules.xml` outside `rule_rate_memory_reconciliation_company`.
- `.pre-commit-config.yaml`, `AGENTS.md`, `Makefile`, `scripts/git_push_with_pr.sh`, `scripts/pr_check_run.sh`, `tests/test_pr_check_scope.py`, `tests/production-rehearsal/**`.
- `Dockerfile`, `docker-compose.yml`, `.github/workflows/**`, `scripts/pr_check_scope.py`, `pipeline_v2.py`, `.env`, secrets, migrations that are not the verified nullable-column change, other module manifests, ERP import paths, CRM and VanillaSoft paths, the Production branch.
- #183, #299, #307, #353, #354.
- No new model, ACL row, or helper framework.
- No test skip and no mock that replaces the Odoo upgrade or the Odoo.sh registry proof.
- No issue close on PR creation. No merge. No `make update-all`. No direct push. No `make pr-nosmoke`.

## Stop conditions

Stop on a dirty plan worktree, a Staging SHA that moved without the baseline table being updated, a dependency solver that rejects the candidate pair, a `make lock-deps` diff outside cryptography and pyOpenSSL, a missing ADR or a missing visibility decision, a failed nullable-column upgrade, or an Odoo.sh Staging log that is missing or shows `GEN_EMAIL` or `X509_`. An older merged PR or a green local hook does not replace these receipts.

## Evidence to store on each future implementation PR

Base SHA, head SHA, allowlist diff, each test command and its exit status, the Odoo database name and receipt, the GitHub CI conclusion, and the issue acceptance list. #217 and #182 each have their own PR into Staging unless a reviewer writes that one combined PR is accepted. Neither PR merges itself.

## FINAL CHECKLIST

- [x] Current `origin/Staging` SHA, PR list, and worktree dirt verified this revision. Stale PR #408 and detached-HEAD `9b3ec0a5` claims removed. SHA `b5b6056f01639212e722ccdec5b964b36deee9f5`. Open PR #409 only. Dirty files listed above.
- [x] #217 and #182 are independently gated. #217 does not wait on the #182 decision.
- [ ] Crypto candidate pair and downstream compatibility re-verified at implementation time, not assumed from this plan.
- [x] `make lock-deps` is required for #217. Unrelated lock drift stops the work. No silent hand edit.
- [ ] `pip-audit`, registry import, module tests, and an actual Odoo.sh Staging log are still required before #217 can close.
- [ ] #182 ADR path is `docs/adr/` but the file is not approved and has no number yet. Status remains blocked.
- [ ] Cross-company visibility of `company_id=False` is an open security decision. No domain is approved.
- [ ] Disposition, idempotency, immutability, two-company, and real upgrade gates are specified and not yet run.
- [x] Future implementation allowlist and prohibited list are in this plan.
- [x] Neither issue closes when a PR opens. No merge and no production action is authorized.
- [ ] Plan PR 1 contains only this plan and the four publisher files. Not opened in this revision turn.
- [ ] Publisher tests and body preview are specified. Not run in this revision turn.
- [ ] `PR_CHECK_SCOPE=full PR_CHECK_SMOKE_CACHE=0 make pr` is the Plan PR 1 command. It has not been run.
- [x] Front-matter todos match the two blocked workstreams and the unpublished plan PR.
- [x] This revision did not change issue code, dependencies, git history, or issue state.
