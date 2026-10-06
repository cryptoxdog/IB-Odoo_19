# Runbook — ERP historical import (`plasticos_partner_import`, `make import-erp`)

## Purpose

Deterministic, replay-safe import of the ERP source into Odoo:
counterparties, addresses/locations, contacts, contact roles, salespersons,
transactions and transaction lines — keyed by the source-native identifiers
`CpID`, `AddressID`, `CT_ID`, `CRA_ID`, `BuySellNo` and `DetailID` via
`ir.model.data` markers (`legacy_erp_*` in `ir.model.data`; the prefix is the
stored identity and is not renamed). Running the same validated input twice
creates no duplicates.

ERP data enters through SQL ([ADR-021](../adr/ADR-021-erp-sql-crm-api-import.md)).
The runtime source is a **direct read of the restored ERP database** through the
projection scripts in `plasticos_partner_import/erp_extracted_data/`. The frozen
grid under `erp_extracted_data/bulk/` is a regression fixture and is never edited
to make an import pass.

> **Naming note:** the vendor this export came from is **banned as an
> identifier in this repository** (`BAN001`, `ci/check_banned_identifier.py`).
> The name to use is **ERP**. The vendor name must never appear
> in tracked files, commands, or docs. `make import-erp` is the
> canonical command.

## Field mapping authority

- Machine-readable disposition of **every** source column:
  `plasticos_partner_import/erp/mapping_status.py` (statuses
  `VERIFIED` / `NEEDS_CORRECTION` / `UNMAPPED_INTENTIONALLY` / `UNKNOWN`;
  every intentional drop carries its measured reason).
- Narrative mapping + identity contract: [`docs/erp_import_mapping.md`](../erp_import_mapping.md).
- Completeness is CI-enforced: `tests/test_erp_mapping_status.py` fails
  on any silently discarded column.

## Secrets

The direct read needs the ERP SQL Server login: `ERP_SQL_USER` /
`ERP_SQL_PASSWORD` (or `ERP_SQL_DRIVER=pyodbc` with the caller's Windows login).
They are read from the environment of the `odoo shell` process only and are never
echoed, logged, or written into the summary. Bind them from the secret store;
never put them in a tracked file. The grid and statement forms need no secret.

## Prerequisites

- A **disposable, nonproduction** Odoo database with `plasticos_partner_import`
  installed (`make update m=plasticos_partner_import` on `ODOO_DB_NAME`). The
  database check refuses any database other than `ODOO_DB_NAME`
  (`ERP_TARGET_DB`), any database whose name says `production`/`prod`, and any
  container where Odoo.sh sets `ODOO_STAGE=production`. The partner table must
  hold only the company and the login users (`ERP_REQUIRE_EMPTY=1`, the
  default) unless a reload onto a populated database is deliberate.
- A runtime: `docker compose` (Docker Desktop running) or the no-Docker local
  harness (`scripts/setup_local_runtime.sh`, `L9_ODOO_VENV`). The direct read
  needs the `pymssql` driver in that runtime (`requirements-dev.txt`).
- Network reach from that runtime to the restored ERP SQL Server.

## Run — Concern 1 (partners) against the restored database

```bash
make import-erp PARTNERS_ONLY=1 \
  ERP_SQL_SERVER=<host[,port]> ERP_SQL_DATABASE=<restored db> \
  ERP_SQL_USER=<login> ERP_SQL_PASSWORD=<secret>
```

Stages run in this order, always: counterparties → addresses/locations →
contacts → roles → salespersons. After each stage its validator
(`scripts/validate_partner_layer.py`) runs **before** anything commits; a
failing validator rolls the whole run back and exits 1, so a failed layer never
poisons the target for the next attempt. Validators read the rows the import
read, never a bundled CSV.

Other forms:

```bash
make import-erp PARTNERS_ONLY=1 DRY=1  ERP_SQL_SERVER=… ERP_SQL_DATABASE=…   # resolve + map, persist nothing
make import-erp PARTNERS_ONLY=1 LAYER=counterparties ERP_SQL_SERVER=… …      # one stage at a time, in order
make import-erp PARTNERS_ONLY=1 PAYLOAD_ROOT=/abs/path                       # statement or grid form (fixtures, replay checks)
make import-erp                                                              # full import incl. transactions (Concern 2; not part of the partner proof)
make import-erp REPORT_PATH=/abs/summary.json
```

Default machine summary: `.l9/pr/import-erp-summary.json`
(shared `import-run-summary` contract; validate with
`python3 scripts/validate_import_summary.py <file>`). `final_status` is
`success` when nothing was rejected, `partial` when rows were rejected or left
unresolved (an inactive counterparty's child, an unknown representative — the
source explains them), and `failed` only when a transaction unit raised; the
command exits nonzero on `failed`.

## Verification

1. **Reconciliation** — summary must satisfy
   `records_seen == records_created + records_updated + records_unchanged + records_rejected`
   (every source row of every table has exactly one outcome; set-valued writes
   such as role tags still credit each row) and `duplicates == 0`.
2. **Replay** — run the same command again against the same target; expect
   `records_created == 0`, `records_updated == 0`, everything `unchanged`: no
   new companies, locations, people, identity markers, role tags, or
   salesperson churn.
3. **Changed record** — change one source row, re-run; expect exactly that
   record `updated`, nothing duplicated.
4. **Runtime gate** — `make runtime-gate g=run_erp_import.py` runs the
   live-DB proof with independent `psycopg2` verification. Exit 77 is
   SKIPPED (no local runtime, or the configured `L9_ODOO_TEMPLATE_DB` does not
   exist), never PASS.

## Test tiers

| Tier | Command | Proves |
|------|---------|--------|
| T0 pure | `make test` | source layer (grid, statement, and direct-database forms), mapping vocabularies, mapping-status completeness, summary projection, stage ordering, validate-before-commit, row accounting contracts (no Odoo) |
| T1 Odoo | `make test-module m=plasticos_partner_import` | import service upsert + marker semantics in real ORM |
| T2 gates | `make runtime-gate g=run_erp_import.py` | live-DB first import + repeat-run + changed-record + savepoint recovery |
| T3 replay | fresh disposable DB, `make import-erp PARTNERS_ONLY=1 ERP_SQL_…` twice | one-command Concern 1 against the restored database, then an idempotent replay |

## Known boundaries

- `transaction_date` is reconstructed from `GPLedger.TradeDt` but **not
  persisted** (`plasticos.transaction` has no such field yet) — mapping doc §8;
  a follow-on change, not an import blocker.
- The direct database read covers the partner tables (Concern 1). The deal
  tables keep their statement or grid form until the transaction concern is
  proven; `make import-erp` without `PARTNERS_ONLY=1` and with `ERP_SQL_*` set
  fails closed naming the tables it cannot read directly.
- `PayablesBatch`, `UACashLedger` and `WksDocument` are tracked export
  evidence, deliberately unconsumed (reasons in `mapping_status.py`).
