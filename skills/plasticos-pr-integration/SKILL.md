---
name: plasticos-pr-integration
description: >
  Combine named or all open pull requests of this PlasticOS repository into a
  new disposable worktree and prove that tree on the pinned Odoo 19 Enterprise
  fixture. Use when asked to integration-test open pull requests, merge several
  PRs and run full smoke, or load a combined Staging tree with the admitted
  module roster. Do not use for the checkout already open, an Odoo.sh deploy,
  a template rebuild, or editing the governance integration-testing pack.
disable-model-invocation: false
metadata:
  skill_schema: 1
  layer: control_plane
  role: skill_entrypoint
  tags: [plasticos, odoo, docker, enterprise, pull-request, install-smoke]
  owner: plasticos
  status: active
  version: "1.1.0"
  updated: "2026-11-10"
  topology_scan: EXTEND_EXISTING
  topology_nearest: plasticos-odoo-docker-testing
  topology_judgment: CREATE_NEW
  topology_reason: >
    plasticos-odoo-docker-testing proves the checkout already open. This pack
    proves a merged set of pull-request heads. The governance integration pack
    is not the runner and is not edited.
---

# PlasticOS pull-request integration

## Purpose

Merge exact pull-request heads onto current `Staging` in a new disposable worktree, then load that tree on the pinned Odoo 19 Enterprise fixture. Full smoke is `make install-smoke` from that worktree. `plasticos-odoo-docker-testing` stays the load gate for the checkout already open.

## Authority

1. Pull requests the operator named. When none are named, every open pull request whose base repository is `cryptoxdog/IB-Odoo_19`.
2. The head SHA just fetched. A title, a review, or a green check does not order or approve a merge.
3. `config/test_env_fixture.conf` and `scripts/test_env.sh`. That template is the only database.
4. `scripts/install_smoke.sh`, invoked only as `make install-smoke`.
5. The roster printed by `scripts/get_odoo_module_order.py` on the merged tree.

## Procedure

Do this in the primary clone's object database, then only inside the new worktree. Do not commit, push, publish, or deploy. Do not edit the Cursor-Governance checkout. Do not change the operator's branch.

1. **Bind.** Record `number`, `baseRefName`, `baseRefOid`, and `headRefOid` from `gh pr list`. Fetch each head and stop if the fetched SHA differs from `headRefOid`. Commands: [disposable-merge.md](references/disposable-merge.md).
2. **Order.** Merge only tips, in the order that file defines. A head that is an ancestor of a tip is already included. A head whose base is not `Staging` and that is not an ancestor of a tip stops the run. Do not retarget a pull request.
3. **Worktree.** Create it with `.cursor-commands/ops/scripts/worktree_add_wired.sh --detach` at a path that does not exist, from the `origin/Staging` SHA just fetched. Stop if `git status --porcelain` is not empty before the first merge.
4. **Merge.** One `--no-ff` merge per tip, author set with `git -c`, not `git config`. A conflict stops the run; list the files and do not resolve them. When the merge commit's tree equals its first parent, record an empty merge and continue.
5. **Enterprise.** In that same shell, export `ODOO_ENTERPRISE_PATH` when the worktree has no Enterprise checkout, then follow [enterprise-smoke.md](references/enterprise-smoke.md). `scripts/test_env.sh status` must show parity `ee` and the pinned template `ready` at this worktree's fingerprint. Otherwise stop. Do not set `TEST_ENV_ALLOW_NEW_TEMPLATE` and do not rebuild the template.
6. **Full smoke.** `make install-smoke`, attached, alone. The wait is at least 600000 ms and longer than the command. A wait of 0 kills the command when the shell is backgrounded.
7. **Changed-module tests.** From `git diff --name-only <staging-sha> HEAD`, keep `plasticos_*` directories that contain a tests package and are printed by `scripts/get_odoo_module_order.py`. If that list is empty, runtime is not applicable and smoke still is. If the diff adds a tests package for a module the roster does not print, stop. Otherwise `make runtime-test m=<comma-separated list>` with no spaces, attached, after smoke has exited.
8. **Changed pure-Python tests.** Files under the repository tests directory named `test_*.py` that the same diff touches, run with the primary clone's `.venv/bin/python -m pytest` and the worktree as the working directory. If that interpreter is absent, record the tests as not run. Do not substitute another pytest.

## Pass

| Gate | Pass | Not a pass |
|---|---|---|
| Smoke | Exit 0 and this worktree printed `install-smoke PASSED`, or exit 0 and it printed `install-smoke evidence matches; not upgrading` | A receipt file from another checkout, a skipped upgrade you did not just recheck, any module not installed |
| Runtime | Receipt `tests` greater than 0, `failed` 0, `errors` 0 | An empty module list, or `make runtime-test` with no `m=` |
| Pytest | The selected files passed under the primary `.venv` | A pass used in place of smoke |

Report the bound `Staging` SHA, each head SHA, the combined SHA, the worktree path, the smoke database (`odoo_test_smoke_` plus this worktree's owner), the template name, and the fingerprint. Publish only if the operator asks after smoke has passed.

## Stop

| Condition | What to report |
|---|---|
| Fetched head differs from `headRefOid` | Both SHAs. Do not test the moved branch. |
| Base is not `Staging` and the head is not an ancestor of a tip | The pull-request number and base ref. |
| Merge conflict | The conflicted paths. |
| Worktree path already exists, or the new worktree is dirty before the merge | The path and `git status --porcelain`. |
| Docker is down, Enterprise is unreadable, or parity is not `ee` | The status line. Do not use Community or another database. |
| Template is not `ready` for this fingerprint | The `input` lines from status. Do not rebuild. |
| `install-smoke refused: lock busy` | The compose project is already in use. Do not delete the lock. |
| Smoke or runtime exits non-zero | The failing module or the Odoo summary line. |
| A changed module has a tests package and is absent from the roster | The module name. Do not drop it from `m=` to obtain a pass. |
