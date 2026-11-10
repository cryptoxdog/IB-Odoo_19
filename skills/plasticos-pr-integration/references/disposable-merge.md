<!-- L9_META
schema: 1
parent: plasticos-pr-integration
layer: reference
role: merge-order
version: 1.1.0
status: active
-->

# Disposable merge

Run the fetch in the primary clone. The new worktree shares that object database.

## Bind

```bash
git fetch origin Staging
git rev-parse FETCH_HEAD
```

That SHA is the only `Staging` the worktree may start from. Record it as `<staging-sha>`.

For each selected pull request, fetch its head and refuse a mismatch:

```bash
git fetch origin pull/<n>/head
git rev-parse FETCH_HEAD
git update-ref refs/pr/<n> FETCH_HEAD
```

`FETCH_HEAD` must equal the `headRefOid` recorded from `gh pr list` in this same attempt. The `update-ref` writes a local ref only. Do not push it.

## Which heads merge

Compare every pair with `git merge-base --is-ancestor`.

A tip is a selected head that is not an ancestor of another selected head. Merge tips only, in this order:

1. Tips that contain at least one other selected head as an ancestor, ascending by pull-request number.
2. Remaining tips whose `baseRefName` is `Staging`, ascending by pull-request number.

Do not merge a head that is an ancestor of a tip. Merging the tip already contains those commits.

Stop when a selected head's `baseRefName` is not `Staging` and that head is not an ancestor of a tip. Do not retarget the pull request and do not invent an order for it.

## Worktree

From the primary clone:

```bash
bash .cursor-commands/ops/scripts/worktree_add_wired.sh \
  --detach "$HOME/.l9/pr-integration/cryptoxdog-IB-Odoo_19/<UTC-date>/<UTC-time>-open-prs" \
  <staging-sha>
```

The path must not exist. Do not reuse a previous worktree. Do not run raw `git worktree add`.

Immediately after creation, `git status --porcelain` must be empty. Record `git rev-parse HEAD` and confirm it equals `<staging-sha>`.

## Merge

Inside the worktree, for each tip, with a clean status:

```bash
git -c user.name='L9 Integration' -c user.email='integration@example.invalid' \
  merge --no-ff --no-edit refs/pr/<n>
```

Do not change git config. On a conflict, stop and list the unmerged paths. Do not edit the conflict.

When the merge succeeds, compare trees:

```bash
git rev-parse 'HEAD^{tree}' 'HEAD^1^{tree}'
```

Equal trees mean the tip's patch was already in the first parent. Record an empty merge. The combined result is still `HEAD`.

Do not push the worktree. Do not update the source pull-request branches.

The changed path list for later steps is:

```bash
git diff --name-only <staging-sha> HEAD
```
