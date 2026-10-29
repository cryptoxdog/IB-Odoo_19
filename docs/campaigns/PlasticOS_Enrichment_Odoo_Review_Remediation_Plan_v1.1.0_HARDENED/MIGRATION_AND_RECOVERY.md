# Existing-history preservation, migration and recovery

## Read-only target census before any commit

Capture Odoo.sh database/filestore paired recovery identifier, installed `ir.module.module` versions, custom Enterprise modules, XML ID ownership, enrichment source/run/extraction/provenance totals, states/engine_used/partner/company distributions, Gate packet IDs, actual system parameters, native security groups and ACL rows, company record rules, server actions, automations, cron definitions/active values, pending jobs, and model-field registry. Count previous local-run and Gate-run histories separately, including archived records. Any unknown remains a blocker.

## Additive migration policy

The current Git source manifest is `19.0.2.5.5`. Candidate successor is `19.0.2.5.6` (source path `plasticos_enrichment/migrations/19.0.2.5.6/post-migrate.py`) **only if** actual installed version and Odoo.sh versioning conventions admit it. Never retrofit historical `migrations/19.0.2.0.0/post-migrate.py` or silently rely on `<odoo noupdate="1">` old cron XML to reset active jobs. If the installed revision differs, recalculate the version and exact path before code grant.

1. Add proposal-line model with database uniqueness `(run_id,target_field)` and restrict source deletion; add server-native ACL/company protection before creating review lines.
2. Keep current run, source, extraction and provenance IDs. Do not fabricate approval decisions for historical `review` or `injected` runs or replay EIE packets automatically.
3. Add `company_id` only under proven source-company policy. For shared/unknown existing partners, quarantine to administrative read-only rather than assigning a guessed operating company.
4. Preserve existing run confidence/extraction results and raw Gate summary; source EIE aggregate evidence stays distinct from future user-attested individual evidence.
5. Migrate effective installed ACLs/record rules using supported upgrade behavior; removing a CSV line in git may not revoke previously loaded rights. Inspect and explicitly reconcile installed rows by exact XML ID and group, with before/after counts and rollback note.
6. Determine actual cron user group membership and all valid consumers before revoking the retired enrichment-manager grant. Preserve other groups and unrelated jobs. Both retired enrichment crons must remain inactive in actual database after upgrade even if `noupdate` prevented XML reload.
7. Do not create any res.partner, material profile, CRM opportunity, transaction, PO or offer as a side effect of migration.
8. Preserve externally referenced XML IDs, original historical run names/sequence and old source URLs/attachments. Never delete trusted evidence just to make a fresh UI look clean.

## Recovery

If a new permission or approval path fails, disable Apply Approved and route Gate proposals to review-only; do not restore old bulk Inject. Persist classified incidents/receipts with protected access. If restoration is necessary, restore a tested paired Odoo.sh PostgreSQL/filestore backup and validated release SHA; reconcile any concurrent legitimate business writes before destructive restore. No local engine/cron resurrection as fallback. Prove same historical row count/ID mapping, no unauthorized partner write, active cron OFF, group/record rules, and truthful approved-effect count before resuming.

## Receipts that must be produced during authorized code work

Pre/post `ir.module.module` version; exact scope/company, operator and changeset; before/after original records by model and state; installed XML IDs and security access diff; cron user/group membership and number of active retired crons; source-to-line migration cardinality; transaction failure/rollback; backup/restore ID; terminal historical source-count parity; actual Enterpise test output. No such receipts exist in this package.
