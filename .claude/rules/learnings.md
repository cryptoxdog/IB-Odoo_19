# Agent Learnings

Agents should append non-obvious patterns and gotchas discovered while working in this repo.
Review periodically and promote stable learnings to CLAUDE.md or relevant rule files.

## Format
- **[date] Category: description** — brief explanation

## Learnings
<!-- Agents: append new entries below this line -->

- **[2026-03-27] Workflow: Always run `make pr-check` before every push** — catches Odoo 19 violations, cross-module ACL issues, XML errors, and format problems before hitting Odoo.sh. One command replaces a dozen separate checks.

- **[2026-03-27] Never remove a field/filter to fix a validation error — fix the root cause instead:**
  - Non-stored computed field in Odoo 19 domain filter → add a `search` method (`search="_search_foo"`) that translates to a stored field query
  - Related field dot-notation (`partner_id.field`) in views → define an explicit `related` field on the model, name it properly
  - `attrs=` → `invisible=` (Odoo 19), `<group>` in `<search>` → flat `<filter>` elements, `@string` in xpath → `@name`

- **[2026-03-27] Cross-module ACL rule**: An `ir.model.access.csv` row must live in the SAME module that defines the model. If `model_id:id` has no module prefix, Odoo looks in the current module and returns NULL. Use `other_module.model_name` prefix for foreign models.

- **[2026-03-27] SQL VIEW `init()` timing**: When a module installs itself AND the SQL VIEW references columns being added by that SAME install (via `_inherit`), the columns don't exist yet when `init()` runs. Use literal defaults for first install, then `odoo-update` immediately after to rebuild the VIEW with real columns.

- **[2026-03-27] `res_users` has no `name` column** — user display names are on `res.partner` via `partner_id`. Always join `res_partner rp ON rp.id = u.partner_id` to get `rp.name`.

- **[2026-03-27] Odoo 19 removed from `ir.cron`**: `doall`, `numbercall` fields. Remove from XML data files.

- **[2026-03-27] `documents.folder` still exists in Odoo 19 Enterprise** — KeyError occurs only when Enterprise `documents` module is not installed on the instance. Verify Enterprise modules are present before installing `plasticos_documents_native`.

- **[2026-10-22] Publication: `make pr-check` is change-class scoped** — `scripts/odoo_load_surface.py` is the only definition of what `odoo-bin -i` reads; install-smoke evidence (v4) and pr-check scope selection both consume it. A README, fixture CSV or test under an addon is not a load input. The Enterprise base lives in the `odoo_install_smoke_base` template; a smoke install clones it and installs only `plasticos_*`. Force the old behaviour with `PR_CHECK_SCOPE=full`, `ODOO_INSTALL_SMOKE_BASE=0`, `PR_CHECK_SMOKE_PARALLEL=0`.

- **[2026-10-22] Publication: the Odoo install-smoke runs on GitHub, not before the push** — `.github/workflows/odoo-install-smoke.yml` runs `scripts/install_smoke.sh` on every PR with Enterprise checked out from `odoo/enterprise` (`secrets.ODOO_ENTERPRISE_TOKEN`). `make pr` / `make pr-check` never call the installer; `make install-smoke` is the explicit local run. Docker-less surfaces (Claude Code cloud) can therefore complete `make pr`.
