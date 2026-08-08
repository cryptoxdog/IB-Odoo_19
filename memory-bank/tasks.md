# Queued work

## OPEN — Track B external intelligence (not fully executed)

**Status:** Partial. Odoo Track A client exists; M0/`TASK-046` proved
`LIVE_TRANSPORT_ROUNDTRIP_PASS` only — **not** full `LIVE_INTEGRATION_PASS`.
Local matcher/enrichment engines retired (M7); Gate path must be live or
match/enrich fail closed.

**Load these files first (execution pack):**

| Order | File | Role |
|------:|------|------|
| 0 | [`docs/track_b/00_AGENT_HANDOFF.md`](../docs/track_b/00_AGENT_HANDOFF.md) | Master brief + wire contract + DoD |
| 1 | [`docs/track_b/01_constellation_gate_node.md`](../docs/track_b/01_constellation_gate_node.md) | Build Gate hub first |
| 2 | [`docs/track_b/02_cognitive_engine_graphs.md`](../docs/track_b/02_cognitive_engine_graphs.md) | CEG `action=match` |
| 3 | [`docs/track_b/03_enrichment_inference_engine.md`](../docs/track_b/03_enrichment_inference_engine.md) | EIE `action=converge` |
| 4 | [`docs/track_b/04_odoo_gate_consumer_wiring.md`](../docs/track_b/04_odoo_gate_consumer_wiring.md) | Odoo consumer adapts to Gate_SDK |
| 5 | [`docs/track_b/05_external_authority_readiness.md`](../docs/track_b/05_external_authority_readiness.md) | Readiness / live e2e proof |

**Authority:** [`docs/adr/ADR-002-gate-hub-phased-autonomy.md`](../docs/adr/ADR-002-gate-hub-phased-autonomy.md),
[`docs/adr/ADR-003-single-external-intelligence-authority.md`](../docs/adr/ADR-003-single-external-intelligence-authority.md),
[`docs/GATE_AUTONOMY_ROADMAP.md`](../docs/GATE_AUTONOMY_ROADMAP.md).

- [ ] Execute Track B pack to DoD in `00_AGENT_HANDOFF.md` §5 (Gate → CEG match → EIE converge)
- [ ] Prove live five-service stack via `docs/track_b/05_external_authority_readiness.md` (`LIVE_INTEGRATION_PASS`)
- [ ] Set staging `plasticos.gate.url` and verify `match_source` / `engine_used` == `gate`

---
## Session 2026-07-22T04:23:40Z
No summary.

---
## Session 2026-07-22T04:28:40Z
No summary.

---
## Session 2026-07-22T19:19:16Z
No summary.

---
## Session 2026-07-23T00:54:04Z
No summary.

---
## Session 2026-07-23T01:26:26Z
No summary.

---
## Session 2026-07-23T16:11:57Z
No summary.

---
## Session 2026-07-23T16:22:28Z
No summary.

---
## Session 2026-07-23T16:24:45Z
No summary.

---
## Session 2026-07-23T16:24:45Z
No summary.

---
## Session 2026-07-23T16:25:32Z
No summary.

---
## Session 2026-07-23T16:26:13Z
No summary.

---
## Session 2026-07-23T16:26:18Z
No summary.

---
## Session 2026-07-23T16:26:20Z
No summary.

---
## Session 2026-07-24T18:00:48Z
No summary.

---
## Session 2026-07-24T18:20:00Z (worktree ~/dev/IB-Odoo_19-ci-fail-slow, PR #116)
- [x] Fix `SQL without justification` UserWarning (3 files added to `_SQL_JUSTIFIED_FILES`)
- [x] Fix `l9-analysis.yml` publish job hardcoded `profile: pr_fast` (real bug via codex review)
- [x] Push both fixes to PR #116 (`fix/ci-fail-slow-and-restore-audits`)
- [ ] Monitor PR #116 CI to green, then merge (needs explicit user approval)
- [ ] Triage `docs/agent-docs-refresh-and-repo-index` branch divergence in main
      Dropbox checkout — large uncommitted diff, not evaluated this session,
      needs explicit user direction before any action

---
## Session 2026-07-24T18:12:00Z (this Dropbox checkout, PR #117)
- [x] Identified exact set of untracked-only-on-this-machine files (matches
      the conversation's original `git_status` snapshot: repo-index `.txt`
      files, `repo-index.yml`, `.vscode/extensions.json`,
      `export_repo_indexes.py`, `install_editor_extensions.sh`, `odools.toml`,
      `plasticos-prompt-pack/SKILL.md`, one `docs/cursor-briefs/*.md`)
- [x] Verified none gitignored (`git check-ignore -v`)
- [x] Built isolated worktree off fresh `origin/Staging`
      (`~/dev/IB-Odoo_19-repo-index-tooling`) — did not touch this checkout's
      unrelated uncommitted diff or switch its branch
- [x] Committed + pushed `chore/repo-index-and-dev-tooling` → PR #117
- [ ] Monitor PR #117 CI to green, then merge (needs explicit user approval)
- [ ] Graphiti VPS unreachable — used memory-bank (T0) directly per explicit
      user instruction this session; retry Graphiti health check next session

---
## Session 2026-07-24T18:14:58Z
No summary.

---
## Session 2026-07-24T18:15:02Z
No summary.

---
## Session 2026-07-24T18:15:09Z
No summary.

---
## Session 2026-07-24T18:18:00Z
- [x] Re-verified "CI Config Drift Cleanup" plan against current disk state —
      all 3 findings (unpinned semgrep, dangling `baseline-ratchet.yml` refs,
      stale `security.yml` docs) confirmed still accurate; zero plan content
      changed
- [x] Re-filed plan as `ci_config_drift_cleanup_0490fa7d.plan.md`; user
      copied it into `memory-bank/` for tracking
- [ ] Execute Wave 1 (PI-01 `l9-analysis.yml`, PI-02 `governance/README.md`,
      PI-03 `AGENTS.md`) then Wave 2 (PI-04 verification sweep) — needs
      explicit user approval to leave plan mode and edit
- [ ] Graphiti VPS unreachable this session (per user); no Graphiti/Redis MCP
      tools available — used memory-bank (T0) directly, no T1 episode written

---
## Session 2026-07-24T18:23:03Z
No summary.

---
## Session 2026-07-24T18:26:00Z (this Dropbox checkout — memory-bank tracking pass)
- [x] Re-read all memory-bank files fresh after concurrent agent finished writing
      (avoided clobbering the CI-config-drift-cleanup thread's updates to
      `tasks.md`/`progress.md`/`ci_config_drift_cleanup_0490fa7d.plan.md`)
- [x] Noted `activeContext.md`'s detailed content had been overwritten with a
      generic templated stub by an automated end-session pass — appended a
      consolidated-status section restoring the lost detail (see tech-debt.md
      for the root-cause note re: append-vs-overwrite in the hook)
- [x] Added repo-local `.gitignore` negation (`!/memory-bank/`, `!/memory-bank/**`)
      to override this machine's global `~/.gitignore_global` exclusion, scoped to
      this repo only
- [x] Verified `memory-bank/` at repo root cannot break Odoo module loading or the
      `plasticos_*`-scoped CI wiring checks (no `__manifest__.py`/`__init__.py`,
      both scanners filter by `plasticos_*` first path segment)
- [ ] Push `memory-bank/` + `.gitignore` negation via an isolated worktree/branch
      off fresh `origin/Staging` (same pattern as PR #116/#117) — open PR
- [ ] Monitor PR #116 and PR #117 CI to green, then merge (needs explicit user
      approval for both)
