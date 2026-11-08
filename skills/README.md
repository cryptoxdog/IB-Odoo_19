# PlasticOS agent skills (repo SSOT)

**Owner:** `cryptoxdog/IB-Odoo_19` — not Claude Code config, not Cursor-Governance.

This directory holds PlasticOS project skills (`plasticos-*`). It is agent
tooling, parallel to `scripts/` and `tools/`.

## Not an Odoo addon

- No `__manifest__.py` / `__init__.py` in this tree (do not add them).
- Folder name is `skills` (not `plasticos_*`), so module scanners that
  glob `plasticos_*` never treat these packs as installable addons.
- Odoo only loads directories that contain `__manifest__.py`; these packs have
  `SKILL.md` only.

## Layout

```
skills/
  PLASTICOS_SKILLS_MANIFEST.yaml   # registry SSOT
  plasticos-<name>/
    SKILL.md
    references/
```

## Discovery adapters

Thin symlinks under `.claude/skills/plasticos-*` → `../../skills/plasticos-*`
exist only so Claude/Cursor skill discovery that still scans `.claude/skills/`
can find packs. **Edit files under `skills/` only.**

## Validate

```bash
make check-plasticos-skills
```
