---
name: odoo-sh-deploy
description: Debug Odoo.sh production errors via SSH logs, then deploy fixes. Use for any production error, registry failure, RPC error, or module update issue. ALWAYS diagnose via SSH before writing code.
---

You are a production debugging assistant for the PlasticOS Odoo.sh instance.

## #1 RULE: DIAGNOSE BEFORE YOU FIX

**NEVER fire blindly.** Before writing a single line of code:

1. **SSH into staging** and read the actual logs
ssh 29915952@cryptoxdog-ib-odoo-19-staging-29915952.dev.odoo.com


2. **Identify the root cause** from tracebacks, not from the user's error summary alone
3. **Confirm what's deployed** — check git log on server matches what you expect
4. **Only then** propose and implement a fix

The user-reported error (browser RPC error, 500, 404, etc.) is a **symptom**. The real cause is in the server logs.

## SSH Access

```bash
# Production
ssh 29915952@cryptoxdog-ib-odoo-19.odoo.com

# Staging
ssh 29915952@cryptoxdog-ib-odoo-19-staging-29915952.dev.odoo.com
```

## Critical Facts

- **Source is read-only** on the server — you CANNOT edit files via SSH (`sed -i` will fail with "Read-only file system")
- Code updates ONLY come from git pushes to GitHub — Odoo.sh pulls automatically
- **Production branch** on GitHub: `Production`
- **Staging branch** on GitHub: `Staging`
- Local branch name is `staging` (lowercase) — remote branches are capitalized
- Odoo.sh instance ID: `29915952`
- Production URL: `cryptoxdog-ib-odoo-19.odoo.com`
- **Correct addons path for manual odoo-bin commands:**
  `/home/odoo/src/odoo/addons,/home/odoo/src/enterprise,/home/odoo/src/user`

---

## Phase 1: DIAGNOSE (Always Do This First)

### Step 1 — Check what's actually deployed on the server

```bash
# What commits are live?
ssh 29915952@cryptoxdog-ib-odoo-19.odoo.com "cd /home/odoo/src/user && git log --oneline -10"

# What branch is active?
ssh 29915952@cryptoxdog-ib-odoo-19.odoo.com "cd /home/odoo/src/user && git branch"
```

### Step 2 — Read the server logs for the REAL error

```bash
# update.log — module install/update tracebacks (START HERE for registry failures)
ssh 29915952@cryptoxdog-ib-odoo-19.odoo.com "tail -200 ~/logs/update.log | grep -A20 'ERROR\|CRITICAL\|Traceback'"

# odoo.log — live runtime errors (RPC failures, field errors, permission errors)
ssh 29915952@cryptoxdog-ib-odoo-19.odoo.com "tail -200 ~/logs/odoo.log | grep -A10 'ERROR\|Traceback'"

# Registry load failures specifically
ssh 29915952@cryptoxdog-ib-odoo-19.odoo.com "grep -A10 'Failed to load registry' ~/logs/update.log | tail -50"
```

### Step 3 — Inspect specific files on the server

```bash
# Check a specific file's contents
ssh 29915952@cryptoxdog-ib-odoo-19.odoo.com "sed -n '85,110p' /home/odoo/src/user/<module>/models/<file>.py"

# Confirm a specific change is or isn't live
ssh 29915952@cryptoxdog-ib-odoo-19.odoo.com "grep -n 'search_term' /home/odoo/src/user/<module>/models/<file>.py"

# Check manifest version
ssh 29915952@cryptoxdog-ib-odoo-19.odoo.com "grep version /home/odoo/src/user/<module>/__manifest__.py"
```

### Step 4 — Check available log files

```bash
ssh 29915952@cryptoxdog-ib-odoo-19.odoo.com "ls -lh ~/logs/"
```

### Log Files Reference

| File | Purpose |
|---|---|
| `~/logs/update.log` | Module install/update output — **start here for registry failures** |
| `~/logs/odoo.log` | Live server log — runtime errors, RPC failures, cron jobs |
| `~/logs/odoo.log.1` | Previous log rotation |
| `~/logs/install.log` | Initial install log |

### Noise to Ignore

- WARNINGs about `alert (class alert-*)` — accessibility notices, NOT errors
- `INFO` lines about asset compilation — normal build output
- `WARNING ... deprecated` — not the cause of failures unless paired with ERROR

---

## Phase 2: FIX (Only After Diagnosis Is Complete)

### Step 1 — Make and commit the fix locally

```bash
git add <file>
git commit -m "fix(module): description"
```

### Step 2 — Bump module version to trigger Odoo.sh update

In the module's `__manifest__.py`, increment the patch version:
```
"version": "19.0.X.Y.Z"  →  "version": "19.0.X.Y+1.Z"
```
Commit the version bump separately or together with the fix.

### Step 3 — Push to Production (REQUIRES EXPLICIT USER APPROVAL)

```bash
git push origin staging:Production
```
> Odoo.sh watches the `Production` branch. Push triggers an automatic rebuild.

---

## Phase 3: VERIFY (Confirm the Fix Landed)

```bash
# Confirm commits arrived on server
ssh 29915952@cryptoxdog-ib-odoo-19.odoo.com "cd /home/odoo/src/user && git log --oneline -5"

# Check update log for success
ssh 29915952@cryptoxdog-ib-odoo-19.odoo.com "tail -100 ~/logs/update.log"

# Confirm specific file change is live
ssh 29915952@cryptoxdog-ib-odoo-19.odoo.com "grep -n 'your_change' /home/odoo/src/user/<module>/models/<file>.py"
```

### Successful Deployment Confirmation

Update log ends with:
```
X modules loaded in Y.XXs, NNNNN queries (+NNNNN extra)
Modules loaded.
Registry loaded in Y.XXXs
```
If you see `Registry loaded` — the deploy succeeded.

---

## Manual Module Upgrade via SSH

Use when Odoo.sh hasn't auto-deployed or you need to force a module update:

```bash
ssh 29915952@cryptoxdog-ib-odoo-19.odoo.com \
  "/home/odoo/src/odoo/odoo-bin \
    -c ~/.config/odoo/odoo.conf \
    --addons-path=/home/odoo/src/odoo/addons,/home/odoo/src/enterprise,/home/odoo/src/user \
    -u <module_name> \
    --stop-after-init"
# Success indicator: "Registry loaded in X.XXXs" with no ERROR lines
```

---

## Common Issues

### "Failed to load registry"
- Check `update.log` — the actual Python traceback is there, not in the browser
- Look for `ERROR` or `Traceback` lines for the real root cause

### KeyError on model (404 RPC)
- Model referenced in action/view/menu but not registered in the ORM
- Check: Is the module installed? Is the model in `__init__.py`? Is `__manifest__.py` dependency declared?

### "Read-only file system" when trying to edit
- You CANNOT edit files on Odoo.sh via SSH — push via git instead
- Fix locally → commit → push to `Production` branch

### Version not triggering update
- Bump `"version"` in `__manifest__.py` — Odoo only updates modules with version changes
- Format: `19.0.X.Y.Z` — increment the 4th segment for patches

### Push went to wrong branch
- Remote branches are `Production` and `Staging` (capital first letter)
- Local branch is `staging` (lowercase)
- Always use: `git push origin staging:Production` for production deploys
