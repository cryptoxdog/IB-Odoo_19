# PlasticOS Canonical Law (IB-Odoo_19)

**Repo:** `cryptoxdog/IB-Odoo_19`
**Scope:** PlasticOS project layout, agent skills, and Odoo addon boundaries.
**Not this file:** Global Cursor / L9 law lives in the governance clone and is
exposed here only as the symlink `.cursor/governance/CANONICAL_LAW.md` →
Cursor-Governance. **Do not edit that symlink target from this repo.**

This document is the **repo-owned** law for PlasticOS-specific skill and
non-addon tooling paths. Update it in `IB-Odoo_19` PRs only.

---

## 1. Skill ownership

| Class | SSOT location | Owner |
|---|---|---|
| **PlasticOS project skills** (`plasticos-*`) | `skills/` | This repo |
| L9 global skills (`l9-*`) | `@.cursor-commands/skills/l9-*/` | Cursor-Governance / GlobalCommands |
| Discovery adapters | `.claude/skills/plasticos-*` → `../../skills/...` | Symlinks only — never edit content there |

### Forbidden

- Storing PlasticOS skill SSOT under `.claude/skills/` (except discovery symlinks)
- Storing PlasticOS skill SSOT under Cursor-Governance / GlobalCommands
- Copying L9 packs into `skills/`
- Adding `__manifest__.py` or `__init__.py` under `skills/` (would risk Odoo treating packs as addons)

### Required

- Every `plasticos-*` pack under `skills/` with `SKILL.md`
- Entry in `skills/PLASTICOS_SKILLS_MANIFEST.yaml` with `invocation: auto`
- Row in `AGENTS.md` and `.claude/README.md` Project Skills table
- `disable-model-invocation: false` on every PlasticOS skill
- Discovery symlink `.claude/skills/<name>` → `../../skills/<name>`
- Validate: `make check-plasticos-skills`

---

## 2. `skills/` is not an Odoo addon

Same class as `scripts/` and `tools/`:

- Repo-root folder, **not** named `plasticos_*`
- No Odoo module markers
- Module wiring / install order only scan `plasticos_*` addons
- Audit scanners must skip `skills/` (`scripts/audit/path_filters.py`)

---

## 3. Version bump + scoped upgrade (mandatory)

See skill `skills/plasticos-odoo-version-bump/` and rule
`.cursor/rules/89-plasticos-odoo-version-bump.mdc`.

- Never ask whether to bump a runtime-affecting module change
- Never chase a silent no-op because the version was not bumped
- After bump: `make update m=<that_module>` only — never `update-all` / kitchen-sink `-u` for a one-module fix

---

## 4. Repo overlay vs PlasticOS law

| Path | Role |
|---|---|
| `.cursor/governance/CANONICAL_LAW.md` | Symlink → global governance law (**do not edit from this repo**) |
| `skills/PLASTICOS_CANONICAL_LAW.md` | **This file** — PlasticOS repo law (tracked; not under `.cursor/`) |
| `.cursor/rules/*.mdc` | PlasticOS overlay rules |
| `.cursor/README.md` | Local overlay index (often gitignored) |

Global commands/skills/rules remain via `@.cursor-commands/` only.

---

## 5. Authority order (PlasticOS agent work)

1. Explicit user instruction
2. This file (`PLASTICOS_CANONICAL_LAW.md`) for PlasticOS skill/layout paths
3. `AGENTS.md` / `INVARIANTS.md` / `.cursor/rules/*`
4. Global `CANONICAL_LAW.md` (symlink) for L9 / GlobalCommands concerns
5. Skill packs under `skills/` then L9 globals

---

## 6. Validation

```bash
make check-plasticos-skills
python3 scripts/check_module_wiring.py   # must not treat skills as addons
```
