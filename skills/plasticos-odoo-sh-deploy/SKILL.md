---
name: plasticos-odoo-sh-deploy
description: debug odoo.sh production errors via ssh logs, then deploy fixes. use for production errors, registry failures, rpc errors, or module update issues. always diagnose via ssh before writing code.
skill_schema: 1
layer: control_plane
role: skill_entrypoint
tags: [plasticos, odoo, odoo-sh, deploy, production, ssh]
owner: igor_beylin
status: active
disable-model-invocation: false
version: 1.2.1
updated: 2026-10-07
---

# Odoo.sh Deploy & Debug

## Purpose

Diagnose PlasticOS Odoo.sh production/staging failures from server logs, then publish the repair through `make pr`. Never edit files on the server.

## Core Contract

| Phase | Rule |
|-------|------|
| Diagnose | SSH logs first; user-reported symptom is not root cause |
| Fix | Local commit + manifest version bump; publish through `make pr` |
| Verify | Confirm commits on server + `Registry loaded` in update.log |
| Server FS | Read-only — all code changes via GitHub → Odoo.sh pull |

## Authority Order

1. Explicit user request and deploy target (Staging vs Production).
2. Server log evidence (`update.log`, `odoo.log`) over user error summary.
3. `.env.local` SSH values; branch model `Staging` / `Production` (capitalized).
4. Publication SSOT — `make pr` only. Feature work targets `Staging`. Production promotion is `Staging` → `Production` through `make pr base=Production`, and only from the `Staging` branch.
5. Odoo runtime tests stay local. Production promotion still requires explicit user approval.
6. This skill's references.
7. `Unknown` — stop if SSH access or deployed commit cannot be verified.


## Staging / Production SSH (env-first)

**SSOT:** repo-root `.env.local` (never hardcode a stale build ID over env).

```bash
set -a && source .env.local && set +a
# Staging
ssh "$ODOO_SH_STAGING_SSH"
# Production
ssh "$ODOO_SH_PRODUCTION_SSH"
```

- `ODOO_SH_STAGING_SSH` format: `BUILD_ID@…-staging-BUILD_ID.dev.odoo.com` — **no** leading `ssh `.
- Build IDs rotate on every Odoo.sh Staging rebuild; update `.env.local` from Connect, then sync `.cursor/rules/98-odoo-sh-staging.mdc` snapshot if needed.
- Overlay rule: `.cursor/rules/98-odoo-sh-staging.mdc`.

## Compact Workflow

1. **Diagnose** — [ssh-diagnose.md](references/ssh-diagnose.md): git log on server, read logs, inspect files.
2. **Fix** — implement locally, bump module version, commit.
3. **Deploy** — user approval required for Production; [deploy-verify.md](references/deploy-verify.md).
4. **Verify** — confirm registry load and file contents on server.

## Resource Map

- [references/ssh-diagnose.md](references/ssh-diagnose.md) — SSH hosts, log files, diagnose commands, common issues.
- [references/deploy-verify.md](references/deploy-verify.md) — `make pr` publication, manual module upgrade, success indicators.

## Validation

Before declaring deploy success:

- Server `git log` shows expected commits.
- `update.log` ends with `Registry loaded` and no ERROR tracebacks.
- Specific fix grep confirms change is live on server.

Local fix MUST pass `make pr-check` before `make pr` (PlasticOS policy).

## Failure Handling

- No SSH access → STOP; request credentials or `.env.local` values.
- "Read-only file system" on server → expected; fix locally and publish through `make pr`.
- Registry failure → root cause is in `update.log` traceback, not browser RPC message.
- Production promotion without explicit user approval → STOP.
- Version not triggering update → follow **`plasticos-odoo-version-bump`** (bump without asking; `make update m=<module>` only).
