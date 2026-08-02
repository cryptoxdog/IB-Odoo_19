# Progress this sprint

- 2026-07-24: PR #116 — fail-slow `ci.yml` restoring unique checks from the 4
  deleted legacy workflows (mypy, shellcheck, manifest/ACL validation,
  audit-baseline regression, `_name` string-literal enforcement, test-attribute
  guard) + adopted `l9-ci-core` governed Semgrep pipeline (`l9-analysis.yml`,
  advisory-first) + `Makefile`/`AGENTS.md` parity updates. Followed up with two
  small fixes in the same PR: SQL-justification allowlist (3 files) and
  `l9-analysis.yml` publish-job profile threading bug. PR open, mergeable,
  awaiting CI + user merge approval.
- 2026-07-24: PR #117 — committed the 24 files that were untracked/local-only
  (repo-index generator + `.txt` output, `repo-index.yml` workflow, editor
  bootstrap `.vscode/extensions.json` + `install_editor_extensions.sh`,
  `odools.toml`, `plasticos-prompt-pack` skill, one cursor brief) so a fresh
  clone reproduces the same working environment. Built in an isolated worktree
  off fresh `origin/Staging` to avoid dragging in this checkout's unrelated
  uncommitted diff. Verified none of the files are gitignored before
  committing. CI passing; awaiting user merge approval.
- 2026-07-24: Audited `pyproject.toml` / `tests/conftest.py` / CI workflow
  templates for config drift, then drafted and re-verified an "evidence-backed
  execution plan kernel" plan (`memory-bank/ci_config_drift_cleanup_0490fa7d.plan.md`)
  covering 3 confirmed low-severity doc/config drift findings: unpinned
  semgrep in `l9-analysis.yml` (vs. `1.164.0` pinned in `Makefile`/`ci.yml`),
  dangling `baseline-ratchet.yml` references in 3 files (that workflow does
  not exist — 9 files confirmed on disk), and stale `security.yml` docs in
  `AGENTS.md` (described as active; file on disk is a `workflow_dispatch`-only
  tombstone).   `pyproject.toml`/`conftest.py` audited clean, explicitly
  excluded from the plan. Doc/config-only, zero behavior change. Plan is
  Ready; no edits applied yet — plan mode only this session.
- 2026-07-24: Made `memory-bank/` (T0 resume state) trackable in this repo —
  it was silently dropped by this machine's global `~/.gitignore_global`, not
  this repo's own `.gitignore`. Added a repo-local negation so a fresh clone
  gets the same resume context. Verified it cannot affect Odoo module loading
  or the `plasticos_*`-scoped CI/wiring checks before pushing. Pushed via an
  isolated worktree/branch off fresh `origin/Staging` (see tasks.md for the
  PR number) rather than the stale/diverged local branch, to keep it
  unblocked by the branch-divergence tech debt below.
