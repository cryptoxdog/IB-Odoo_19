# Workflow State — PlasticOS (IB-Odoo_19)

## PHASE

ERP import inside `plasticos_partner_import` — committed locally in
`refactor(import): load ERP extract from partner import`, not pushed. Docker testing is **in progress** on the isolated stack
`wt-origin-staging` (worktree mounted at `6407943`, Odoo up on port 8069).

Web-lead inbound port is its own local commit (`feat(web-leads): admit leads
through a provider-neutral inbound port`). Operator cutover
(Cognito, Infisical, n8n) is still open.

## Active TODO Plan

| TODO | Status |
|------|--------|
| Move ERP source layer, grids, and `make import-erp` into `plasticos_partner_import` | ✅ committed (`19.0.2.9.0`) |
| Shell driver import through `odoo.addons` | ⚠️ uncommitted one-line change in `scripts/import_erp_shell.py` |
| Docker dry-run of the existing import | ✅ finished; wrote nothing |
| Docker testing of the import mechanism | 🔄 in progress on `wt-origin-staging` |
| p0–p8 inbound port | ✅ committed (web-lead inbound port commit) |
| p9 web-lead verify | ✅ module tests and local upgrade; `make pr-check` stopped at install-smoke |
| Cognito Forms → Odoo, no n8n | ⚠️ unfinished — fields, secrets, and settings still to configure; done only when a test submission lands in web-lead intake |
| VS lead notes and grades (`vs_lead_notes_grades_fee25eec`) | ⏸ pending execution — blocked on `res.partner` import |
| Final cross-repo L9 constellation testing | ⏸ starts only after the Docker import tests pass |

## Files in Scope

plasticos_web_leads/** (adapters, controller, web_lead.py, config, views,
migrations/19.0.2.8.0/, tests), tests/test_web_lead_adapter_contract.py,
tests/test_web_lead_packet.py, tests/test_error_handling.py,
tests/test_golden_flows.py, tests/contracts/test_api_signature_contracts.py,
docs/adr/ADR-020-web-lead-inbound-port.md, docs/adr/README.md,
.cursor/rules/50-plasticos-web-lead-guard.mdc,
.cursor/rules/98-odoo-sh-staging.mdc.

The port is its own commit, right after the ERP-import refactor. HEAD is
`ci: pin GitHub Actions in ci.yml to commit SHAs`. Working tree is clean
except `plasticos_partner_import/scripts/import_erp_shell.py` and this file.

`plasticos_partner_import` in the ERP-import refactor commit (manifest `19.0.2.8.0` → `19.0.2.9.0`,
depends now includes `plasticos_transaction`):

- `erp/` — reader, mapping, mapping status, source index, summary, report,
  header forensics.
- `models/erp_import_service.py` — upsert model `plasticos.erp.import`.
- `scripts/run_erp_import.py` and `scripts/import_erp_shell.py` — `make import-erp`.
- `erp_extracted_data/` — SQL query definitions (`00`–`06`, `10`–`17`), frozen
  grids under `bulk/`, and the meta/diagnostics files the importer still reads.
- `make import-erp` reads `erp_extracted_data/` first. Those files are `SELECT`
  scripts, so they contribute no rows. The loader then uses the frozen grids
  under `erp_extracted_data/bulk/`.
- Uncommitted: `import_erp_shell.py` imports
  `odoo.addons.plasticos_partner_import.scripts.run_erp_import`. A plain
  `plasticos_partner_import` import is rejected inside `odoo shell`. The same
  line is in the mounted worktree and is not committed.

## Test Status

- Docker testing **in progress** on project `wt-origin-staging`
  (`wt-origin-staging-odoo-1` and `wt-origin-staging-db-1`). The container
  mounts the worktree checked out at `6407943`. The local `odoo19` stack is
  stopped.
- Dry run of `make import-erp` inside that container finished and wrote
  nothing (`ERP_DRY=1`). Mapped rows: counterparties 1,290; locations 2,584;
  contacts 3,707; transactions 8,257; transaction lines 11,303. Contact roles
  stay at 0 in a dry run (applied only when a contact partner is created).
  No failed transactions. Report notes: 725 unresolved counterparty references
  and 5,085 mapping notes (mostly payment terms absent from this database:
  `Net 10`, `Due on receipt`, `N45`).
- Pure web-lead + contract + phantom-enum + dependency integrity: **193 passed**.
- `make pr-check` pytest tier: **904 passed, 45 skipped**, then
  `install-smoke` exited 127 because `COOLIFY_TOKEN` in `.env` contains shell
  metacharacters and cannot be sourced. Not caused by the web-lead change.
- Rebuilt `odoo19` image: `plasticos_web_leads` tests **0 failed, 0 errors**
  (24 post-install tests, including `test_web_lead_inbound_http`).
- Local DB `odoo`: `plasticos_web_leads` **installed at 19.0.2.8.1**.
  Migration `19.0.2.8.0` logged `inbound provider keys backfilled`.
- `make update m=plasticos_web_leads` then exited 1: the one-off server stayed
  up, and the Makefile tail grep matched unrelated ERROR/Traceback lines
  (localization imports, commission docstring RST, filestore GC). The module
  load and migration had already succeeded.

## Recent Changes

- [2026-10-01] [EXECUTE] Files: plasticos_partner_import | Action: ERP extract, grids, and import command moved into the module; `make import-erp` reads `erp_extracted_data/` then the frozen grids | Tests: Docker dry run mapped the full extract and wrote 0 rows; live Docker testing still running
- [2026-10-01] [EXECUTE] Files: plasticos_web_leads, tests, ADR-020, rules 50 and 98 | Action: Odoo-owned `WebLeadAdapter` port; Cognito posts to `/api/v1/web-lead/inbound/cognito`; `/api/v1/web-lead` and `create_from_agent` removed | Tests: 193 pure; 24 Odoo post-install green
- [2026-09-17] [EXECUTE] Files: plasticos_crm_sync, plasticos_partner_import, tests | Action: GMP-129 ingestion milestone | Tests: 736 passed pure tier

## Decision Log

- Port is module-local (`plasticos_web_leads/adapters/base.py`). A new form
  tool is one adapter file plus one registry line. Triage stays Phase 1 local
  (ADR-016). Gate is not on this path.
- Auth: `?access_token=`, Bearer, or `X-API-Key`. Submit admits. Update/Delete
  return HTTP 200 `ignored` and do not mutate a lead. A parseable submission
  that fails adapter validation is stored `state=error` and answered HTTP 200
  `rejected`.
- `POST /api/v1/cognito-webhook` remains an alias for provider `cognito`.
- Manifest on `Staging` is **19.0.2.8.1** (plan target was 19.0.2.8.0; the
  local database recorded 19.0.2.8.1). Do not downgrade the manifest under
  that installed version.
- Do not commit or push without operator approval (`96-git-push-approval`).
  Use `make push`, not raw `git push`.

## Pending plan — blocked

`~/.cursor/plans/vs_lead_notes_grades_fee25eec.plan.md` (VanillaSoft lead notes
and deferred grade profiles) is pending execution. It is blocked by the import
of `res.partner` rows.

The plan writes general VanillaSoft `Notes` onto `crm.lead.description`, stores
non-empty grade groups (including MRP) as JSON on the lead, and skips freight
columns. It does not create partners or `plasticos.material.profile` rows in
that change. Material profiles come later, one per stored grade, and
`plasticos.material.profile` requires a facility `partner_id`. That step waits
until the partner import has created those partners.

Todos still pending: `map-notes`, `store-grades`, `omit-freight`, `test-upsert`
(bump `plasticos_crm_sync`). Do not start them until the `res.partner` import
is in.

## Cognito Forms → Odoo (no n8n) — must finish

The revised inbound path posts Cognito Forms directly into Odoo. n8n is not
part of it. Code for the port is in the local commits. The integration is not
finished until every field, secret, and setting is configured and a live test
passes.

Success: a test web-lead submission posts into the web-lead intake and a
`plasticos.web.lead` record exists for it.

Still to configure (ADR-020): the web-lead API key, Infisical
`ODOO_WEB_LEAD_API_KEY` and `ODOO_WEB_LEAD_WEBHOOK_PATH`
(`/api/v1/web-lead/inbound/cognito`), and the Cognito Submit Entry Endpoint
(`https://<host>/api/v1/web-lead/inbound/cognito?access_token=<api_key>`).
Leave Cognito Update and Delete empty. After the test submission lands,
retire n8n and the `N8N_*` Infisical names.

## Open Questions

- Operator cutover: regenerate the web-lead API key, set Infisical
  `ODOO_WEB_LEAD_API_KEY` and `ODOO_WEB_LEAD_WEBHOOK_PATH` to
  `/api/v1/web-lead/inbound/cognito`, point the Cognito Submit Entry Endpoint
  at `https://<host>/api/v1/web-lead/inbound/cognito?access_token=<api_key>`,
  leave Update/Delete empty, submit one staging entry and record duration,
  then retire n8n and the `N8N_*` Infisical names. Checklist: ADR-020.
- `install-smoke` cannot source `.env` until `COOLIFY_TOKEN` is quoted.

## Next after these tests pass

Once the Docker import tests pass, move to the final cross-repo L9
constellation test. Do not start it before that.

Included:

- https://github.com/cryptoxdog/IB-Odoo_19
- https://github.com/Quantum-L9/Cognitive.Engine.Graphs
- https://github.com/Quantum-L9/Enrichment.Inference.Engine
- https://github.com/Quantum-L9/Constellation.Gate

Explicitly excluded:

- https://github.com/Quantum-L9/Gate
- https://github.com/Quantum-L9/Gate_SDK

## Next Steps

1. Finish the Docker import of `res.partner` rows on `wt-origin-staging`. The
   VanillaSoft notes-and-grades plan stays blocked until that import lands.
   When those tests pass, start the cross-repo L9 constellation test above.
2. Record whether a non-dry import run was executed.
3. Commit the `odoo.addons` import in `import_erp_shell.py` only when asked.
4. Finish Cognito Forms → Odoo with no n8n: configure every field, secret, and
   setting, then submit a test web lead. Success is that submission posted
   into the web-lead intake.
5. When the operator asks to publish: `make pr-check` (after `.env` sourcing
   is fixed) then `make push pr=1` into `Staging`.

## Recent Sessions

- ⚠️ 2026-10-01: Cognito Forms → Odoo (no n8n) is unfinished until fields,
  secrets, and settings are configured and a test web-lead submission posts
  into the web-lead intake.
- ⏸ 2026-10-01: After the Docker import tests pass, run the final cross-repo L9
  constellation test across IB-Odoo_19, Cognitive.Engine.Graphs,
  Enrichment.Inference.Engine, and Constellation.Gate. Gate and Gate_SDK are
  excluded.
- ⏸ 2026-10-01: VanillaSoft lead notes and grades plan is pending and blocked
  on the `res.partner` import.
- 🔄 2026-10-01: ERP import consolidated into `plasticos_partner_import`.
  Docker testing in progress on `wt-origin-staging`. Dry run wrote nothing.
- ✅ 2026-10-01: Web-lead inbound port implemented and upgraded on the rebuilt
  local `odoo19` image. Not pushed. Rollout still open.
- ✅ 2026-09-17: GMP-129 odoo-intent-1-ingestion — 15 todos, 14 landed, live-DB
  proofs UNKNOWN by environment, suite 736/32 green.
