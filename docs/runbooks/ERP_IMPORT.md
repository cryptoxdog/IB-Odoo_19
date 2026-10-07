# Runbook — ERP historical import

## Purpose

Deterministic, replay-safe import of the historical ERP into Odoo 19.

The pipeline covers:

- counterparties;
- addresses / locations;
- contacts;
- contact roles;
- salespersons;
- historical transaction headers;
- historical transaction lines.

Identity is source-native (`CpID`, `AddressID`, `CT_ID`, `BuySellNo`, `DetailID`, plus set-valued relationship semantics) and is materialized through stable `ir.model.data` markers. Names, email addresses, phone numbers, and Odoo database IDs are not identity.

## Source authority

ERP data enters through SQL. The production-intent source is a direct read of the restored ERP SQL Server database using projection scripts under `plasticos_partner_import/erp_extracted_data/` and the registry in `plasticos_partner_import/erp/reader.py`.

The frozen files under `erp_extracted_data/bulk/` are regression fixtures only. Never edit them to make an import pass and never document them as runtime authority.

## Direct-SQL source set

A full direct database read can open all 11 sources required by the current partner + transaction reconstruction pipeline:

- `CounterParty`
- `Address`
- `Contact`
- `ContactRoleAssignment`
- `SalesReps`
- `Payables`
- `Receipt`
- `ReceiptBatch`
- `GPLedger`
- `WKSDetail`
- `WksDelivery`

`PARTNERS_ONLY=1` restricts the source request to the five partner-side sources. Deal tables are not opened in partner-only mode.

## Canonical entrypoint

`make import-erp` is the repository operator entrypoint.

Direct restored-database source selection uses the `ERP_SQL_*` settings consumed by `plasticos_partner_import/scripts/import_erp_shell.py`.

A full run must have the transaction realization extension from `plasticos_transaction` available. If it is not available, the run must fail before partner writes. Completing only partner stages is not a successful full historical import.

## Safety boundary

Applied imports are restricted to an explicitly named disposable nonproduction target database. The preflight rejects production-stage or production-named databases.

Partner stages run in this order:

1. counterparties
2. addresses / locations
3. contacts
4. roles
5. salespersons

Each stage validator executes before the partner stage is allowed to become durable. A failed validator rolls the run back.

Full runs continue through the transaction extension after the partner stages. Each `BuySellNo` is one atomic deal unit guarded by a savepoint.

## Result accounting

The machine summary is not merely presentation. It is part of the fail-closed contract.

Every source row must close into exactly one of:

- created;
- updated;
- unchanged;
- rejected.

The reconciliation equation is:

```text
records_seen = records_created + records_updated + records_unchanged + records_rejected
```

`duplicates` must remain zero. Any reconciliation mismatch is a material failure and must produce a non-successful command result. A missing downstream realization is not allowed to disappear into an apparently green summary.

## Replay proof

The same validated input must be safe to run again against the same disposable target.

An identical replay must produce:

- `records_created == 0`;
- `records_updated == 0`;
- no duplicate external identities;
- unchanged records instead of write churn.

A changed-record test must update the one changed source identity without minting a second Odoo record.

## Runtime proof levels

### Pure/static proof

The normal test suite proves projection coverage, deterministic source indexing, mapping rules, structural transaction atomicity, and summary behavior without claiming a real Odoo/SQL Server seam.

### Odoo/PostgreSQL runtime gate

`make runtime-gate g=run_erp_import.py` is the existing live Odoo/PostgreSQL gate. It proves first import, replay, changed-record handling, and savepoint recovery using the frozen regression fixture.

Exit 77 means SKIPPED because the required local runtime/template is unavailable. It is never PASS.

### Direct-SQL E2E proof

PR #221 changes the source seam, so production readiness additionally requires a direct restored-SQL-Server run through the real Odoo/PostgreSQL runtime.

Required evidence:

1. direct SQL Server source is selected;
2. all required partner and deal projection scripts are executed through the shared reader;
3. full import reaches `plasticos_transaction` transaction realization;
4. summary reconciliation closes;
5. sampled supplier, buyer, state, and line values agree with the restored source;
6. identical second direct-SQL run reports zero creates and zero update churn;
7. no duplicate `legacy_erp_*` identities exist.

Fixture-backed runtime proof is necessary but cannot substitute for this source-to-runtime seam proof.

## Historical PO approval date

`GPLedger.TradeDt` means the date the PO was issued and the transaction approved under current PlasticOS rules.

Native Odoo 19 ownership is `purchase.order.date_approve` (`Confirmation Date`) when the historical PO is realized. `purchase.order.date_order` remains the RFQ/order-deadline field.

There is no authorization to create `plasticos.transaction.transaction_date`. Until the historical PO realization slice exists, the reconstructed trade date remains source evidence rather than being copied into an unrelated transaction/logistics field.

## Mapping authority

- Machine-readable column disposition: `plasticos_partner_import/erp/mapping_status.py`
- Narrative mapping + identity contract: `docs/erp_import_mapping.md`
- Source architecture decision: `docs/adr/ADR-021-erp-sql-crm-api-import.md`

No field may be added to mirror the source without a proven representation gap and explicit operator approval.

## Known non-runtime sources

`PayablesBatch`, `UACashLedger`, `WksDocument`, and other research/export evidence not present in the runtime source registry remain intentionally unconsumed until a separately proven business requirement needs them.

## Operator reference

Retained from the previous runbook; corrected where the direct-SQL source set
grew beyond Concern 1.

> **Naming note:** the vendor this export came from is **banned as an
> identifier in this repository** (`BAN001`, `ci/check_banned_identifier.py`).
> The name to use is **ERP**. The vendor name must never appear in tracked
> files, commands, or docs. `make import-erp` is the canonical command.

### Secrets

The direct read needs the ERP SQL Server login: `ERP_SQL_USER` /
`ERP_SQL_PASSWORD` (or `ERP_SQL_DRIVER=pyodbc` with the caller's Windows login).
They are read from the environment of the `odoo shell` process only and are never
echoed, logged, or written into the summary. Bind them from the secret store;
never put them in a tracked file. The grid and statement forms need no secret.

### Prerequisites

- A **disposable, nonproduction** Odoo database (`ODOO_DB_NAME`, passed to the
  preflight as `ERP_TARGET_DB`) with `plasticos_partner_import` installed. A full
  run additionally needs `plasticos_transaction` installed; the preflight refuses
  a full run without it before any partner stage writes. The partner table must
  hold only the company and the login users (`ERP_REQUIRE_EMPTY=1`, the default)
  unless a reload onto a populated database is deliberate.
- A runtime: `docker compose` (Docker Desktop running) or the no-Docker local
  harness (`scripts/setup_local_runtime.sh`, `L9_ODOO_VENV`). The direct read
  needs the `pymssql` driver in that runtime (`requirements-dev.txt`).
- Network reach from that runtime to the restored ERP SQL Server.

### Commands

```bash
# Full import (partners + transactions) from the restored database
make import-erp ERP_SQL_SERVER=<host[,port]> ERP_SQL_DATABASE=<restored db> \
  ERP_SQL_USER=<login> ERP_SQL_PASSWORD=<secret>

make import-erp PARTNERS_ONLY=1 ERP_SQL_SERVER=… ERP_SQL_DATABASE=…        # Concern 1 only
make import-erp PARTNERS_ONLY=1 LAYER=counterparties ERP_SQL_SERVER=… …    # one partner stage, in order
make import-erp DRY=1 ERP_SQL_SERVER=… ERP_SQL_DATABASE=…                  # resolve + map, persist nothing
make import-erp PAYLOAD_ROOT=/abs/path                                     # statement or grid form (fixtures, replay checks)
make import-erp REPORT_PATH=/abs/summary.json
```

Default machine summary: `.l9/pr/import-erp-summary.json` (shared
`import-run-summary` contract; validate with
`python3 scripts/validate_import_summary.py <file>`). `final_status` is
`success` when nothing was rejected, `partial` when rows were rejected or left
unresolved for a reason the source explains, and `failed` when a transaction
unit raised or the reconciliation does not close; the command exits nonzero on
`failed`. `LIMIT=N` is diagnostics only: the transactions beyond `N` have no
outcome, so a limited applied run reports `failed` by construction and is never
import evidence.
