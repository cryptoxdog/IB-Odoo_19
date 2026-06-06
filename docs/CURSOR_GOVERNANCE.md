# Cursor Governance (PlasticOS)

**Law:** `@.cursor/governance/CANONICAL_LAW.md`

## One GlobalCommands entry

| Asset | Path |
|-------|------|
| **GlobalCommands (all)** | `@.cursor-commands/` |
| L9 skills | `@.cursor-commands/skills/l9-*/` |
| Slash commands | `@.cursor-commands/commands/` |
| Global rules | `@.cursor-commands/rules/` |
| Setup / validate | `.cursor-commands/ops/scripts/` |

**Not** under `.cursor/governance/` — that folder is local-only (law symlink + README).

## Repo symlinks

| Link | Target |
|------|--------|
| `.cursor-commands` | Dropbox `GlobalCommands/` |
| `.cursor/governance/CANONICAL_LAW.md` | Dropbox `CANONICAL_LAW.md` |

## GitHub backup (never lose governance)

| Item | Detail |
|------|--------|
| SSOT | Dropbox `$HOME/Dropbox/cursor governance/GlobalCommands/` |
| Backup repo | [cryptoxdog/Cursor-Governance](https://github.com/cryptoxdog/Cursor-Governance) |
| Git root | Same as GlobalCommands (what `.cursor-commands` points at) |

**Manual push:**

```bash
make governance-backup
# or: bash .cursor-commands/ops/scripts/backup_to_github.sh
# or: /governance-backup
```

**Automatic (session end):** after one-time setup, Cursor runs `sessionEnd` hook → backup script. Log: `~/.cursor-governance/backup.log`.

## Forbidden

- `.cursor/governance` → Dropbox root (duplicates GlobalCommands in sidebar)
- `.cursor/governance/GlobalCommands/`
- `.cursor/commands`, `.cursor/skills`

## Setup (once per machine + each new clone)

```bash
bash .cursor-commands/ops/scripts/setup_workspace_symlinks.sh   # symlinks + sessionEnd hook
bash scripts/validate_l9_skill_wiring.sh
bash .cursor-commands/ops/scripts/backup_to_github.sh             # optional: first GitHub sync
```

Clone without Dropbox: clone `Cursor-Governance` into `~/Dropbox/cursor governance/GlobalCommands` (or adjust paths in setup script), then run setup above.
