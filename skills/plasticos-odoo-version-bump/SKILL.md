---
name: plasticos-odoo-version-bump
description: >
  Mandatory PlasticOS Odoo module version bumps and scoped module upgrades.
  Use whenever changing plasticos_* Python, XML, data, security, hooks, or
  migrations; before make update / Odoo.sh deploy; when a module did not reload;
  or when deciding whether to bump a manifest. Never ask whether to bump —
  bump the changed module and upgrade only that module.
skill_schema: 1
layer: control_plane
role: skill_entrypoint
tags: [plasticos, odoo, version, manifest, migrate, upgrade, staging]
owner: igor_beylin
status: active
disable-model-invocation: false
version: 1.0.0
updated: 2026-08-07
---

# PlasticOS Odoo Version Bump (Mandatory)

## Purpose

Prevent silent no-op deploys: Odoo only reloads a module when its
`__manifest__.py` version advances. Staging has a large `res.partner` set —
never pay a full-stack reload for a one-module fix.

## Operator Law (verbatim)

- never ask whether to bump a version
- never chase a module that did not load because the version was not bumped —
  this is mandatory
- when you bump a module, reload only that module — do not bump or reload the
  entire codebase wasting time reloading what had no errors or issues and was
  solid already

## Hard Rules

1. **Bump without asking.** If you change a `plasticos_*` module in a way that
   must reach a running DB (Python model/logic, XML views/data/security, hooks,
   migrations, ACL CSV loaded via `data`), bump that module's version in the
   **same PR / same commit set**. Do not wait for the user to notice a no-op.
2. **One module → one bump → one `-u`.** Upgrade **only** the module(s) whose
   versions you bumped:
   ```bash
   make update m=plasticos_security_base
   # comma-list ONLY when multiple modules were actually bumped:
   make update m=plasticos_security_base,plasticos_logistics
   ```
3. **Never** `make update-all`, bare `-u all`, or a kitchen-sink `-u` of
   unrelated modules "to be safe." Staging partner/import load makes that
   expensive and hides the real failure.
4. **Migrations require a version advance.** Editing
   `migrations/19.0.X.Y.Z/*` after that version already ran on Staging does
   **nothing** until you bump to a **new** version folder + matching manifest
   version (usually next PATCH).
5. **`ruff format` the manifest** after every version edit.

## When to bump (decision table)

| Change in module M | Bump M? | Segment |
|---|---|---|
| New/changed migration scripts | **YES** | PATCH (or MINOR if schema-facing); add `migrations/<new_version>/` |
| Edited existing migrate that already ran on target DB | **YES** — new version | PATCH; copy/forward logic into new folder |
| Python models / business logic | **YES** | PATCH (bugfix) or MINOR (field/model) |
| XML views, data, security, ACL CSV in `data` | **YES** | PATCH |
| Hooks (`pre_init` / `post_init` / `hooks.py`) | **YES** | PATCH |
| Tests / CI / docs / comments only | NO | — |
| Unrelated modules not touched | **NO** — leave their versions alone | — |

Format: `19.0.MAJOR.MINOR.PATCH` (see `.cursor/rules/81-ci-manifest-contract.mdc`).

Read [references/bump-matrix.md](references/bump-matrix.md) for examples and
Staging verify commands.

## Compact Workflow

1. List every `plasticos_*` module with runtime-affecting diffs.
2. For each, read current `"version"` in `__manifest__.py`.
3. Bump PATCH (or MINOR per table). If adding migrations, create
   `migrations/<new_version>/` matching the new manifest version.
4. `ruff format <module>/__manifest__.py`
5. Commit version bump with the code change (same PR).
6. Upgrade **only** bumped modules: `make update m=<module>` (Docker) or confirm
   Odoo.sh `-u` list is scoped the same way.
7. Verify in logs / DB: `installed_version` == new version; migrate lines ran.

## Failure Handling

| Symptom | Cause | Fix |
|---|---|---|
| Code on disk, DB behavior unchanged | Version not bumped | Bump PATCH, redeploy, `-u` that module only |
| Migrate file edited, log shows no `Running upgrade` | Version already applied | Bump to next version + new migrate folder |
| Staging update takes forever | `-u` too broad / `update-all` | Abort pattern; re-run with only bumped module(s) |
| Agent asks "should I bump?" | Protocol violation | Bump; do not ask |

## Cross-links

- Deploy verify: `plasticos-odoo-sh-deploy`
- Docker smoke / module order: `plasticos-odoo-docker-testing`
- Manifest contract: `.cursor/rules/81-ci-manifest-contract.mdc`
- Overlay rule: `.cursor/rules/89-plasticos-odoo-version-bump.mdc`
- SSOT path: `skills/` (discovery symlink under `.claude/skills/` — do not edit there)
