# make pr — one validation pass per publication attempt

Date: 2026-11-03 · PR #358 · base `Staging` at `9ee917e` · plan `make_pr_single_validation_pass_32909105` (revision 2)

## What changed

Before this change, one `make pr` attempt validated the same candidate twice:

1. `scripts/git_push_with_pr.sh` ran `gitleaks detect`, then `make pr-check`.
2. The `git push` that followed ran the pre-push stage: 35 hooks, including the same full
   `gitleaks detect` and 23 whole-tree Odoo scanners that `make pr-check` (`make audit`) had just run.

The obvious fix, moving all validation into the pre-push hook, is unsafe. pre-commit 4.7.0 runs no
pre-push hook when the push carries nothing new, so a retry after a partial publication would reach PR
verification unvalidated. `tests/test_publication_real_push.py` proves this with real git and real
pre-commit.

The change keeps the gate in the publisher and makes the hook the second gate for direct pushes:

| Component | Owns |
|---|---|
| `scripts/git_push_with_pr.sh` | Runs on every attempt, before `git push`: gitleaks, smoke resolve, `make pr-check`, HEAD/worktree check, smoke recheck, then the **second L4 check at the push boundary** (the first stays in `make_push_pipeline.sh`). Pushes one refspec carrying `L9_PUBLISH_VALIDATED_SHA` and `L9_PUBLISH_TARGET`. Clears any inherited values first. |
| `scripts/pre_push_validate.sh` | Pre-push gate (`gitleaks` and `gate` modes). Skips its work only when the binding names this exact push: pushed SHA = HEAD, clean tree, remote `origin`, `refs/heads/<target>`. Otherwise runs the full gitleaks scan and `make pr-check`. |
| `.pre-commit-config.yaml` | `default_stages: [pre-commit]`. Pre-push stage is 10 hooks (below). The 23 Odoo scanners are commit-only. |

No validation receipt or other file is read as evidence anywhere.

## Pre-push hook mapping (before → after)

| Hook | Pre-push before | Pre-push after | Still enforced by |
|---|---|---|---|
| `ruff`, `ruff-format` | yes (stage-less) | no | commit stage; `make pr-check` → `audit-quick` (`lint`, `format`); ci.yml `lint` |
| `banned-identifier` | yes (stage-less) | no | commit stage; `make audit` → `ban-check`; ci.yml static-checks BAN001 |
| `check-xml` | yes (stage-less) | **yes** | kept: `make audit` `xml-check` covers only `plasticos_*`, this hook covers every changed XML file |
| `check-yaml`, `check-merge-conflict` | yes (stage-less) | **yes** | kept: no `make` or ci.yml counterpart |
| `end-of-file-fixer`, `trailing-whitespace`, `check-added-large-files` | yes (manifest) | **yes** | kept: no `make` or ci.yml counterpart |
| `phantom-enum-values`, `manifest-contract` | yes | **yes** | unchanged |
| `gitleaks-push` | yes | **yes** (bound) | entry is now `scripts/pre_push_validate.sh gitleaks`, `fail_fast: true` |
| `pr-validate` | — | **yes** (bound, new) | `make pr-check` for a direct push |
| `odoo-patterns` | yes | no | commit stage; `make audit` `odoo-patterns`; ci.yml static-checks |
| `no-local-intelligence` | yes | no | commit stage; `make audit` `no-local-intelligence`; ci.yml static-checks |
| `module-wiring` | yes | no | commit stage; `make audit-quick` `wiring`; ci.yml static-checks |
| `cron-invariants` | yes | no | commit stage; `make audit-quick` `cron-check`; ci.yml via `tests/test_cron_invariants.py` |
| `circular-deps` | yes | no | commit stage; `make audit-quick` `deps-check`; ci.yml static-checks |
| `orphan-model-refs`, `xpath-stability`, `field-integrity`, `model-inheritance`, `orm-integrity` | yes | no | commit stage; `make audit` → `run_audit_integrity.sh`; ci.yml static-checks |
| `constraint-patterns`, `disabled-actions`, `automation-field-refs` | yes | no | commit stage; `make audit` → `run_audit_integrity.sh` (not in ci.yml before or after) |
| `package-init`, `odoo19-hooks`, `odoo-antipatterns`, `critical-manifest`, `enhanced-audit` | yes | no | commit stage; `make audit` targets of the same names; ci.yml static-checks |
| `odoo19-xml` | yes | no | commit stage; `make audit-quick` `odoo19-check`; ci.yml static-checks |
| `state-guard-bypass`, `pipeline-v2-guard`, `dev-tools-fence` | yes | no | commit stage; `make audit` → `guards`; ci.yml static-checks |
| `acl-completeness` | yes | no | commit stage; `make audit` `acl-check`; ci.yml static-checks |

`make pr-check` runs `make audit` only when a non-documentation path changed (the 2026-10-22 scoping
law). A documentation-only branch no longer runs the Odoo scanners at push; ci.yml still runs all of them
on the PR. The only `ci.yml` change is one added pin, `pre-commit==4.7.0`, on the pure-tests install
line (operator-authorized), so the real-runner tests in `tests/test_publication_real_push.py` execute in CI
instead of skipping. No CI check was removed.

## Supported push forms

Measured on pre-commit 4.7.0 (`tests/test_publication_real_push.py`).

| Push | Pre-push stage | Result |
|---|---|---|
| Update, or new branch with new commits | runs; `PRE_COMMIT_TO_REF` = full pushed SHA | validated (bound skip only for `make pr`'s own push) |
| Up to date (retry after partial publication) | git calls the hook with no ref lines; pre-commit runs nothing | `make pr` already validated before the push; a direct push changes nothing remotely |
| New ref to a commit the remote already has | pre-commit runs nothing; the ref is created | no new content reaches the remote; not publication |
| Branch deletion | no hook | no content |
| Several refs in one push | pre-commit binds the **first** new ref only; hooks see no stdin | limitation, unchanged from before; `make pr` pushes exactly one refspec (asserted) |
| Root of history (all-files mode, no `PRE_COMMIT_TO_REF`) | refused | `pre-push refused: a push that includes the root of history is not supported` |
| Pushed SHA other than the clean checked-out `HEAD` | refused | `make pr-check` validates the working tree, so it cannot vouch for another commit |

## Threat model

- **Publication cannot be authorized by forged or stale evidence.** `git_push_with_pr.sh` clears
  inherited binding values, runs its gate, and sets the binding only on its own push.
  `test_inherited_publisher_binding_does_not_skip_publisher_validation` covers this.
- **A binding is honoured only on an exact match.** A mismatch in SHA, target, remote name or
  remote branch runs the full gate (`tests/test_pre_push_validate.py`). A binding for a SHA other than
  `HEAD` is refused.
- **A deliberate local actor can skip hooks with `git push --no-verify`.** That was true before this
  change and still is. This work neither widens nor closes that hole. ci.yml is the merge gate.
- **L4** runs twice per `make pr`: before local work, and after validation at the push boundary
  (`test_l4_denial_and_second_check_failure_do_not_push`). Direct pushes are not publication and are not
  L4-gated by this repository.

## Benchmark

Disposable clones only (session scratchpad), each with a local bare `origin`; nothing was committed on
`Staging` or pushed to GitHub. Machine: 4 vCPU x86_64 Linux container, `PR_CHECK_JOBS=4`, repo venv
(ruff 0.16.0, pytest 8.3.5), pre-commit 4.7.0, gitleaks 8.24.3.

- **Old**: `9ee917e` + a one-line comment appended to `plasticos_claims/models/__init__.py`.
- **New**: feature head (`f338bf6`) + the same fixture. Each clone's base is its own starting revision, so the
  scoped `pr-check` sees the fixture only. Each push re-creates the remote ref and deletes the local
  tracking ref, so every push is a real push that reaches the pre-push stage.
- 3 runs per phase. Every phase exited 0. The old push ran 35 hooks; the new pushes ran 10.

| Phase (seconds) | Old run 1 / 2 / 3 | Old median | New run 1 / 2 / 3 | New median |
|---|---|---|---|---|
| commit stage (`pre-commit run --hook-stage pre-commit --files <fixture>`) | 16.77 / 24.34 / 19.00 | 19.00 | 18.89 / 20.10 / 20.72 | 20.10 |
| publisher `gitleaks detect` | 3.35 / 3.99 / 3.79 | 3.79 | 3.59 / 3.93 / 3.96 | 3.93 |
| publisher `make pr-check` (scoped) | 37.76 / 40.53 / 40.55 | 40.53 | 39.31 / 40.37 / 42.12 | 40.37 |
| `make pr-remote-feedback` (GitHub API, no PR for the branch) | 1.98 / 2.11 / 2.16 | 2.11 | 2.23 / 1.99 / 2.24 | 2.23 |
| pre-push stage on `make pr`'s own push | 43.49 / 45.76 / 45.22 | **45.22** | 23.27 / 22.48 / 26.00 (bound) | **23.27** |
| pre-push stage on a direct `git push` | same as above | 45.22 | 72.87 / 66.70 / 78.24 | 72.87 |

Derived from the medians:

- **Local `make pr` validation** (gitleaks + `pr-check` + pre-push stage): 89.54 s → 67.57 s, **−21.97 s (−24.5%)**
  per attempt. The whole saving is in the pre-push stage (−21.95 s, −48.5%); the publisher's own phases are
  unchanged within noise. Remote feedback is about 2 s in both, so Priority D/E would save little here.
- The old pre-push stage cost is whole-tree work, so it does not shrink with a smaller change. The saving
  should hold for larger branches, but only this fixture was measured.
- **A direct `git push` is slower** (45.22 s → 72.87 s, +27.65 s) because it now runs `make pr-check`
  instead of 35 hooks that skipped tests and the audit baseline. That is the cost of a stronger direct gate.
- The bound push still costs about 23 s: the six hygiene hooks and the two contract pytest hooks
  (`phantom-enum-values`, `manifest-contract`) are not bound. Measuring and trimming those is a possible follow-up.
- Caveat: new run 3 `make pr-check` (42.12 s) overlapped a `make commit` in the worktree. Commit-stage
  timings vary ±4 s run to run; their difference is noise.

Raw CSV: kept outside the repository (session scratchpad), reproduced by the harness described here.

## Not changed

- `Makefile`, `scripts/pr_check_run.sh`, `scripts/pr_check_scope.py`. `ci.yml` gains only the `pre-commit` pin.
- Commit-stage hooks: the 23 scanners still run on every commit.
- Priority D (`pr_check_remote_feedback.py` checks SHA before collecting) and Priority E
  (`apply_pr_kernel_metadata.sh` single label fetch) are a separate follow-up.
- `workflow_state.md` is left unchanged: it lists open campaigns only and has no change log.
