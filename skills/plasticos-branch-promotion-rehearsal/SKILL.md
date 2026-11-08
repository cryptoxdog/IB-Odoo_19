---
name: plasticos-branch-promotion-rehearsal
description: rehearse a PlasticOS Staging-to-Production promotion by running the real post-cutover imports, make import-erp and make import-vanillasoft, at 10 percent volume on a named non-production database, and record failures and misalignments in at most five evidence files. use when preparing a Staging to Production merge, before the production ERP and VanillaSoft import, or when asked to rehearse the cutover imports.
disable-model-invocation: false
metadata:
  skill_schema: 1
  layer: control_plane
  role: skill_entrypoint
  tags: [plasticos, odoo, promotion, rehearsal, import-erp, import-vanillasoft, cutover]
  owner: igor_beylin
  status: active
  version: 1.0.0
  updated: 2026-11-08
---

# PlasticOS Branch Promotion Rehearsal

## Purpose

Before `Staging` is merged into `Production`, run the two imports that follow
the cutover exactly as the operator will run them, at a tenth of the volume,
and keep a short record of what failed and what did not line up. The
rehearsal is the real commands with a volume cap. It is not a second import
implementation and adds no gate of its own.

## Activation

Use when:

- a `Staging` -> `Production` merge is being prepared;
- the operator asks to rehearse the cutover, the ERP import, or the VanillaSoft history import;
- a change to `plasticos_partner_import`, `plasticos_crm_sync`, or `plasticos_transaction`
  needs import-level evidence before promotion.

Do not use for:

- the production import itself (no permit is ever passed here);
- the rolling VanillaSoft window (`VANILLASOFT_CALL_FLOOR`) — another import, refused here;
- Odoo runtime tests or install-smoke — `plasticos-odoo-docker-testing` owns those.

## What runs

`scripts/rehearse.sh` runs exactly two commands, in this order, and nothing else:

| Step | Command | Volume cap |
|---|---|---|
| 1 | `make import-erp LIMIT=10%` | newest 10 percent of ERP worksheets (transactions). Partners, addresses, contacts, roles, and salespersons stay complete. |
| 2 | `make import-vanillasoft VANILLASOFT_HISTORY_MAX_IDS=<n>` | `n` = 10 percent of the census data rows, rounded up (488 of the 4,876-ContactID cohort). History mode only. |

Step 2 runs whatever step 1 returned, so one rehearsal shows every failure.
The Makefile guards, the empty-database guard (`ERP_REQUIRE_EMPTY=1`), and
both importers' own preflights are unchanged and still decide first.

## Inputs

| Variable | Required | Meaning |
|---|---|---|
| `ODOO_DB_NAME` | yes | Rehearsal database. A name containing `prod` is refused. |
| `ERP_SQL_SERVER`, `ERP_SQL_DATABASE` | yes | Restored ERP source; plus `ERP_SQL_USER` / `ERP_SQL_PASSWORD` or `ERP_SQL_DRIVER`. |
| `VANILLASOFT_HISTORY_CENSUS` | yes | Frozen no-PII census, inside this checkout. |
| `VANILLASOFT_HISTORY_CENSUS_SHA256` | yes | Its declared SHA-256. |
| `VANILLASOFT_HISTORY_CHECKPOINT` | yes | Append-only ledger for this database. A fresh rehearsal database needs a fresh ledger. |
| `REHEARSAL_EVIDENCE_DIR` | no | Relative path inside the checkout; default `.l9/runtime/promotion-rehearsal/<UTC stamp>`. Must be empty. |

The script refuses, before either command, when `ODOO_STAGE=production`,
`ERP_PRODUCTION_PERMIT` or `VANILLASOFT_PRODUCTION_PERMIT` is set,
`ERP_REQUIRE_EMPTY` is not `1`, a payload root is set, or a call / contact
floor is set. A refusal exits 2 and imports nothing.

## Procedure

1. Confirm the target is a non-production database the operator named, and that it is empty of business partners (the ERP importer refuses otherwise).
2. Export the inputs above. Never put the reader password on argv or in chat.
3. Run:

   ```bash
   bash skills/plasticos-branch-promotion-rehearsal/scripts/rehearse.sh
   ```

4. Read `misalignments.json` first, then `receipt.json`. Report the verdict, each misalignment, and the evidence path.
5. A `FAIL` is evidence. Repair the importer or the source mapping in its owning module through a normal PR, then rehearse again on a fresh database and ledger. Do not edit the evidence or loosen a cap to get `PASS`.

## Evidence (at most five files)

| File | Source |
|---|---|
| `erp-summary.json` | the ERP importer's own summary, copied when written |
| `vanillasoft-summary.json` | the VanillaSoft importer's own `HISTORY VERDICT`, copied when written |
| `misalignments.json` | every failure the script read: non-zero exits (with a redacted log tail), a missing summary, `records_seen` not equal to created + updated + unchanged + rejected, `duplicates` above 0, a `final_status` other than `success`, each ERP error row, the ERP source-exception census counts, a VanillaSoft stop other than the session cap, dispositions without a source reason, imported-with-error signals, and genuine failures |
| `receipt.json` | branch, SHA, database, both commands with their caps and exit codes, file list, verdict |

Logs and the ERP `-census.json` sibling are written to a scratch directory and
deleted; the census counts are carried into `misalignments.json`. VanillaSoft
ContactIDs not reached under the 10 percent cap are expected and are not
misalignments. The script exits 0 only when both commands exit 0 and
`misalignments.json` lists nothing.

## Failure modes

| Condition | Judgment | Action |
|---|---|---|
| ERP refuses a populated database | the target is not a fresh rehearsal database | clone a fresh one; never set `ERP_REQUIRE_EMPTY=0` here |
| VanillaSoft refuses the ledger | ledger bound to another database or census | give a new ledger path for this database |
| `stopped: auth` | credential rejected | fix the API key in Settings; rerun |
| Reconciliation misaligned | source rows unaccounted | trace in `plasticos_partner_import`; not a rehearsal defect |
| Evidence over five files | the directory was reused | use a fresh `REHEARSAL_EVIDENCE_DIR` |

## Boundaries

- No production permit, no `ODOO_STAGE=production`, no full-volume import.
- No change to the `Makefile`, either importer, or any addon from this skill.
- 10 percent is a transaction and contact cap; it is not a partner cap.
