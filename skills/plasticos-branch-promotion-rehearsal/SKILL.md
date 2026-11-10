---
name: plasticos-branch-promotion-rehearsal
description: rehearse a PlasticOS Staging-to-Production promotion by running the real post-cutover ERP import, make import-erp, at 10 percent volume on a named non-production database, and record failures and misalignments in at most five evidence files. make import-vanillasoft writes only the Odoo.sh production database and is not rehearsed. use when preparing a Staging to Production merge, before the production ERP import, or when asked to rehearse the cutover imports.
disable-model-invocation: false
metadata:
  skill_schema: 1
  layer: control_plane
  role: skill_entrypoint
  tags: [plasticos, odoo, promotion, rehearsal, import-erp, cutover]
  owner: igor_beylin
  status: active
  version: 1.1.0
  updated: 2026-11-10
---

# PlasticOS Branch Promotion Rehearsal

## Purpose

Before `Staging` is merged into `Production`, run the ERP import that follows
the cutover exactly as the operator will run it, at a tenth of the volume,
and keep a short record of what failed and what did not line up. The
rehearsal is the real command with a volume cap. It is not a second import
implementation and adds no gate of its own.

`make import-vanillasoft` is not part of this rehearsal (operator decision
2026-11-10). It writes only the Odoo.sh production database: it pipes
`plasticos_crm_sync/scripts/import_vanillasoft_shell.py` into `odoo-bin shell`
over SSH (`ODOO_SH_PRODUCTION_SSH`), uses neither Docker nor the local runner,
and refuses when `TEST_ENV_VERIFIED_CLONE` is set. There is no non-production
database it can run against, so it is never run from this skill.

## Activation

Use when:

- a `Staging` -> `Production` merge is being prepared;
- the operator asks to rehearse the cutover or the ERP import;
- a change to `plasticos_partner_import` or `plasticos_transaction`
  needs import-level evidence before promotion.

Do not use for:

- the production import itself (no permit is ever passed here);
- any VanillaSoft import (`make import-vanillasoft`, every mode) — it writes only the Odoo.sh production database;
- Odoo runtime tests or install-smoke — `plasticos-odoo-docker-testing` owns those.

## What runs

`scripts/rehearse.sh` runs exactly one command and nothing else:

| Command | Volume cap |
|---|---|
| `make import-erp LIMIT=10%` | newest 10 percent of ERP worksheets (transactions). Partners, addresses, contacts, roles, and salespersons stay complete. |

The Makefile guards, the empty-database guard (`ERP_REQUIRE_EMPTY=1`), and
the importer's own preflight are unchanged and still decide first.

## Inputs

| Variable | Required | Meaning |
|---|---|---|
| `ODOO_DB_NAME` | yes | Rehearsal database. A name containing `prod` is refused. |
| `ERP_SQL_SERVER`, `ERP_SQL_DATABASE` | yes | Restored ERP source; plus `ERP_SQL_USER` / `ERP_SQL_PASSWORD` or `ERP_SQL_DRIVER`. |
| `REHEARSAL_EVIDENCE_DIR` | no | Relative path inside the checkout; default `.l9/runtime/promotion-rehearsal/<UTC stamp>`. Must be empty. |

The script refuses, before the command, when `ODOO_STAGE=production`,
`ERP_PRODUCTION_PERMIT` or `VANILLASOFT_PRODUCTION_PERMIT` is set,
`ERP_REQUIRE_EMPTY` is not `1`, or a payload root is set. A refusal exits 2
and imports nothing.

## Procedure

1. Confirm the target is a non-production database the operator named, and that it is empty of business partners (the ERP importer refuses otherwise).
2. Export the inputs above. Never put the reader password on argv or in chat.
3. Run:

   ```bash
   bash skills/plasticos-branch-promotion-rehearsal/scripts/rehearse.sh
   ```

4. Read `misalignments.json` first, then `receipt.json`. Report the verdict, each misalignment, and the evidence path.
5. A `FAIL` is evidence. Repair the importer or the source mapping in its owning module through a normal PR, then rehearse again on a fresh database. Do not edit the evidence or loosen a cap to get `PASS`.

## Evidence (at most five files)

| File | Source |
|---|---|
| `erp-summary.json` | the ERP importer's own summary, copied when written |
| `misalignments.json` | every failure the script read: a non-zero exit (with a redacted log tail), a missing summary, `records_seen` not equal to created + updated + unchanged + rejected, `duplicates` above 0, a `final_status` other than `success`, each ERP error row, and the ERP source-exception census counts |
| `receipt.json` | branch, SHA, database, the command with its cap and exit code, `import-vanillasoft` recorded as not rehearsed, file list, verdict |

Logs and the ERP `-census.json` sibling are written to a scratch directory and
deleted; the census counts are carried into `misalignments.json`. The script
exits 0 only when the command exits 0 and `misalignments.json` lists nothing.

## Failure modes

| Condition | Judgment | Action |
|---|---|---|
| ERP refuses a populated database | the target is not a fresh rehearsal database | clone a fresh one; never set `ERP_REQUIRE_EMPTY=0` here |
| Reconciliation misaligned | source rows unaccounted | trace in `plasticos_partner_import`; not a rehearsal defect |
| Evidence over five files | the directory was reused | use a fresh `REHEARSAL_EVIDENCE_DIR` |

## Boundaries

- No production permit, no `ODOO_STAGE=production`, no full-volume import.
- No change to the `Makefile`, the importer, or any addon from this skill.
- No `make import-vanillasoft`: it writes only the Odoo.sh production database.
- 10 percent is a transaction cap; it is not a partner cap.
