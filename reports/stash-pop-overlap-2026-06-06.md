# Stash pop overlap log — 2026-06-06

**Branch at pop:** `fix/python39-compat-cron-scripts`  
**Stash:** `stash@{0}` — `wip-staging-before-merge-pr95` (from `feat/material-profile-intake-delta-bridge`)

## Overlap (same paths in stash + uncommitted working tree)

| File | Uncommitted (preserve) | Stash (WIP) |
|------|------------------------|-------------|
| `Makefile` | `.cursor-commands` commit/push exclusion (`COMMIT_EXCLUDE`, guarded `make commit`/`make push`) | `pr-check-%`, `governance-backup`, remote PR feedback targets, other Makefile kernel updates |
| `AGENTS.md` | Git workflow bullet: omit `.cursor-commands` on `make commit`/`make push` | ADR index table, skill registry refresh (L9/plasticos names), `make push` command docs, ADR link fixes |

## No overlap (uncommitted only)

| File | Change |
|------|--------|
| `.gitignore` | Ignore `.cursor-commands` symlink |

## Stash-only paths (46 files total)

- `.claude/README.md`, `.claude/agents/*`, `.claude/skills/*` (moves/deletes/updates)
- `.cursor/rules/*.mdc` (master context, audit kernels, github push rule, etc.)

## Recovery

Preserved uncommitted overlap via `/tmp/overlap-preserve.patch` (git diff of `.gitignore`, `Makefile`, `AGENTS.md` before pop), applied after `git stash pop`.

### Resolution (completed)

| File | Action |
|------|--------|
| `Makefile` | Merged stash (`PR_REMOTE_REF`, `pr-check-%`, `governance-backup`) + upstream push help + **re-applied** `COMMIT_EXCLUDE` guard |
| `AGENTS.md` | Kept stash ADR/skill registry + pr-check docs (updated push wording) + **re-applied** `.cursor-commands` omit bullet |
| `.gitignore` | **Re-applied** `.cursor-commands` ignore |
| `.cursor/rules/70-github-api-commit.mdc` | Merged: current `make push` flow + `.cursor-commands` omit note on `make commit` |

Stash dropped. Untracked paths from stash (`.claude/adapters/`, `.claude/skills/plasticos-*`, `.cursor/rules/01-*`, `scripts/pr_check*.py`, etc.) remain for a separate commit.
