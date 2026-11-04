> **OPERATIVE CONTRACT, v2.4.0:** Test #301 and #303 as they would run after a clean merge into current `Staging`, on the existing Enterprise Docker fixture. Test each merge alone, then test both merges together. Save the findings under `docs/reports/evidence/` so the operator can remediate the PRs before merging them. Do not patch product code, do not push, and do not resolve a merge conflict.

# Pre-merge Enterprise test of PR #301 and PR #303

**Version:** 2.4.0 (2026-10-24). **Status:** the execution contract. v2.3.1's isolated-head handoff is retired. The directory name still says v2.3.1; the version in this file is the one that governs.

## Operator intent

The question is how the open import PRs behave once they are on current `Staging`, inside the admitted Odoo 19 Enterprise fixture. The answer has to exist before those PRs are merged, so the operator can change the branches on purpose.

That requires three trees, each in its own detached worktree:

| Tree | What it is | Why this tree |
|---|---|---|
| M301 | Current `Staging` merged with PR #301 | #301's branch tip does not contain current `Staging`. The tip is not the post-merge tree. |
| M303 | PR #303's head | At the v2.4.0 snapshot this head already contains current `Staging`, so the head tree and the merge tree are the same. Re-check that before the run. |
| BOTH | M301 merged with #303 | This is the tree the operator would get by merging both PRs. A green result on M301 and on M303 does not answer it. |

Build each tree with `git merge-tree`. If the merge is clean, check it out with `bash "$HOME/.cursor-governance/ops/scripts/worktree_add_wired.sh" --detach`. If the merge conflicts, stop that lane and write the conflict as the finding. Do not hand-edit the resolution. The local merge commit is a test object. Do not push it, do not move the operator's branch, and do not open or merge a GitHub PR.

## What a run is allowed to do

| Allowed | Not allowed |
|---|---|
| Fetch PR heads and `Staging`. Build the three merge trees in detached worktrees. | Patch, commit, or push product code, tests, manifests, or the PRs |
| Run the catalog's existing pure tests and `make test-module` on owned clones of the pinned Enterprise template | Create, adopt, rebuild, or re-stamp a template. Use Community. Run `make test-odoo` or logistics/Linda tests |
| Write findings to `docs/reports/evidence/pr301-pr303-premerge-enterprise-<date>/` | Treat a module-green receipt as a live ERP or VanillaSoft import |
| Drop only the clone this run created, after the receipt is copied | Drop the template, another owner's clone, or a business database |

`scripts/test_env.sh status` may run a quiet image build. Continue only when the pinned template is still `ready` and its fingerprint still matches. Record an image-ID change. Stop if the template stops being the admitted ready fixture.

## One behavior-ID list

`BEHAVIOR_CATALOG.csv` is the only ID list. Score `S-01` through `S-14`, `301-A` through `301-I`, `303-A` through `303-G`, and the `303-DIAG-*` rows. The v2.3.1 matrix used the same `301-*` letters for different claims. Those matrix letters are retired. The crosswalk is in `02_PR_BEHAVIOR_MATRIX.md`.

## What the published #303 handoff is

`10_PR303_PUBLISHED_HANDOFF_ACCEPTANCE.md` keeps the Community failure inventory as background. It does not decide which tree to test, and it does not forbid the combined merge run. Enterprise results on M303 and BOTH replace that inventory where the same method actually ran. A Community failure that this run did not execute stays `REPORTED_CE_NOT_ENTERPRISE_VERIFIED`.

## Reading order

1. This file.
2. `07_EXACT_PREFLIGHT_AND_RUN_COMMANDS.md` for the merge-tree and fixture commands.
3. `02_PR_BEHAVIOR_MATRIX.md` and `BEHAVIOR_CATALOG.csv` for what to score.
4. `03_EXECUTION_SEQUENCE.md` for the order of commands.
5. `08_EVIDENCE_AND_APPROVAL_PACKET.md` and `04_FINDINGS_AND_APPROVAL.md` for the report shape.
6. `06_FINAL_COHESION_GATE.md` for the BOTH tree. It runs in this campaign.
7. `09_SCOPE_AND_LIMITATIONS.md` for logistics and live-import limits.
8. `10_PR303_PUBLISHED_HANDOFF_ACCEPTANCE.md` only as the Community background for #303.

## Snapshot this version was aligned to

Re-resolve every SHA before a new run. On 2026-10-24:

| Coordinate | Value |
|---|---|
| `Staging` | `2a3b9cda9b127c284d12f98bf35ab0344a500d10` |
| PR #301 head | `cc3f8cbb90d7f57c58de75af9d893d8ac2ed4c79` (open, mergeable, does not contain `Staging`) |
| M301 commit | `b91937fb26020d097391cb142fce35e9c8434cd2` (tree `187b69b8fbaa0add60089e5e4b783cbc85d853fa`) |
| PR #303 head = M303 | `190c497bdea1362cad87e231c713efdcd25240d4` (tree equals the merge onto `Staging`) |
| BOTH commit | `1606626ee845e1eb64a525cb0c39fc8140de9db3` (tree `203986bc9553955ee86e7c683ae4a563b900dafb`) |
| Fixture | `odoo_test_tpl_ee_c9e8a81f52f23680`, ready, parity `ee` |

#301's merge onto `Staging` differs from #301's tip by the already-merged PR #300 Linda BRS documents. #303's executable baseline remains `702ebaf77d987dc844e2758bd354b2ecef4f26cd`; the later commit adds five handoff documents. The only path both PRs change is `plasticos_transaction/__manifest__.py`, and those blobs are identical (`19.0.2.3.40`). The combined tree is a clean union. Runtime interaction is still unproven until BOTH is tested, because the PRs change different files in the same module.
