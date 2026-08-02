# Session context: CI config drift cleanup (this agent's thread)

**Session:** 2026-07-24T18:18:00Z
**Repo:** /Users/macm2/Library/CloudStorage/Dropbox/Repo_Dropbox_IB/IB-Odoo_19-1
**Branch:** docs/agent-docs-refresh-and-repo-index

> This is a **secondary, thread-scoped** context file. `activeContext.md` is the
> shared "where we left off" file other agents/sessions also write to — do not
> overwrite it. This file tracks only this thread's plan + todos.

## Session Summary

Audited `pyproject.toml` / `tests/conftest.py` / CI workflow templates for
config drift, then drafted and re-verified an "evidence-backed execution plan
kernel" plan covering 3 confirmed low-severity doc/config drift findings:

- Unpinned semgrep in `l9-analysis.yml` (vs. `1.164.0` pinned in
  `Makefile`/`ci.yml`)
- Dangling `baseline-ratchet.yml` references in 3 files (that workflow does
  not exist on disk)
- Stale `security.yml` docs in `AGENTS.md` (described as active; file on disk
  is a `workflow_dispatch`-only tombstone)

`pyproject.toml`/`conftest.py` were audited clean and are explicitly excluded
from the plan. Doc/config-only, zero behavior change. Re-verified against
current disk state — all findings, line numbers, and before/after text blocks
still match exactly. No plan content changed.

Graphiti VPS unreachable this session (per user) — used memory-bank (T0)
directly; no Graphiti/Redis MCP tools available in this session's tool list,
so no T1 episode was written.

## Plan

`memory-bank/ci_config_drift_cleanup_0490fa7d.plan.md` — Ready, not yet
executed. 4 plan items, Wave 1 (PI-01/02/03) parallel + Wave 2 (PI-04)
verification sweep.

## Todos (this thread)

- [ ] PI-01 — `l9-analysis.yml`: pin `semgrep==1.164.0` (line 89) + remove
      dangling `baseline-ratchet.yml` reference from `L9_CORE_REF` comment
      (lines 25-27)
- [ ] PI-02 — `governance/README.md`: remove dangling `baseline-ratchet.yml`
      reference (lines 37-40)
- [ ] PI-03 — `AGENTS.md`: remove `baseline-ratchet.yml` row (line 292),
      rewrite `security.yml` row as tombstone (line 293), remove
      `dependency-scan`/`trivy-scan` advisory rows (lines 320-321)
- [ ] PI-04 — verification grep sweep (`baseline-ratchet`, semgrep pin,
      `dependency-scan`/`trivy-scan`) and confirm `AGENTS.md` workflow table
      row count = 9

**Next action:** Get explicit user approval to leave plan mode and execute
Wave 1 (PI-01/02/03) then Wave 2 (PI-04), per
`ci_config_drift_cleanup_0490fa7d.plan.md`.
