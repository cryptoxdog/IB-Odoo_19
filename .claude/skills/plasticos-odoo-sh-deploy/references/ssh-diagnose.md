<!-- L9_META
skill_schema: 1
parent: plasticos-odoo-sh-deploy
layer: reference
role: diagnose_playbook
tags: [plasticos, odoo-sh, ssh, logs, diagnose]
owner: igor_beylin
status: active
version: 1.1.0
updated: 2026-06-06
/L9_META -->

# SSH Diagnose Playbook

## #1 Rule: Diagnose Before Fix

Never write code before reading server logs. Browser RPC/500 errors are symptoms.

## SSH Access

```bash
# Production
ssh 29882273@cryptoxdog-ib-odoo-19.odoo.com

# Staging
ssh 32727906@cryptoxdog-ib-odoo-19-staging-32727906.dev.odoo.com
```

Values also in `.env.local` (`ODOO_SH_PRODUCTION_SSH`, `ODOO_SH_STAGING_SSH`).

## Critical Facts

- Source is **read-only** on server — no `sed -i`; push via git only.
- GitHub branches: `Production`, `Staging` (capital first letter).
- Addons path: `/home/odoo/src/odoo/addons,/home/odoo/src/enterprise,/home/odoo/src/user`
- Build IDs (rotate): Production `29882273`, Staging `32727906`

## Phase 1 Commands

```bash
# Deployed commits
ssh 29882273@cryptoxdog-ib-odoo-19.odoo.com "cd /home/odoo/src/user && git log --oneline -10"

# Registry failures — START HERE
ssh 29882273@cryptoxdog-ib-odoo-19.odoo.com "tail -200 ~/logs/update.log | grep -A20 'ERROR\|CRITICAL\|Traceback'"

# Runtime errors
ssh 29882273@cryptoxdog-ib-odoo-19.odoo.com "tail -200 ~/logs/odoo.log | grep -A10 'ERROR\|Traceback'"

# Inspect specific file
ssh 29882273@cryptoxdog-ib-odoo-19.odoo.com "sed -n '85,110p' /home/odoo/src/user/<module>/models/<file>.py"
```

## Log Files

| File | Purpose |
|------|---------|
| `~/logs/update.log` | Module install/update — registry failures |
| `~/logs/odoo.log` | Live runtime, RPC, cron |
| `~/logs/install.log` | Initial install |

## Noise to Ignore

- WARNINGs about `alert (class alert-*)` — accessibility, not errors
- Asset compilation INFO lines
- Deprecation WARNINGs unless paired with ERROR

## Odoo Runtime Tests vs Odoo.sh CI

- **`make test-odoo`** / **`make test-module`** — local Docker only.
- **`ci/odoo.sh (dev)`** on PRs — external Odoo.sh status; not GitHub Actions.
- Repo CI stays pure-Python (`make pr-check`).

## Common Issues

| Symptom | Action |
|---------|--------|
| Failed to load registry | Read `update.log` traceback |
| KeyError model (404 RPC) | Check module installed, `__init__.py`, manifest dep |
| Read-only filesystem | Fix locally → push |
| Version not triggering update | Bump manifest patch segment |
