# Tech debt — revisit later

- **Branch divergence:** Main Dropbox checkout's `docs/agent-docs-refresh-and-repo-index`
  branch is far behind `origin/Staging` with a large uncommitted diff (deleted
  `.cursor/rules/*.mdc`, deleted `docs/README_plasticos_*.md`, modified `ci.yml`/
  `AGENTS.md`/`ARCHITECTURE.md`/`Makefile`, new `repo-index.yml`, etc). Not
  evaluated or touched as of 2026-07-24 — needs explicit user triage: rebase,
  discard, or cherry-pick relevant pieces onto current Staging.
- **`make push`'s remote-feedback check is circular for same-PR follow-up fixes:**
  when a fix for a codex-flagged bug is committed locally but not yet pushed,
  `pr-remote-feedback` still sees the stale (pre-fix) comment and blocks, because
  it queries GitHub state before `git push` runs. Currently worked around with
  `PR_CHECK_SKIP_REMOTE=1` after independently verifying the fix locally — but
  this has now happened twice on PR #116. Consider teaching `pr_autopilot.py` to
  diff the comment's anchor commit against local HEAD and downgrade
  already-fixed-locally findings to advisory instead of REAL_BUG.
- **Audit baselines carry pre-existing debt, not zero:** `odoo_audit.py` baseline
  is 444 CRITICAL / 1 HIGH (documented false positives: `ir.ui.view`/
  `ir.actions.*` structural fields, cross-module `_inherit` fields).
  `run_all_audits.py` baseline is 15 HIGH (9 N+1 queries + 6 sensitive-data-log
  false positives). Both are tracked/gated against regression, not resolved.
- **`activeContext.md` was overwritten instead of appended:** between the
  2026-07-24T18:12:00Z session and 2026-07-24T18:23:03Z session, the file's
  detailed "where we left off" content (PR #116/#117 status, blockers, next
  actions) was replaced with a generic templated stub ("No summary provided" /
  "update manually or via end-session command"). If an automated end-session
  hook is generating that stub, it needs to append a new dated section (like
  `tasks.md`/`progress.md` already do) instead of truncating the file. Detail
  was reconstructed this session from `tasks.md`/`progress.md` and re-appended
  to `activeContext.md`, but future sessions should check whether the hook
  itself needs a fix.
