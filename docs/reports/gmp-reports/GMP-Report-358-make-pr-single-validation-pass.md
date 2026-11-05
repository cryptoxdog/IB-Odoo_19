# GMP-358 — make pr: one validation pass per publication attempt

**Task:** `/l9-plan-build` of plan `make_pr_single_validation_pass_32909105` (revision 2), T1–T10.
**Branch:** `fix/make-pr-single-validation-pass` (worktree `wt-make-pr-validation`)
**Base:** `Staging` `9ee917e7521d64d0e759afd2fdef8198d4c32b30`
**PR:** [#358](https://github.com/cryptoxdog/IB-Odoo_19/pull/358) → `Staging`
**Seam status:** green locally (153 targeted tests, ruff, shellcheck, all commit-stage hooks, root-file gate). CI green on `f338bf6`; red on `0738308` (coverage combine), fixed in `0490514` and `8cc9f03` (see Incident).

## Plan gates

| Gate | Result |
|---|---|
| `validate_plan_document.py` | PASS |
| Section receipt (`validate_plan_section_receipt.py`, cursor-build) | PASS |
| Kernel receipt: Improve → Recursive Alignment → Validate & Repair (`validate_plan_kernel_receipt.py`) | PASS, with nine recorded deltas from T1 evidence and the operator's sanctioned-commands instruction |
| MEMORY_PREFETCH | namespace `ib-odoo-19`, snapshot `4f53cda1…5ed12ab4`, 0 records checked, 0 conflicts, `memory-phase-lock/v2` |

The governance GMP executor was not used. It writes reports to a root `reports/gmp/` directory, which this
repository forbids (AGENTS.md 2026-10-21), and its finalize step commits and publishes on its own. The run contract
(lock, ground truth, verify, evidence) was applied by hand. Commits went through `make commit`; publication through
`make pr-nosmoke`. The executor defect is recorded in the governance session-debt ledger.

## Todos

| Todo | Result | Commit |
|---|---|---|
| T1 counterexample first | Real git + pre-commit 4.7.0 characterization (root push has no refs; up-to-date push reaches the hook with no ref lines and pre-commit runs nothing; new ref to an existing commit runs no hook; multi-ref binds the first ref only; `--to-ref HEAD` is literal) and a `make pr` no-op retry guard. 67 tests passed on unmodified scripts. | `8803dba` |
| T2 `scripts/pre_push_validate.sh` | `gitleaks` and `gate` modes; push-ref matrix; five-field publisher binding; fail-closed refusals. | `0019ef5` |
| T3 `.pre-commit-config.yaml` | `default_stages: [pre-commit]`; pre-push = 10 hooks incl. `check-xml`; 23 scanners commit-only; `gitleaks-push` wrapped with `fail_fast`; `pr-validate` appended. Marker commit subject `ALLOW-ROOT-DELETION: .pre-commit-config.yaml — …`. | `cee7748` |
| T4 `scripts/git_push_with_pr.sh` | Clears inherited binding; gate unconditional; second L4 at the push boundary; one refspec with binding; verbatim push-failure text. | `3b10c64` |
| T5 `scripts/make_push_pipeline.sh` | Comment only. | `3b10c64` |
| T6 `tests/test_make_pr_publication.py` | Order, one pr-check / one gitleaks / two L4, binding env and one refspec on push, L4 denial at the boundary, forged inherited binding, push-failure text. | `3b10c64` |
| T7 `tests/test_pre_push_validate.py`, real-gate tests | 28 script tests; 5 real-runner gate tests using the hook definitions from the real config. | `0019ef5`, `669585b`, `f338bf6` |
| T8 docs | AGENTS.md dated correction (additive), CLAUDE.md hook count, `docs/LOCAL_DEV_SETUP.md` hook install step. | `f5ac764` |
| T9 benchmark | Disposable clones, 3 runs per phase, all phases exit 0. Local `make pr` validation 89.54 s → 67.57 s median (−21.97 s, −24.5%); direct push 45.22 s → 72.87 s. Details in `docs/reports/make-pr-validation-consolidation.md`. | this commit |
| T10 publication | `8803dba` via `make pr-nosmoke`; `f338bf6` via `make pr-nosmoke` after `make pr` refused at `install-smoke --resolve` (no readable Odoo Enterprise checkout in the container; branch changes no smoke input). | — |

Operator-authorized change outside the original lock: `.github/workflows/ci.yml` pure-tests install line gains
`pre-commit==4.7.0` (`7e65817`), answering the Codex review finding that the real-runner tests always skipped in CI.

## Validation

| Check | Command | Result |
|---|---|---|
| V1 | `bash -n` + `shellcheck` on the three publication scripts | PASS |
| V2/V7/V8/V9 | `pytest tests/test_make_pr_publication.py tests/test_pre_push_validate.py tests/test_publication_real_push.py tests/test_pr_check_scope.py tests/test_remote_feedback_revision.py tests/contracts/test_no_local_intelligence.py tests/test_repo_dependency_integrity.py` | 153 passed, 0 skipped |
| V3 | `pre-commit validate-config` + pre-push inventory probe | PASS: 39 hooks, 10 at pre-push, exact expected list |
| V4 | `ci.yml` versus `Staging` | One added pin only (operator-authorized) |
| V5 | `ruff check .`, `ruff format --check .`, `pre-commit run --all-files` | PASS (33 commit-stage hooks) |
| V6 | consolidation report | mapping, push-ref matrix, threat model, 3+3 timings |
| V7a | `validate_root_file_protection.py --base origin/Staging --head HEAD` | PASS: AGENTS.md additive, `.pre-commit-config.yaml` justified by marker, CLAUDE.md managed |
| Live | `make pr-nosmoke` publishing `f338bf6` | publisher gate once; pre-push stage ran the 10 new hooks, none of the 23 scanners |

## Review findings

| Finding | Disposition |
|---|---|
| Copilot (medium): skip the real-runner module when `git` is missing too | Fixed in `f338bf6`; thread resolved |
| Codex (P2): real-runner tests always skip in CI | Fixed in `7e65817` (operator-authorized `ci.yml` pin) |

## Deviations and evidence corrections

- Revision 2 said git does not invoke pre-push on an up-to-date push. T1 showed git does invoke it, with no ref
  lines; pre-commit then runs nothing. The conclusion (the hook cannot own the gate) is unchanged.
- `make commit` takes a one-line message, so the `ALLOW-ROOT-DELETION` marker is the whole subject of `cee7748`
  rather than a body line. The root-file gate accepts it; commitizen's changelog will not list that commit.
- The first two benchmark attempts were discarded: wrong ruff / no pytest on PATH, then a harness that compared
  different scopes and re-used tracking refs. Only the corrected third run is reported.
- `workflow_state.md` was not updated: it lists open campaigns only and has no change log.

## Incident and fixes after publication (2026-11-03)

| Event | Detail |
|---|---|
| CI red on `0738308` | Pure Python Tests: 2008 passed, then pytest-cov `DataError` at combine. Once `pre-commit` was installed in CI, the real-runner tests' `pre-commit` and probe subprocesses inherited `COV_CORE_*` and wrote coverage files without this repo's config. Fixed in `0490514` (strip `COV_CORE_*` / `COVERAGE_*`, as `tests/test_make_pr_publication.py::_env` already did). |
| Local direct push corrupted the local repo | A direct `git push` from the linked worktree ran `pr-validate` → `make pr-check` inside the hook. Git runs hooks with an absolute `GIT_DIR` in a linked worktree, so test fixtures calling `git -C <tmp>` acted on the real repository: commits on the branch, `core.bare = true` in the shared config, index replaced. Nothing reached GitHub; `Staging` and the remote branch were untouched. |
| Recovery | Backup ref `refs/l9/incident/pre-push-gitdir-20261103` and a worktree patch captured first. `core.bare` restored. Branch moved back with an operator-authorized `git reset --soft 0490514a` (hard reset is never waived on this surface), index restored with `git restore --staged --source=HEAD -- .`. Worktree files were intact. |
| Root-cause fix | `8cc9f03`: `scripts/pre_push_validate.sh` unsets every `git rev-parse --local-env-vars` variable before `make pr-check`. Regression test `test_pr_check_runs_without_the_hooks_repo_local_git_variables` failed before the fix (nested `git -C <other>` resolved to the hook's repo) and passes after. |
| Why the earlier evidence missed it | The real-runner gate tests stub `make`. `make pr`'s own push is bound, so the hook never ran `make pr-check` during publication. The benchmark clones are plain clones, whose hooks get a relative `GIT_DIR`, so their direct-push timings stand. |
| Publication | `8cc9f03` via `make pr-nosmoke` (operator instruction; `L9_FULL_PYTEST_AUTHORIZED` set with that reason): 2010 passed, 48 skipped; pre-push gate passed. |

## Integration review fixes (2026-11-04)

The four-PR Docker integration run (#355–#358 combined, `85843194`) passed. The independent source review
then found two items on #358:

| Finding | Fix |
|---|---|
| MEDIUM: the hook skipped on the binding variables alone, so a direct `git push` with them set by hand skipped gitleaks and `make pr-check` | The publisher passes its own PID as `L9_PUBLISH_PID` on its push; `scripts/pre_push_validate.sh` honours the binding only when that PID is a live ancestor whose argv[0] or argv[1] is `scripts/git_push_with_pr.sh`, and unreadable ancestry fails closed. The red test (`test_forged_binding_on_a_direct_push_runs_the_full_gate`) failed before the fix and passes after. Two intermediate versions failed on evidence: a substring match accepted an unrelated shell that only mentioned the path (`test_an_ancestor_that_only_names_the_publisher_does_not_count`; a manual run showed the substring version skips and the argv version runs the gate), and an "any publisher ancestor" check let forged tests skip when the suite ran inside `make pr-nosmoke` (5 failed of 2015; `test_publisher_pid_must_name_the_publisher_ancestor`; the modules now pass nested under a publisher-named wrapper). Real-runner tests push through a stand-in publisher outside the repo, and a forged direct push is tested under real git and pre-commit. |
| LOW: the AGENTS.md correction claimed all 23 commit-only scanners run in `ci.yml` | Corrected: all 23 run in `make pr-check` (`make audit`); `constraint-patterns`, `disabled-actions` and `automation-field-refs` are not in `ci.yml`. Not added to `ci.yml` here (outside the authorized change). `INVARIANTS.md` hook count updated (36 → 39). |

Other publication-path findings: `make commit` breaks on an apostrophe in `m=` (single-quoted `MSG`); the
governance push gate parsed a shell redirection `>` as a branch name; a compound command is checked against
the L4 receipt as a whole, so `authorize-release` must run as its own command before `make commit`.

## Rollback

Before merge: close PR #358 and delete `origin/fix/make-pr-single-validation-pass` (human). After merge: a
corrective PR into `Staging` restoring `.pre-commit-config.yaml`, `scripts/git_push_with_pr.sh`,
`scripts/make_push_pipeline.sh`, `tests/test_make_pr_publication.py`, `.github/workflows/ci.yml`, `AGENTS.md`,
`CLAUDE.md` and `docs/LOCAL_DEV_SETUP.md` from `9ee917e`, and deleting `scripts/pre_push_validate.sh`,
`tests/test_pre_push_validate.py`, `tests/test_publication_real_push.py` and the two reports. No force-push, no
`git revert` of foreign commits. Installed hooks need no change.

## Follow-up

Priority D (`pr_check_remote_feedback.py` SHA-first) and Priority E (`apply_pr_kernel_metadata.sh` single label
fetch) remain a separate plan. Measured remote feedback is about 2 s per run, so both are low value. The bound push
still spends about 23 s in hygiene and contract-test hooks.
