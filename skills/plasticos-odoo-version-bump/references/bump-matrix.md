<!-- L9_META
skill_schema: 1
parent: plasticos-odoo-version-bump
layer: reference
role: bump_matrix
tags: [plasticos, odoo, version, migrate]
owner: igor_beylin
status: active
version: 1.0.0
updated: 2026-08-07
/L9_META -->

# Version bump matrix & scoped upgrade

## Segment meaning (PlasticOS)

`19.0.MAJOR.MINOR.PATCH`

| Segment | Bump when |
|---|---|
| PATCH | Bugfix, migrate re-run, XML/security tweak, hook fix |
| MINOR | New field/model, new migrate chain that changes schema/data contract |
| MAJOR | Rare; breaking module contract (explicit human call) |

Always keep the `19.0.` prefix.

## Migration folder = manifest version

```
plasticos_foo/
  __manifest__.py          # "version": "19.0.1.2.12"
  migrations/
    19.0.1.2.12/
      pre-migrate.py       # runs when upgrading TO 19.0.1.2.12
```

If `19.0.1.2.11` already ran on Staging, editing
`migrations/19.0.1.2.11/pre-migrate.py` is a no-op until you ship `19.0.1.2.12`.

## Scoped upgrade only

```bash
# ✅ correct — only the module you bumped
make update m=plasticos_security_base

# ✅ correct — only if BOTH manifests were bumped in this change
make update m=plasticos_security_base,plasticos_logistics

# ❌ forbidden unless user explicitly orders a rebuild
make update-all
make update m=plasticos_base,plasticos_security_base,plasticos_intake,...  # kitchen sink
```

Odoo.sh: after merge to `Staging`, confirm `update.log` shows
`-u <only_bumped_module>` (or Odoo.sh auto `-u` for modules with version
delta — still do not manually expand the list).

## Staging verify (SSH)

```bash
set -a && source .env.local && set +a
BID="${ODOO_SH_STAGING_SSH%%@*}"
ssh "$ODOO_SH_STAGING_SSH" "git -C ~/src/user log -1 --oneline"
# then odoo-bin shell: env['ir.module.module'].search([('name','=','plasticos_…')]).installed_version
# and: rg 'Running upgrade|plasticos_…' ~/logs/update.log | tail -20
```

Success: `installed_version` matches bumped manifest; migrate log line present
when a migrate folder shipped.

## Worked examples

| Situation | Action |
|---|---|
| Fix migrate after 1.2.11 already applied | Bump to 1.2.12 + new `migrations/19.0.1.2.12/`; `make update m=plasticos_security_base` |
| Add field on `plasticos.intake` | Bump `plasticos_intake` MINOR/PATCH; `-u plasticos_intake` only |
| Docs-only AGENTS.md edit | No bump |
| Touch security_base + logistics XML | Bump **both**; `-u plasticos_security_base,plasticos_logistics` — still not `-u all` |
