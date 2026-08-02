<!-- L9_META
skill_schema: 1
parent: plasticos-odoo-sh-deploy
layer: reference
role: deploy_playbook
tags: [plasticos, odoo-sh, deploy, verify, push]
owner: igor_beylin
status: active
version: 1.1.0
updated: 2026-06-06
/L9_META -->

# Deploy and Verify Playbook

## Phase 2 — Fix (After Diagnosis)

1. Fix locally; commit with conventional message.
2. Bump module version in `__manifest__.py` (`19.0.X.Y.Z` → increment patch segment).
3. Run `make pr-check` locally.

## Phase 3 — Push (Requires Explicit User Approval for Production)

```bash
make push b=Production   # preferred PlasticOS workflow
# or after pr-check: git push origin <branch>:Production
```

Odoo.sh watches `Production` branch; push triggers rebuild.

## Phase 4 — Verify

```bash
ssh 29882273@cryptoxdog-ib-odoo-19.odoo.com "cd /home/odoo/src/user && git log --oneline -5"
ssh 29882273@cryptoxdog-ib-odoo-19.odoo.com "tail -100 ~/logs/update.log"
ssh 29882273@cryptoxdog-ib-odoo-19.odoo.com "grep -n 'your_change' /home/odoo/src/user/<module>/models/<file>.py"
```

### Success Indicator

```
X modules loaded in Y.XXs, NNNNN queries (+NNNNN extra)
Modules loaded.
Registry loaded in Y.XXXs
```

## Manual Module Upgrade (when auto-deploy lagging)

```bash
ssh 29882273@cryptoxdog-ib-odoo-19.odoo.com \
  "/home/odoo/src/odoo/odoo-bin \
    -c ~/.config/odoo/odoo.conf \
    --addons-path=/home/odoo/src/odoo/addons,/home/odoo/src/enterprise,/home/odoo/src/user \
    -u <module_name> \
    --stop-after-init"
```

Success: `Registry loaded in X.XXXs` with no ERROR lines.

## Rollback Note

If deploy fails: revert commit locally, push revert, or restore DB backup on Odoo.sh per incident policy.
