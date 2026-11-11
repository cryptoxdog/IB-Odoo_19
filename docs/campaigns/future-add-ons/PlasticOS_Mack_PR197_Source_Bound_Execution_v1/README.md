# Mack PR #197 | source-bound execution pack v1

**Mission:** close the two CURRENT code-review defects and produce Mack-specific Odoo 19 runtime proof for [#197](https://github.com/cryptoxdog/IB-Odoo_19/pull/197). **No merge.** No production or Staging mutation. No other PR/issue campaign.

**Binding:** `cryptoxdog/IB-Odoo_19`, branch `mack`, head `7dcada49fd301d3b5dafb30405d0242667915fbe`, target `Development` at `3318fa646a9f33aed55b9ea8f8596316e30684da`. All values were verified from GitHub on 2026-10-15. Recheck them at execution; head drift blocks this patch rather than silently rebasing.

**Critical human hold:** PR #197 has an explicit top-level comment `DO NOT MERGE`. No chat authorizes lifting it. The branch's Makefile is old and provides `make push` but no `make pr`; the modern Staging publication ceremony cannot be assumed to exist on `mack`. Do not use the old push/API fallback, retarget to Staging, or claim the branch is publish-ready. Prepare a validated local Mack commit and request the separately approved Odoo-appropriate publication route. Merge remains prohibited until a new express operator grant.

## Files

- `00_OPERATOR_CARD.md`: command and scope summary.
- `01_LIVE_EVIDENCE.md`: exact current code and review facts, confirmed vs unproven.
- `02_CURSOR_EXECUTION_CONTRACT.md`: complete Mack-only code/test handoff.
- `03_RUNTIME_ACCEPTANCE.md`: native tests and two real multi-session concurrency gates.
- `04_PUBLICATION_AND_CLOSEOUT.md`: exact-host controls, forbidden old ceremony, evidence receipt.
- `scripts/build_repair.py`: strict SHA + git blob bound generator. By default only writes a patch outside checkout and runs `git apply --check`. `--apply` changes only four Mack-owned local paths.
- `tests/test_builder.py`: offline structural and negative checks, deliberately no GitHub/Odoo claims.
- `manifest.sha256`: bundle integrity.

## Usage

On an isolated clean checkout of the EXACT PR head, invoke:

```bash
python3 scripts/build_repair.py --repo /absolute/path/to/mack-worktree --output /tmp/mack-197-repair.patch
```

The script and tests above refer to the **pack's** `scripts/` and `tests/` directories, not a script already installed in the repository. To apply after reviewing the diff:

```bash
python3 scripts/build_repair.py --repo /absolute/path/to/mack-worktree --output /tmp/mack-197-repair.patch --apply
```

Do not run against the newer `Staging` tree; it has different module code, helpers and Makefile. See the execution contract for exact validation and stopping points. The `--apply` flag does not commit, publish, comment, or merge.

## Completion vocabulary

`PATCH_PREPARED`: exact-head `git apply --check` passed. `LOCAL_REPAIRED`: patch applied in the bounded checkout. `RUNTIME_PROVED`: native module tests and real concurrency gates passed on an approved disposable Odoo/Postgres environment, no required skip. `PR_UPDATED`: separately authorized approved publication recorded against a new SHA. `MERGE_HOLD`: ALWAYS, given the explicit DO NOT MERGE comment. Never equate passing offline builder tests with any later state.
