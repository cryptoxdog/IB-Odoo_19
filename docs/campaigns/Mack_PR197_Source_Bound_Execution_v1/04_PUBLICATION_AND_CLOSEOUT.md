# Publication hold and closure receipt | PR #197

## Hard fact: two different publisher generations

Current default `Staging` at `3c249...` implements repo-owned `make pr`, no `make push`. Mack `7dcada4...` and its actual `Development` base at `3318fa6...` have Makefile blob `2d72...` implementing **only legacy `make push`**, plus an API fallback. An execution pack cannot magically use modern `make pr` against that old checkout. DO NOT call `make push`, `make api-push-check`, raw `git push`, or an ad hoc API patch as a workaround. Bringing the whole Staging publication system into Mack is not part of this bounded defect repair. The owner must resolve/authorize a suitable publication route for the Development/Mack topology as a separately evidenced dependency.

**Operator comment on PR #197:** `DO NOT MERGE` (2026-09-30). It was live when this pack was prepared and must remain in force until an explicit separate revocation/merge authorization for an exact future SHA. “GitHub says mergeable” is not permission. Do not enable auto-merge. Do not retarget to Staging, Development's Production-equivalent branch, or merge anything under this pack.

## What can be closed locally

- Four-file source-bound patch prepared/applied in the existing `mack` branch, *without* publication. Do not create a replacement PR.
- Two Codex defects locally fixed with native test discrimination.
- Material Odoo tests and real two-session runtime gates evidenced on a separately verified clone.
- No unrelated commits/changes to the PR, no stale blob reuse, no new semantics.

## What remains outside this pack

- Authorizing and executing remote branch update through a **verified** suitable publication mechanism (Mack's old Makefile is not it).
- Resolving the two review threads *after* the fixed code reaches the exact PR head and reviewers can re-evaluate.
- Approval to merge #197: **explicitly prohibited now**. No merge scheduling.
- Any integration of Mack onto modern `Staging`, upgrade of `Development` publisher plumbing, or deployment/Production advancement: distinct authorization and separate scope.

## Operator receipt template

| Item | Status | SHA + artifact/log | Disposition / blocker |
|---|---|---|---|
| Frozen PR source & branch verified | UNKNOWN | | |
| F1 helper import fixed locally | UNKNOWN | | |
| F2 hash bytes validated | UNKNOWN | | |
| Module version bumped to `19.0.1.1.1` | UNKNOWN | | |
| Target repo `make pr-check` | UNKNOWN | | |
| Odoo fresh install & scoped upgrade | UNKNOWN | | |
| Registered native Odoo tests | UNKNOWN | | |
| Gate M1 / M2 | UNKNOWN | | |
| Gate I1 / I2 | UNKNOWN | | |
| In-app-only notification | UNKNOWN | | |
| GitHub review threads current | 2 OPEN at frozen SHA | [#197](https://github.com/cryptoxdog/IB-Odoo_19/pull/197) | Refresh if new head |
| Publication | BLOCKED | Mack source Makefile lacks `make pr` | Separately authorize native route |
| Merge | BLOCKED | Operator says DO NOT MERGE | Do not merge |

State `PASS` only for an exact observed command and revision, and `UNKNOWN` for unavailable evidence. Re-run against a changed head. Report blockers and stop, rather than silently moving the target branch.
